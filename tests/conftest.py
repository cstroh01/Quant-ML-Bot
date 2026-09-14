"""Retain actual collection evidence before -k/-m deselection for suite guards."""

from pathlib import Path

import pytest


COLLECTED_PATHS = pytest.StashKey[frozenset[Path]]()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    config.stash[COLLECTED_PATHS] = frozenset(item.path.resolve() for item in items)


@pytest.fixture
def collected_test_paths(request):
    return request.config.stash[COLLECTED_PATHS]
