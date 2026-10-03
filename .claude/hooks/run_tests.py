"""Stop hook: run the full required suite once per change set, never in a loop.

Guarantees:
- Runs ``<this python> -m pytest tests -rfEsx`` from the repository root (found
  by the CLAUDE.md + .specify marker, never by Git) and keeps its COMPLETE
  output in a distinct log file whose path is reported.
- The child's true exit code decides the outcome. A non-zero exit, or any change
  to the trial-ledger manifest across the run, blocks the stop with a reason.
- At most one suite run per (session, tree fingerprint). A Stop event with
  ``stop_hook_active`` true, an in-progress marker for this session, or a tree
  identical to the last completed run never launches pytest again; a remembered
  failure is re-reported instead.

Limitation: the fingerprint covers the name, size and mtime of every file in the
repository except generated or environment directories (.git, venvs,
node_modules, caches, build output, data/cache) and this hook's own state. An
edit that preserves all three is not seen. The fingerprint is taken after the
run, so files the suite itself writes do not force a rerun.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKIP_DIRS = {".git", "venv", ".venv", "node_modules", "__pycache__", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", "dist", ".serena"}
SKIP_PATHS = ("data/cache",)
LEDGER_DIR = Path("docs/trials")
SUITE_TIMEOUT_S = 1800
STATE_DIR = Path(tempfile.gettempdir()) / "quant-ml-bot-stop-hook"


def find_root(start: Path) -> Path | None:
    """Nearest ancestor holding both CLAUDE.md and .specify/ (no Git)."""
    for d in (start, *start.parents):
        if (d / "CLAUDE.md").is_file() and (d / ".specify").is_dir():
            return d
    return None


def tree_fingerprint(root: Path) -> str:
    """Hash of (path, size, mtime) for every repository file the suite can read."""
    h = hashlib.sha256()
    state = STATE_DIR.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        rel_dir = d.relative_to(root).as_posix()
        dirnames[:] = sorted(
            n for n in dirnames
            if n not in SKIP_DIRS
            and (d / n).resolve() != state
            and (n if rel_dir == "." else f"{rel_dir}/{n}") not in SKIP_PATHS)
        for f in sorted(filenames):
            p = d / f
            try:
                st = p.stat()
            except OSError:
                continue
            h.update(f"{p.relative_to(root).as_posix()}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


def ledger_manifest(root: Path) -> dict[str, str]:
    """SHA-256 of every file under docs/trials/, plus explicit absence markers."""
    base = root / LEDGER_DIR
    manifest: dict[str, str] = {}
    if not base.is_dir():
        return {LEDGER_DIR.as_posix(): "absent"}
    for p in sorted(base.rglob("*")):
        if p.is_file():
            manifest[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    returns = (LEDGER_DIR / "returns").as_posix()
    if not (root / returns).exists():
        manifest[returns] = "absent"
    return manifest


def _state_path(session: str) -> Path:
    safe = "".join(c for c in session if c.isalnum() or c in "-_") or "nosession"
    return STATE_DIR / f"{safe}.json"


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def _block(reason: str) -> tuple[int, str]:
    return 0, json.dumps({"decision": "block", "reason": reason})


def _allow(note: str = "") -> tuple[int, str]:
    return 0, json.dumps({"suppressOutput": True}) if not note else json.dumps({"systemMessage": note})


def run(payload: dict, runner=subprocess.run, python: str = sys.executable) -> tuple[int, str]:
    """Return (exit code, stdout JSON). ``runner`` is injectable for tests."""
    if payload.get("stop_hook_active"):
        return _allow("run_tests: stop already re-entered once; not relaunching pytest")
    cwd = Path(payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    root = find_root(cwd.resolve())
    if root is None:
        return _allow("run_tests: repository root not found; suite not run")
    session = str(payload.get("session_id") or "nosession")
    state_file = _state_path(session)
    state = _load(state_file)
    fp = tree_fingerprint(root)

    if state.get("in_progress"):
        return _allow("run_tests: a suite run is already in progress for this session")
    last = state.get("last")
    if last and last.get("fingerprint") == fp:
        if last.get("exit") == 0 and not last.get("ledger_changed"):
            return _allow()
        return _block(f"Unchanged tree since a FAILED suite run (exit {last.get('exit')}). Log: {last.get('log')}")

    log = STATE_DIR / f"{state_file.stem}-{time.strftime('%Y%m%dT%H%M%S')}-{fp[:8]}.log"
    before = ledger_manifest(root)
    _save(state_file, {**state, "in_progress": True})
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "wb") as fh:
            try:
                proc = runner([python, "-m", "pytest", "tests", "-rfEsx"], cwd=root,
                              stdout=fh, stderr=subprocess.STDOUT, timeout=SUITE_TIMEOUT_S)
                code = proc.returncode
            except subprocess.TimeoutExpired:
                code = -1
                fh.write(f"\n[run_tests] TIMEOUT after {SUITE_TIMEOUT_S}s\n".encode())
        after = ledger_manifest(root)
    finally:
        state = _load(state_file)
        state["in_progress"] = False
        _save(state_file, state)

    ledger_changed = before != after
    # Fingerprint AFTER the run: artifacts the suite writes are part of the
    # baseline, so only an agent's later edits trigger the next run.
    state["last"] = {"fingerprint": tree_fingerprint(root), "exit": code, "log": str(log), "ledger_changed": ledger_changed}
    _save(state_file, state)
    if ledger_changed:
        return _block(f"docs/trials/ changed during the suite run (forbidden). Log: {log}")
    if code != 0:
        return _block(f"Full suite failed (exit {code}). Fix before stopping. Complete log: {log}")
    return _allow(f"run_tests: full suite passed. Log: {log}")


def main(stdin: str) -> tuple[int, str, str]:
    try:
        payload = json.loads(stdin)
        if not isinstance(payload, dict):
            raise ValueError
    except (ValueError, TypeError):
        return 1, "", "run_tests: invalid hook input; suite not run"
    code, out = run(payload)
    return code, out, ""


if __name__ == "__main__":
    c, o, e = main(sys.stdin.read())
    if o:
        sys.stdout.write(o)
    if e:
        sys.stderr.write(e)
    sys.exit(c)
