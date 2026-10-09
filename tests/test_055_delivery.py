"""Spec 055 F02b: summaries and incidents queued and delivered reliably (F02b1/F02b2 of the split).

Fakes only: the "broker command" is a tiny Python one-liner; the poster is a recording fake.
No network, no GitHub call. EXAMPLE — NOT A RESULT.
"""
from datetime import date, datetime
import json
import sys
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401
from ops_runner import run_once
from ops_runtime import summary_from_loop_record

NY = ZoneInfo("America/New_York")
DUE = datetime(2026, 10, 8, 8, 30, tzinfo=NY)


def marker_cmd(path, code=0):
    return [sys.executable, "-c", f"open({str(path)!r}, 'w').write('x'); raise SystemExit({code})"]


def go(tmp_path, command, run_log=None, now=DUE):
    return run_once(tmp_path, profile="paper_small", command=command, now=now, strategy_version="v1",
                    run_log=run_log)


def outbox(tmp_path):
    return sorted((tmp_path / "ops" / "outbox").glob("*.json"))


def test_summary_from_the_loop_record_counts_outcomes_and_open_reservations():
    record = {"session": "2026-10-08", "actions": [{"outcome": "SUBMITTED"}, {"outcome": "UNKNOWN"},
                                                  {"outcome": "BUDGET_REFUSED"}],
              "reconciliation": [{"client_order_id": "a", "broker_status": "FILLED"},
                                 {"client_order_id": "b", "broker_status": "ACCEPTED"}]}
    text = summary_from_loop_record(record, profile="paper_small", session=date(2026, 10, 8), model="v1")
    for needle in ("submitted: 1", "unknown: 1", "budget_refused: 1", "Open reservations: 1",
                   "check UNKNOWN orders", "Data session: 2026-10-08", "Not a performance result"):
        assert needle in text, needle


def test_aborted_loop_record_says_so_in_the_next_action():
    text = summary_from_loop_record({"aborted": "market is open"}, profile="p", session=date(2026, 10, 8), model="v1")
    assert "aborted: market is open" in text


def test_every_executed_run_queues_exactly_one_summary(tmp_path):
    run_log = tmp_path / "loop.jsonl"
    go(tmp_path, append_cmd(run_log, {"session": "2026-10-07", "actions": [{"outcome": "SUBMITTED"}]}), run_log=run_log)
    summaries = [json.loads(p.read_text()) for p in outbox(tmp_path) if json.loads(p.read_text())["kind"] == "summary"]
    assert len(summaries) == 1 and "submitted: 1" in summaries[0]["body"]
    assert summaries[0]["title"] == "paper-loop daily summary"


def test_missing_run_log_still_queues_a_summary_that_says_so(tmp_path):
    go(tmp_path, marker_cmd(tmp_path / "ran"), run_log=tmp_path / "absent.jsonl")
    bodies = [json.loads(p.read_text())["body"] for p in outbox(tmp_path)]
    assert any("loop record missing" in b for b in bodies)


@pytest.mark.parametrize("status_now", [datetime(2026, 10, 8, 10, 0, tzinfo=NY)])
def test_incidents_on_non_due_invocations_are_queued_too(tmp_path, status_now):
    result = go(tmp_path, marker_cmd(tmp_path / "ran"), now=status_now)  # first-ever, after cutoff: missed run
    assert result["status"] == "after_cutoff"
    assert [json.loads(p.read_text())["kind"] for p in outbox(tmp_path)] == ["incident"]


# --- Codex follow-up: current-invocation record only; data session carried ---

def append_cmd(log, record):
    line = json.dumps(record)
    return [sys.executable, "-c", f"open({str(log)!r}, 'a').write({line!r} + '\\n')"]


def summary_body(tmp_path):
    return next(json.loads(p.read_text())["body"] for p in outbox(tmp_path) if "summary" in p.name)


def test_a_stale_record_from_yesterday_is_never_reported_as_todays_run(tmp_path):
    log = tmp_path / "loop.jsonl"
    log.write_text(json.dumps({"session": "2026-10-06", "actions": [{"outcome": "SUBMITTED"}]}) + "\n")
    go(tmp_path, [sys.executable, "-c", "raise SystemExit(4)"], run_log=log)  # exits before appending
    body = summary_body(tmp_path)
    assert "loop record missing" in body and "submitted" not in body


def test_the_newly_appended_record_is_reported_with_its_data_session(tmp_path):
    log = tmp_path / "loop.jsonl"
    log.write_text(json.dumps({"session": "2026-10-06", "actions": [{"outcome": "DENIED"}]}) + "\n")  # control: old line
    go(tmp_path, append_cmd(log, {"session": "2026-10-07", "profile": "paper_small",
                                  "actions": [{"outcome": "SUBMITTED"}]}), run_log=log)
    body = summary_body(tmp_path)
    assert "submitted: 1" in body and "denied" not in body
    assert "Data session: 2026-10-07" in body


def test_a_record_for_another_profile_is_not_this_runs_record(tmp_path):
    log = tmp_path / "loop.jsonl"
    go(tmp_path, append_cmd(log, {"session": "2026-10-07", "profile": "paper_large", "actions": []}), run_log=log)
    assert "loop record missing" in summary_body(tmp_path)

