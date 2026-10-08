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


# --- U2: leases, deterministic client ids, intents persisted before submit (FR-002/003) ---

import hashlib
import json
import os
from pathlib import Path


class LeaseHeld(RuntimeError):
    """A run for this (profile, session) already started or finished."""


def _lease_path(state_dir, profile: str, session: date) -> Path:
    return Path(state_dir) / "leases" / f"{profile}-{session.isoformat()}.json"


def acquire_lease(state_dir, profile: str, session: date, *, run_id: str) -> None:
    """Atomically claim (profile, session); refuse if any run ever claimed it."""
    path = _lease_path(state_dir, profile, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise LeaseHeld(f"{profile} {session} already claimed: {path.read_text(encoding='utf-8')}") from error
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump({"run_id": run_id, "state": "running"}, stream)
        stream.flush()
        os.fsync(stream.fileno())


def complete_lease(state_dir, profile: str, session: date, *, run_id: str) -> None:
    path = _lease_path(state_dir, profile, session)
    lease = json.loads(path.read_text(encoding="utf-8"))
    if lease["run_id"] != run_id:
        raise LeaseHeld(f"{profile} {session} is held by {lease['run_id']}, not {run_id}")
    path.write_text(json.dumps({"run_id": run_id, "state": "completed"}), encoding="utf-8")


def client_order_id(profile: str, session: date, ticker: str, side: str) -> str:
    """Same intent → same id, so a retry after an UNKNOWN submit reconciles, never duplicates."""
    digest = hashlib.sha256(f"{profile}|{session.isoformat()}|{ticker}|{side}".encode()).hexdigest()[:24]
    return f"qmb-{session:%Y%m%d}-{digest}"


def _intents_path(state_dir) -> Path:
    return Path(state_dir) / "intents.jsonl"


def open_intents(state_dir) -> list[dict]:
    path = _intents_path(state_dir)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_intent(state_dir, client_id: str, intent: dict) -> None:
    """Durably append the intent BEFORE any submit; identical re-records are no-ops."""
    for existing in open_intents(state_dir):
        if existing["client_order_id"] == client_id:
            if existing["intent"] != intent:
                raise ValueError(f"{client_id}: intent differs from the recorded one")
            return
    path = _intents_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"client_order_id": client_id, "intent": intent}, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
