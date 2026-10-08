"""Retain actual collection evidence before -k/-m deselection for suite guards."""

from pathlib import Path
import os
import sys
import tempfile

import pytest

from ledger_copy_support import changed, manifest

if str(Path(__file__).resolve().parents[1] / "scripts") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from trial_runner import SYNTHETIC_LABEL  # noqa: E402


COLLECTED_PATHS = pytest.StashKey[frozenset[Path]]()
SYNTHETIC_SESSION = pytest.StashKey[object]()
PRIOR_SYNTHETIC_ROOT = pytest.StashKey[object]()
PRODUCTION_LEDGER_MANIFEST = pytest.StashKey[dict]()
REPO_ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config):
    """Inject before collection and unittest class setup, not only test bodies."""
    session = tempfile.TemporaryDirectory(prefix="spec033-synthetic-")
    root = Path(session.name)
    (root / "synthetic-context.json").write_text(SYNTHETIC_LABEL, encoding="utf-8")
    config.stash[SYNTHETIC_SESSION] = session
    config.stash[PRIOR_SYNTHETIC_ROOT] = os.environ.get("SPEC033_SYNTHETIC_ROOT")
    os.environ["SPEC033_SYNTHETIC_ROOT"] = str(root)
    config.stash[PRODUCTION_LEDGER_MANIFEST] = manifest(REPO_ROOT)


def pytest_unconfigure(config):
    if SYNTHETIC_SESSION not in config.stash:
        return
    previous = config.stash[PRIOR_SYNTHETIC_ROOT]
    if previous is None:
        os.environ.pop("SPEC033_SYNTHETIC_ROOT", None)
    else:
        os.environ["SPEC033_SYNTHETIC_ROOT"] = previous
    config.stash[SYNTHETIC_SESSION].cleanup()
    paths = changed(config.stash[PRODUCTION_LEDGER_MANIFEST], manifest(REPO_ROOT))
    if paths:
        raise RuntimeError("spec043: tests changed docs/trials paths: " + ", ".join(paths))


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    config.stash[COLLECTED_PATHS] = frozenset(item.path.resolve() for item in items)


@pytest.fixture
def collected_test_paths(request):
    return request.config.stash[COLLECTED_PATHS]


@pytest.fixture(autouse=True)
def synthetic_research_context(tmp_path, monkeypatch):
    """Inject labelled isolated recording, including spawned comparison workers."""
    root = tmp_path / "spec033-research"
    root.mkdir()
    (root / "synthetic-context.json").write_text(SYNTHETIC_LABEL, encoding="utf-8")
    monkeypatch.setenv("SPEC033_SYNTHETIC_ROOT", str(root))
