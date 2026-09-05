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

from datetime import date, timedelta
from pathlib import Path

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
    return (
        tidy[TIDY_COLUMNS]
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )


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
