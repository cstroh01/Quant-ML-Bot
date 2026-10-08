"""Spec 055 U3: daily summary and deduplicated incident alerts. EXAMPLE — NOT A RESULT."""
from datetime import date

import context  # noqa: F401
from ops_runtime import Incident, daily_summary, incidents_to_send

S = date(2026, 10, 8)


def run(**extra):
    base = dict(profile="paper_small", session=S, data_session=date(2026, 10, 7), model="sma_10_30",
                orders={"filled": 3, "unknown": 1}, open_reservations=2, position_differences={"AAA": 1.0})
    return base | extra


def test_summary_names_every_required_field_and_next_action():
    text = daily_summary(run())
    for needle in ("paper_small", "2026-10-08", "2026-10-07", "sma_10_30", "filled: 3", "unknown: 1",
                   "Open reservations: 2", "AAA: 1.0", "Next action:", "Not a performance result"):
        assert needle in text, needle


def test_clean_run_says_no_action_needed():
    text = daily_summary(run(orders={"filled": 2}, open_reservations=0, position_differences={}))
    assert "Next action: none" in text


def test_new_incident_is_sent_and_identical_repeat_is_not():
    sent = {}
    first = incidents_to_send([Incident("missed_run", "paper_small", "2026-10-06 missed")], sent)
    assert [i.kind for i in first] == ["missed_run"]
    assert incidents_to_send([Incident("missed_run", "paper_small", "2026-10-06 missed")], sent) == []


def test_changed_incident_is_sent_again():
    sent = {}
    incidents_to_send([Incident("reconciliation", "paper_small", "1 mismatch")], sent)
    again = incidents_to_send([Incident("reconciliation", "paper_small", "2 mismatches")], sent)
    assert [i.detail for i in again] == ["2 mismatches"]


def test_incidents_for_different_profiles_are_independent():
    sent = {}
    incidents_to_send([Incident("halt", "paper_small", "kill")], sent)
    assert len(incidents_to_send([Incident("halt", "paper_large", "kill")], sent)) == 1


def test_unknown_orders_alone_require_an_operator_action():
    text = daily_summary(run(orders={"filled": 2, "unknown": 1}, open_reservations=1, position_differences={}))
    assert "Next action: check UNKNOWN orders at the broker" in text
