"""Sole lifetime ledger: canonical start events, immutable returns, verified chain.

Canonical JSON is UTF-8, sorted keys, compact separators, finite numbers only.
Unknown workspace state is honest: no index/dirtiness guesses and no git process.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

from _project import project_root

ROOT = project_root()
DEFAULT_TRIALS_PATH = ROOT / "docs/trials/trials.jsonl"
ROLES = {"candidate", "buy_and_hold_baseline", "random_signal_baseline", "synthetic_test"}
TERMINALS = {"completed", "rejected", "errored", "abandoned"}
CONFIG_FIELDS = set("data universe date_range features transforms target model cv seed initial_capital commission slippage liquidation risk_free".split())
ZERO = "0" * 64
# Spec 058 D-1: a preregistered family's trials are refused until its declaration is in docs/trials.
FAMILY_DIR = "docs/trials/families"
DECLARED_FAMILIES = {"058-edge": ".specify/specs/058-edge-research-program/declaration.json",
                     "059-allocation": ".specify/specs/059-live-allocation/declaration.json"}
ENABLE_ACTION = ("pass --record-trial to the CLI, or wrap library code in "
                 "`with production_recording(reason=...)`")
# Spec 043 D-1 B: production recording is per-run, never environmental. Only
# production_recording sets this temporarily; import alone never enables it.
_production_enabled: ContextVar[str | None] = ContextVar("production_recording", default=None)


class LedgerWriteRefused(RuntimeError):
    """Production ledger write attempted without deliberate per-run enablement."""


@contextmanager
def production_recording(reason: str):
    """Deliberate permission for this context only; always restore its parent."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("production recording requires a nonempty reason")
    token = _production_enabled.set(reason)
    try:
        yield
    finally:
        _production_enabled.reset(token)


def production_recording_reason() -> str | None:
    """Explicit token to pass to spawned workers; never read environment state."""
    return _production_enabled.get()


def _require_production_enabled(runner: str, path: Path) -> None:
    """Raise before any ledger byte (lock, directory, record, sidecar) exists.

    Guarantees FR-001/FR-003: unless enabled, refuse naming the runner, the
    resolved ledger path, that nothing was written, and the enabling action.
    """
    if _production_enabled.get() is None:
        raise LedgerWriteRefused(
            f"LedgerWriteRefused: production recording is not enabled for runner "
            f"{runner!r}; ledger {path}; no ledger byte was written. "
            f"To record deliberately, {ENABLE_ACTION}.")


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


# Windows refuses to create a file whose previous holder has unlinked it while another process
# still has it open ("delete pending"); os.open then raises PermissionError, not FileExistsError.
# That is contention, so it is retried until the deadline. On POSIX, EACCES is a real refusal.
_RETRY_DELETE_PENDING = os.name == "nt"


@contextmanager
def serialized(path: Path, timeout: float = 10.):
    """An orphan lock is never silently removed; recover explicitly after inspection.

    A Windows delete-pending lock is waited out like a held one; past ``timeout`` the
    PermissionError propagates. Elsewhere a PermissionError propagates at once.
    """
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
        except PermissionError:
            if not _RETRY_DELETE_PENDING or time.monotonic() >= deadline:
                raise
            time.sleep(.02)
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


def _family_path(family: str, root: Path) -> Path:
    if family not in DECLARED_FAMILIES:
        raise ValueError(f"family {family!r} has no preregistered declaration source")
    return Path(root) / FAMILY_DIR / f"{family}.json"


def declare_family(family: str, *, root: Path = ROOT, synthetic: bool = False) -> dict:
    """Write the one-time, immutable family declaration (spec 058 T005/T006).

    Guarantees: production writes require deliberate enablement and happen before any
    trial of that family exists; a second declaration never replaces the first.
    """
    root = Path(root).resolve()
    path = _family_path(family, root)
    if (root == ROOT) == synthetic:
        raise ValueError("synthetic declarations require an injected root, and only those")
    if not synthetic:
        _require_production_enabled("trial_registry.declare_family", path)
    source = root / DECLARED_FAMILIES[family]
    declaration = json.loads(source.read_text(encoding="utf-8"))
    if declaration.get("family") != family:
        raise ValueError(f"declaration source names family {declaration.get('family')!r}, not {family!r}")
    ledger = TrialLedger(root, synthetic=synthetic)
    state = ledger.verify()
    if any(e["family"] == family for e in state["events"]):
        raise ValueError(f"family {family!r} already has trials; it can no longer be preregistered")
    record = {"family": family, "declaration": declaration, "declaration_hash": digest(declaration),
              "source": DECLARED_FAMILIES[family], "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "ledger_head_at_declaration": state["head"], "declared_at_utc": datetime.now(timezone.utc).isoformat()}
    record["record_hash"] = digest(record)
    immutable_write(path, canonical_json(record))
    return record


AMEND_COMMAND = "python scripts/amend_family.py {family} --record"


def _amendment_paths(family: str, root: Path) -> list[Path]:
    """Amendment files in index order; a gap or a stray index raises (058 T006a)."""
    pattern = re.compile(re.escape(family) + r"\.amend-(\d+)\.json")
    found = {}
    for path in (Path(root) / FAMILY_DIR).glob(f"{family}.amend-*.json"):
        match = pattern.fullmatch(path.name)
        if not match or match.group(1) != str(int(match.group(1))):
            raise ValueError(f"family {family!r} amendment file {path.name!r} is malformed")
        found[int(match.group(1))] = path
    if sorted(found) != list(range(1, len(found) + 1)):
        raise ValueError(f"family {family!r} amendments are not contiguous from 1: {sorted(found)}")
    return [found[k] for k in sorted(found)]


def _apply_addition(declaration: dict, path: str, value) -> None:
    *parents, key = path.split("/")
    target = declaration
    for part in parents:
        target = target.get(part) if isinstance(target, dict) else None
    if not isinstance(target, dict) or key in target:
        raise ValueError(f"amendment adds {path!r}, which is not a new key of an existing object")
    target[key] = value


def _verified_family(family: str, root: Path) -> dict:
    """Base record plus every amendment, each verified and chained; no drift check."""
    path = _family_path(family, root)
    if not path.exists():
        raise ValueError(f"family {family!r} requires its declaration (spec 058 T006) at {FAMILY_DIR}")
    record = json.loads(path.read_bytes())
    claimed = record.pop("record_hash", None)
    if (claimed != digest(record) or record.get("family") != family
            or digest(record.get("declaration")) != record.get("declaration_hash")):
        raise ValueError(f"family {family!r} declaration record is altered or malformed")
    effective = json.loads(canonical_json(record["declaration"]))
    previous, amendments = claimed, []
    for index, amend_path in enumerate(_amendment_paths(family, root), 1):
        amendment = json.loads(amend_path.read_bytes())
        amend_hash = amendment.pop("record_hash", None)
        if (amend_hash != digest(amendment) or amendment.get("family") != family
                or amendment.get("amendment_index") != index or amendment.get("previous_record_hash") != previous
                or not isinstance(amendment.get("added"), dict) or not amendment["added"]):
            raise ValueError(f"family {family!r} amendment {index} is altered, reordered or unchained")
        for key in sorted(amendment["added"]):
            _apply_addition(effective, key, amendment["added"][key])
        amendments.append({**amendment, "record_hash": amend_hash})
        previous = amend_hash
    return {**record, "record_hash": claimed, "base_declaration": record["declaration"], "declaration": effective,
            "effective_declaration_hash": digest(effective), "amendments": amendments,
            "anchors": [record["ledger_head_at_declaration"], *(a["ledger_head_at_amendment"] for a in amendments)]}


def _first_difference(frozen, source, path: str = "") -> str | None:
    if isinstance(frozen, dict) and isinstance(source, dict):
        for key in sorted(set(frozen) | set(source)):
            if key not in frozen or key not in source:
                return f"{path}/{key}".lstrip("/")
            found = _first_difference(frozen[key], source[key], f"{path}/{key}")
            if found: return found
        return None
    return None if canonical_json(frozen) == canonical_json(source) else (path.lstrip("/") or "<root>")


def verify_family(family: str, *, root: Path = ROOT) -> dict:
    """Return the verified record whose `declaration` is the effective one (base + amendments).

    Guarantees: raises naming the missing or altered declaration or amendment, and raises when the
    committed declaration source differs from the effective frozen declaration (drift), naming the
    first differing key and the command that records an additions-only amendment.
    """
    verified = _verified_family(family, root)
    source = Path(root) / DECLARED_FAMILIES[family]
    if not source.is_file():
        raise ValueError(f"family {family!r} declaration source {DECLARED_FAMILIES[family]} is missing")
    current = json.loads(source.read_text(encoding="utf-8"))
    differs = _first_difference(verified["declaration"], current)
    if differs is not None:
        raise ValueError(f"family {family!r} declaration source drifted from its frozen record at {differs!r}; "
                         f"record the additions with `{AMEND_COMMAND.format(family=family)}` before any trial")
    return verified


def _additions(frozen: dict, source: dict, family: str) -> dict:
    """New top-level or `common` keys only; any changed or removed value is refused by name."""
    added = {}
    for key in sorted(set(frozen) | set(source)):
        if key not in source:
            raise ValueError(f"amendment refused: {key!r} would be removed from family {family!r}")
        if key not in frozen:
            added[key] = source[key]
        elif key == "common" and isinstance(frozen[key], dict) and isinstance(source[key], dict):
            for inner in sorted(set(frozen[key]) | set(source[key])):
                if inner not in source[key]:
                    raise ValueError(f"amendment refused: 'common/{inner}' would be removed from family {family!r}")
                if inner not in frozen[key]:
                    added[f"common/{inner}"] = source[key][inner]
                elif canonical_json(frozen[key][inner]) != canonical_json(source[key][inner]):
                    raise ValueError(f"amendment refused: 'common/{inner}' changes an existing value of family {family!r}")
        elif canonical_json(frozen[key]) != canonical_json(source[key]):
            raise ValueError(f"amendment refused: {key!r} changes an existing value of family {family!r}")
    if any("/" in name for name in [*source, *(source.get("common") or {})] if isinstance(name, str)):
        raise ValueError("amendment refused: a declaration key may not contain '/'")
    return added


def amend_family(family: str, *, root: Path = ROOT, synthetic: bool = False) -> dict:
    """Write the next additions-only amendment record (spec 058 T006a, Camden's "A", 2026-10-12).

    Guarantees: production writes require deliberate enablement; only new top-level or `common`
    keys enter; refused once any trial of the family exists or when nothing changed; each record
    chains to the previous record hash and is never replaced.
    """
    root = Path(root).resolve()
    base_path = _family_path(family, root)
    if (root == ROOT) == synthetic:
        raise ValueError("synthetic amendments require an injected root, and only those")
    if not synthetic:
        _require_production_enabled("trial_registry.amend_family", base_path)
    verified = _verified_family(family, root)
    source = root / DECLARED_FAMILIES[family]
    current = json.loads(source.read_text(encoding="utf-8"))
    if current.get("family") != family:
        raise ValueError(f"declaration source names family {current.get('family')!r}, not {family!r}")
    added = _additions(verified["declaration"], current, family)
    if not added:
        raise ValueError(f"amendment refused: family {family!r} source adds nothing to its frozen declaration")
    state = TrialLedger(root, synthetic=synthetic).verify()
    if any(e["family"] == family for e in state["events"]):
        raise ValueError(f"amendment refused: family {family!r} already has trials; its declaration is final")
    index = len(verified["amendments"]) + 1
    previous = verified["amendments"][-1]["record_hash"] if verified["amendments"] else verified["record_hash"]
    record = {"family": family, "amendment_index": index, "previous_record_hash": previous, "added": added,
              "source": DECLARED_FAMILIES[family], "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "ledger_head_at_amendment": state["head"], "amended_at_utc": datetime.now(timezone.utc).isoformat()}
    record["record_hash"] = digest(record)
    immutable_write(base_path.with_name(f"{family}.amend-{index}.json"), canonical_json(record))
    return record


def _family_count(family: str, events: list[dict], root: Path) -> dict:
    cap = verify_family(family, root=root)["declaration"]["n_family_cap"]
    n = sum(1 for e in events if e["event_type"] == "started" and e["family"] == family
            and e["role"] in {"candidate", "synthetic_test"})
    return {"family": family, "n_family": n, "cap": cap, "within_cap": n <= cap}


def family_status(family: str, ledger: "TrialLedger") -> dict:
    """Candidate starts in a declared family against its cap; over the cap voids family N (058 D-1)."""
    return _family_count(family, ledger.verify()["events"], ledger.root)


def _undefined(reason: str, **fields) -> dict:
    return {"value": None, "reason": reason, **fields}


def trial_counts(backfill: dict, ledger: "TrialLedger", *, family: str | None = None) -> dict:
    """N_current = N_backfill + every post-ledger candidate start (FR-026); family N beside it (058 D-1).

    Guarantees: the backfill counts only as a complete, self-hashed artifact stored under the ledger
    root's docs/trials/backfill and never below a stored superseding count; the ledger is read only
    through its verified chain; duplicate, failed and unterminated candidate starts all count, while
    baselines, unique hashes, completions and matrix columns never stand in for N. A family is
    evaluated at N_family only while its declaration verifies, is anchored in the chain before the
    family's first start, and its starts stay within a cap of at most 50; otherwise N reverts to
    the lifetime N_current. The ledger is verified once: lifetime N, family N and `ledger_head_hash`
    (also on the family block) all come from that one verified state (spec 033 amendment 2026-10-11).
    """
    body = {k: v for k, v in backfill.items() if k != "sha256"}
    if backfill.get("sha256") != digest(body): return _undefined("evidence_corrupt")
    n_backfill = backfill.get("n_backfill")
    if backfill.get("status") != "complete" or isinstance(n_backfill, bool) or not isinstance(n_backfill, int) or n_backfill < 0:
        return _undefined("backfill_incomplete")
    stored = [json.loads(p.read_bytes()) for p in sorted((ledger.root / "docs/trials/backfill").glob("*.json")) if p.name != "manifest.json"]
    if backfill not in stored: return _undefined("evidence_missing")
    if any(n_backfill < (a.get("n_backfill") or 0) for a in stored): return _undefined("backfill_changed")
    try: state = ledger.verify()
    except ValueError as exc: return _undefined("ledger_invalid", detail=str(exc))
    n_post = state["n_post_ledger"]
    counts = {"reason": None, "n_backfill": n_backfill, "n_post_ledger": n_post, "n_current": n_backfill + n_post,
              "backfill_hash": backfill["sha256"], "ledger_head_hash": state["head"], "family": None}
    if family is not None:
        try:
            status = _family_count(family, state["events"], ledger.root)
            anchors = verify_family(family, root=ledger.root)["anchors"]
            heads = [ZERO, *(e["record_hash"] for e in state["events"])]
            first = next((i for i, e in enumerate(state["events"], 1) if e["family"] == family), len(heads))
            if any(a not in heads[:first] for a in anchors): raise ValueError("declaration not anchored before the family's first start")
            if not 1 <= status["cap"] <= 50: raise ValueError("family cap outside 1..50")
        except (ValueError, KeyError, TypeError) as exc:
            status = {"family": family, "n_family": None, "cap": None, "within_cap": False, "detail": str(exc)}
        n_dsr = status["n_family"] if status["within_cap"] else counts["n_current"]
        counts["family"] = {**status, "n_dsr": n_dsr, "reverted_to_lifetime": not status["within_cap"],
                            "ledger_head_hash": state["head"]}
    return counts


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
        if not self.synthetic: _require_production_enabled(runner, self.path)
        if role not in ROLES: raise ValueError("unknown trial role")
        if role == "synthetic_test" and not self.synthetic: raise ValueError("synthetic role requires injected ledger")
        if family in DECLARED_FAMILIES: verify_family(family, root=self.root)
        normalized, hashed = canonical_config(config, root=self.root)
        with serialized(self.path):
            state = self.verify()
            event = self._append({"trial_id": str(uuid.uuid4()), "event_type": "started", "role": role, "family": family, "runner": runner, "config": normalized, "config_hash": hashed, "source": source or source_identity()}, state["head"], len(state["events"]))
        return event["trial_id"]

    def finish(self, trial_id: str, outcome: str, *, returns: list[dict] | None = None, metadata: dict | None = None, reason: str | None = None) -> dict:
        if not self.synthetic: _require_production_enabled(f"TrialLedger.finish({trial_id})", self.path)
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
