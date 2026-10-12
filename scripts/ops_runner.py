"""Spec 055 U4: one scheduled invocation — due-check, lease, run, record, alert.

Guarantees: the wrapped command runs at most once per (profile, session) because
the lease is taken before it starts; a session that is not due runs nothing; a
non-zero exit and any missed session — including today's once its cutoff passes,
and a first-ever miss — become incidents (deduplicated by content) on every
invocation, due or not; every executed run appends one record, carrying
(profile, session, strategy_version), to ``<state>/ops/runs.jsonl``.
The wrapped command is the existing paper loop; this module never imports
broker code or reads credentials.

Drill support (055 T007): a kill stops only the profile it names until a reset that names the
same profile again; an injected clock and a held-lease fixture exist only under ``--drill``.
While killed, every invocation queues a ``halt`` incident naming the sessions not run so far; a reset
records each session whose cutoff passed during the kill in ``<state>/ops/skipped.jsonl``, and only
a session recorded there (or completed) is exempt from missed-run detection. A drill
needs a state dir marked by a ``DRILL`` file (and a real run refuses one), takes no persist command,
and refuses a command that mentions ``submit`` or abbreviates ``--submit``. That is a tripwire
against an operator slip, not a sandbox: a wrapper script that submits internally is not detected.
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

from ops_runtime import (CUTOFF, NY, SUMMARY_TITLE, Incident, LeaseHeld, _lease_path, acquire_lease,
                         atomic_write, complete_lease, due_run, incidents_to_send, missed_sessions,
                         queue_outbox, require_storage_identifier, summary_from_loop_record)


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


def _kill_path(state_dir, profile: str) -> Path:
    return Path(state_dir) / "ops" / f"kill-{require_storage_identifier(profile)}.json"


def _skipped_while_killed(state_dir, profile: str, kill_at: datetime, now: datetime) -> list[date]:
    """Sessions with no completed run whose 09:28 New York cutoff fell after ``kill_at`` and by ``now``.

    A session whose cutoff had already passed when the kill landed was missed before the kill, and a
    session with a lease was started by a run that never completed (its orders may exist); both stay
    missed runs and are never attributed to the kill.
    """
    runs = _jsonl(Path(state_dir) / "ops" / "runs.jsonl")
    completed = {date.fromisoformat(r["session"]) for r in runs if r["profile"] == profile}
    since = kill_at.astimezone(NY).date()
    return [s for s in missed_sessions(now, completed_sessions=completed, since=since)
            if datetime.combine(s, CUTOFF, tzinfo=NY) > kill_at
            and not _lease_path(state_dir, profile, s).exists()]


def _killed(state_dir, profile: str, now: datetime) -> dict:
    """A killed profile runs nothing; each invocation re-raises one ``halt`` incident (deduplicated by
    content, so it is re-sent when another session goes unrun)."""
    kill = json.loads(_kill_path(state_dir, profile).read_text(encoding="utf-8"))
    skipped = _skipped_while_killed(state_dir, profile, datetime.fromisoformat(kill["at_utc"]), now)
    detail = (f"killed at {kill['at_utc']}: {kill['reason']}; nothing runs until a reset naming this profile; "
              f"sessions not run: {', '.join(map(str, skipped)) or 'none yet'}")
    return {"status": "killed", "new_incidents": _deliver(Path(state_dir) / "ops", [Incident("halt", profile, detail)])}


def set_kill(state_dir, profile: str, *, reason: str, reset: bool = False, now: datetime | None = None) -> dict:
    """Kill, or with ``reset`` clear the kill on, ONE profile; other profiles are untouched.

    Both need a non-empty reason (for a reset, the review note). A reset of a profile that is not
    killed, or a kill of one that already is, raises. Every kill and reset is appended to
    ``<state>/ops/kills.jsonl``. A reset lists the sessions skipped while killed in its record, appends
    one ``<state>/ops/skipped.jsonl`` line per session, and queues one ``halt_reset`` incident.
    """
    if not str(reason or "").strip():
        raise ValueError("a kill or reset needs a reason")
    now = _now() if now is None else now
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    path = _kill_path(state_dir, profile)
    record = {"profile": profile, "action": "reset" if reset else "kill", "reason": reason,
              "at_utc": now.astimezone(timezone.utc).isoformat()}
    if reset != path.exists():
        raise ValueError(f"{profile} is {'not' if reset else 'already'} killed")
    if reset:
        kill = json.loads(path.read_text(encoding="utf-8"))
        skipped = _skipped_while_killed(state_dir, profile, datetime.fromisoformat(kill["at_utc"]), now)
        record["skipped_sessions"] = [s.isoformat() for s in skipped]
        ops = Path(state_dir) / "ops"
        for session in skipped:
            _append(ops / "skipped.jsonl", {"profile": profile, "session": session.isoformat(), "cause": "killed",
                                            "kill_at_utc": kill["at_utc"], "reset_at_utc": record["at_utc"],
                                            "review_note": reason})
        _deliver(ops, [Incident("halt_reset", profile, f"reset at {record['at_utc']}: {reason}; sessions skipped "
                                f"while killed: {', '.join(record['skipped_sessions']) or 'none'}")])
        path.unlink()
    else:
        atomic_write(path, json.dumps(record, sort_keys=True))
    _append(Path(state_dir) / "ops" / "kills.jsonl", record)
    return record


def _may_submit(command: str) -> bool:
    """True if ``command`` mentions submit or carries an argparse abbreviation of ``--submit``."""
    return "submit" in command.lower() or any(
        len(token) > 2 and "--submit".startswith(token) for token in shlex.split(command))


def _log_size(run_log) -> int:
    return Path(run_log).stat().st_size if run_log is not None and Path(run_log).exists() else 0


def _appended_record(run_log, offset: int, profile: str) -> dict | None:
    """The last record the wrapped command appended in THIS invocation, or None.

    Bytes before ``offset`` (the log's size when the command started) are never read, so a command
    that exits before appending can't be reported with yesterday's record; a record naming another
    profile is not this run's record.
    """
    if run_log is None or not Path(run_log).exists():
        return None
    with Path(run_log).open("rb") as stream:
        stream.seek(offset)
        fresh = stream.read().decode("utf-8", errors="replace")
    lines = [line for line in fresh.splitlines() if line.strip()]
    try:
        record = json.loads(lines[-1]) if lines else None
    except ValueError:
        return None
    if not isinstance(record, dict) or record.get("profile", profile) != profile:
        return None
    return record


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
    require_storage_identifier(profile)  # names lease and outbox files: one portable component only
    if _kill_path(state_dir, profile).exists():
        return _killed(state_dir, profile, now)  # nothing runs until an explicit reset
    ops = Path(state_dir) / "ops"
    runs = [r for r in _jsonl(ops / "runs.jsonl") if r["profile"] == profile]
    skipped = {date.fromisoformat(r["session"]) for r in _jsonl(ops / "skipped.jsonl") if r["profile"] == profile}
    completed = {(profile, date.fromisoformat(r["session"])) for r in runs}
    decision = due_run(now, profile=profile, completed=completed)
    anchor = _first_seen(ops, profile, decision.session)
    since = max([anchor] + [s for _, s in completed])
    incidents = []
    missed = missed_sessions(now, completed_sessions={s for _, s in completed} | skipped, since=since)
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
    log_offset = _log_size(run_log)
    result = subprocess.run(command, capture_output=True, text=True)
    status = "completed" if result.returncode == 0 else "failed"
    complete_lease(state_dir, profile, decision.session, run_id=run_id)
    record = {"profile": profile, "session": decision.session.isoformat(), "strategy_version": strategy_version,
              "run_id": run_id, "status": status, "exit_code": result.returncode,
              "finished_at_utc": datetime.now(timezone.utc).isoformat()}
    _append(ops / "runs.jsonl", record)
    if status == "failed":
        incidents.append(Incident("failure", profile, f"{decision.session} exit {result.returncode}"))
    body = summary_from_loop_record(_appended_record(run_log, log_offset, profile), profile=profile,
                                    session=decision.session,
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
    parser.add_argument("--command", help="the wrapped run, e.g. 'python exec/paper_loop.py --submit'")
    parser.add_argument("--persist-command", help="run after the lease is claimed and before --command; non-zero aborts")
    parser.add_argument("--run-log", type=Path, help="the wrapped loop's runs.jsonl, for the daily summary")
    parser.add_argument("--drill", action="store_true", help="supervised drill; refused with a --submit command")
    parser.add_argument("--now", type=datetime.fromisoformat, help="drill only: injected timezone-aware clock")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--hold-lease", type=date.fromisoformat, metavar="SESSION",
                        help="drill only: write a held lease for SESSION and run nothing")
    action.add_argument("--kill", metavar="REASON", help="halt this profile only; runs nothing")
    action.add_argument("--reset-kill", metavar="REVIEW_NOTE", help="clear this profile's kill; needs --confirm-reset")
    parser.add_argument("--confirm-reset", metavar="PROFILE", help="must name --profile for --reset-kill")
    args = parser.parse_args(argv)
    if (args.now is not None or args.hold_lease is not None) and not args.drill:
        parser.error("--now and --hold-lease are drill-only; add --drill")
    if args.drill and _may_submit(args.command or ""):
        parser.error("--drill is refused for a command that may submit")
    if args.drill and args.persist_command:
        parser.error("--drill takes no --persist-command")
    if args.drill != (args.state_dir / "DRILL").exists():
        parser.error("--drill needs a state dir marked DRILL, and only a drill may use one")
    if args.confirm_reset is not None and args.reset_kill is None:
        parser.error("--confirm-reset is only for --reset-kill")
    if args.now is not None and args.now.tzinfo is None:
        parser.error("--now must be timezone-aware")
    if args.kill is not None or args.reset_kill is not None:
        if args.reset_kill is not None and args.confirm_reset != args.profile:
            parser.error("--reset-kill needs --confirm-reset naming this profile")
        try:
            record = set_kill(args.state_dir, args.profile, reason=args.kill or args.reset_kill,
                              reset=args.reset_kill is not None, now=_now() if args.now is None else args.now)
        except ValueError as error:
            parser.error(str(error))
        print(json.dumps(record, sort_keys=True))
        return 0
    if args.hold_lease is not None:
        acquire_lease(args.state_dir, args.profile, args.hold_lease, run_id="drill-held-lease")
        print(json.dumps({"status": "lease_fixture", "session": args.hold_lease.isoformat()}))
        return 0
    if not args.command:
        parser.error("--command is required for a run")
    result = run_once(args.state_dir, profile=args.profile, command=shlex.split(args.command),
                      now=args.now or _now(), strategy_version=args.strategy_version,
                      persist_command=shlex.split(args.persist_command) if args.persist_command else None,
                      run_log=args.run_log)
    print(json.dumps(result, sort_keys=True, default=str))
    ok = result["status"] in ("completed", "done", "not_session", "before_window", "after_cutoff")
    return 0 if ok and not result["new_incidents"] else 1


if __name__ == "__main__":
    sys.exit(main())
