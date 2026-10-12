"""Spec 052: point-in-time instrument identity and eligibility.

U1 guarantees: identity is a stable instrument id, never a ticker; a fact is
visible in ``snapshot(as_of)`` only if it took effect on or before ``as_of``
AND was observed no later than the end of that session (America/New_York), so
a late-filed fact cannot leak backward; an instrument is active only once a
``listed`` fact is visible and until a later ``delisted`` fact; delisted
instruments remain in every snapshot, marked inactive; snapshots hash
deterministically. Pure: no network.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
import json
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
FIELDS = frozenset({"symbol", "listed", "delisted", "share_class", "corporate_action"})


class RegistryError(ValueError):
    """A fact or query the registry must refuse."""


@dataclass(frozen=True)
class Fact:
    instrument_id: str
    field: str
    value: str
    effective_date: date
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        if self.field not in FIELDS:
            raise RegistryError(f"unknown field {self.field!r}")
        if self.observed_at.tzinfo is None:
            raise RegistryError("observed_at must be timezone-aware")
        if not self.source.strip() or not self.instrument_id.strip():
            raise RegistryError("instrument_id and source are required")


def _session_end(session: date) -> datetime:
    return datetime.combine(session, time(23, 59, 59), tzinfo=NY)


class Registry:
    def __init__(self, facts: list[Fact]):
        self._facts = sorted(facts, key=lambda f: (f.instrument_id, f.effective_date, f.observed_at, f.field))

    def snapshot(self, as_of: date) -> dict[str, dict]:
        """State of every instrument known on ``as_of``, using only facts knowable then."""
        cutoff = _session_end(as_of)
        state: dict[str, dict] = {}
        for fact in self._facts:
            if fact.effective_date > as_of or fact.observed_at > cutoff:
                continue
            entry = state.setdefault(fact.instrument_id, {"active": False})
            entry[fact.field] = fact.value
            if fact.field == "listed":
                entry["active"] = True
            elif fact.field == "delisted":
                entry["active"] = False
        return state

    def snapshot_hash(self, as_of: date) -> str:
        payload = json.dumps(self.snapshot(as_of), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(f"{as_of.isoformat()}|{payload}".encode()).hexdigest()


# --- U2/U3: research and executable eligibility with named reasons (FR-003/004/007) ---

import math

import pandas as pd


def _finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class EligibilityLimits:
    min_sessions: int
    min_price: float
    min_median_dollar_volume: float
    max_spread_bps: float
    max_participation: float

    def __post_init__(self) -> None:
        """Limits are configuration: a NaN or out-of-range limit would silently disable its gate."""
        if isinstance(self.min_sessions, bool) or not isinstance(self.min_sessions, int) or self.min_sessions < 1:
            raise ValueError("min_sessions must be a positive integer")
        for name in ("min_price", "min_median_dollar_volume", "max_spread_bps"):
            value = getattr(self, name)
            if not (_finite(value) and value >= 0):
                raise ValueError(f"{name} must be finite and non-negative")
        if not (_finite(self.max_participation) and 0 < self.max_participation <= 1):
            raise ValueError("max_participation must be finite and in (0, 1]")


def research_eligibility(bars: pd.DataFrame, *, as_of: date, limits: EligibilityLimits,
                         actions_reconciled: bool, basis_known: bool) -> list[str]:
    """Reasons ``bars`` (Close, Volume by session) is not research-eligible on ``as_of``.

    Reads only rows at or before ``as_of``. Empty list means eligible. A NaN close fails closed
    (``price_below_floor``); any non-finite dollar volume or negative volume in the 20-row window
    fails closed (``illiquid``) — one bad observation can leave a median finite.
    """
    past = bars.loc[:pd.Timestamp(as_of)]
    reasons = []
    if len(past) < limits.min_sessions:
        reasons.append("insufficient_history")
    last = float(past["Close"].iloc[-1]) if not past.empty else float("nan")
    if not _finite(last) or last < limits.min_price:
        reasons.append("price_below_floor")
    window = past.tail(20)
    dollar = window["Close"] * window["Volume"]
    usable = not window.empty and bool(dollar.map(_finite).all()) and bool((window["Volume"] >= 0).all())
    median = float(dollar.median()) if usable else float("nan")
    if not _finite(median) or median < limits.min_median_dollar_volume:
        reasons.append("illiquid")
    if not actions_reconciled:
        reasons.append("corporate_actions_unreconciled")
    if not basis_known:
        reasons.append("price_basis_unknown")
    return reasons


@dataclass(frozen=True)
class ExecutableQuote:
    tradable: bool
    halted: bool
    last_bar_session: date
    instrument_class: str
    spread_bps: float
    adv_shares: float
    min_notional_usd: float
    quoted_at: datetime


def executable_eligibility(quote: ExecutableQuote, *, previous_session: date, allowed_classes: tuple[str, ...],
                           order_qty: float, order_notional: float, limits: EligibilityLimits,
                           now: datetime, max_quote_age_seconds: float) -> list[str]:
    """Reasons an order may not be sent now; inputs come from an injected read-only snapshot.

    Fails closed: an unknown (non-finite) spread, ADV or broker minimum, an invalid order, or a
    quote that is naive, future-dated or older than ``max_quote_age_seconds`` each name a reason.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if isinstance(max_quote_age_seconds, bool) or not (_finite(max_quote_age_seconds) and float(max_quote_age_seconds) >= 0):
        raise ValueError("max_quote_age_seconds must be finite and non-negative")
    max_quote_age_seconds = float(max_quote_age_seconds)
    reasons = []
    if quote.quoted_at.tzinfo is None or not (0 <= (now - quote.quoted_at).total_seconds() <= max_quote_age_seconds):
        reasons.append("stale_quote")
    if not quote.tradable:
        reasons.append("not_tradable")
    if quote.halted:
        reasons.append("halted")
    if quote.last_bar_session != previous_session:
        reasons.append("stale_bar")
    if quote.instrument_class not in allowed_classes:
        reasons.append("class_not_permitted")
    if not (_finite(order_qty) and order_qty > 0 and _finite(order_notional) and order_notional > 0):
        reasons.append("order_invalid")
        return reasons
    if not _finite(quote.spread_bps):
        reasons.append("spread_unknown")
    elif quote.spread_bps < 0:
        reasons.append("spread_invalid")
    elif quote.spread_bps > limits.max_spread_bps:
        reasons.append("spread_too_wide")
    if not _finite(quote.adv_shares):
        reasons.append("adv_unknown")
    elif quote.adv_shares <= 0 or order_qty / quote.adv_shares > limits.max_participation:
        reasons.append("participation_too_high")
    if not _finite(quote.min_notional_usd):
        reasons.append("broker_minimum_unknown")
    elif quote.min_notional_usd < 0:
        reasons.append("broker_minimum_invalid")
    elif order_notional < quote.min_notional_usd:
        reasons.append("below_broker_minimum")
    return reasons


# --- U4: causal membership and fold-local cross-sectional statistics (FR-005) ---


def causal_membership(registry: Registry, sessions: list[date]) -> dict[date, set[str]]:
    """Active (listed, not delisted) instruments for each session, from that session's own snapshot only."""
    return {s: {i for i, entry in registry.snapshot(s).items() if entry.get("active") is True} for s in sessions}


def fold_local_cross_section(frame: pd.DataFrame, column: str, train_rows: list):
    """Z-score ``column`` with mean/std fitted on ``train_rows`` only; returns (scores, params)."""
    train = frame.loc[train_rows, column]
    params = {"mean": float(train.mean()), "std": float(train.std(ddof=0)) or 1.0}
    return (frame[column] - params["mean"]) / params["std"], params


# --- Spec 060 T002 (FR-001): offline ETF universe builder and v1 list format ---

import re

# Spec 060 §3 rule 5: the fixed asset-class taxonomy (14 classes).
ETF_ASSET_CLASSES = (
    "us_equity_broad", "us_equity_sector", "us_equity_factor_style", "international_developed",
    "emerging", "treasuries", "tips", "ig_credit", "high_yield", "munis", "real_estate",
    "commodities_broad", "gold_precious", "currency",
)
HISTORY_YEARS = 3                 # §3 rule 3
DOLLAR_VOLUME_SESSIONS = 252      # §3 rule 4: trailing window
MIN_MEDIAN_DOLLAR_VOLUME = 20e6   # §3 rule 4: $20 million
CLASS_CAP = 12                    # §3: at most 12 per class
UNIVERSE_COLUMNS = (
    "symbol", "name", "etf_flag", "test_issue", "issuer_category", "asset_class", "listing_date",
    "first_bar", "median_dollar_volume_252", "as_of", "rank", "selected", "exclusion_reason",
)
CANDIDATE_COLUMNS = ("symbol", "name", "etf_flag", "test_issue", "issuer_category", "asset_class",
                     "listing_date")
# §3 rule 2 name screen. Fails toward exclusion, but a short-maturity bond name ("Short
# Treasury", "Short Maturity", "Ultra Short Duration", "Short-Term") and "Low Volatility" (a factor
# style) are ordinary names, not leveraged/inverse/vol ETPs. The reviewed list (§3) overrides.
_DURATION = r"(?:term|treasury|maturity|duration|bond|income|government|corporate|muni)"
_LEVERAGED_NAME = re.compile(
    r"\b(ultra(?![- ]short)\w*|[1-9]x|bull|bear(?:ish)?|inverse|leveraged|vix|(?<!low )volatility)\b"
    rf"|(?<!ultra[- ])\bshort\b(?![- ]{_DURATION})", re.IGNORECASE)
EXCLUSION_REASONS = frozenset({
    "not_etf", "test_issue", "name_missing", "leveraged_inverse_or_volatility", "unknown_asset_class",
    "insufficient_history", "illiquid", "class_cap", "below_cutoff",
})
_LEVERAGED_CATEGORY = re.compile(r"leverag|inverse|volatil", re.IGNORECASE)


def _flag(value) -> bool:
    return value is True or (isinstance(value, str) and value.strip().upper() in {"Y", "TRUE"})


def _no(value) -> bool:  # fail closed: only an explicit N/False clears a flag
    return value is False or (isinstance(value, str) and value.strip().upper() in {"N", "FALSE"})


def _reason(etf_flag, test_issue, category, name, asset_class, first, median,
            history_cutoff: pd.Timestamp, listed=None) -> str:
    """The first §3 rule a row fails, or "" when eligible (shared by builder and validator)."""
    if not _flag(etf_flag):
        return "not_etf"
    if not _no(test_issue):  # unknown counts as a test issue
        return "test_issue"
    if pd.isna(name) or not str(name).strip():  # fail closed: the name screen cannot run
        return "name_missing"
    if _LEVERAGED_CATEGORY.search(str(category or "")):
        return "leveraged_inverse_or_volatility"
    if _LEVERAGED_NAME.search(str(name)):
        return "leveraged_inverse_or_volatility"
    if asset_class not in ETF_ASSET_CLASSES:
        return "unknown_asset_class"
    if (first is None or pd.isna(first) or first > history_cutoff
            or (pd.notna(listed) and first < listed)):  # bars before listing: another instrument
        return "insufficient_history"
    if not (_finite(median) and median >= MIN_MEDIAN_DOLLAR_VOLUME):
        return "illiquid"
    return ""


def _labels(series: pd.Series, what: str) -> pd.Series:
    dates = pd.to_datetime(series)
    if dates.dt.tz is not None:
        raise ValueError(f"{what} must be naive session labels")
    return dates.dt.normalize()


def _liquidity(frame: pd.DataFrame, cutoff: pd.Timestamp) -> tuple:
    """(first bar, trailing median dollar volume) from sessions at or before ``cutoff`` only."""
    past = frame.loc[frame["Date"] <= cutoff].sort_values("Date")
    if past.empty:
        return None, float("nan")
    window = past.tail(DOLLAR_VOLUME_SESSIONS)
    dollar = (window["Close"] * window["Volume"]).astype(float)
    usable = (len(window) == DOLLAR_VOLUME_SESSIONS and bool(dollar.map(_finite).all())
              and bool((window["Volume"] >= 0).all()) and bool((window["Close"] > 0).all()))
    return past["Date"].iloc[0], float(dollar.median()) if usable else float("nan")


def _select(pool: pd.DataFrame, size: int) -> tuple[list, list, list]:
    """(chosen in rank order, class-capped, cut) indices: top ``CLASS_CAP`` per class by median
    dollar volume, then the top ``size`` overall; ties break by symbol."""
    ordered = pool.sort_values(["median_dollar_volume_252", "symbol"], ascending=[False, True])
    in_class = ordered.groupby("asset_class", sort=False).cumcount()
    kept = list(in_class.index[in_class < CLASS_CAP])
    return kept[:size], list(in_class.index[in_class >= CLASS_CAP]), kept[size:]


def build_etf_universe(candidates: pd.DataFrame, bars: pd.DataFrame, *, as_of: date,
                       size: int = 100) -> pd.DataFrame:
    """Apply spec 060 §3 on ``as_of`` and return one ``UNIVERSE_COLUMNS`` row per candidate.

    Point-in-time (Rule 1): only bars dated on or before ``as_of`` are read. A candidate is
    eligible when it is an ETF, not a test issue, passes the leveraged/inverse/volatility screen
    (name or issuer category), carries a taxonomy class, has its first bar on or before
    ``as_of`` minus ``HISTORY_YEARS`` years (bars before its listing date are ignored: a reused
    ticker's older bars belong to another instrument; no listing date means no history), and has a trailing ``DOLLAR_VOLUME_SESSIONS``-session
    median dollar volume of at least ``MIN_MEDIAN_DOLLAR_VOLUME`` (inclusive; a short, non-finite
    or negative window fails closed). Eligible ETFs keep the top ``CLASS_CAP`` per class by that
    median, then the top ``size`` overall; ties break by symbol. Every unselected row names
    exactly one reason, the first rule it fails. Selected rows come first by rank, then the rest
    by symbol. Inputs are never mutated; the result is deterministic.
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("size must be a positive integer")
    missing = set(CANDIDATE_COLUMNS) - set(candidates.columns)
    if missing:
        raise ValueError(f"candidates missing columns {sorted(missing)}")
    if candidates["symbol"].duplicated().any():
        raise ValueError("duplicate candidate symbol")
    cutoff = pd.Timestamp(as_of)
    panel = bars[["Date", "Ticker", "Close", "Volume"]].copy()
    panel["Date"] = _labels(panel["Date"], "bar dates")
    if panel.duplicated(["Ticker", "Date"]).any():
        raise ValueError("duplicate bar (Ticker, Date)")
    listing = _labels(candidates["listing_date"], "listing dates")
    history_cutoff = cutoff - pd.DateOffset(years=HISTORY_YEARS)
    groups = dict(tuple(panel.groupby("Ticker", sort=False)))

    rows = []
    for (_, cand), listed in zip(candidates.iterrows(), listing):
        bars_of = groups.get(cand["symbol"], panel.iloc[0:0])  # bound by listing: a reused ticker's
        bars_of = bars_of.loc[bars_of["Date"] >= listed] if pd.notna(listed) else bars_of.iloc[0:0]
        first, median = _liquidity(bars_of, cutoff)  # older bars belong to another instrument
        etf, test = "Y" if _flag(cand["etf_flag"]) else "N", "N" if _no(cand["test_issue"]) else "Y"
        category = "" if pd.isna(cand["issuer_category"]) else str(cand["issuer_category"])
        reason = _reason(etf, test, category, cand["name"], cand["asset_class"], first, median,
                         history_cutoff, listed)
        rows.append({
            "symbol": cand["symbol"], "name": cand["name"], "etf_flag": etf, "test_issue": test,
            "issuer_category": category, "asset_class": cand["asset_class"],
            "listing_date": "" if pd.isna(listed) else listed.strftime("%Y-%m-%d"),
            "first_bar": "" if first is None else first.strftime("%Y-%m-%d"),
            "median_dollar_volume_252": median, "as_of": cutoff.strftime("%Y-%m-%d"),
            "rank": pd.NA, "selected": False, "exclusion_reason": reason,
        })
    result = pd.DataFrame(rows, columns=list(UNIVERSE_COLUMNS))
    chosen, capped, cut = _select(result.loc[result["exclusion_reason"].eq("")], size)
    result.loc[capped, "exclusion_reason"] = "class_cap"
    result.loc[cut, "exclusion_reason"] = "below_cutoff"
    result.loc[chosen, "selected"] = True
    result["rank"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result.loc[chosen, "rank"] = range(1, len(chosen) + 1)
    order = list(chosen) + sorted(set(result.index) - set(chosen), key=lambda i: result.at[i, "symbol"])
    return result.loc[order].reset_index(drop=True)


def validate_universe(frame: pd.DataFrame, *, require_all_classes: bool = True,
                      size: int = 100) -> None:
    """Refuse a universe list (built, or read back from CSV) that breaks the v1 format.

    Checks: every ``UNIVERSE_COLUMNS`` present; one ``as_of``; no duplicate symbol; ``selected``
    is a boolean; every selected row's class is in the taxonomy; a selected row has a listing
    date and no exclusion reason, an unselected row has a known reason; at most ``CLASS_CAP``
    selected per class; every selected row meets the dollar-volume floor and the history rule
    against ``as_of``; ranks run 1..n and re-deriving the selection from the eligible rows
    (selected, ``class_cap``, ``below_cutoff``) for ``size`` reproduces every rank and reason; every other
    row's reason is re-derived from its own fields (flags, category, name, class, first bar,
    median); and, unless ``require_all_classes`` is false, every taxonomy class has a selected ETF.
    Raises ``ValueError`` naming the first broken check; returns ``None`` otherwise.
    """
    missing = set(UNIVERSE_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"universe list missing columns {sorted(missing)}")
    if frame["as_of"].astype(str).nunique() != 1:
        raise ValueError("universe list must carry exactly one as_of")
    if frame["symbol"].duplicated().any():
        raise ValueError("universe list has a duplicate symbol")
    selected = frame["selected"].map({True: True, False: False, "True": True, "False": False})
    if selected.isna().any():
        raise ValueError("universe list selected must be True or False")
    selected = selected.astype(bool)
    unknown = sorted(set(frame.loc[selected, "asset_class"]) - set(ETF_ASSET_CLASSES))
    if unknown:
        raise ValueError(f"universe list has an unknown asset class: {unknown}")
    reason = frame["exclusion_reason"].fillna("").astype(str)
    listed = frame["listing_date"].fillna("").astype(str)
    if (selected & listed.str.strip().eq("")).any():
        raise ValueError("universe list has a selected row without a listing date")
    if (selected & reason.ne("")).any():
        raise ValueError("universe list has a selected row with an exclusion reason")
    if (~selected & reason.eq("")).any():
        raise ValueError("universe list has an excluded row without a reason")
    unknown = sorted(set(reason[~selected]) - EXCLUSION_REASONS)
    if unknown:
        raise ValueError(f"universe list has an unknown exclusion reason: {unknown}")
    counts = frame.loc[selected, "asset_class"].value_counts()
    over = sorted(counts.index[counts > CLASS_CAP])
    if over:
        raise ValueError(f"universe list over the class cap: {', '.join(over)}")
    picked = frame.loc[selected]
    median = pd.to_numeric(picked["median_dollar_volume_252"], errors="coerce")
    if not (median.map(_finite) & (median >= MIN_MEDIAN_DOLLAR_VOLUME)).all():
        raise ValueError("universe list has a selected row below the dollar-volume floor")
    first = pd.to_datetime(picked["first_bar"].replace("", None), errors="coerce")
    history_cutoff = pd.Timestamp(str(frame["as_of"].iloc[0])) - pd.DateOffset(years=HISTORY_YEARS)
    if not (first.notna() & (first <= history_cutoff)).all():
        raise ValueError("universe list has a selected row short of the history rule")
    ranks = pd.to_numeric(picked["rank"], errors="coerce").astype("float64").sort_values().tolist()
    if ranks != list(range(1, len(picked) + 1)):
        raise ValueError("universe list rank must run 1..n over the selected rows")
    medians = pd.to_numeric(frame["median_dollar_volume_252"], errors="coerce")
    firsts = pd.to_datetime(frame["first_bar"].replace("", None), errors="coerce")
    listeds = pd.to_datetime(frame["listing_date"].replace("", None), errors="coerce")
    for i in frame.index:
        derived = _reason(frame.at[i, "etf_flag"], frame.at[i, "test_issue"],
                          frame.at[i, "issuer_category"], frame.at[i, "name"],
                          frame.at[i, "asset_class"], firsts[i], medians[i], history_cutoff,
                          listeds[i])
        if derived != ("" if reason[i] in {"", "class_cap", "below_cutoff"} else reason[i]):
            raise ValueError(f"universe list exclusion reason does not match its fields: "
                             f"{frame.at[i, 'symbol']} ({reason[i] or 'selected'} vs {derived})")
    pool = frame.loc[selected | reason.isin({"class_cap", "below_cutoff"})].assign(
        median_dollar_volume_252=lambda f: pd.to_numeric(f["median_dollar_volume_252"], errors="coerce"))
    chosen, capped, cut = _select(pool, size)
    by_rank = list(picked.assign(_r=pd.to_numeric(picked["rank"])).sort_values("_r").index)
    if (by_rank != chosen or set(capped) != set(pool.index[reason[pool.index].eq("class_cap")])
            or set(cut) != set(pool.index[reason[pool.index].eq("below_cutoff")])):
        raise ValueError("universe list is not the highest-dollar-volume selection under the class cap")
    if require_all_classes:
        absent = [c for c in ETF_ASSET_CLASSES if c not in counts.index]
        if absent:
            raise ValueError(f"universe list class not covered: {', '.join(absent)}")
