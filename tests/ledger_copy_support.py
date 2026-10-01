"""Spec 043 copy isolation; only ledger hashing ever targets the real tree."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
REAL_ROOT = Path(os.environ.get("SPEC043_REAL_ROOT", REPO)).resolve()


def manifest(root: Path) -> dict[str, str]:
    """Hash every ledger path, including directories and explicit absences."""
    base = Path(root) / "docs/trials"
    result = {".": "directory" if base.is_dir() else "absent"}
    for path in sorted(base.rglob("*")):
        result[path.relative_to(base).as_posix()] = (
            "directory" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
        )
    for name in ("trials.jsonl", "trials.head.json", "returns", "backfill"):
        result.setdefault(name, "absent")
    return result


def changed(before: dict, after: dict) -> list[str]:
    return sorted(key for key in before.keys() | after.keys()
                  if before.get(key) != after.get(key))


@contextmanager
def tripwire(root: Path | None = None):
    """Always compare the real ledger, even if the operation raises."""
    root = REAL_ROOT if root is None else root
    before = manifest(root)
    try:
        yield
    finally:
        paths = changed(before, manifest(root))
        if paths:
            raise AssertionError("ledger tripwire: " + ", ".join(paths))


def make_copy(dst: Path) -> Path:
    """Copy the full working tree, excluding only the specified caches/tools."""
    dst = Path(dst).resolve()
    assert not dst.is_relative_to(REAL_ROOT.parent), str(dst)
    assert not dst.is_relative_to(REPO), str(dst)

    def ignore(folder, names):
        return [name for name in names
                if name in {"venv", "node_modules", ".git", "__pycache__"}
                or (Path(folder) == REPO / "data" and name == "cache")]

    shutil.copytree(REPO, dst, ignore=ignore)
    return dst


def child_env() -> dict[str, str]:
    """D-1 B has no environment switch; strip the legacy proposal as well."""
    env = os.environ.copy()
    for key in ("SPEC033_SYNTHETIC_ROOT", "QMB_LEDGER_WRITE", "QMB_PROJECT_ROOT",
                "PYTHONPATH", "GITHUB_SHA", "PYTEST_ADDOPTS"):
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
               MPLBACKEND="Agg", SPEC043_REAL_ROOT=str(REAL_ROOT))
    return env


def ledger_counts(root: Path) -> tuple[int, int]:
    base = root / "docs/trials"
    return (len((base / "trials.jsonl").read_bytes().splitlines()),
            len(list((base / "returns").glob("*.jsonl"))))


def run_child(entry: str, *, enabled: bool = False) -> dict:
    """Run the actual entry point in a disposable full copy, with evidence."""
    with tripwire(), tempfile.TemporaryDirectory(prefix="qmb043-") as temp:
        root = make_copy(Path(temp) / "repo")
        before, counts = manifest(root), ledger_counts(root)
        command = [sys.executable, "-B", "tests/ledger_guard_child.py", entry]
        if enabled:
            command.append("--record-trial")
        process = subprocess.run(command, cwd=root, env=child_env(),
                                 capture_output=True, text=True, encoding="utf-8", timeout=180)
        after, end_counts = manifest(root), ledger_counts(root)
        outcome = root / "guard-outcome.json"
        report = json.loads(outcome.read_text()) if outcome.exists() else {}
        result = dict(entry=entry, enabled=enabled, copy=str(root),
                      returncode=process.returncode, before=before, after=after,
                      changed=changed(before, after), records=end_counts[0] - counts[0],
                      sidecars=end_counts[1] - counts[1], outcome=report,
                      stdout=process.stdout, stderr=process.stderr)
        evidence = {key: value for key, value in result.items() if key not in {"stdout", "stderr"}}
        evidence.update(stdout_empty=not process.stdout, stderr=process.stderr,
                        label="EXAMPLE \u2014 NOT A RESULT")
        result["evidence"] = evidence
        # Tests are side-effect-free (043 review F10). Harvesting evidence into
        # a file is an explicit act: name the destination in SPEC043_EVIDENCE_LOG.
        if log := os.environ.get(EVIDENCE_LOG_VAR):
            with Path(log).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(evidence, sort_keys=True) + "\n")
        return result


EVIDENCE_LOG_VAR = "SPEC043_EVIDENCE_LOG"
E5_RECORDING_COMMAND = ("ma_crossover_backtest", "--record-trial")


def assert_e5_refused(request: dict) -> None:
    """AC-10 409 branch: a ledger-silent refusal naming the E1 recording command."""
    assert request["status"] == 409, request
    assert request["records"] == request["sidecars"] == 0, request
    assert request["n_before"] == request["n_after"], request
    body = str(request["body"])
    for token in E5_RECORDING_COMMAND:
        assert token in body, f"409 does not name the recording command ({token}): {body}"


def assert_e5_served(result: dict) -> None:
    """AC-10 200 branch: after recording, GET serves the recorded trial read-only.

    The child replaces every compute/record seam after recording, so a 200 here
    cannot come from a fresh evaluation, and an unconditional 409 cannot pass.
    """
    assert result["returncode"] == 0, result["stderr"]
    # Only the deliberate E1 recording may change bytes: 1 candidate + 21 baselines.
    counts = (result["records"], result["sidecars"])
    assert counts == (44, 22), f"bytes beyond the E1 recording: {counts} {result['changed']}"
    requests = result["outcome"]["requests"]
    assert len(requests) == 2, requests
    for request in requests:
        assert request["status"] == 200, f"recorded config not served: {request}"
        assert request["records"] == request["sidecars"] == 0, request
        assert request["n_before"] == request["n_after"], request
    assert requests[0]["body_sha256"] == requests[1]["body_sha256"], requests


def assert_refused(result: dict, runner: str, action: str = "--record-trial") -> None:
    assert not result["changed"], (
        f'{result["entry"]}: changed {result["records"]} records, '
        f'{result["sidecars"]} sidecars: {result["changed"]}'
    )
    assert result["returncode"] != 0
    assert result["stdout"] == ""
    message = result["stderr"]
    for token in ("LedgerWriteRefused", runner, "no ledger byte", action):
        assert token.lower() in message.lower(), message
    assert str(Path(result["copy"]) / "docs/trials/trials.jsonl") in message
