"""Spec 055 U4: the cloud runner wraps a run with due-check, lease, summary and incidents.

Fakes only: the wrapped command is a tiny Python one-liner, never the broker loop. EXAMPLE — NOT A RESULT.
"""
from datetime import datetime
import json
import sys
from zoneinfo import ZoneInfo

import context  # noqa: F401
from ops_runner import main, run_once as _run_once

NY = ZoneInfo("America/New_York")
OK = [sys.executable, "-c", "print('ok')"]
FAIL = [sys.executable, "-c", "import sys; sys.exit(3)"]
SV = "sma10-30@abc123"


def run_once(*args, **kwargs):
    kwargs.setdefault("strategy_version", SV)
    return _run_once(*args, **kwargs)


def incidents(tmp_path):
    path = tmp_path / "ops" / "incidents.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_due_run_executes_once_and_writes_summary(tmp_path):
    now = datetime(2026, 10, 8, 8, 30, tzinfo=NY)
    first = run_once(tmp_path, profile="paper_small", command=OK, now=now)
    assert first["status"] == "completed" and first["exit_code"] == 0
    second = run_once(tmp_path, profile="paper_small", command=OK, now=now)
    assert second["status"] == "done"  # never a second run for the same session
    record = json.loads((tmp_path / "ops" / "runs.jsonl").read_text().splitlines()[0])
    assert record["session"] == "2026-10-08" and record["profile"] == "paper_small"


def test_not_due_does_not_execute(tmp_path):
    saturday = datetime(2026, 10, 10, 8, 30, tzinfo=NY)
    assert run_once(tmp_path, profile="p", command=OK, now=saturday)["status"] == "not_session"
    assert not (tmp_path / "ops" / "runs.jsonl").exists()


def test_failed_command_raises_an_incident_once(tmp_path):
    now = datetime(2026, 10, 8, 8, 30, tzinfo=NY)
    result = run_once(tmp_path, profile="paper_small", command=FAIL, now=now)
    assert result["status"] == "failed" and result["exit_code"] == 3
    incidents = (tmp_path / "ops" / "incidents.jsonl").read_text().splitlines()
    assert len(incidents) == 1 and json.loads(incidents[0])["kind"] == "failure"


def test_missed_sessions_are_reported_as_incidents(tmp_path):
    run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 5, 8, 30, tzinfo=NY))
    run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 8, 8, 30, tzinfo=NY))
    kinds = [json.loads(line) for line in (tmp_path / "ops" / "incidents.jsonl").read_text().splitlines()]
    assert [i["kind"] for i in kinds] == ["missed_run"] and "2026-10-06" in kinds[0]["detail"] and "2026-10-07" in kinds[0]["detail"]


def test_concurrent_worker_holding_the_lease_blocks_execution(tmp_path):
    import pytest
    from datetime import date as _date
    from ops_runtime import LeaseHeld, acquire_lease
    acquire_lease(tmp_path, "paper_small", _date(2026, 10, 8), run_id="other-worker")
    marker = tmp_path / "ran.txt"
    cmd = [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('x')"]
    with pytest.raises(LeaseHeld):
        run_once(tmp_path, profile="paper_small", command=cmd, now=datetime(2026, 10, 8, 8, 30, tzinfo=NY))
    assert not marker.exists()


def test_run_identity_records_strategy_version(tmp_path):
    record = run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 8, 8, 30, tzinfo=NY))
    assert record["strategy_version"] == SV


def test_blank_strategy_version_refuses_before_any_run(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="strategy_version"):
        run_once(tmp_path, profile="p", command=OK, now=datetime(2026, 10, 8, 8, 30, tzinfo=NY), strategy_version=" ")
    assert not (tmp_path / "ops").exists()


def test_after_cutoff_without_a_run_reports_todays_session_missed(tmp_path):
    run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 7, 8, 30, tzinfo=NY))
    result = run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 8, 10, 0, tzinfo=NY))
    assert result["status"] == "after_cutoff"
    assert [i["kind"] for i in incidents(tmp_path)] == ["missed_run"]
    assert "2026-10-08" in incidents(tmp_path)[0]["detail"]


def test_first_ever_invocation_after_cutoff_is_a_missed_run(tmp_path):
    result = run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 8, 10, 0, tzinfo=NY))
    assert result["status"] == "after_cutoff" and result["new_incidents"] == 1
    assert "2026-10-08" in incidents(tmp_path)[0]["detail"]


def test_first_ever_miss_is_reported_on_a_later_due_run(tmp_path):
    run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 7, 7, 0, tzinfo=NY))  # before window
    run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 8, 8, 30, tzinfo=NY))
    assert [i["kind"] for i in incidents(tmp_path)] == ["missed_run"]
    assert "2026-10-07" in incidents(tmp_path)[0]["detail"]


def test_missed_run_alert_is_deduplicated_and_exits_nonzero_once(tmp_path, capsys):
    run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 7, 8, 30, tzinfo=NY))
    argv = ["--state-dir", str(tmp_path), "--profile", "paper_small", "--strategy-version", SV, "--command", "true"]
    import ops_runner
    ops_runner_now = ops_runner._now
    try:
        ops_runner._now = lambda: datetime(2026, 10, 8, 10, 0, tzinfo=NY)
        assert main(argv) == 1  # new missed_run incident: the workflow's failure() alert fires
        assert main(argv) == 0  # same incident: deduplicated, no second alert
    finally:
        ops_runner._now = ops_runner_now
    assert len(incidents(tmp_path)) == 1
