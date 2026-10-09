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
    elif quote.spread_bps > limits.max_spread_bps:
        reasons.append("spread_too_wide")
    if not _finite(quote.adv_shares):
        reasons.append("adv_unknown")
    elif quote.adv_shares <= 0 or order_qty / quote.adv_shares > limits.max_participation:
        reasons.append("participation_too_high")
    if not _finite(quote.min_notional_usd):
        reasons.append("broker_minimum_unknown")
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
