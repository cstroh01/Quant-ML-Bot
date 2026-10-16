"""§11.3 item 1 evidence runner. Offline: drivers are faked; no driver or suite actually runs."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from context import SCRIPTS_DIR  # noqa: F401 -- makes scripts importable

import run_mutation_suite as rms


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "tests" / "mutation").mkdir(parents=True)
    (tmp_path / "tests" / "mutation" / "run_a_mutants.py").write_text("print('3/3 killed')\n")
    (tmp_path / "tests" / "mutation" / "run_b_mutants.py").write_text("import sys\nd = sys.argv[1]\n")
    (tmp_path / "tests" / "mutation" / "driver_support.py").write_text("")
    monkeypatch.setattr(rms, "ROOT", tmp_path)
    return tmp_path


def fake_run(codes, dirty_after=None):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        name = Path(args[2]).name if len(args) > 2 else ""
        return SimpleNamespace(returncode=codes.get(name, 0), stdout="KILLED x\n2/2 killed\n", stderr="")
    return run, calls


def test_runs_every_driver_serially_and_gives_output_dirs_only_to_those_that_take_one(repo, monkeypatch, tmp_path):
    run, calls = fake_run({})
    monkeypatch.setattr(rms.subprocess, "run", run)
    monkeypatch.setattr(rms, "_git", lambda *a: "")
    results = rms.run_drivers(tmp_path / "work")
    assert [r["driver"] for r in results] == ["tests/mutation/run_a_mutants.py", "tests/mutation/run_b_mutants.py"], \
        "ITEM1 every run_*.py driver, helpers excluded"
    assert len(calls[0]) == 3 and len(calls[1]) == 4 and calls[1][3].endswith("run_b_mutants"), "ITEM1 OUTDIR"
    assert all(r["exit_code"] == 0 and r["last_line"] == "2/2 killed" for r in results)


def test_a_driver_that_leaves_a_mutant_stops_the_run(repo, monkeypatch, tmp_path):
    run, _ = fake_run({})
    monkeypatch.setattr(rms.subprocess, "run", run)
    monkeypatch.setattr(rms, "_git", lambda *a: " M scripts/x.py" if "status" in a else "")
    with pytest.raises(RuntimeError, match="left tracked files changed"):
        rms.run_drivers(tmp_path / "work")


def test_verdict_fails_on_any_failing_driver_and_refuses_a_dirty_tree(repo, monkeypatch, tmp_path):
    run, _ = fake_run({"run_b_mutants.py": 1})
    monkeypatch.setattr(rms.subprocess, "run", run)
    monkeypatch.setattr(rms, "_git", lambda *a: "abc1234" if "rev-parse" in a else "")
    out = tmp_path / "record.json"
    assert rms.main(["--out", str(out), "--skip-suite"]) == 1, "ITEM1 VERDICT one failing driver"
    record = json.loads(out.read_text())
    assert record["verdict"] == "FAIL" and record["drivers_passed"] == "1/2" and record["commit"] == "abc1234"
    monkeypatch.setattr(rms, "_git", lambda *a: " M scripts/x.py")
    assert rms.main(["--out", str(out), "--skip-suite"]) == 2, "ITEM1 DIRTY refused"
