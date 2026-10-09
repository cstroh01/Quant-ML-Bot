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


class IntentLogCorrupt(RuntimeError):
    """The intent log has a torn or unparseable line; no new intent until a human reconciles it."""


def _fsync_dir(directory: Path) -> None:
    """Make a create/rename in ``directory`` durable (no-op where directories can't be opened)."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write(path, text: str) -> None:
    """Replace ``path`` with ``text`` so a crash leaves the old or the new content, never a mix."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


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
    _fsync_dir(path.parent)


def complete_lease(state_dir, profile: str, session: date, *, run_id: str) -> None:
    path = _lease_path(state_dir, profile, session)
    try:
        lease = json.loads(path.read_text(encoding="utf-8"))
        holder = lease["run_id"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise LeaseHeld(f"{profile} {session} lease is unreadable (torn write?); reconcile by hand") from error
    if holder != run_id:
        raise LeaseHeld(f"{profile} {session} is held by {holder}, not {run_id}")
    atomic_write(path, json.dumps({"run_id": run_id, "state": "completed"}))


def client_order_id(profile: str, session: date, ticker: str, side: str) -> str:
    """Same intent → same id, so a retry after an UNKNOWN submit reconciles, never duplicates."""
    digest = hashlib.sha256(f"{profile}|{session.isoformat()}|{ticker}|{side}".encode()).hexdigest()[:24]
    return f"qmb-{session:%Y%m%d}-{digest}"


def _intents_path(state_dir) -> Path:
    return Path(state_dir) / "intents.jsonl"


def open_intents(state_dir) -> list[dict]:
    """Every recorded intent; raises ``IntentLogCorrupt`` on a torn final line or unparseable record."""
    path = _intents_path(state_dir)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        raise IntentLogCorrupt(f"{path.name}: last record is torn (no newline); reconcile before trading")
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            row["client_order_id"], row["intent"]
        except (ValueError, KeyError, TypeError) as error:
            raise IntentLogCorrupt(f"{path.name}: line {number} is not a valid intent record") from error
        rows.append(row)
    return rows


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


# --- U3: daily summary and deduplicated incident alerts (FR-005) ---

DISCLOSURE = "Paper mechanics prototype. Not a performance result."


@dataclass(frozen=True)
class Incident:
    kind: str  # missed_run | halt | reconciliation | failure
    profile: str
    detail: str

    def key(self) -> str:
        return f"{self.profile}:{self.kind}"

    def fingerprint(self) -> str:
        return hashlib.sha256(f"{self.key()}|{self.detail}".encode()).hexdigest()


def daily_summary(run: dict) -> str:
    """Plain-text daily summary; ends with the one next operator action, or none."""
    orders = ", ".join(f"{status}: {count}" for status, count in sorted(run["orders"].items())) or "none"
    differences = run["position_differences"]
    diffs = "not reported" if differences is None else (
        ", ".join(f"{t}: {d}" for t, d in sorted(differences.items())) or "none")
    data_session = run["data_session"].isoformat() if run["data_session"] is not None else "not reported"
    needs = list(run.get("notes", ()))
    if run["orders"].get("unknown"):
        needs.append("check UNKNOWN orders at the broker")
    if differences:
        needs.append("review position differences")
    return "\n".join([
        f"Profile: {run['profile']}  Session: {run['session'].isoformat()}",
        f"Data session: {data_session}  Model: {run['model']}",
        f"Orders: {orders}",
        f"Open reservations: {run['open_reservations']}",
        f"Position differences: {diffs}",
        f"Next action: {'; '.join(needs) if needs else 'none'}",
        DISCLOSURE,
    ])


def incidents_to_send(incidents: list[Incident], sent: dict[str, str]) -> list[Incident]:
    """New or changed incidents only; ``sent`` maps incident key → last sent fingerprint."""
    out = []
    for incident in incidents:
        if sent.get(incident.key()) != incident.fingerprint():
            sent[incident.key()] = incident.fingerprint()
            out.append(incident)
    return out


# --- F02b: summaries built from the paper loop's own run record; outbox for reliable delivery ---

_TERMINAL = frozenset({"FILLED", "CANCELLED", "CANCELED", "EXPIRED", "REJECTED"})
SUMMARY_TITLE = "paper-loop daily summary"


def summary_from_loop_record(record: dict | None, *, profile: str, session: date, model: str) -> str:
    """Daily summary from 049's run record; missing or aborted records say so in the next action."""
    notes = []
    if record is None:
        notes.append("loop record missing: inspect the run log")
        record = {}
    if "aborted" in record:
        notes.append(f"aborted: {record['aborted']}")
    orders: dict[str, int] = {}
    for action in record.get("actions", []):
        outcome = str(action.get("outcome", "unknown")).lower()
        orders[outcome] = orders.get(outcome, 0) + 1
    open_reservations = sum(1 for row in record.get("reconciliation", [])
                            if str(row.get("broker_status")).upper() not in _TERMINAL)
    return daily_summary({"profile": profile, "session": session, "data_session": None, "model": model,
                          "orders": orders, "open_reservations": open_reservations,
                          "position_differences": None, "notes": notes})


def queue_outbox(state_dir, name: str, *, kind: str, title: str, body: str) -> Path:
    """Durably queue one message; delivery later moves it out only after a successful post."""
    path = Path(state_dir) / "ops" / "outbox" / f"{name}.json"
    atomic_write(path, json.dumps({"kind": kind, "title": title, "body": body}, sort_keys=True))
    return path
