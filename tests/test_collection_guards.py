"""Fail closed on misplaced Python tests and silent zero-case collection."""

from fnmatch import fnmatch
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"
# These contain tooling or third-party code, not repository-owned tests.
EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", "node_modules", "site-packages",
}


def python_test_files(root):
    """Include hidden spec folders and legacy unittest's broader test*.py names."""
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(
            name for name in dirs
            if name not in EXCLUDED_DIRS
            and not (Path(directory) / name / "pyvenv.cfg").is_file()
        )
        for name in sorted(files):
            if fnmatch(name, "test*.py") or fnmatch(name, "*_test.py"):
                yield (Path(directory) / name).resolve()


def test_python_tests_live_under_tests():
    misplaced = [str(path.relative_to(REPO)) for path in python_test_files(REPO)
                 if not path.is_relative_to(TESTS)]
    assert not misplaced, "Python test files outside tests/:\n" + "\n".join(misplaced)


def test_each_test_module_collects_cases(collected_test_paths):
    missing = sorted(str(path.relative_to(REPO)) for path in python_test_files(TESTS)
                     if path not in collected_test_paths)
    assert not missing, (
        "Test modules with zero collected cases (rename helpers without a test prefix; "
        "run the full suite when selecting this guard):\n" + "\n".join(missing)
    )


@pytest.mark.parametrize(
    "scenario, expected_error",
    [
        ("control", None),
        ("hidden_spec", "Python test files outside tests/"),
        ("suffix_test", "Python test files outside tests/"),
        ("empty_module", "Test modules with zero collected cases"),
        ("ignored_module", "Test modules with zero collected cases"),
        ("legacy_filename", "Test modules with zero collected cases"),
        ("dependencies", None),
    ],
)
def test_collection_guards_reject_silent_omissions(tmp_path, scenario, expected_error):
    """Exercise real pytest collection in isolated trees, including -k deselection."""
    target = tmp_path / "tests"
    target.mkdir()
    for name in ("conftest.py", "test_collection_guards.py"):
        shutil.copy2(TESTS / name, target / name)
    (target / "test_valid.py").write_text("def test_ok():\n    assert True\n")

    relative = {
        "hidden_spec": ".specify/specs/example/test_stray.py",
        "suffix_test": "docs/stray_test.py",
        "empty_module": "tests/test_empty.py",
        "ignored_module": "tests/test_ignored.py",
        "legacy_filename": "tests/testlegacy.py",
    }.get(scenario)
    if relative:
        stray = tmp_path / relative
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("VALUE = 1\n" if scenario == "empty_module"
                         else "def test_ok():\n    assert True\n")
    if scenario == "ignored_module":
        with (target / "conftest.py").open("a") as stream:
            stream.write("\ncollect_ignore = ['test_ignored.py']\n")
    if scenario == "dependencies":
        for folder in ("reports/web/node_modules/pkg", ".custom-env", ".pytest_cache"):
            dependency = tmp_path / folder
            dependency.mkdir(parents=True)
            (dependency / "test_vendor.py").write_text("VALUE = 1\n")
        (tmp_path / ".custom-env/pyvenv.cfg").write_text("home = example\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-k",
         "test_python_tests_live_under_tests or test_each_test_module_collects_cases"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""},
    )
    output = result.stdout + result.stderr
    assert result.returncode == (1 if expected_error else 0), output
    if expected_error:
        assert expected_error in output, output
        assert str(Path(relative)) in output, output
    else:
        assert "2 passed" in output, output
