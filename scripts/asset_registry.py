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
