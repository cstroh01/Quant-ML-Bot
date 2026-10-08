"""Spec 043 D-4 (a + c): the one isolation helper every mutation driver uses.

Copies carry `tests/conftest.py`, its `ledger_copy_support.py` and
`pyproject.toml`, so each child has the project marker and conftest's own
whole-tree shutdown guard. Children run with `child_env()`, which strips every
enablement. `guarded()` wraps a whole driver run in the real-ledger tripwire.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "tests") not in sys.path:
    sys.path.insert(0, str(REPO / "tests"))

from ledger_copy_support import child_env, tripwire  # noqa: E402

ISOLATION = ("pyproject.toml", "tests/conftest.py", "tests/ledger_copy_support.py")


def copy_into(root: Path, relatives) -> Path:
    """Copy `relatives` plus the D-4 isolation files from the repository into `root`."""
    for relative in dict.fromkeys((*relatives, *ISOLATION)):
        source, target = REPO / relative, Path(root) / relative
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"),
                            dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return Path(root)


def run_pytest(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run pytest in a copy with every production enablement stripped."""
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *args], cwd=root,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=child_env(), check=False)


@contextmanager
def guarded(root: Path | None = None):
    """Fail, naming each path, if the real `docs/trials/` changes during the run."""
    with tripwire(root):
        yield
