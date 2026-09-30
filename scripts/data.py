"""Download, cache, and calendar-inspect daily adjusted OHLCV data.

This module owns how market data enters the system. It knows nothing about
signals, positions, or P&L — those stay downstream (constitution Rule 8).

Timestamp convention
--------------------
``Date`` is a timezone-naive, midnight-normalized timestamp, and it denotes a
trading *session* rather than an instant. A daily bar has no single moment to
attach a zone to, and every choice of one creates an off-by-one across a date
boundary for some reader: the same bar stored as midnight Eastern and read as
UTC lands on a different calendar day. That is the silent one-bar shift Rule 5
exists to catch, so the label stays zone-free and means "this session".

This is the project-wide rule from CLAUDE.md (*Conventions → Timestamps*), not
a choice local to this module: instants are timezone-aware without exception,
session labels are timezone-naive. A caller that needs an instant localizes to
``America/New_York`` itself, at the boundary where it crosses over.

The convention is applied by ``_normalize_dates`` on both the fresh-download
path and the cache-read path. That it is one function and not two is what
makes a cache hit and a cache miss substitutable for the caller.

Point-in-time correctness (Rule 1)
----------------------------------
No value in a returned row is computed from any other row. Each row is the
provider's report of one session, carried through unmodified apart from column
layout. Gap detection *reports*; it never fills. A backward fill or an
interpolation would write a value into row ``t`` that was not knowable at
``t``, which Rule 1 forbids by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Protocol

import numpy as np
import pandas as pd
import yfinance as yf

# Single source of truth for where generated artifacts live. Every script
# writes here rather than rebuilding the same relative path by hand, so the
# layout can change in one place. data/cache/ is already gitignored: it holds
# regenerable output, never repository content.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
TIDY_COLUMNS = ["Date", "Ticker", *OHLCV_COLUMNS]

UNADJUSTED_CACHE_DIR = CACHE_DIR / "unadjusted"
CORPORATE_ACTION_COLUMNS = [
    "Date",
    "Ticker",
    "Action_Type",
    "Value",
    "Dividend_Pay_Date",
    "Dividend_Pay_Date_Basis",
]
# Version-1 bundles predate the per-dividend basis marker (spec 041).
_V1_CORPORATE_ACTION_COLUMNS = CORPORATE_ACTION_COLUMNS[:5]
PAY_DATE_BASES = frozenset({"sourced", "bound"})
# Version 2 (spec 041) adds the pay-date policy and the basis column. Version 1
# bundles still load, strictly, with every dividend requiring a vendor date.
UNADJUSTED_MANIFEST_VERSION = 2
UNADJUSTED_PRICE_BASIS = "unadjusted_dollars"

# Spec 036 D-7 option C1 (DECIDED 2026-09-26); spec 041.
# None = unbounded: a dividend with no vendor pay date never converts to cash
# within the run. It is strictly conservative and involves no figure (Rule 11).
# A finite value is option C2 and requires DIVIDEND_PAY_DATE_BOUND_SOURCE to
# cite primary-filing evidence that it is an UPPER bound over every dividend
# in the bundle. A typical lag is not enough.
DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS: int | None = None
DIVIDEND_PAY_DATE_BOUND_SOURCE: str | None = None
# The resolved pay date of an unbounded dividend (spec 041 FR-005). It is the
# latest midnight datetime64[ns] can hold, deliberately not a plausible date.
# The loader refuses a bundle whose sessions reach it, so it always lies after
# every session of any bundle it is attached to.
UNBOUNDED_PAY_DATE = pd.Timestamp.max.normalize()
_BOUND_POLICY = re.compile(r"bound_sessions:[1-9][0-9]*")
# A real split creates a large nominal discontinuity. This deliberately
# fail-closed tolerance permits an ordinary overnight move while rejecting an
# adjusted series whose split discontinuity has been smoothed away.
SPLIT_RATIO_RELATIVE_TOLERANCE = 0.25


@dataclass(frozen=True)
class UnadjustedSourceSnapshot:
    """One source adapter's nominal bars, separate actions, and provenance.

    The type has no price-basis field. Callers cannot request a trusted stamp;
    only ``load_unadjusted_market_data`` applies one after validating the cache
    bundle written from this snapshot.
    """

    prices: pd.DataFrame
    corporate_actions: pd.DataFrame
    source_name: str
    source_method: str
    downloaded_at_utc: datetime
    capital_gate_eligible: bool
    limitations: tuple[str, ...] = ()
    # Strict by default: an adapter that declares nothing gets vendor-only pay
    # dates (spec 041 FR-003). The source is required for bound_sessions:N.
    dividend_pay_date_policy: str = "sourced"
    dividend_pay_date_bound_source: str | None = None


class UnadjustedDailySource(Protocol):
    """Adapter boundary for a source that declares nominal daily prices."""

    def fetch(self, ticker: str, start: date, end: date) -> UnadjustedSourceSnapshot:
        """Return inclusive daily bars and separate ex-date action records."""


@dataclass(frozen=True)
class _ValidatedUnadjustedBundle:
    manifest: dict[str, object]
    manifest_path: Path
    manifest_sha256: str
    prices: pd.DataFrame
    corporate_actions: pd.DataFrame
    # None for a version-1 manifest, which declares no policy and has no basis.
    pay_date_policy: str | None = None
    pay_date_bound_source: str | None = None

# Juneteenth became a market holiday in 2022. Applying it to earlier years
# would excuse a genuinely missing bar on every June 19th before that — a
# false negative, which is the direction that actually hurts in a gap
# detector.
JUNETEENTH_FIRST_YEAR = 2022

# Closures that follow no rule: national days of mourning and weather. They
# have to be listed because there is nothing to compute. The list is
# necessarily incomplete for closures that have not happened yet, and that is
# acceptable — an unlisted closure is reported as an unexplained gap, which is
# a false positive and the safe direction to be wrong in.
AD_HOC_CLOSURES = frozenset(
    {
        date(2001, 9, 11),  # September 11th; the exchange stayed shut
        date(2001, 9, 12),  # through the 14th and reopened the 17th.
        date(2001, 9, 13),
        date(2001, 9, 14),
        date(2004, 6, 11),  # Reagan, national day of mourning
        date(2007, 1, 2),  # Ford, national day of mourning
        date(2012, 10, 29),  # Hurricane Sandy
        date(2012, 10, 30),
        date(2018, 12, 5),  # G.H.W. Bush, national day of mourning
        date(2025, 1, 9),  # Carter, national day of mourning
    }
)


def cache_path(name: str) -> Path:
    """Return a path inside data/cache/, creating the directory if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


# --------------------------------------------------------------------------
# Trading calendar
#
# Hand-rolled rather than taken from a library. pandas ships
# USFederalHolidayCalendar, but it describes the federal government, not the
# NYSE: it omits Good Friday (a guaranteed false positive every spring) and
# includes Columbus Day and Veterans Day, on which the exchange is open (a
# false negative, which silently excuses a real missing bar). The NYSE rules
# fit on one screen and change about once a decade, so the correct calendar is
# cheaper than the wrong one. See research.md R2.
# --------------------------------------------------------------------------


def _easter(year: int) -> date:
    """Return Easter Sunday for `year` (anonymous Gregorian algorithm).

    Needed only because Good Friday is defined relative to it. Pure integer
    arithmetic, no lookup table, valid across the Gregorian calendar.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (a + 11 * h) // 319
    r = (2 * e + 2 * i - h + m - k + 32) % 7
    month = (h - m + r + 90) // 25
    day = (h - m + r + month + 19) % 32
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the `n`-th `weekday` (Mon=0) of `month` — e.g. 3rd Monday."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last `weekday` (Mon=0) of `month` — e.g. last Monday."""
    next_month = date(year + month // 12, month % 12 + 1, 1)
    last = next_month - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    """Apply the NYSE weekend-observation rule to a fixed-date holiday.

    A holiday on Saturday is observed the Friday before; on Sunday, the Monday
    after. Returned unchanged on a weekday.
    """
    if day.weekday() == 5:  # Saturday
        return day - timedelta(days=1)
    if day.weekday() == 6:  # Sunday
        return day + timedelta(days=1)
    return day


def market_holidays(year: int) -> set[date]:
    """Return the NYSE holiday dates observed during `year`.

    Observed dates, not nominal ones: July 4th falling on a Saturday appears
    here as July 3rd, because that is the day with no trading.
    """
    holidays = {
        _nth_weekday(year, 1, 0, 3),  # MLK Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _easter(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed(date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),  # Christmas
    }

    if year >= JUNETEENTH_FIRST_YEAR:
        holidays.add(_observed(date(year, 6, 19)))

    # New Year's Day is the documented exception to the observation rule. The
    # NYSE does *not* close the preceding Friday when January 1st falls on a
    # Saturday — it was open on Friday December 31st, 2021. A Sunday New
    # Year's is still observed on the Monday, so only the Saturday case is
    # dropped.
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:
        holidays.add(_observed(new_year))

    holidays |= {day for day in AD_HOC_CLOSURES if day.year == year}
    return {day for day in holidays if day.year == year}


def is_market_holiday(day: date) -> bool:
    """Return True if `day` is an NYSE holiday.

    Weekends are not holidays — a Saturday returns False. Callers asking "was
    the market open" want `trading_days`, which excludes both.
    """
    return day in market_holidays(day.year)


def trading_days(start: date, end: date) -> list[date]:
    """Return the NYSE sessions in [start, end], inclusive, ascending.

    Empty if `start` is after `end`.
    """
    if start > end:
        return []

    # Cache per year rather than recomputing the holiday set for every day in
    # the span; a multi-year range otherwise rebuilds the same ten dates
    # hundreds of times.
    holidays: set[date] = set()
    for year in range(start.year, end.year + 1):
        holidays |= market_holidays(year)

    sessions = []
    day = start
    while day <= end:
        if day.weekday() < 5 and day not in holidays:
            sessions.append(day)
        day += timedelta(days=1)
    return sessions


def find_missing_bars(market_data: pd.DataFrame) -> pd.DataFrame:
    """Report NYSE sessions that have no bar, per ticker (FR-009).

    Returns a `Ticker`/`Date` frame. A row means: the exchange was open that
    day, the day falls inside that ticker's own observed history, and there is
    no bar for it — so no US market holiday explains the absence.

    This is a read-only report. `market_data` is not modified, nothing is
    filled or interpolated, and a gap does not raise. Deciding what a gap
    means belongs to the caller, not to the data layer (Rule 8), and auto-fill
    would have to be checked against Rule 1 before it could exist at all.

    The window is each ticker's *own* first and last bar rather than the
    frame's, so a symbol that listed or delisted mid-period reports gaps only
    within the history it actually has.
    """
    empty = pd.DataFrame({"Ticker": pd.Series(dtype="object"), "Date": pd.Series(dtype="datetime64[ns]")})
    if market_data.empty:
        return empty

    missing = []
    for ticker, group in market_data.groupby("Ticker", sort=True):
        observed = {timestamp.date() for timestamp in pd.to_datetime(group["Date"])}
        expected = trading_days(min(observed), max(observed))
        missing.extend(
            {"Ticker": ticker, "Date": pd.Timestamp(day)}
            for day in expected
            if day not in observed
        )

    if not missing:
        return empty
    return (
        pd.DataFrame(missing)
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------------
# Download and cache
# --------------------------------------------------------------------------


def _cache_key(tickers: list[str], period: str) -> str:
    """Return the cache filename for a ticker set and period.

    Sorted and de-duplicated, so ["MSFT", "AAPL"] and ["AAPL", "MSFT"] are one
    cache entry rather than two files that can never be a hit for each other.
    """
    return f"{'-'.join(sorted(set(tickers)))}_{period}.csv"


def _normalize_dates(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the module's timestamp convention to `frame`'s Date column.

    Timezone-naive, midnight-normalized, and pinned to nanosecond resolution.
    This is the only place the convention is applied, and it runs on both the
    download path and the cache-read path — a cache hit and a cache miss must
    hand the caller the same dtype, or a downstream naive/aware comparison
    raises or, worse, silently shifts a bar across a date boundary.

    The explicit unit matters as much as the zone. pandas infers datetime
    resolution from the source, so the same bars arrive as datetime64[s] from
    a fresh download and datetime64[us] from a CSV read-back. The instants are
    identical, but the dtypes are not, and a downstream join or comparison
    between the two is the kind of thing that works until it silently does
    not. Pinning the unit here is what makes the two paths substitutable.
    """
    frame = frame.copy()
    dates = pd.to_datetime(frame["Date"])
    if isinstance(dates.dtype, pd.DatetimeTZDtype):
        dates = dates.dt.tz_localize(None)
    frame["Date"] = dates.dt.normalize().astype("datetime64[ns]")
    return frame


def _tidy(frame: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Return `frame` in the tidy contract shape (FR-008).

    Exactly the requested tickers, normalized dates, sorted by Ticker then
    Date, clean RangeIndex. Both the download and cache-read paths go through
    here so a caller cannot tell which one produced its data.
    """
    requested = set(tickers)
    tidy = frame[frame["Ticker"].isin(requested)]
    tidy = _normalize_dates(tidy)
    result = (
        tidy[TIDY_COLUMNS]
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )
    result.attrs["price_basis"] = "research_adjusted"
    return result



def _write_atomic(frame: pd.DataFrame, path: Path) -> None:
    """Write `frame` to `path` via a temp file and a rename (FR-004).

    A rename is atomic on a single filesystem, so an interrupted run leaves
    the previous good cache intact rather than a half-written file that later
    runs would happily read as valid.
    """
    temporary_path = path.with_suffix(".csv.tmp")
    frame.to_csv(temporary_path, index=False)
    temporary_path.replace(path)


def download_market_data(
    tickers: list[str],
    period: str = "2y",
    force_refresh: bool = False,
    downloader=yf.download,
) -> pd.DataFrame:
    """Download daily adjusted OHLCV data and return it in tidy form.

    Returns one row per ticker per session with `Date`, `Ticker`, and adjusted
    `Open`/`High`/`Low`/`Close`/`Volume`, sorted by `Ticker` then `Date`.

    Reads `data/cache/` when a cached file holds every requested ticker, and
    makes no network call in that case. `force_refresh` bypasses the cache
    unconditionally.

    `downloader` exists so the download and error paths are reachable without
    network in a test; production callers never pass it.

    Raises `ValueError` on an empty ticker list, and `RuntimeError` — naming
    the specific symbol — when the provider returns nothing at all or silently
    omits a requested one.
    """
    if not tickers:
        raise ValueError("At least one ticker is required.")

    path = cache_path(_cache_key(tickers, period))

    if path.exists() and not force_refresh:
        cached = pd.read_csv(path, parse_dates=["Date"])
        # A cache file is only usable if it actually holds every ticker asked
        # for. A truncated or interrupted write would otherwise be read back
        # as if it were complete, and the error would surface much later as a
        # confusing empty-slice bug in whichever script consumed it.
        if set(tickers).issubset(cached["Ticker"].unique()):
            return _tidy(cached, tickers)

    downloaded_data = downloader(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
    )

    if downloaded_data.empty:
        raise RuntimeError(
            "yfinance returned no data. Check the symbols or connection."
        )

    # yfinance returns one nested column block per ticker. Flattening each
    # block into its own table makes filtering easier than using a MultiIndex.
    tidy_frames = []
    for ticker in tickers:
        try:
            ticker_data = downloaded_data[ticker].copy()
        except KeyError as error:
            # yfinance drops unknown symbols silently rather than raising, so
            # naming the bad ticker here turns a bare KeyError into a message
            # that says which symbol was actually the problem.
            raise RuntimeError(
                f"yfinance returned no data for ticker {ticker!r}."
            ) from error
        ticker_data.columns.name = None
        ticker_data = ticker_data.reset_index()
        ticker_data["Ticker"] = ticker
        tidy_frames.append(ticker_data)

    market_data = _tidy(pd.concat(tidy_frames, ignore_index=True), tickers)
    _write_atomic(market_data, path)
    return market_data


def execution_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate declared historical-dollar bars; derive causal research units.

    No downloads, cache migration, or inference of dollar units from adjusted
    values. The caller must supply verified unadjusted OHLCV and action data.
    Split is new shares per old share (1 means none). Dividend is dollars per
    post-split share on the ex-date, with an explicit payment session.
    Research_Close chains total returns forward, never adjusts past rows.
    """
    if frame.attrs.get("price_basis") != "unadjusted_dollars":
        raise ValueError("verified unadjusted dollar prices required")
    missing = set(TIDY_COLUMNS + ["Split", "Dividend", "Dividend_Pay_Date"]) - set(frame)
    if missing or frame.empty:
        raise ValueError(f"raw snapshot missing columns or rows: {sorted(missing)}")
    result = frame.copy()
    dates = pd.to_datetime(result.Date)
    if (dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing
            or dates.dt.tz is not None or not dates.equals(dates.dt.normalize())
            or result.Ticker.nunique() != 1):
        raise ValueError("one instrument with ordered unique session labels required")
    values = result[OHLCV_COLUMNS + ["Split", "Dividend"]].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values[:, :4] <= 0).any()
            or (result.Volume < 0).any() or (result.Split <= 0).any() or (result.Dividend < 0).any()
            or (result.High < result[["Open", "Close", "Low"]].max(axis=1)).any()
            or (result.Low > result[["Open", "Close", "High"]].min(axis=1)).any()):
        raise ValueError("invalid raw OHLCV or action values")
    pay = pd.to_datetime(result.Dividend_Pay_Date)
    if pay.dt.tz is not None or (result.Dividend.gt(0) & (pay.isna() | (pay < dates))).any():
        raise ValueError("dividend requires a payment session on or after ex-date")
    gross = result.Split * (result.Close + result.Dividend) / result.Close.shift(1)
    gross.iloc[0] = 1.
    result["Research_Close"] = result.Close.iloc[0] * gross.cumprod()
    result["Research_Volume"] = result.Volume / result.Split.cumprod()
    result.attrs["research_basis"] = "causal_total_return_index"
    return result


# --------------------------------------------------------------------------
# Manifest-backed unadjusted prices and separate corporate actions (spec 020)
# --------------------------------------------------------------------------


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(payload: dict[str, object], path: Path) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _validated_utc_timestamp(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} check failed: timestamp must be UTC-aware")
    return value.astimezone(timezone.utc)


def _parse_utc_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"manifest {field} check failed: non-empty ISO timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"manifest {field} check failed: invalid ISO timestamp") from error
    return _validated_utc_timestamp(parsed, f"manifest {field}")


def _session_series(frame: pd.DataFrame, column: str, check: str) -> pd.Series:
    try:
        sessions = pd.to_datetime(frame[column], errors="raise")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{check} check failed: invalid {column} session labels") from error
    if isinstance(sessions.dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{check} check failed: {column} session labels must be timezone-naive")
    sessions = sessions.astype("datetime64[ns]")
    if sessions.isna().any() or not sessions.equals(sessions.dt.normalize()):
        raise ValueError(f"{check} check failed: {column} sessions must be midnight-normalized")
    return sessions


def _validate_unadjusted_prices(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    missing = set(TIDY_COLUMNS) - set(prices.columns)
    if missing:
        raise ValueError(f"price schema check failed: missing columns {sorted(missing)}")
    if prices.empty:
        raise ValueError("price row-count check failed: no rows")

    result = prices[TIDY_COLUMNS].copy()
    result["Date"] = _session_series(result, "Date", "price date")
    if result["Ticker"].isna().any() or set(result["Ticker"].astype(str)) != {ticker}:
        raise ValueError(f"price ticker check failed: expected only {ticker}")
    if result["Date"].duplicated().any():
        raise ValueError("price session check failed: duplicate Date rows")
    if not result["Date"].is_monotonic_increasing:
        raise ValueError("price session check failed: rows are not ascending")

    try:
        values = result[OHLCV_COLUMNS].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("price value check failed: OHLCV must be numeric") from error
    if not np.isfinite(values).all():
        raise ValueError("price value check failed: OHLCV contains a non-finite value")
    if (values[:, :4] <= 0).any():
        raise ValueError("price value check failed: OHLC prices must be positive")
    if (result["Volume"] < 0).any():
        raise ValueError("price value check failed: Volume must be nonnegative")
    if (result["High"] < result[["Open", "Close", "Low"]].max(axis=1)).any():
        raise ValueError("price value check failed: High is below another OHLC value")
    if (result["Low"] > result[["Open", "Close", "High"]].min(axis=1)).any():
        raise ValueError("price value check failed: Low is above another OHLC value")

    actual = list(result["Date"].dt.date)
    expected = trading_days(actual[0], actual[-1])
    if actual != expected:
        missing_sessions = [session.isoformat() for session in expected if session not in set(actual)]
        unexpected = [session.isoformat() for session in actual if session not in set(expected)]
        raise ValueError(
            "price session-contiguity check failed: "
            f"missing={missing_sessions[:5]}, unexpected={unexpected[:5]}"
        )
    return result.reset_index(drop=True)


def declared_dividend_pay_date_policy() -> str:
    """Return the pay-date policy that newly written yfinance bundles declare.

    Derived only from the two FR-001 constants: ``"unbounded"`` when the lag is
    None, else ``"bound_sessions:N"``. A zero, negative or non-integer lag, or a
    finite lag without a non-blank citation, raises ``ValueError`` so no bundle
    can be written under it (spec 041 FR-002). Loaders never call this; they
    read the policy a bundle's manifest recorded.
    """
    lag = DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS
    if lag is None:
        return "unbounded"
    if isinstance(lag, bool) or not isinstance(lag, int) or lag <= 0:
        raise ValueError("dividend pay-date lag check failed: lag must be a positive number of sessions")
    source = DIVIDEND_PAY_DATE_BOUND_SOURCE
    if not isinstance(source, str) or not source.strip():
        raise ValueError("dividend pay-date lag check failed: a finite lag requires a cited upper-bound source")
    return f"bound_sessions:{lag}"


def _validated_pay_date_policy(policy: object, bound_source: object, origin: str) -> tuple[str, str | None]:
    """Accept sourced, unbounded, or bound_sessions:N (N >= 1) with a cited source."""
    if policy in ("sourced", "unbounded"):
        if bound_source is not None:
            raise ValueError(
                f"{origin} dividend_pay_date_bound_source check failed: only bound_sessions:N carries a source"
            )
        return str(policy), None
    if not isinstance(policy, str) or not _BOUND_POLICY.fullmatch(policy):
        raise ValueError(
            f"{origin} dividend_pay_date_policy check failed: "
            "sourced, unbounded, or bound_sessions:N with N a positive integer required"
        )
    if not isinstance(bound_source, str) or not bound_source.strip():
        raise ValueError(
            f"{origin} dividend_pay_date_bound_source check failed: "
            f"{policy} requires a cited upper-bound source"
        )
    return policy, bound_source


def _empty_corporate_actions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.Series(dtype="datetime64[ns]"),
            "Ticker": pd.Series(dtype="object"),
            "Action_Type": pd.Series(dtype="object"),
            "Value": pd.Series(dtype="float64"),
            "Dividend_Pay_Date": pd.Series(dtype="datetime64[ns]"),
            "Dividend_Pay_Date_Basis": pd.Series(dtype="object"),
        }
    )


def _validate_corporate_actions(
    actions: pd.DataFrame,
    ticker: str,
    price_sessions: pd.Series,
    *,
    pay_date_policy: str = "sourced",
    manifest_version: int = UNADJUSTED_MANIFEST_VERSION,
) -> pd.DataFrame:
    """Validate ex-date action rows; version 1 has no basis column and stays strict.

    A dividend's pay date may be null only when its basis is ``bound`` and the
    policy is not ``sourced`` (spec 041 FR-004). Every other rule is unchanged.
    """
    if pay_date_policy not in ("sourced", "unbounded") and not _BOUND_POLICY.fullmatch(str(pay_date_policy)):
        raise ValueError("corporate-actions pay-date policy check failed: unknown policy")
    columns = CORPORATE_ACTION_COLUMNS if manifest_version >= 2 else _V1_CORPORATE_ACTION_COLUMNS
    missing = set(columns) - set(actions.columns)
    if missing:
        raise ValueError(f"corporate-actions schema check failed: missing columns {sorted(missing)}")
    if actions.empty:
        return _empty_corporate_actions()[columns]

    result = actions[columns].copy()
    result["Date"] = _session_series(result, "Date", "corporate-actions ex-date")
    if result["Ticker"].isna().any() or set(result["Ticker"].astype(str)) != {ticker}:
        raise ValueError(f"corporate-actions ticker check failed: expected only {ticker}")
    allowed = {"split", "dividend"}
    if not set(result["Action_Type"]).issubset(allowed):
        raise ValueError("corporate-actions type check failed: expected split or dividend")
    if result.duplicated(["Date", "Ticker", "Action_Type"]).any():
        raise ValueError("corporate-actions uniqueness check failed: duplicate action row")
    result = result.sort_values(["Date", "Action_Type"]).reset_index(drop=True)

    try:
        values = pd.to_numeric(result["Value"], errors="raise").astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError("corporate-actions value check failed: Value must be numeric") from error
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("corporate-actions value check failed: action values must be finite and positive")
    result["Value"] = values

    known_sessions = set(price_sessions)
    if not set(result["Date"]).issubset(known_sessions):
        raise ValueError("corporate-actions ex-date check failed: action has no price session")

    pay_dates = pd.to_datetime(result["Dividend_Pay_Date"], errors="coerce")
    if isinstance(pay_dates.dtype, pd.DatetimeTZDtype):
        raise ValueError("corporate-actions payment-date check failed: sessions must be timezone-naive")
    pay_dates = pay_dates.astype("datetime64[ns]")
    dividends = result["Action_Type"].eq("dividend")
    splits = result["Action_Type"].eq("split")
    bound = pd.Series(False, index=result.index)
    if "Dividend_Pay_Date_Basis" in columns:
        basis = result["Dividend_Pay_Date_Basis"]
        if not basis[dividends].isin(PAY_DATE_BASES).all():
            raise ValueError("corporate-actions pay-date basis check failed: dividend pay-date basis missing or invalid")
        if basis[splits].notna().any():
            raise ValueError("corporate-actions pay-date basis check failed: split must not have a pay-date basis")
        bound = dividends & basis.eq("bound")
    # Spec 041 FR-004, the single relaxation: bound basis under a declared policy.
    null_pay_date_allowed = bound & (pay_date_policy != "sourced")
    if pay_dates[dividends & ~null_pay_date_allowed].isna().any():
        raise ValueError("corporate-actions payment-date check failed: dividend payment date missing")
    if pay_dates[splits].notna().any():
        raise ValueError("corporate-actions payment-date check failed: split must not have a payment date")
    if pay_dates[bound].notna().any():
        raise ValueError("corporate-actions payment-date check failed: bound dividend must not have a payment date")
    if (pay_dates[dividends] < result.loc[dividends, "Date"]).any():
        raise ValueError("corporate-actions payment-date check failed: payment precedes ex-date")
    for payment in pay_dates[dividends].dropna():
        if trading_days(payment.date(), payment.date()) != [payment.date()]:
            raise ValueError("corporate-actions payment-date check failed: payment is not a market session")
    result["Dividend_Pay_Date"] = pay_dates
    return result.reset_index(drop=True)


def _validate_split_discontinuities(prices: pd.DataFrame, actions: pd.DataFrame) -> None:
    if actions.empty:
        return
    session_to_position = {session: position for position, session in enumerate(prices["Date"])}
    for action in actions.loc[actions["Action_Type"].eq("split")].itertuples(index=False):
        position = session_to_position[action.Date]
        if position == 0:
            raise ValueError("split reconciliation check failed: no preceding price session")
        observed_ratio = float(prices.iloc[position - 1]["Close"] / prices.iloc[position]["Open"])
        declared_ratio = float(action.Value)
        relative_error = abs(observed_ratio / declared_ratio - 1.0)
        if not np.isfinite(observed_ratio) or relative_error > SPLIT_RATIO_RELATIVE_TOLERANCE:
            raise ValueError(
                "split reconciliation check failed: nominal price discontinuity "
                f"does not match the {declared_ratio:g}:1 action"
            )


def _bundle_member(manifest_path: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise ValueError(f"manifest {field} check failed: a bundle-local filename is required")
    root = manifest_path.parent.resolve()
    candidate = (root / value).resolve()
    if candidate.parent != root:
        raise ValueError(f"manifest {field} check failed: path escapes bundle directory")
    return candidate


def _read_manifest_document(manifest_path: Path) -> tuple[dict[str, object], bytes]:
    try:
        payload = manifest_path.read_bytes()
    except FileNotFoundError as error:
        raise FileNotFoundError(f"manifest existence check failed: {manifest_path}") from error
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("manifest JSON check failed: invalid UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise ValueError("manifest JSON check failed: top-level object required")
    return document, payload


def _read_hashed_member(path: Path, expected_hash: object, field: str) -> bytes:
    try:
        payload = path.read_bytes()
    except FileNotFoundError as error:
        raise FileNotFoundError(f"{field} existence check failed: {path.name}") from error
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError(f"manifest {field} hash check failed: lowercase SHA-256 required")
    actual = _sha256_bytes(payload)
    if actual != expected_hash:
        raise ValueError(f"{field} hash check failed: expected {expected_hash}, got {actual}")
    return payload


def _validate_manifest_bundle(manifest_path: Path) -> _ValidatedUnadjustedBundle:
    manifest_path = Path(manifest_path)
    manifest, manifest_payload = _read_manifest_document(manifest_path)
    required = {
        "manifest_version",
        "source_name",
        "source_method",
        "downloaded_at_utc",
        "created_by_revision",
        "ticker",
        "start_date",
        "end_date",
        "row_count",
        "data_file",
        "data_sha256",
        "corporate_actions_file",
        "corporate_actions_sha256",
        "corporate_actions_row_count",
        "price_basis",
        "capital_gate_eligible",
        "source_limitations",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError(f"manifest schema check failed: missing fields {sorted(missing)}")
    version = manifest["manifest_version"]
    if version not in (1, UNADJUSTED_MANIFEST_VERSION):
        raise ValueError("manifest version check failed: unsupported manifest_version")
    pay_date_policy, pay_date_bound_source = None, None
    if version == UNADJUSTED_MANIFEST_VERSION:
        # Version 1 ignores any stray policy field and stays strict.
        pay_date_policy, pay_date_bound_source = _validated_pay_date_policy(
            manifest.get("dividend_pay_date_policy"),
            manifest.get("dividend_pay_date_bound_source"),
            "manifest",
        )
    if manifest["price_basis"] != UNADJUSTED_PRICE_BASIS:
        raise ValueError("manifest price-basis check failed: unadjusted_dollars required")
    for field in ("source_name", "source_method", "created_by_revision"):
        if not isinstance(manifest[field], str) or not str(manifest[field]).strip():
            raise ValueError(f"manifest {field} check failed: non-empty string required")
    _parse_utc_timestamp(manifest["downloaded_at_utc"], "downloaded_at_utc")
    if not isinstance(manifest["capital_gate_eligible"], bool):
        raise ValueError("manifest capital_gate_eligible check failed: boolean required")
    limitations = manifest["source_limitations"]
    if not isinstance(limitations, list) or not all(isinstance(item, str) and item for item in limitations):
        raise ValueError("manifest source_limitations check failed: string list required")

    ticker = manifest["ticker"]
    if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z0-9.-]+", ticker):
        raise ValueError("manifest ticker check failed: canonical uppercase ticker required")
    if not isinstance(manifest["row_count"], int) or manifest["row_count"] < 1:
        raise ValueError("manifest row-count check failed: positive integer required")
    if not isinstance(manifest["corporate_actions_row_count"], int) or manifest["corporate_actions_row_count"] < 0:
        raise ValueError("manifest corporate-actions row-count check failed: nonnegative integer required")

    data_path = _bundle_member(manifest_path, manifest["data_file"], "data_file")
    actions_path = _bundle_member(
        manifest_path,
        manifest["corporate_actions_file"],
        "corporate_actions_file",
    )
    if data_path == actions_path:
        raise ValueError("manifest pairing check failed: data and corporate-actions files must differ")
    data_payload = _read_hashed_member(data_path, manifest["data_sha256"], "data file")
    actions_payload = _read_hashed_member(
        actions_path,
        manifest["corporate_actions_sha256"],
        "corporate-actions file",
    )
    try:
        prices = pd.read_csv(io.BytesIO(data_payload), parse_dates=["Date"])
    except Exception as error:
        raise ValueError("data file parse check failed: valid OHLCV CSV required") from error
    try:
        actions = pd.read_csv(io.BytesIO(actions_payload), parse_dates=["Date", "Dividend_Pay_Date"])
    except Exception as error:
        raise ValueError("corporate-actions file parse check failed: valid action CSV required") from error

    prices = _validate_unadjusted_prices(prices, ticker)
    actions = _validate_corporate_actions(
        actions, ticker, prices["Date"],
        pay_date_policy=pay_date_policy or "sourced", manifest_version=version,
    )
    if len(prices) != manifest["row_count"]:
        raise ValueError(
            f"manifest row-count check failed: expected {manifest['row_count']}, got {len(prices)}"
        )
    if len(actions) != manifest["corporate_actions_row_count"]:
        raise ValueError(
            "manifest corporate-actions row-count check failed: "
            f"expected {manifest['corporate_actions_row_count']}, got {len(actions)}"
        )
    actual_start = prices["Date"].iloc[0].date().isoformat()
    actual_end = prices["Date"].iloc[-1].date().isoformat()
    if manifest["start_date"] != actual_start or manifest["end_date"] != actual_end:
        raise ValueError(
            "manifest date-range check failed: "
            f"expected {manifest['start_date']}..{manifest['end_date']}, "
            f"got {actual_start}..{actual_end}"
        )
    _validate_split_discontinuities(prices, actions)
    return _ValidatedUnadjustedBundle(
        manifest=manifest,
        manifest_path=manifest_path.resolve(),
        manifest_sha256=_sha256_bytes(manifest_payload),
        prices=prices,
        corporate_actions=actions,
        pay_date_policy=pay_date_policy,
        pay_date_bound_source=pay_date_bound_source,
    )


def _nth_session_after(day: date, sessions: int) -> date:
    """Return the ``sessions``-th NYSE session strictly after ``day``.

    Uses the market calendar, not a bundle's rows, so the answer is correct
    past a bundle's final session and across holidays.
    """
    span = 2 * sessions + 14
    while True:
        following = trading_days(day + timedelta(days=1), day + timedelta(days=span))
        if len(following) >= sessions:
            return following[sessions - 1]
        span *= 2


def _merge_actions_for_execution(
    prices: pd.DataFrame,
    actions: pd.DataFrame,
    *,
    pay_date_policy: str | None = None,
) -> pd.DataFrame:
    """Place actions on their ex-date rows; resolve bound pay dates late.

    ``pay_date_policy`` is the manifest's, never the module constants', so a
    bundle is always read the way it was written. None means a version-1
    bundle: vendor dates only and no basis column. A ``bound`` row resolves to
    ``UNBOUNDED_PAY_DATE`` under ``unbounded`` and to the N-th session after
    its ex-date under ``bound_sessions:N``; a ``sourced`` row keeps its date.
    """
    result = prices.copy()
    result["Split"] = 1.0
    result["Dividend"] = 0.0
    result["Dividend_Pay_Date"] = pd.NaT
    marked = pay_date_policy is not None
    if marked:
        result["Dividend_Pay_Date_Basis"] = None
    if result["Date"].iloc[-1] >= UNBOUNDED_PAY_DATE:
        raise ValueError("pay-date resolution check failed: sessions reach the unbounded sentinel")
    if actions.empty:
        return result
    lag = None
    if marked and pay_date_policy.startswith("bound_sessions:"):
        lag = int(pay_date_policy.split(":", 1)[1])
    positions = {session: position for position, session in enumerate(result["Date"])}
    for action in actions.itertuples(index=False):
        position = positions[action.Date]
        if action.Action_Type == "split":
            result.loc[position, "Split"] = float(action.Value)
        else:
            result.loc[position, "Dividend"] = float(action.Value)
            pay_date = action.Dividend_Pay_Date
            if marked and action.Dividend_Pay_Date_Basis == "bound":
                if lag is None:
                    pay_date = UNBOUNDED_PAY_DATE
                else:
                    pay_date = pd.Timestamp(_nth_session_after(action.Date.date(), lag))
            result.loc[position, "Dividend_Pay_Date"] = pay_date
            if marked:
                result.loc[position, "Dividend_Pay_Date_Basis"] = action.Dividend_Pay_Date_Basis
    return result


def load_unadjusted_market_data(manifest_path: Path) -> pd.DataFrame:
    """Load one validated cache bundle for funded execution/accounting.

    The price-basis stamp is applied only after manifest schema, source
    provenance, both file hashes, both row counts, date range, complete session
    calendar, action semantics, and split discontinuities pass. There is no
    adjusted-data fallback and no caller-supplied basis override.
    """
    bundle = _validate_manifest_bundle(Path(manifest_path))
    result = _merge_actions_for_execution(
        bundle.prices, bundle.corporate_actions, pay_date_policy=bundle.pay_date_policy,
    )
    manifest = bundle.manifest
    # Version 1 has no basis marker: nothing is inferred sourced, and its strict
    # validation makes a bound row impossible.
    basis = bundle.corporate_actions.get("Dividend_Pay_Date_Basis")
    result.attrs.update(
        {
            "price_basis": manifest["price_basis"],
            "source_name": manifest["source_name"],
            "source_method": manifest["source_method"],
            "downloaded_at_utc": manifest["downloaded_at_utc"],
            "created_by_revision": manifest["created_by_revision"],
            "source_manifest": str(bundle.manifest_path),
            "source_manifest_sha256": bundle.manifest_sha256,
            "data_sha256": manifest["data_sha256"],
            "corporate_actions_sha256": manifest["corporate_actions_sha256"],
            "capital_gate_eligible": manifest["capital_gate_eligible"],
            "source_limitations": tuple(manifest["source_limitations"]),
            "dividend_pay_date_policy": bundle.pay_date_policy,
            "dividend_pay_date_bound_source": bundle.pay_date_bound_source,
            "dividends_sourced": None if basis is None else int(basis.eq("sourced").sum()),
            "dividends_bound": 0 if basis is None else int(basis.eq("bound").sum()),
        }
    )
    return result


class UnadjustedDataUnavailable(LookupError):
    """Name a missing, ambiguous, or invalid funded-price bundle."""

    def __init__(self, ticker: str, reason: str, check: str):
        self.ticker = ticker
        self.reason = reason
        self.check = check
        super().__init__(f"{ticker}: unadjusted price data unavailable ({reason}): {check}")


def resolve_unadjusted_manifest(
    ticker: str, cache_dir: Path = UNADJUSTED_CACHE_DIR,
) -> Path:
    """Resolve exactly one local manifest; no network, writes, or fallback."""
    canonical = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.-]+", canonical):
        raise UnadjustedDataUnavailable(ticker, "invalid", "ticker check failed: canonical symbol required")
    root = Path(cache_dir)
    if not root.is_dir():
        raise UnadjustedDataUnavailable(canonical, "missing", str(root))
    pattern = re.compile(
        rf"^{re.escape(canonical)}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}-\d{{2}}-\d{{2}}\.manifest\.json$"
    )
    matches = sorted(path for path in root.iterdir() if path.is_file() and pattern.fullmatch(path.name))
    if not matches:
        raise UnadjustedDataUnavailable(canonical, "missing", str(root))
    if len(matches) > 1:
        raise UnadjustedDataUnavailable(canonical, "ambiguous", ", ".join(map(str, matches)))
    return matches[0]


def load_unadjusted_for_ticker(
    ticker: str, cache_dir: Path = UNADJUSTED_CACHE_DIR,
    *, manifest_path: Path | None = None,
) -> pd.DataFrame:
    """Load a verified local bundle; no network, writes, or adjusted fallback."""
    path = Path(manifest_path) if manifest_path is not None else resolve_unadjusted_manifest(ticker, cache_dir)
    try:
        return load_unadjusted_market_data(path)
    except (FileNotFoundError, ValueError) as error:
        raise UnadjustedDataUnavailable(ticker.strip().upper(), "invalid", str(error)) from error


def cache_unadjusted_market_data(
    adapter: UnadjustedDailySource,
    ticker: str,
    start: date,
    end: date,
    *,
    created_by_revision: str,
    cache_dir: Path = UNADJUSTED_CACHE_DIR,
) -> Path:
    """Fetch and atomically publish a manifest-backed unadjusted cache bundle.

    The adapter is the source trust boundary. This function validates its
    output before writing data, then writes the manifest last. An interrupted
    replacement therefore leaves either the prior valid bundle or a bundle
    whose old manifest rejects the new member hash.
    """
    ticker = ticker.upper()
    if not re.fullmatch(r"[A-Z0-9.-]+", ticker):
        raise ValueError("ticker check failed: canonical symbol required")
    if start > end:
        raise ValueError("date-range check failed: start is after end")
    if not created_by_revision.strip():
        raise ValueError("created_by_revision check failed: non-empty revision required")

    snapshot = adapter.fetch(ticker, start, end)
    downloaded_at = _validated_utc_timestamp(
        snapshot.downloaded_at_utc,
        "source downloaded_at_utc",
    )
    for field, value in (
        ("source_name", snapshot.source_name),
        ("source_method", snapshot.source_method),
    ):
        if not value.strip():
            raise ValueError(f"source provenance check failed: {field} is empty")
    pay_date_policy, pay_date_bound_source = _validated_pay_date_policy(
        snapshot.dividend_pay_date_policy, snapshot.dividend_pay_date_bound_source, "source",
    )
    source_actions = snapshot.corporate_actions
    if pay_date_policy == "sourced" and "Dividend_Pay_Date_Basis" not in source_actions.columns:
        raise ValueError("corporate-actions pay-date basis check failed: dividend pay-date basis missing or invalid")
    prices = _validate_unadjusted_prices(snapshot.prices, ticker)
    actions = _validate_corporate_actions(
        source_actions, ticker, prices["Date"], pay_date_policy=pay_date_policy,
    )
    _validate_split_discontinuities(prices, actions)

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    start_label = prices["Date"].iloc[0].date().isoformat()
    end_label = prices["Date"].iloc[-1].date().isoformat()
    stem = f"{ticker}_{start_label}_{end_label}"
    data_path = cache_dir / f"{stem}.ohlcv.csv"
    actions_path = cache_dir / f"{stem}.actions.csv"
    manifest_path = cache_dir / f"{stem}.manifest.json"

    _write_atomic(prices, data_path)
    _write_atomic(actions, actions_path)
    manifest: dict[str, object] = {
        "manifest_version": UNADJUSTED_MANIFEST_VERSION,
        "source_name": snapshot.source_name,
        "source_method": snapshot.source_method,
        "downloaded_at_utc": downloaded_at.isoformat().replace("+00:00", "Z"),
        "created_by_revision": created_by_revision,
        "ticker": ticker,
        "start_date": start_label,
        "end_date": end_label,
        "row_count": len(prices),
        "data_file": data_path.name,
        "data_sha256": _sha256_file(data_path),
        "corporate_actions_file": actions_path.name,
        "corporate_actions_sha256": _sha256_file(actions_path),
        "corporate_actions_row_count": len(actions),
        "price_basis": UNADJUSTED_PRICE_BASIS,
        "capital_gate_eligible": snapshot.capital_gate_eligible,
        "source_limitations": list(snapshot.limitations),
        "dividend_pay_date_policy": pay_date_policy,
        "dividend_pay_date_bound_source": pay_date_bound_source,
    }
    _write_json_atomic(manifest, manifest_path)
    return manifest_path


class YFinanceUnadjustedAdapter:
    """Provisional yfinance nominal-price adapter; not a capital-gate source.

    Calls ``Ticker.history`` with ``auto_adjust=False`` and ``actions=True``.
    It does not guarantee delisted-security coverage, spinoff treatment, symbol
    change continuity, authoritative corporate-action completeness, or
    historical dividend payment dates. Dividend rows therefore have no payment
    date. They are marked ``Dividend_Pay_Date_Basis="bound"`` under the policy
    from ``declared_dividend_pay_date_policy`` (spec 041), and the loader
    resolves them late; the adapter never writes a date. The adapter's
    snapshots always declare ``capital_gate_eligible=False``.
    """

    def __init__(self, ticker_factory=yf.Ticker):
        self._ticker_factory = ticker_factory

    def fetch(self, ticker: str, start: date, end: date) -> UnadjustedSourceSnapshot:
        # FR-002: an invalid lag configuration fails before any download or write.
        pay_date_policy = declared_dividend_pay_date_policy()
        history = self._ticker_factory(ticker).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=True,
        )
        if history.empty:
            raise RuntimeError(f"yfinance provisional source returned no rows for {ticker}")
        history = history.copy()
        sessions = pd.DatetimeIndex(pd.to_datetime(history.index))
        if sessions.tz is not None:
            sessions = sessions.tz_localize(None)
        sessions = sessions.normalize().astype("datetime64[ns]")

        prices = pd.DataFrame(
            {
                "Date": sessions,
                "Ticker": ticker,
                "Open": history["Open"].to_numpy(),
                "High": history["High"].to_numpy(),
                "Low": history["Low"].to_numpy(),
                "Close": history["Close"].to_numpy(),
                "Volume": history["Volume"].to_numpy(),
            }
        )
        action_rows: list[dict[str, object]] = []
        dividends = history.get("Dividends", pd.Series(0.0, index=history.index))
        splits = history.get("Stock Splits", pd.Series(0.0, index=history.index))
        for session, dividend, split in zip(sessions, dividends, splits):
            if float(split) != 0.0:
                action_rows.append(
                    {
                        "Date": session,
                        "Ticker": ticker,
                        "Action_Type": "split",
                        "Value": float(split),
                        "Dividend_Pay_Date": pd.NaT,
                        "Dividend_Pay_Date_Basis": None,
                    }
                )
            if float(dividend) != 0.0:
                action_rows.append(
                    {
                        "Date": session,
                        "Ticker": ticker,
                        "Action_Type": "dividend",
                        "Value": float(dividend),
                        # yfinance history identifies the ex-date, not a
                        # verified historical payment date. Never substitute.
                        "Dividend_Pay_Date": pd.NaT,
                        # The date is left empty; the basis declares that the
                        # loader resolves it under the manifest's policy.
                        "Dividend_Pay_Date_Basis": "bound",
                    }
                )
        actions = (
            pd.DataFrame(action_rows, columns=CORPORATE_ACTION_COLUMNS)
            if action_rows
            else _empty_corporate_actions()
        )
        limitations = (
            "No guarantee of delisted-security coverage.",
            "No guarantee of complete or correctly classified spinoffs.",
            "No guarantee of continuity across historical symbol changes.",
            "No authoritative historical dividend payment dates.",
        )
        return UnadjustedSourceSnapshot(
            prices=prices,
            corporate_actions=actions,
            source_name="yfinance",
            source_method="yfinance.Ticker.history(interval=1d, auto_adjust=False, actions=True)",
            downloaded_at_utc=datetime.now(timezone.utc),
            capital_gate_eligible=False,
            limitations=limitations,
            dividend_pay_date_policy=pay_date_policy,
            dividend_pay_date_bound_source=(
                None if pay_date_policy == "unbounded" else DIVIDEND_PAY_DATE_BOUND_SOURCE
            ),
        )


def download_unadjusted_market_data(
    ticker: str,
    start: date,
    end: date,
    *,
    created_by_revision: str,
    cache_dir: Path = UNADJUSTED_CACHE_DIR,
    adapter: UnadjustedDailySource | None = None,
) -> Path:
    """Publish one provisional/provider cache through the source-adapter seam."""
    source = adapter if adapter is not None else YFinanceUnadjustedAdapter()
    return cache_unadjusted_market_data(
        source,
        ticker,
        start,
        end,
        created_by_revision=created_by_revision,
        cache_dir=cache_dir,
    )
