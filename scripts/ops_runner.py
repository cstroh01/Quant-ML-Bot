"""Spec 055 U4: one scheduled invocation — due-check, lease, run, record, alert.

Guarantees: the wrapped command runs at most once per (profile, session) because
the lease is taken before it starts; a session that is not due runs nothing; a
non-zero exit and any missed session — including today's once its cutoff passes,
and a first-ever miss — become incidents (deduplicated by content) on every
invocation, due or not; every executed run appends one record, carrying
(profile, session, strategy_version), to ``<state>/ops/runs.jsonl``.
The wrapped command is the existing paper loop; this module never imports
broker code or reads credentials.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

from ops_runtime import (SUMMARY_TITLE, Incident, LeaseHeld, _lease_path, acquire_lease, atomic_write,
                         complete_lease, due_run, incidents_to_send, missed_sessions, queue_outbox,
                         summary_from_loop_record)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _first_seen(ops: Path, profile: str, session: date) -> date:
    """The session of this profile's first-ever invocation; anchors missed-run detection."""
    path = ops / "first_seen.json"
    seen = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if profile not in seen:
        seen[profile] = session.isoformat()
        atomic_write(path, json.dumps(seen, sort_keys=True))
    return date.fromisoformat(seen[profile])


def _deliver(ops: Path, incidents: list[Incident]) -> int:
    """Append new or changed incidents; returns how many were new (deduplicated by content)."""
    sent_path = ops / "sent.json"
    sent = json.loads(sent_path.read_text(encoding="utf-8")) if sent_path.exists() else {}
    fresh = incidents_to_send(incidents, sent)
    for incident in fresh:
        _append(ops / "incidents.jsonl", {"kind": incident.kind, "profile": incident.profile, "detail": incident.detail})
        queue_outbox(ops.parent, f"incident-{incident.fingerprint()[:16]}", kind="incident",
                     title=f"[{incident.profile}] {incident.kind}", body=incident.detail)
    atomic_write(sent_path, json.dumps(sent, sort_keys=True))
    return len(fresh)


def _last_record(run_log) -> dict | None:
    if run_log is None or not Path(run_log).exists():
        return None
    lines = [line for line in Path(run_log).read_text(encoding="utf-8").splitlines() if line.strip()]
    try:
        return json.loads(lines[-1]) if lines else None
    except ValueError:
        return None


def run_once(state_dir, *, profile: str, command: list[str], now: datetime, strategy_version: str,
             persist_command: list[str] | None = None, run_log=None) -> dict:
    """One invocation. Missed sessions are checked on EVERY invocation, due or not, from the later of
    the last completed session and this profile's first-ever invocation; the run identity records
    (profile, session, strategy_version).

    With ``persist_command``, the claimed lease is made durable BEFORE the broker command runs; if
    persisting fails the command never runs, the lease is released and a ``persist_failed``
    incident is queued. Every executed run queues one daily summary in ``<state>/ops/outbox``.
    """
    if not str(strategy_version).strip():
        raise ValueError("strategy_version is required for the run identity")
    ops = Path(state_dir) / "ops"
    runs = [r for r in _jsonl(ops / "runs.jsonl") if r["profile"] == profile]
    completed = {(profile, date.fromisoformat(r["session"])) for r in runs}
    decision = due_run(now, profile=profile, completed=completed)
    anchor = _first_seen(ops, profile, decision.session)
    since = max([anchor] + [s for _, s in completed])
    incidents = []
    missed = missed_sessions(now, completed_sessions={s for _, s in completed}, since=since)
    if missed:
        incidents.append(Incident("missed_run", profile, "missed sessions: " + ", ".join(map(str, missed))))
    if decision.status != "due":
        return {"status": decision.status, "session": decision.session.isoformat(),
                "new_incidents": _deliver(ops, incidents)}
    run_id = uuid.uuid4().hex
    try:
        acquire_lease(state_dir, profile, decision.session, run_id=run_id)
    except LeaseHeld as held:
        # A lease with no completed run record means an earlier run started and never finished:
        # its orders may exist. Never rerun automatically; reconcile at the broker first.
        incidents.append(Incident("lease_held", profile, f"{decision.session}: {held}; reconcile before any rerun"))
        return {"status": "lease_held", "session": decision.session.isoformat(),
                "new_incidents": _deliver(ops, incidents)}
    if persist_command is not None:
        persisted = subprocess.run(persist_command, capture_output=True, text=True)
        if persisted.returncode != 0:
            _lease_path(state_dir, profile, decision.session).unlink()  # nothing durable, nothing sent
            incidents.append(Incident("persist_failed", profile,
                                      f"{decision.session}: state not persisted (exit {persisted.returncode}); "
                                      "broker command not run"))
            return {"status": "persist_failed", "session": decision.session.isoformat(),
                    "new_incidents": _deliver(ops, incidents)}
    result = subprocess.run(command, capture_output=True, text=True)
    status = "completed" if result.returncode == 0 else "failed"
    complete_lease(state_dir, profile, decision.session, run_id=run_id)
    record = {"profile": profile, "session": decision.session.isoformat(), "strategy_version": strategy_version,
              "run_id": run_id, "status": status, "exit_code": result.returncode,
              "finished_at_utc": datetime.now(timezone.utc).isoformat()}
    _append(ops / "runs.jsonl", record)
    if status == "failed":
        incidents.append(Incident("failure", profile, f"{decision.session} exit {result.returncode}"))
    body = summary_from_loop_record(_last_record(run_log), profile=profile, session=decision.session,
                                    model=strategy_version)
    queue_outbox(state_dir, f"summary-{profile}-{decision.session.isoformat()}", kind="summary",
                 title=SUMMARY_TITLE, body=f"Run status: {status} (exit {result.returncode})\n{body}")
    return record | {"new_incidents": _deliver(ops, incidents)}


def main(argv: list[str] | None = None) -> int:
    """Exit 1 on a failed run or any new incident, so the workflow's failure() alert step fires."""
    parser = argparse.ArgumentParser(description="Run one scheduled profile session if due")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--strategy-version", required=True, help="pinned code/strategy identity, e.g. the deploy SHA")
    parser.add_argument("--command", required=True, help="the wrapped run, e.g. 'python exec/paper_loop.py --submit'")
    parser.add_argument("--persist-command", help="run after the lease is claimed and before --command; non-zero aborts")
    parser.add_argument("--run-log", type=Path, help="the wrapped loop's runs.jsonl, for the daily summary")
    args = parser.parse_args(argv)
    result = run_once(args.state_dir, profile=args.profile, command=shlex.split(args.command),
                      now=_now(), strategy_version=args.strategy_version,
                      persist_command=shlex.split(args.persist_command) if args.persist_command else None,
                      run_log=args.run_log)
    print(json.dumps(result, sort_keys=True, default=str))
    ok = result["status"] in ("completed", "done", "not_session", "before_window", "after_cutoff")
    return 0 if ok and not result["new_incidents"] else 1


if __name__ == "__main__":
    sys.exit(main())
