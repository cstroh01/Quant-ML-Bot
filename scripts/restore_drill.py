"""066: restore drill for one profile's durable state (paper_small, paper_large, live_fidelity).

Copies a backup (a workflow's ``state-<profile>-<run>`` artifact) into a fresh scratch
directory and proves the copy reproduces the primary (the ``ops-state`` checkout of that
profile) byte for byte and as every consumer reads it: latches, leases, intents, the due-run
decision, JSON/JSONL state and gate SQLite. Never writes either input; writes only the
scratch copy and the evidence file. No network, no broker, no credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from ops_runtime import IntentLogCorrupt, due_run, open_intents, require_storage_identifier

LATCHES = ("HALTED", "KILL")


class DrillRefused(RuntimeError):
    """The inputs cannot be drilled (missing, symlinked, nested); not a restore failure."""


def manifest(root: Path) -> dict[str, str]:
    """Relative POSIX path -> SHA-256 of every regular file. A symlink anywhere refuses."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise DrillRefused(f"{root.name}: not a directory")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise DrillRefused("symlink in state: " + path.relative_to(root).as_posix())
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _sqlite(path: Path) -> dict:
    """Integrity check and logical dump through an immutable read-only connection."""
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        check = connection.execute("PRAGMA integrity_check").fetchone()[0]
        return {"integrity": check, "dump_sha256": hashlib.sha256(
            "\n".join(connection.iterdump()).encode("utf-8")).hexdigest()}
    except sqlite3.DatabaseError as error:
        return {"integrity": "unreadable: " + type(error).__name__}
    finally:
        connection.close()


def _parsed(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return json.loads(text)
    except ValueError:
        return "unparseable"


def consumer_view(state: Path, profile: str, now: datetime) -> dict:
    """What the runtime would read from ``state``; equal views mean an equal restart."""
    state = Path(state)
    try:
        intents = open_intents(state)
    except IntentLogCorrupt:
        intents = "corrupt"
    runs = state / "ops" / "runs.jsonl"
    rows = _parsed(runs) if runs.exists() else []  # an unparseable log still differs under "json"
    completed = {(r["profile"], date.fromisoformat(r["session"]))
                 for r in (rows if isinstance(rows, list) else []) if r.get("profile") == profile}
    decision = due_run(now, profile=profile, completed=completed)
    return {
        "latches": sorted(name for name in LATCHES if (state / name).exists()),
        "leases": {p.name: _parsed(p) for p in sorted((state / "leases").glob("*.json"))},
        "open_intents": intents,
        "due_run": {"status": decision.status, "session": decision.session.isoformat()},
        "json": {p.relative_to(state).as_posix(): _parsed(p)
                 for p in sorted(state.rglob("*")) if p.suffix in (".json", ".jsonl") and p.is_file()},
        "sqlite": {p.relative_to(state).as_posix(): _sqlite(p)
                   for p in sorted(state.rglob("*.sqlite")) if p.is_file()},
    }


def drill(primary: Path, backup: Path, *, profile: str, now: datetime, scratch: Path | None = None) -> dict:
    """Restore ``backup`` into an isolated scratch copy and compare it with ``primary``.

    Returns evidence with ``verdict`` PASS or FAIL; both inputs are left byte-identical.
    """
    require_storage_identifier(profile)
    if now.tzinfo is None:
        raise DrillRefused("now must be timezone-aware")
    primary, backup = Path(primary).resolve(), Path(backup).resolve()
    before = {"primary": manifest(primary), "backup": manifest(backup)}
    if not before["backup"]:
        raise DrillRefused("backup is empty")
    owned = scratch is None
    scratch = Path(tempfile.mkdtemp(prefix="qmb-restore-")) if owned else Path(scratch)
    try:
        restored = scratch / profile
        if restored.exists():
            raise DrillRefused("scratch already holds a restore")
        shutil.copytree(backup, restored, symlinks=True)
        files = manifest(restored)
        views = {"primary": consumer_view(primary, profile, now), "restored": consumer_view(restored, profile, now)}
    finally:
        if owned:
            shutil.rmtree(scratch, ignore_errors=True)
    after = {"primary": manifest(primary), "backup": manifest(backup)}
    if after != before:
        raise DrillRefused("an input changed during the drill; rerun when no writer is active")
    differing = sorted(p for p in set(files) | set(before["primary"]) if files.get(p) != before["primary"].get(p))
    view_diff = sorted(k for k in views["primary"] if views["primary"][k] != views["restored"][k])
    unhealthy = sorted(p for p, s in views["restored"]["sqlite"].items() if s["integrity"] != "ok")
    passed = not differing and not view_diff and not unhealthy and views["restored"]["open_intents"] != "corrupt"
    return {"verdict": "PASS" if passed else "FAIL", "profile": profile, "as_of": now.isoformat(),
            "files": len(files), "manifest_sha256": hashlib.sha256(
                json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest(),
            "differing_files": differing, "differing_views": view_diff, "unhealthy_sqlite": unhealthy,
            "latches": views["restored"]["latches"], "leases": sorted(views["restored"]["leases"]),
            "open_intents": (len(views["restored"]["open_intents"])
                             if isinstance(views["restored"]["open_intents"], list) else "corrupt"),
            "due_run": views["restored"]["due_run"], "sqlite": sorted(views["restored"]["sqlite"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--primary", type=Path, required=True, help="ops-state checkout's <profile> directory")
    parser.add_argument("--backup", type=Path, required=True, help="downloaded state-<profile>-<run> artifact")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        evidence = drill(args.primary, args.backup, profile=args.profile, now=datetime.now(timezone.utc))
    except (DrillRefused, ValueError) as error:
        evidence = {"verdict": "REFUSED", "profile": args.profile, "reason": str(error)}
    args.evidence.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: evidence[k] for k in ("verdict", "profile")}))
    return 0 if evidence["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
