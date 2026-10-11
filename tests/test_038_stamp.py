"""Spec 038 T020 (FR-002): the provenance stamp contract.

EXAMPLE — NOT A RESULT. Synthetic trees under tmp_path; no Git, no socket, no cache.
Witness strings ("038 STAMP ...") let the T022 driver count a kill.
"""
from datetime import date, datetime, timedelta, timezone
import hashlib
import os
import socket
import subprocess
import time

import pandas as pd
import pytest

from context import SCRIPTS_DIR  # noqa: F401  (puts scripts/ on sys.path)
import disclosure

SHA_A = "a" * 40
SHA_B = "b" * 40
BODY = b"session,close\n2024-03-08,1.0\n"


def tree(tmp_path, sha=SHA_A):
    (tmp_path / ".git" / "refs" / "heads").mkdir(parents=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / ".git" / "refs" / "heads" / "main").write_text(sha + "\n")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "sample.csv").write_bytes(BODY)
    return tmp_path


def at(*args, tz=timezone.utc):
    return lambda: datetime(*args, tzinfo=tz)


@pytest.fixture(autouse=True)
def no_github_sha(monkeypatch):
    # source_identity prefers GITHUB_SHA (trial_registry.source_identity); CI sets it.
    monkeypatch.delenv("GITHUB_SHA", raising=False)


def line(stamp, prefix):
    return next((x for x in stamp if x.startswith(prefix)), None)


def test_descriptive_stamp_lines_exactly(tmp_path):
    root = tree(tmp_path)
    stamp = disclosure.provenance_stamp("artifacts/sample.csv", root=root, clock=at(2024, 3, 10, 2, 0))
    assert stamp == [
        f"source: artifacts/sample.csv sha256={hashlib.sha256(BODY).hexdigest()}",
        f"commit: {SHA_A}",
        "workspace: unknown",
        "trial: none (descriptive, not a trial)",
        "run (UTC): 2024-03-10 02:00:00Z",
    ], "038 STAMP lines"


def test_model_and_descriptive_stamps_differ_only_in_trial(tmp_path):
    root = tree(tmp_path)
    kw = dict(root=root, clock=at(2024, 3, 10, 2, 0))
    model = disclosure.provenance_stamp("artifacts/sample.csv", trial_id="trial-7", **kw)
    plain = disclosure.provenance_stamp("artifacts/sample.csv", **kw)
    assert [(m, p) for m, p in zip(model, plain) if m != p] == [
        ("trial: trial-7", "trial: none (descriptive, not a trial)")], "038 STAMP trial"


def test_workspace_state_is_passed_through(tmp_path):
    stamp = disclosure.provenance_stamp("artifacts/sample.csv", root=tree(tmp_path), clock=at(2024, 3, 10), workspace_state="dirty")
    assert line(stamp, "workspace:") == "workspace: dirty", "038 STAMP workspace"


def test_commit_is_unknown_without_readable_git(tmp_path):
    root = tree(tmp_path)
    (root / ".git" / "refs" / "heads" / "main").write_text("not-a-sha\n")
    stamp = disclosure.provenance_stamp("artifacts/sample.csv", root=root, clock=at(2024, 3, 10))
    assert line(stamp, "commit:") == "commit: unknown", "038 STAMP unknown commit"


def test_commit_is_read_fresh_after_head_moves(tmp_path):
    # M2: a stamp that caches the first commit would repeat SHA_A.
    root = tree(tmp_path)
    first = disclosure.provenance_stamp("artifacts/sample.csv", root=root, clock=at(2024, 3, 10))
    (root / ".git" / "refs" / "heads" / "main").write_text(SHA_B + "\n")
    second = disclosure.provenance_stamp("artifacts/sample.csv", root=root, clock=at(2024, 3, 10))
    assert [line(first, "commit:"), line(second, "commit:")] == [
        f"commit: {SHA_A}", f"commit: {SHA_B}"], "038 STAMP M2 stale commit"


@pytest.mark.parametrize("end", [date(2024, 3, 8), datetime(2024, 3, 8), pd.Timestamp("2024-03-08")])
def test_run_time_is_the_clock_and_last_session_is_separate(tmp_path, end):
    # M3: the run date must not be taken from the data's last bar (Fri 2024-03-08).
    root = tree(tmp_path)
    stamp = disclosure.provenance_stamp("artifacts/sample.csv", root=root, clock=at(2024, 3, 11, 12, 0), data_end=end)
    assert stamp[-2:] == ["run (UTC): 2024-03-11 12:00:00Z", "data through (last session): 2024-03-08"], "038 STAMP M3 run date"


@pytest.mark.parametrize("clock, expected", [
    (at(2024, 3, 9, 21, 0, tz=timezone(timedelta(hours=-5))), "2024-03-10 02:00:00Z"),  # UTC-5 evening
    (at(2024, 3, 9, 23, 30), "2024-03-09 23:30:00Z"),  # just before UTC midnight
])
def test_run_date_is_the_utc_date_either_side_of_midnight(tmp_path, clock, expected):
    stamp = disclosure.provenance_stamp("artifacts/sample.csv", root=tree(tmp_path), clock=clock)
    assert line(stamp, "run (UTC):") == f"run (UTC): {expected}", "038 STAMP M3b midnight"


@pytest.fixture
def new_york(monkeypatch):
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is unavailable on Windows; test_offset_clock_is_converted_to_utc_date covers the conversion")
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.parametrize("hour", [2, 12])
def test_run_date_is_utc_under_a_new_york_local_zone(tmp_path, new_york, hour):
    # M3b: at 02:00Z the New York date is still Mar 9; at 12:00Z (control) both agree.
    root = tree(tmp_path)
    stamp = disclosure.provenance_stamp("artifacts/sample.csv", root=root, clock=at(2024, 3, 10, hour, 0))
    assert line(stamp, "run (UTC):") == f"run (UTC): 2024-03-10 {hour:02d}:00:00Z", "038 STAMP M3b local zone"


@pytest.mark.parametrize("change, error", [
    (dict(clock=lambda: datetime(2024, 3, 10, 2, 0)), ValueError),
    (dict(data_end=pd.Timestamp("2024-03-08", tz="UTC")), ValueError),
    (dict(data_end=datetime(2024, 3, 8, 16, 0)), ValueError),
    (dict(data_end=pd.Timestamp("2024-03-08") + pd.Timedelta(1, "ns")), ValueError),
    (dict(data_end=date(2024, 3, 11)), ValueError),  # last session after the 2024-03-10 run
    (dict(trial_id=" "), ValueError),
    (dict(source="../outside.csv"), ValueError),
    (dict(source="artifacts/missing.csv"), FileNotFoundError),
])
def test_refusals(tmp_path, change, error):
    root = tree(tmp_path / "repo")
    (tmp_path / "outside.csv").write_bytes(BODY)
    kw = dict(source="artifacts/sample.csv", root=root, clock=at(2024, 3, 10, 2, 0)) | change
    with pytest.raises(error):
        disclosure.provenance_stamp(kw.pop("source"), **kw)


def test_stamp_runs_no_git_and_opens_no_socket(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("038 STAMP spawned a process or opened a socket")
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(os, "system", refuse)
    stamp = disclosure.provenance_stamp("artifacts/sample.csv", root=tree(tmp_path), clock=at(2024, 3, 10))
    assert line(stamp, "commit:") == f"commit: {SHA_A}", "038 STAMP offline"
