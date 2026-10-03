"""Tests for the local Stop hook .claude/hooks/run_tests.py (one-shot full-suite gate).

No test launches Git or a real pytest child: the guard is a pure string
classifier, and the Stop hook's runner is injected.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_hook_{name}", HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


stop = _load("run_tests")

# ---------------------------------------------------------------- Stop hook


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_text("x")
    (tmp_path / ".specify").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("x = 1\n")
    (tmp_path / "docs" / "trials").mkdir(parents=True)
    (tmp_path / "docs" / "trials" / "trials.jsonl").write_text("{}\n")
    monkeypatch.setattr(stop, "STATE_DIR", tmp_path / "_state")
    return tmp_path


class FakeRunner:
    def __init__(self, code=0, side_effect=None):
        self.code, self.calls, self.side_effect = code, [], side_effect

    def __call__(self, args, cwd, stdout, stderr, timeout):
        self.calls.append(args)
        stdout.write(b"collected 3 items\n" * 2000)
        if self.side_effect:
            self.side_effect()
        return subprocess.CompletedProcess(args, self.code)


def _stop(repo, runner, **extra):
    payload = {"session_id": "s1", "cwd": str(repo), **extra}
    return json.loads(stop.run(payload, runner=runner, python="py")[1])


def test_passing_suite_allows_and_keeps_full_log(repo):
    r = FakeRunner(0)
    out = _stop(repo, r)
    assert "decision" not in out and r.calls == [["py", "-m", "pytest", "tests", "-rfEsx"]]
    log = Path(out["systemMessage"].split("Log: ")[1])
    assert log.read_bytes().count(b"collected") == 2000


def test_failing_suite_blocks_with_true_exit_code(repo):
    out = _stop(repo, FakeRunner(5))
    assert out["decision"] == "block" and "exit 5" in out["reason"]


def test_stop_hook_active_never_relaunches(repo):
    r = FakeRunner(1)
    _stop(repo, r, stop_hook_active=True)
    assert r.calls == []


def test_unchanged_tree_after_failure_reports_without_relaunch(repo):
    r = FakeRunner(1)
    _stop(repo, r)
    out = _stop(repo, r)
    assert len(r.calls) == 1 and out["decision"] == "block" and "Unchanged tree" in out["reason"]


def test_unchanged_tree_after_pass_skips(repo):
    r = FakeRunner(0)
    _stop(repo, r)
    _stop(repo, r)
    assert len(r.calls) == 1


def test_changed_tree_reruns(repo):
    r = FakeRunner(0)
    _stop(repo, r)
    (repo / "scripts" / "b.py").write_text("y = 2\n")
    _stop(repo, r)
    assert len(r.calls) == 2


@pytest.mark.parametrize("rel", [".claude/hooks/git_guard.py", "reports/web/src/App.tsx", "AGENTS.md"])
def test_change_outside_python_dirs_reruns(repo, rel):
    """Codex P1 on #22: every path the suite reads is in the fingerprint."""
    r = FakeRunner(0)
    _stop(repo, r)
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text("changed\n")
    _stop(repo, r)
    assert len(r.calls) == 2


def test_files_written_by_the_suite_do_not_force_rerun(repo):
    def artifact():
        (repo / "scripts" / "phase1-events.jsonl").write_text("{}\n")
    r = FakeRunner(0, side_effect=artifact)
    _stop(repo, r)
    _stop(repo, r)
    assert len(r.calls) == 1


def test_generated_dirs_are_ignored(repo):
    r = FakeRunner(0)
    _stop(repo, r)
    for rel in ("node_modules/x.js", "data/cache/a.csv", "venv/lib.py", "scripts/__pycache__/a.pyc"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("x")
    _stop(repo, r)
    assert len(r.calls) == 1


def test_in_progress_marker_prevents_second_run(repo):
    import time
    stop._save(stop._state_path("s1"), {"in_progress": time.time()})
    r = FakeRunner(0)
    _stop(repo, r)
    assert r.calls == []


def test_ledger_change_during_run_blocks(repo):
    def touch():
        (repo / "docs" / "trials" / "trials.jsonl").write_text("{}\n{}\n")
    out = _stop(repo, FakeRunner(0, side_effect=touch))
    assert out["decision"] == "block" and "docs/trials" in out["reason"]


def test_ledger_manifest_records_absent_returns(repo):
    assert stop.ledger_manifest(repo)["docs/trials/returns"] == "absent"


def test_no_root_means_no_run(tmp_path):
    r = FakeRunner(0)
    stop.run({"session_id": "s", "cwd": str(tmp_path)}, runner=r)
    assert r.calls == []


def test_rule12_planted_defect_ignoring_exit_code_goes_red(repo, monkeypatch):
    """Planted defect: failures reported as success. The failing case must flip."""
    monkeypatch.setattr(stop, "_block", lambda reason: stop._allow(reason))
    out = _stop(repo, FakeRunner(5))
    assert "decision" not in out, "mutant not caught by the failing-suite case"


@pytest.mark.parametrize("marker", [True, 1.0])
def test_stale_in_progress_marker_does_not_disable_the_gate(repo, marker):
    """Codex P1 on #22: a hook killed mid-run must not leave the gate off."""
    stop._save(stop._state_path("s1"), {"in_progress": marker})
    r = FakeRunner(0)
    _stop(repo, r)
    assert len(r.calls) == 1


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null"])
def test_invalid_input_blocks_the_stop(raw):
    code, out, _ = stop.main(raw)
    assert code == 0 and json.loads(out)["decision"] == "block"


def test_hook_crash_blocks_the_stop(monkeypatch):
    def boom(payload):
        raise OSError("disk full")
    monkeypatch.setattr(stop, "run", boom)
    code, out, _ = stop.main('{"session_id": "s"}')
    assert json.loads(out)["decision"] == "block" and "disk full" in json.loads(out)["reason"]
