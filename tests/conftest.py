"""Retain actual collection evidence before -k/-m deselection for suite guards."""

from pathlib import Path
import os
import tempfile

import pytest


COLLECTED_PATHS = pytest.StashKey[frozenset[Path]]()
SYNTHETIC_SESSION = pytest.StashKey[object]()
PRIOR_SYNTHETIC_ROOT = pytest.StashKey[object]()
PRODUCTION_LEDGER_BYTES = pytest.StashKey[bytes]()


def pytest_configure(config):
    """Inject before collection and unittest class setup, not only test bodies."""
    session = tempfile.TemporaryDirectory(prefix="spec033-synthetic-")
    root = Path(session.name)
    (root / "synthetic-context.json").write_text("EXAMPLE — NOT A RESULT", encoding="utf-8")
    config.stash[SYNTHETIC_SESSION] = session
    config.stash[PRIOR_SYNTHETIC_ROOT] = os.environ.get("SPEC033_SYNTHETIC_ROOT")
    os.environ["SPEC033_SYNTHETIC_ROOT"] = str(root)
    path = Path(__file__).resolve().parents[1] / "docs/trials/trials.jsonl"
    config.stash[PRODUCTION_LEDGER_BYTES] = path.read_bytes() if path.exists() else b""


def pytest_unconfigure(config):
    if SYNTHETIC_SESSION not in config.stash:
        return
    previous = config.stash[PRIOR_SYNTHETIC_ROOT]
    if previous is None:
        os.environ.pop("SPEC033_SYNTHETIC_ROOT", None)
    else:
        os.environ["SPEC033_SYNTHETIC_ROOT"] = previous
    config.stash[SYNTHETIC_SESSION].cleanup()
    path = Path(__file__).resolve().parents[1] / "docs/trials/trials.jsonl"
    current = path.read_bytes() if path.exists() else b""
    if current != config.stash[PRODUCTION_LEDGER_BYTES]:
        raise RuntimeError("spec033: tests changed the production lifetime ledger")


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
    (root / "synthetic-context.json").write_text("EXAMPLE — NOT A RESULT", encoding="utf-8")
    monkeypatch.setenv("SPEC033_SYNTHETIC_ROOT", str(root))
