"""Spec 055 U2: one lease per (profile, session); intents persisted before submit.

EXAMPLE — NOT A RESULT.
"""
from datetime import date

import pytest

import context  # noqa: F401
from ops_runtime import LeaseHeld, acquire_lease, client_order_id, complete_lease, open_intents, record_intent

S = date(2026, 10, 8)


def test_second_lease_for_same_key_refuses_before_any_work(tmp_path):
    acquire_lease(tmp_path, "paper_small", S, run_id="run-1")
    with pytest.raises(LeaseHeld, match="paper_small"):
        acquire_lease(tmp_path, "paper_small", S, run_id="run-2")


def test_completed_lease_still_refuses_a_rerun(tmp_path):
    acquire_lease(tmp_path, "paper_small", S, run_id="run-1")
    complete_lease(tmp_path, "paper_small", S, run_id="run-1")
    with pytest.raises(LeaseHeld):
        acquire_lease(tmp_path, "paper_small", S, run_id="run-2")


def test_other_profile_or_session_is_independent(tmp_path):
    acquire_lease(tmp_path, "paper_small", S, run_id="a")
    acquire_lease(tmp_path, "paper_large", S, run_id="b")
    acquire_lease(tmp_path, "paper_small", date(2026, 10, 9), run_id="c")


def test_client_order_id_is_deterministic_per_intent_and_distinct_otherwise():
    first = client_order_id("paper_small", S, "AAA", "buy")
    assert first == client_order_id("paper_small", S, "AAA", "buy")
    others = {client_order_id("paper_large", S, "AAA", "buy"), client_order_id("paper_small", S, "AAA", "sell"),
              client_order_id("paper_small", date(2026, 10, 9), "AAA", "buy"), client_order_id("paper_small", S, "BBB", "buy")}
    assert first not in others and len(others) == 4
    assert len(first) <= 48 and first.isascii()


def test_intent_is_durable_before_submit_and_survives_a_crash(tmp_path):
    cid = client_order_id("paper_small", S, "AAA", "buy")
    record_intent(tmp_path, cid, {"ticker": "AAA", "side": "buy", "qty": 3})
    # simulated crash: nothing else runs; a fresh process reads the same store
    assert [i["client_order_id"] for i in open_intents(tmp_path)] == [cid]


def test_recording_the_same_intent_twice_does_not_duplicate(tmp_path):
    cid = client_order_id("paper_small", S, "AAA", "buy")
    record_intent(tmp_path, cid, {"ticker": "AAA", "side": "buy", "qty": 3})
    record_intent(tmp_path, cid, {"ticker": "AAA", "side": "buy", "qty": 3})
    assert len(open_intents(tmp_path)) == 1
    with pytest.raises(ValueError, match="differs"):
        record_intent(tmp_path, cid, {"ticker": "AAA", "side": "buy", "qty": 4})
