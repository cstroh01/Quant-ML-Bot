"""Spec 055 F03: storage identifiers can't alias another profile's state on the consuming paths.

Path resolution only: no broker, no DB writes. EXAMPLE — NOT A RESULT.
"""
import copy
import os
from datetime import date, datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

import paper_loop  # noqa: E402
from mode_config import load_profiles  # noqa: E402
from mode_fixtures import raw  # noqa: E402
from ops_runner import run_once  # noqa: E402
from ops_runtime import acquire_lease  # noqa: E402

LARGE = load_profiles([raw("paper_large", account="PA-2")])["paper_large"]
SMALL = load_profiles([raw()])["paper_small"]


def corrupted(profile, **fields):
    """A copy of a VALID profile with fields overwritten after construction.

    Spec 051 (#95) refuses these values when a profile is built; this helper bypasses that on
    purpose so the consumer under test (``state_paths``) actually receives the invalid identifier.
    """
    clone = copy.copy(profile)
    for name, value in fields.items():
        object.__setattr__(clone, name, value)
    return clone


def test_corrupted_helper_changes_only_the_named_field():
    clone = corrupted(SMALL, log_namespace="x/y")
    assert clone.log_namespace == "x/y" and SMALL.log_namespace == "paper_small"
    assert {k: v for k, v in vars(clone).items() if k != "log_namespace"} == \
        {k: v for k, v in vars(SMALL).items() if k != "log_namespace"}


def test_codex_alias_namespace_is_refused_by_the_consuming_state_paths():
    alias = corrupted(SMALL, log_namespace="paper_small/../paper_large")  # field-causal: only this differs
    with pytest.raises(paper_loop.RunAborted, match="log_namespace"):
        paper_loop.state_paths(alias)
    gate_s, log_s = paper_loop.state_paths(SMALL)  # sibling control
    gate_l, log_l = paper_loop.state_paths(LARGE)
    assert gate_s.resolve() != gate_l.resolve() and log_s.resolve() != log_l.resolve()
    assert gate_s.resolve().parent.parent == gate_l.resolve().parent.parent  # both directly under live_safety


@pytest.mark.parametrize("namespace", ["a/b", "a\\b", "..", ".", "/abs", "C:x", "ns.", "ns ", "Paper_Small",
                                       "con", "LPT1", ""])
def test_any_non_identifier_namespace_is_refused(namespace):
    with pytest.raises(paper_loop.RunAborted, match="log_namespace"):
        paper_loop.state_paths(corrupted(SMALL, log_namespace=namespace))


BAD_PROFILES = ["paper_small/../paper_large", "../x", "a/b", "Paper", "nul"]


@pytest.mark.parametrize("profile", BAD_PROFILES)
def test_lease_refuses_non_identifier_profiles(tmp_path, profile):
    with pytest.raises(ValueError, match="storage identifier"):
        acquire_lease(tmp_path, profile, date(2026, 10, 8), run_id="r")


@pytest.mark.parametrize("profile", BAD_PROFILES)
def test_runner_refuses_non_identifier_profiles(tmp_path, profile):
    with pytest.raises(ValueError, match="storage identifier"):
        run_once(tmp_path, profile=profile, command=["true"], strategy_version="v1",  # after cutoff: no lease path,
                 now=datetime(2026, 10, 8, 10, 0, tzinfo=ZoneInfo("America/New_York")))  # so only the runner's check can refuse
    assert not (tmp_path / "leases").exists() or not any((tmp_path / "leases").iterdir())


def test_valid_profile_lease_control(tmp_path):
    acquire_lease(tmp_path, "paper_small", date(2026, 10, 8), run_id="r")
    assert [p.name for p in (tmp_path / "leases").iterdir()] == ["paper_small-2026-10-08.json"]


def make_dir_link(link, target):
    """A directory symlink, or an NTFS junction where Windows refuses unprivileged symlinks."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        if os.name != "nt":
            pytest.skip("directory links unavailable on this filesystem")
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
        return "junction"


@pytest.fixture
def temp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_loop, "ROOT", tmp_path)
    live = tmp_path / "data" / "live_safety"
    live.mkdir(parents=True)
    return live


def test_profile_dir_redirected_to_a_sibling_is_refused(temp_root):
    (temp_root / "paper_large").mkdir()
    make_dir_link(temp_root / "paper_small", temp_root / "paper_large")
    with pytest.raises(paper_loop.RunAborted, match="log_namespace resolves to"):
        paper_loop.state_paths(SMALL)
    paper_loop.state_paths(LARGE)  # the real sibling itself is still accepted


def test_real_sibling_dirs_are_accepted_and_distinct(temp_root):
    for name in ("paper_small", "paper_large"):
        (temp_root / name).mkdir()
    small, large = paper_loop.state_paths(SMALL), paper_loop.state_paths(LARGE)
    assert {p.resolve() for p in small}.isdisjoint({p.resolve() for p in large})


def test_a_linked_live_safety_root_like_the_workflow_is_accepted(tmp_path, monkeypatch):
    state = tmp_path / "state" / "live_safety"
    state.mkdir(parents=True)
    (tmp_path / "repo" / "data").mkdir(parents=True)
    make_dir_link(tmp_path / "repo" / "data" / "live_safety", state)  # paper-loop.yml links data/live_safety
    monkeypatch.setattr(paper_loop, "ROOT", tmp_path / "repo")
    gate, runs = paper_loop.state_paths(SMALL)
    assert gate.resolve().parent == (state / "paper_small").resolve()
