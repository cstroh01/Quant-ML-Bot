"""Spec 055 U1: due-run calendar and missed-run detection. EXAMPLE — NOT A RESULT."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import context  # noqa: F401
from ops_runtime import due_run, missed_sessions

NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def at(y, m, d, hh, mm, tz=UTC):
    return datetime(y, m, d, hh, mm, tzinfo=tz)


def test_summer_and_winter_crons_resolve_through_new_york_time():
    # 12:00 UTC is 08:00 EDT (due) in October but 07:00 EST (too early) in December.
    assert due_run(at(2026, 10, 8, 12, 0), profile="paper_small", completed=set()).status == "due"
    assert due_run(at(2026, 12, 8, 12, 0), profile="paper_small", completed=set()).status == "before_window"
    assert due_run(at(2026, 12, 8, 13, 0), profile="paper_small", completed=set()).status == "due"


def test_dst_switch_day_uses_the_new_offset():
    # 2026-03-09 is the first session after DST starts (Mar 8): 12:30 UTC = 08:30 EDT.
    decision = due_run(at(2026, 3, 9, 12, 30), profile="paper_small", completed=set())
    assert decision.status == "due" and decision.session == date(2026, 3, 9)


def test_after_cutoff_and_non_sessions_are_not_due():
    assert due_run(at(2026, 10, 8, 9, 28, NY), profile="p", completed=set()).status == "after_cutoff"
    assert due_run(at(2026, 10, 10, 8, 30, NY), profile="p", completed=set()).status == "not_session"  # Saturday
    assert due_run(at(2026, 11, 26, 8, 30, NY), profile="p", completed=set()).status == "not_session"  # Thanksgiving


def test_completed_key_is_done_and_other_profiles_are_independent():
    done = {("paper_small", date(2026, 10, 8))}
    assert due_run(at(2026, 10, 8, 8, 30, NY), profile="paper_small", completed=done).status == "done"
    assert due_run(at(2026, 10, 8, 8, 30, NY), profile="paper_large", completed=done).status == "due"


def test_missed_sessions_are_those_past_cutoff_without_a_run():
    completed = {date(2026, 10, 5), date(2026, 10, 7)}
    missed = missed_sessions(at(2026, 10, 8, 10, 0, NY), completed_sessions=completed, since=date(2026, 10, 5))
    assert missed == [date(2026, 10, 6), date(2026, 10, 8)]
    before_cutoff = missed_sessions(at(2026, 10, 8, 9, 0, NY), completed_sessions=completed, since=date(2026, 10, 5))
    assert before_cutoff == [date(2026, 10, 6)]


def test_naive_instants_refuse():
    with pytest.raises(ValueError, match="aware"):
        due_run(datetime(2026, 10, 8, 8, 30), profile="p", completed=set())
