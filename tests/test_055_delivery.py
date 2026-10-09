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
from ops_deliver import deliver
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


# --- Codex follow-up: current-invocation record only; data session carried; private-repo target ---

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


def test_gh_poster_always_targets_the_given_repository(monkeypatch):
    import ops_deliver
    seen = []

    class Done:
        stdout = "[]"

    monkeypatch.setattr(ops_deliver.subprocess, "run", lambda args, **_k: (seen.append(args), Done())[1])
    poster = ops_deliver.gh_poster("cstroh01/Quant-ML-Bot-private")
    poster("summary", "paper-loop daily summary", "body")
    poster("incident", "[p] failure", "body")
    assert seen and all(a[:3] == ["gh", "-R", "cstroh01/Quant-ML-Bot-private"] for a in seen)


def test_deliver_cli_requires_an_explicit_repository():
    import ops_deliver
    with pytest.raises(SystemExit):
        ops_deliver.main(["--state-dir", "x"])


def test_workflow_delivery_and_failure_backstop_target_the_running_private_repo():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "ops" / "workflows" / "paper-loop.yml").read_text()
    deliver_line = next(line for line in text.splitlines() if "scripts/ops_deliver.py" in line)
    assert '--repo "${{ github.repository }}"' in deliver_line
    backstop = text[text.index("Open incident issue on failure"):]
    assert 'gh issue create -R "${{ github.repository }}"' in backstop
