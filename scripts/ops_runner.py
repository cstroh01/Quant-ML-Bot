"""Spec 055 U4: one scheduled invocation — due-check, lease, run, record, alert.

Guarantees: the wrapped command runs at most once per (profile, session) because
the lease is taken before it starts; a session that is not due runs nothing; a
non-zero exit and any missed earlier session become incidents (deduplicated
by content); every executed run appends one record to ``<state>/ops/runs.jsonl``.
The wrapped command is the existing paper loop; this module never imports
broker code or reads credentials.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

from ops_runtime import Incident, acquire_lease, complete_lease, due_run, incidents_to_send, missed_sessions


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def run_once(state_dir, *, profile: str, command: list[str], now: datetime) -> dict:
    ops = Path(state_dir) / "ops"
    runs = [r for r in _jsonl(ops / "runs.jsonl") if r["profile"] == profile]
    completed = {(profile, date.fromisoformat(r["session"])) for r in runs}
    decision = due_run(now, profile=profile, completed=completed)
    if decision.status != "due":
        return {"status": decision.status, "session": decision.session.isoformat()}
    incidents = []
    if runs:
        since = max(date.fromisoformat(r["session"]) for r in runs)
        missed = [s for s in missed_sessions(now, completed_sessions={s for _, s in completed}, since=since)
                  if s != decision.session]
        if missed:
            incidents.append(Incident("missed_run", profile, "missed sessions: " + ", ".join(map(str, missed))))
    run_id = uuid.uuid4().hex
    acquire_lease(state_dir, profile, decision.session, run_id=run_id)
    result = subprocess.run(command, capture_output=True, text=True)
    status = "completed" if result.returncode == 0 else "failed"
    complete_lease(state_dir, profile, decision.session, run_id=run_id)
    record = {"profile": profile, "session": decision.session.isoformat(), "run_id": run_id, "status": status,
              "exit_code": result.returncode, "finished_at_utc": datetime.now(timezone.utc).isoformat()}
    _append(ops / "runs.jsonl", record)
    if status == "failed":
        incidents.append(Incident("failure", profile, f"{decision.session} exit {result.returncode}"))
    sent_path = ops / "sent.json"
    sent = json.loads(sent_path.read_text(encoding="utf-8")) if sent_path.exists() else {}
    for incident in incidents_to_send(incidents, sent):
        _append(ops / "incidents.jsonl", {"kind": incident.kind, "profile": incident.profile, "detail": incident.detail})
    sent_path.parent.mkdir(parents=True, exist_ok=True)
    sent_path.write_text(json.dumps(sent, sort_keys=True), encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one scheduled profile session if due")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--command", required=True, help="the wrapped run, e.g. 'python exec/paper_loop.py --submit'")
    args = parser.parse_args(argv)
    result = run_once(args.state_dir, profile=args.profile, command=shlex.split(args.command),
                      now=datetime.now(timezone.utc))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in ("completed", "done", "not_session", "before_window", "after_cutoff") else 1


if __name__ == "__main__":
    sys.exit(main())
