"""Spec 055 (hosted Part B): a dry-run preview never consumes the session lease.

Fakes only: the wrapped command is a tiny Python one-liner, never the broker loop. EXAMPLE — NOT A RESULT.
"""
from datetime import datetime
import json
import sys
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401
from ops_runner import main, preview_once, run_once, set_kill

NY = ZoneInfo("America/New_York")
OK = [sys.executable, "-c", "print('ok')"]
SV = "alloc@abc123"
NOW = datetime(2026, 10, 19, 8, 0, tzinfo=NY)


def test_preview_takes_no_lease_and_the_submit_run_still_runs(tmp_path):
    preview = preview_once(tmp_path, profile="paper_small", command=OK, now=NOW, strategy_version=SV)
    assert preview["status"] == "previewed", f"Part B preview {preview}"
    assert not (tmp_path / "leases" / "paper_small-2026-10-19.json").exists(), "a preview must not take the session lease"
    assert not (tmp_path / "ops" / "runs.jsonl").exists(), "a preview must not count as a completed run"
    real = run_once(tmp_path, profile="paper_small", command=OK, now=NOW, strategy_version=SV)
    assert real["status"] == "completed", f"the real run after a preview was blocked: {real}"
    row = json.loads((tmp_path / "ops" / "previews.jsonl").read_text().splitlines()[0])
    assert row["mode"] == "preview" and row["session"] == "2026-10-19", f"preview record {row}"


def test_preview_refuses_a_command_that_may_submit(tmp_path):
    with pytest.raises(ValueError, match="may submit"):
        preview_once(tmp_path, profile="p", command=["python", "exec/paper_loop.py", "--submit"], now=NOW,
                     strategy_version=SV)
    with pytest.raises(SystemExit):
        main(["--state-dir", str(tmp_path), "--profile", "p", "--strategy-version", SV, "--preview",
              "--command", "python exec/paper_loop.py --sub"])


def test_preview_honours_the_kill(tmp_path):
    set_kill(tmp_path, "paper_small", reason="drill", now=NOW)
    result = preview_once(tmp_path, profile="paper_small", command=OK, now=NOW, strategy_version=SV)
    assert result["status"] == "killed" and not (tmp_path / "ops" / "previews.jsonl").exists(), f"kill ignored {result}"


def test_preview_after_the_session_ran_does_nothing(tmp_path):
    run_once(tmp_path, profile="paper_small", command=OK, now=NOW, strategy_version=SV)
    assert preview_once(tmp_path, profile="paper_small", command=OK, now=NOW, strategy_version=SV)["status"] == "done"
