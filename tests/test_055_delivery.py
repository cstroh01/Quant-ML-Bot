"""Spec 055 F02b: state persisted before the broker command; summaries and incidents delivered reliably.

Fakes only: the "broker command" and "persist command" are tiny Python one-liners; the poster is a
recording fake. No network, no GitHub call. EXAMPLE — NOT A RESULT.
"""
from datetime import date, datetime
import json
import sys
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401
from ops_deliver import deliver
from ops_runner import run_once
from ops_runtime import summary_from_loop_record

NY = ZoneInfo("America/New_York")
DUE = datetime(2026, 10, 8, 8, 30, tzinfo=NY)


def marker_cmd(path, code=0):
    return [sys.executable, "-c", f"open({str(path)!r}, 'w').write('x'); raise SystemExit({code})"]


def persist_cmd(log, code=0):
    """Records what state existed at persist time (the lease must already be there)."""
    script = ("import sys, pathlib, json; d = pathlib.Path(sys.argv[1]);"
              f"open({str(log)!r}, 'a').write(json.dumps(sorted(p.name for p in (d / 'leases').glob('*'))) + '\\n');"
              f"raise SystemExit({code})")
    return [sys.executable, "-c", script]


def go(tmp_path, command, persist=None, run_log=None, now=DUE):
    persist_command = None if persist is None else persist + [str(tmp_path)]
    return run_once(tmp_path, profile="paper_small", command=command, now=now, strategy_version="v1",
                    persist_command=persist_command, run_log=run_log)


def outbox(tmp_path):
    return sorted((tmp_path / "ops" / "outbox").glob("*.json"))


def test_lease_is_persisted_before_the_broker_command_runs(tmp_path):
    log, ran = tmp_path / "persist.log", tmp_path / "ran.txt"
    result = go(tmp_path, marker_cmd(ran), persist=persist_cmd(log))
    assert result["status"] == "completed" and ran.exists()
    assert json.loads(log.read_text().splitlines()[0]) == ["paper_small-2026-10-08.json"]


def test_failed_persist_never_runs_the_broker_and_releases_the_lease(tmp_path):
    log, ran = tmp_path / "persist.log", tmp_path / "ran.txt"
    result = go(tmp_path, marker_cmd(ran), persist=persist_cmd(log, code=2))
    assert result["status"] == "persist_failed" and not ran.exists()
    assert not list((tmp_path / "leases").glob("*"))  # nothing durable happened, so a retry is safe
    kinds = [json.loads(p.read_text())["kind"] for p in outbox(tmp_path)]
    assert "incident" in kinds


def test_summary_from_the_loop_record_counts_outcomes_and_open_reservations():
    record = {"session": "2026-10-08", "actions": [{"outcome": "SUBMITTED"}, {"outcome": "UNKNOWN"},
                                                  {"outcome": "BUDGET_REFUSED"}],
              "reconciliation": [{"client_order_id": "a", "broker_status": "FILLED"},
                                 {"client_order_id": "b", "broker_status": "ACCEPTED"}]}
    text = summary_from_loop_record(record, profile="paper_small", session=date(2026, 10, 8), model="v1")
    for needle in ("submitted: 1", "unknown: 1", "budget_refused: 1", "Open reservations: 1",
                   "check UNKNOWN orders", "Data session: not reported", "Not a performance result"):
        assert needle in text, needle


def test_aborted_loop_record_says_so_in_the_next_action():
    text = summary_from_loop_record({"aborted": "market is open"}, profile="p", session=date(2026, 10, 8), model="v1")
    assert "aborted: market is open" in text


def test_every_executed_run_queues_exactly_one_summary(tmp_path):
    run_log = tmp_path / "loop.jsonl"
    run_log.write_text(json.dumps({"session": "2026-10-08", "actions": [{"outcome": "SUBMITTED"}]}) + "\n")
    go(tmp_path, marker_cmd(tmp_path / "ran"), run_log=run_log)
    summaries = [json.loads(p.read_text()) for p in outbox(tmp_path) if json.loads(p.read_text())["kind"] == "summary"]
    assert len(summaries) == 1 and "submitted: 1" in summaries[0]["body"]
    assert summaries[0]["title"] == "paper-loop daily summary"


def test_missing_run_log_still_queues_a_summary_that_says_so(tmp_path):
    go(tmp_path, marker_cmd(tmp_path / "ran"), run_log=tmp_path / "absent.jsonl")
    bodies = [json.loads(p.read_text())["body"] for p in outbox(tmp_path)]
    assert any("loop record missing" in b for b in bodies)


class Poster:
    def __init__(self, fail_titles=()):
        self.sent, self.fail_titles = [], set(fail_titles)

    def __call__(self, kind, title, body):
        if title in self.fail_titles:
            raise RuntimeError("gh unavailable")
        self.sent.append((kind, title))


def test_delivery_moves_only_successfully_posted_items(tmp_path):
    go(tmp_path, marker_cmd(tmp_path / "ran", code=3), run_log=tmp_path / "absent.jsonl")  # failure incident + summary
    items = outbox(tmp_path)
    assert len(items) == 2
    incident_title = next(json.loads(p.read_text())["title"] for p in items if "incident" in p.name)
    poster = Poster(fail_titles={incident_title})
    delivered, failed = deliver(tmp_path, poster)
    assert (delivered, failed) == (1, 1)
    assert [json.loads(p.read_text())["kind"] for p in outbox(tmp_path)] == ["incident"]  # kept for retry
    delivered, failed = deliver(tmp_path, Poster())
    assert (delivered, failed) == (1, 0) and outbox(tmp_path) == []
    assert len(list((tmp_path / "ops" / "delivered").glob("*.json"))) == 2


def test_redelivery_never_duplicates_a_posted_item(tmp_path):
    go(tmp_path, marker_cmd(tmp_path / "ran"), run_log=tmp_path / "absent.jsonl")
    poster = Poster()
    deliver(tmp_path, poster)
    deliver(tmp_path, poster)
    assert len(poster.sent) == 1


def test_a_corrupt_outbox_item_is_reported_not_silently_dropped(tmp_path):
    box = tmp_path / "ops" / "outbox"
    box.mkdir(parents=True)
    (box / "incident-bad.json").write_text("{not json")
    delivered, failed = deliver(tmp_path, Poster())
    assert (delivered, failed) == (0, 1) and (box / "incident-bad.json").exists()


@pytest.mark.parametrize("status_now", [datetime(2026, 10, 8, 10, 0, tzinfo=NY)])
def test_incidents_on_non_due_invocations_are_queued_too(tmp_path, status_now):
    result = go(tmp_path, marker_cmd(tmp_path / "ran"), now=status_now)  # first-ever, after cutoff: missed run
    assert result["status"] == "after_cutoff"
    assert [json.loads(p.read_text())["kind"] for p in outbox(tmp_path)] == ["incident"]
