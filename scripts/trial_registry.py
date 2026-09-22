"""Sole lifetime ledger: canonical start events, immutable returns, verified chain.

Canonical JSON is UTF-8, sorted keys, compact separators, finite numbers only.
Unknown workspace state is honest: no index/dirtiness guesses and no git process.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRIALS_PATH = ROOT / "docs/trials/trials.jsonl"
ROLES = {"candidate", "buy_and_hold_baseline", "random_signal_baseline", "synthetic_test"}
TERMINALS = {"completed", "rejected", "errored", "abandoned"}
CONFIG_FIELDS = set("data universe date_range features transforms target model cv seed initial_capital commission slippage liquidation risk_free".split())
ZERO = "0" * 64


def canonical_json(value) -> bytes:
    """Return the single canonical representation used by every evidence digest."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ValueError("canonical JSON requires finite JSON values") from exc


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def relative_path(root: Path, path: str | Path) -> str:
    full = Path(path)
    if not full.is_absolute():
        full = root / full
    try:
        # Python/Windows may return an extended-length prefix under contention.
        resolved = Path(str(full.resolve()).removeprefix("\\\\?\\"))
        base = Path(str(root.resolve()).removeprefix("\\\\?\\"))
        return resolved.relative_to(base).as_posix()
    except ValueError as exc:
        raise ValueError("path outside repository; relative path required") from exc


def canonical_config(config: dict, *, root: Path, defaults: dict | None = None) -> tuple[dict, str]:
    """Resolve supplied defaults, retain sequence order, sort true sets, hash all choices."""
    def normalize(value):
        if isinstance(value, Path): return relative_path(root, value)
        if isinstance(value, dict):
            if any(not isinstance(k, str) for k in value): raise ValueError("config keys must be strings")
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, (set, frozenset)): return sorted((normalize(v) for v in value), key=canonical_json)
        if isinstance(value, (list, tuple)): return [normalize(v) for v in value]
        if isinstance(value, float) and not math.isfinite(value): raise ValueError("config requires finite floats")
        return value
    resolved = normalize({**(defaults or {}), **config})
    missing = CONFIG_FIELDS - resolved.keys()
    if missing: raise ValueError(f"unresolved config fields: {sorted(missing)}")
    return resolved, digest(resolved)


def source_identity(root: Path = ROOT, *, git_sha: str | None = None, workspace_state: str = "unknown") -> dict:
    """Read full SHA metadata and hash source contents, without invoking version control."""
    root = Path(root).resolve()
    if workspace_state not in {"clean", "dirty", "unknown"}: raise ValueError("workspace state")
    candidate = git_sha or os.environ.get("GITHUB_SHA")
    gitdir = root / ".git"
    try:
        if gitdir.is_file():
            pointer = gitdir.read_text().strip()
            gitdir = (root / pointer.removeprefix("gitdir: ")).resolve()
            # Do not read metadata outside the authorized repository.
            gitdir.relative_to(root)
        if candidate is None:
            head = (gitdir / "HEAD").read_text().strip()
            if head.startswith("ref: "):
                ref = head[5:]
                refpath = gitdir / ref
                refpath.resolve().relative_to(gitdir.resolve())
                if refpath.is_file(): candidate = refpath.read_text().strip()
                elif (gitdir / "packed-refs").is_file():
                    matches = [line.split()[0] for line in (gitdir / "packed-refs").read_text().splitlines() if len(line.split()) == 2 and line.split()[1] == ref]
                    if len(matches) == 1: candidate = matches[0]
            else: candidate = head
    except (OSError, ValueError):
        candidate = None
    if not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", candidate): candidate = None
    files = []
    for folder in ("scripts", "reports/api"):
        for path in sorted((root / folder).rglob("*.py")):
            files.append([relative_path(root, path), hashlib.sha256(path.read_bytes()).hexdigest()])
    for name in ("requirements.txt", "requirements-dev.txt"):
        path = root / name
        if path.is_file(): files.append([name, hashlib.sha256(path.read_bytes()).hexdigest()])
    return {"git_sha": candidate.lower() if candidate else None, "workspace_state": workspace_state, "source_tree_hash": digest(files)}


def validate_rows(rows: list[dict]) -> list[dict]:
    """Require unique increasing naive daily sessions; preserve gaps and every return."""
    previous = ""
    if not rows: raise ValueError("empty return sidecar")
    for row in rows:
        if set(row) != {"session", "log_return"}: raise ValueError("return row schema")
        session = row["session"]
        if not isinstance(session, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", session): raise ValueError("session must be naive midnight daily label")
        date.fromisoformat(session)
        if session <= previous: raise ValueError("sessions must be strictly ordered and unique")
        value = row["log_return"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value): raise ValueError("finite return required")
        previous = session
    return rows


def immutable_write(path: Path, content: bytes) -> None:
    """Write/fsync a temporary sibling, then publish without replacing evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content); handle.flush(); os.fsync(handle.fileno())
        # link is exclusive on both NTFS and POSIX; unlink leaves the durable inode.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def serialized(path: Path, timeout: float = 10.):
    """An orphan lock is never silently removed; recover explicitly after inspection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "wb") as handle:
                handle.write(canonical_json({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()}))
                handle.flush(); os.fsync(handle.fileno())
            break
        except FileExistsError:
            try: owner = json.loads(lock.read_bytes()).get("pid", -1)
            except (ValueError, OSError): owner = None
            if owner == -1 or time.monotonic() >= deadline:
                raise ValueError(f"lock requires explicit recovery: {lock}")
            time.sleep(.02)
    try:
        yield
    finally:
        # Windows readers may briefly deny deletion. Retry only our own lock.
        for retry in range(100):
            try:
                lock.unlink()
                break
            except PermissionError:
                if retry == 99:
                    raise
                time.sleep(.01)


class TrialLedger:
    """One append-only authority. Injected roots are exclusively synthetic fixtures."""
    def __init__(self, root: Path = ROOT, *, relative_path: str = "docs/trials/trials.jsonl", synthetic: bool = False):
        self.root = Path(root).resolve()
        if self.root != ROOT and not synthetic: raise ValueError("injected root requires synthetic context")
        if self.root == ROOT and synthetic: raise ValueError("synthetic context cannot use production root")
        self.path = self.root / globals()["relative_path"](self.root, relative_path)
        if self.path.relative_to(self.root).as_posix().startswith("data/cache/"): raise ValueError("ledger cannot use data/cache")
        self.synthetic = synthetic
        self.anchor = self.path.with_suffix(".head.json")

    def verify(self) -> dict:
        """Verify events, lifecycle, external head anchor and all bound sidecars."""
        if not self.path.exists():
            if self.anchor.exists(): raise ValueError("missing ledger with existing anchor")
            return {"events": [], "head": ZERO, "n_post_ledger": 0}
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"): raise ValueError("partial final record; explicit recovery required")
        events, starts, terminal, ids = [], {}, set(), set()
        head = ZERO
        for index, line in enumerate(raw.splitlines(), 1):
            try:
                event = json.loads(line)
                claimed = event.pop("record_hash")
                if event["prev_hash"] != head or digest(event) != claimed: raise ValueError("hash disconnected")
                event["record_hash"] = claimed
                if event["event_id"] in ids: raise ValueError("duplicate event")
                ids.add(event["event_id"])
                uuid.UUID(event["trial_id"]); uuid.UUID(event["event_id"])
                if datetime.fromisoformat(event["timestamp_utc"]).utcoffset().total_seconds() != 0: raise ValueError("UTC instant required")
                if event["schema_version"] != 1 or event["role"] not in ROLES: raise ValueError("event schema")
                if digest(event["config"]) != event["config_hash"]: raise ValueError("config hash")
                trial = event["trial_id"]
                if event["event_type"] == "started":
                    if trial in starts: raise ValueError("duplicate start")
                    starts[trial] = event
                else:
                    if event["event_type"] not in TERMINALS or trial not in starts or trial in terminal: raise ValueError("invalid terminal lifecycle")
                    for key in ("role", "family", "runner", "config", "config_hash", "source"):
                        if event[key] != starts[trial][key]: raise ValueError("terminal start mismatch")
                    terminal.add(trial)
                    if event["event_type"] == "completed" and not event.get("sidecar"): raise ValueError("completed return sidecar missing")
                    if event.get("sidecar"):
                        side = event["sidecar"]
                        path = self.root / relative_path(self.root, side["path"])
                        if "data/cache/" in side["path"]: raise ValueError("data/cache sidecar")
                        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != side["sha256"]: raise ValueError(f"sidecar missing/corrupt: {side['path']}")
                        rows = validate_rows([json.loads(x) for x in path.read_bytes().splitlines()])
                        if (len(rows), rows[0]["session"], rows[-1]["session"]) != (side["rows"], side["first_session"], side["last_session"]): raise ValueError(f"sidecar coverage: {side['path']}")
                head = claimed
                events.append(event)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise ValueError(f"record {index}: {exc}") from exc
        expected = {"head": head, "records": len(events)}
        if events and (not self.anchor.is_file() or json.loads(self.anchor.read_bytes()) != expected): raise ValueError("head anchor mismatch; explicit recovery required")
        if not events and self.anchor.exists() and json.loads(self.anchor.read_bytes()) != expected: raise ValueError("head anchor mismatch")
        return {"events": events, "head": head, "n_post_ledger": sum(e["role"] == "candidate" for e in starts.values())}

    def _append(self, event: dict, head: str, count: int) -> dict:
        event = {**event, "schema_version": 1, "event_id": str(uuid.uuid4()), "timestamp_utc": datetime.now(timezone.utc).isoformat(), "prev_hash": head}
        event["record_hash"] = digest(event)
        with self.path.open("ab") as handle:
            handle.write(canonical_json(event) + b"\n"); handle.flush(); os.fsync(handle.fileno())
        temporary = self.anchor.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            handle.write(canonical_json({"head": event["record_hash"], "records": count + 1})); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, self.anchor)
        return event

    def start(self, config: dict, *, role: str, family: str, runner: str, source: dict | None = None) -> str:
        if role not in ROLES: raise ValueError("unknown trial role")
        if role == "synthetic_test" and not self.synthetic: raise ValueError("synthetic role requires injected ledger")
        normalized, hashed = canonical_config(config, root=self.root)
        with serialized(self.path):
            state = self.verify()
            event = self._append({"trial_id": str(uuid.uuid4()), "event_type": "started", "role": role, "family": family, "runner": runner, "config": normalized, "config_hash": hashed, "source": source or source_identity()}, state["head"], len(state["events"]))
        return event["trial_id"]

    def finish(self, trial_id: str, outcome: str, *, returns: list[dict] | None = None, metadata: dict | None = None, reason: str | None = None) -> dict:
        if outcome not in TERMINALS: raise ValueError("unknown terminal outcome")
        with serialized(self.path):
            state = self.verify()
            matches = [e for e in state["events"] if e["trial_id"] == trial_id]
            if len(matches) != 1: raise ValueError("missing start or existing terminal")
            event = {k: matches[0][k] for k in ("trial_id", "role", "family", "runner", "config", "config_hash", "source")}
            event.update(event_type=outcome, reason=reason, sidecar=None)
            if returns is not None:
                rows = validate_rows(returns)
                path = self.path.parent / "returns" / (trial_id + ".jsonl")
                payload = b"".join(canonical_json(row) + b"\n" for row in rows)
                immutable_write(path, payload)
                event["sidecar"] = {"path": relative_path(self.root, path), "sha256": hashlib.sha256(payload).hexdigest(), "rows": len(rows), "first_session": rows[0]["session"], "last_session": rows[-1]["session"], "metadata": metadata or {}}
            elif outcome == "completed": raise ValueError("completed requires complete daily returns")
            return self._append(event, state["head"], len(state["events"]))
