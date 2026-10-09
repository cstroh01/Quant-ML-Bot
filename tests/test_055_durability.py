"""Spec 055 F02a: leases, intents and runner state survive a crash mid-write. EXAMPLE — NOT A RESULT."""
from datetime import date, datetime
import json
import sys
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401
import ops_runtime
from ops_runtime import (IntentLogCorrupt, LeaseHeld, acquire_lease, complete_lease, open_intents,
                         record_intent)
from ops_runner import run_once

S = date(2026, 10, 8)
NY = ZoneInfo("America/New_York")
OK = [sys.executable, "-c", "print('ok')"]


def lease_file(tmp_path):
    return tmp_path / "leases" / f"paper_small-{S.isoformat()}.json"


def test_a_lease_torn_before_its_content_was_written_still_blocks(tmp_path):
    path = lease_file(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")  # crash between O_EXCL create and the JSON write
    with pytest.raises(LeaseHeld):
        acquire_lease(tmp_path, "paper_small", S, run_id="next")
    with pytest.raises(LeaseHeld, match="unreadable"):
        complete_lease(tmp_path, "paper_small", S, run_id="next")


def test_complete_lease_is_an_atomic_replace(tmp_path, monkeypatch):
    acquire_lease(tmp_path, "paper_small", S, run_id="r1")
    calls = []
    real = ops_runtime.os.replace
    monkeypatch.setattr(ops_runtime.os, "replace", lambda a, b: (calls.append((a, b)), real(a, b)))
    complete_lease(tmp_path, "paper_small", S, run_id="r1")
    assert calls and str(calls[0][1]).endswith(lease_file(tmp_path).name)
    assert json.loads(lease_file(tmp_path).read_text())["state"] == "completed"


@pytest.mark.parametrize("tail", ['{"client_order_id": "qmb-1", "intent": {"q', "not json\n",
                                  '{"client_order_id": "qmb-1", "intent": {}}'])  # last: cut exactly at the newline
def test_torn_or_corrupt_intent_log_refuses_reads_and_new_intents(tmp_path, tail):
    record_intent(tmp_path, "qmb-0", {"symbol": "AAA", "qty": 1})
    with (tmp_path / "intents.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(tail)
    with pytest.raises(IntentLogCorrupt):
        open_intents(tmp_path)
    with pytest.raises(IntentLogCorrupt):
        record_intent(tmp_path, "qmb-2", {"symbol": "BBB", "qty": 1})


def test_clean_intent_log_still_round_trips(tmp_path):
    record_intent(tmp_path, "qmb-0", {"symbol": "AAA", "qty": 1})
    record_intent(tmp_path, "qmb-0", {"symbol": "AAA", "qty": 1})  # identical re-record is a no-op
    assert [r["client_order_id"] for r in open_intents(tmp_path)] == ["qmb-0"]


def test_a_lease_left_running_by_a_crashed_run_is_an_incident_not_a_rerun(tmp_path):
    acquire_lease(tmp_path, "paper_small", S, run_id="crashed")
    marker = tmp_path / "ran.txt"
    cmd = [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('x')"]
    result = run_once(tmp_path, profile="paper_small", command=cmd, now=datetime(2026, 10, 8, 8, 30, tzinfo=NY),
                      strategy_version="v1")
    assert result["status"] == "lease_held" and result["new_incidents"] == 1 and not marker.exists()
    incident = json.loads((tmp_path / "ops" / "incidents.jsonl").read_text().splitlines()[-1])
    assert incident["kind"] == "lease_held" and "reconcile" in incident["detail"]


def test_runner_state_files_are_written_atomically(tmp_path, monkeypatch):
    replaced = []
    real = ops_runtime.os.replace
    monkeypatch.setattr(ops_runtime.os, "replace", lambda a, b: (replaced.append(str(b)), real(a, b)))
    run_once(tmp_path, profile="paper_small", command=OK, now=datetime(2026, 10, 8, 10, 0, tzinfo=NY),
             strategy_version="v1")  # after cutoff: writes first_seen and sent
    names = {p.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] for p in replaced}
    assert {"first_seen.json", "sent.json"} <= names
