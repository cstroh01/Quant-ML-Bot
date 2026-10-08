"""Spec 055: operations runtime decisions (pure; no broker, no credentials).

U1 guarantees: whether a run is due is decided in America/New_York local
time from an aware instant, so DST and a delayed scheduler cannot shift the
session; only NYSE sessions are due; nothing is due at or after the 09:28 ET
market-on-open cutoff; a (profile, session) already completed is never due
again; every session whose cutoff passed without a completed run is reported
missed rather than silently skipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from data import trading_days

NY = ZoneInfo("America/New_York")
WINDOW_OPEN = time(8, 0)
CUTOFF = time(9, 28)


@dataclass(frozen=True)
class DueDecision:
    status: str  # due | done | before_window | after_cutoff | not_session
    session: date


def _local(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(NY)


def due_run(now: datetime, *, profile: str, completed: set[tuple[str, date]]) -> DueDecision:
    """Decide whether ``profile``'s run for today's session should start now."""
    local = _local(now)
    session = local.date()
    if trading_days(session, session) != [session]:
        return DueDecision("not_session", session)
    if (profile, session) in completed:
        return DueDecision("done", session)
    if local.time() < WINDOW_OPEN:
        return DueDecision("before_window", session)
    if local.time() >= CUTOFF:
        return DueDecision("after_cutoff", session)
    return DueDecision("due", session)


def missed_sessions(now: datetime, *, completed_sessions: set[date], since: date) -> list[date]:
    """Sessions from ``since`` whose cutoff has passed with no completed run."""
    local = _local(now)
    sessions = trading_days(since, local.date())
    return [s for s in sessions if s not in completed_sessions
            and (s < local.date() or local.time() >= CUTOFF)]
