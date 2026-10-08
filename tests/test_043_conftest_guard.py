"""T028 / AC-6: the shutdown guard names any changed path under docs/trials."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from ledger_copy_support import child_env, manifest, tripwire

REPO = Path(__file__).resolve().parents[1]
PLANT = """from pathlib import Path


def test_plant():
    target = Path(__file__).resolve().parents[1] / "docs/trials/returns/x.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\\n", encoding="utf-8")
"""


def run_minimal_copy(tmp_path, planted):
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir()
    for name in ("pyproject.toml", "tests/conftest.py", "tests/ledger_copy_support.py",
                 "scripts/trial_runner.py", "scripts/trial_registry.py", "scripts/_project.py"):
        shutil.copy2(REPO / name, root / name)
    (root / "docs/trials").mkdir(parents=True)
    (root / "docs/trials/trials.jsonl").write_text("", encoding="utf-8")
    (root / "tests/test_x.py").write_text(PLANT if planted else "def test_x():\n    pass\n",
                                          encoding="utf-8")
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                          cwd=root, env=child_env(), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


@pytest.mark.parametrize("planted", [False, True], ids=["control", "returns-write"])
def test_shutdown_guard_names_changed_ledger_path(tmp_path, planted):
    with tripwire():
        result = run_minimal_copy(tmp_path, planted)
    output = result.stdout + result.stderr
    if planted:
        assert "spec043: tests changed docs/trials paths" in output, output
        assert "returns/x.jsonl" in output, output
        assert result.returncode != 0, output
    else:
        assert result.returncode == 0, output
        assert "spec043" not in output, output


def test_manifest_records_absent_returns():
    assert manifest(REPO).get("returns") == "absent"
