"""Spec 052: point-in-time instrument identity and eligibility.

U1 guarantees: identity is a stable instrument id, never a ticker; a fact is
visible in ``snapshot(as_of)`` only if it took effect on or before ``as_of``
AND was observed no later than the end of that session (America/New_York), so
a late-filed fact cannot leak backward; delisted instruments remain in every
snapshot, marked inactive after their delisting; snapshots hash
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
            entry = state.setdefault(fact.instrument_id, {"active": True})
            entry[fact.field] = fact.value
            if fact.field == "delisted":
                entry["active"] = False
        return state

    def snapshot_hash(self, as_of: date) -> str:
        payload = json.dumps(self.snapshot(as_of), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(f"{as_of.isoformat()}|{payload}".encode()).hexdigest()


# --- U2/U3: research and executable eligibility with named reasons (FR-003/004/007) ---

import pandas as pd


@dataclass(frozen=True)
class EligibilityLimits:
    min_sessions: int
    min_price: float
    min_median_dollar_volume: float
    max_spread_bps: float
    max_participation: float


def research_eligibility(bars: pd.DataFrame, *, as_of: date, limits: EligibilityLimits,
                         actions_reconciled: bool, basis_known: bool) -> list[str]:
    """Reasons ``bars`` (Close, Volume by session) is not research-eligible on ``as_of``.

    Reads only rows at or before ``as_of``. Empty list means eligible.
    """
    past = bars.loc[:pd.Timestamp(as_of)]
    reasons = []
    if len(past) < limits.min_sessions:
        reasons.append("insufficient_history")
    if past.empty or float(past["Close"].iloc[-1]) < limits.min_price:
        reasons.append("price_below_floor")
    window = past.tail(20)
    if window.empty or float((window["Close"] * window["Volume"]).median()) < limits.min_median_dollar_volume:
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


def executable_eligibility(quote: ExecutableQuote, *, previous_session: date, allowed_classes: tuple[str, ...],
                           order_qty: float, order_notional: float, limits: EligibilityLimits) -> list[str]:
    """Reasons an order may not be sent now; inputs come from an injected read-only snapshot."""
    reasons = []
    if not quote.tradable:
        reasons.append("not_tradable")
    if quote.halted:
        reasons.append("halted")
    if quote.last_bar_session != previous_session:
        reasons.append("stale_bar")
    if quote.instrument_class not in allowed_classes:
        reasons.append("class_not_permitted")
    if quote.spread_bps > limits.max_spread_bps:
        reasons.append("spread_too_wide")
    if quote.adv_shares <= 0 or order_qty / quote.adv_shares > limits.max_participation:
        reasons.append("participation_too_high")
    if order_notional < quote.min_notional_usd:
        reasons.append("below_broker_minimum")
    return reasons


# --- U4: causal membership and fold-local cross-sectional statistics (FR-005) ---


def causal_membership(registry: Registry, sessions: list[date]) -> dict[date, set[str]]:
    """Active instruments for each session, from that session's own snapshot only."""
    return {s: {i for i, entry in registry.snapshot(s).items() if entry.get("active", True)} for s in sessions}


def fold_local_cross_section(frame: pd.DataFrame, column: str, train_rows: list):
    """Z-score ``column`` with mean/std fitted on ``train_rows`` only; returns (scores, params)."""
    train = frame.loc[train_rows, column]
    params = {"mean": float(train.mean()), "std": float(train.std(ddof=0)) or 1.0}
    return (frame[column] - params["mean"]) / params["std"], params
