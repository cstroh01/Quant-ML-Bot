"""Spec 055 kill/reset gap (queue Q107): a killed profile raises a halt incident, and a reset records
every session the kill skipped, so those sessions are neither silent nor reported as missed runs.

Fakes only: the wrapped command is a tiny Python one-liner, never the broker loop. Rule 12: each
guard below is shown red by an in-memory mutant (``mutation_support_019.killed``) with a clean
control. EXAMPLE — NOT A RESULT.
"""
from datetime import date, datetime
import json
import sys
from zoneinfo import ZoneInfo

import context  # noqa: F401
from mutation_support_019 import killed
import ops_runner
import ops_runtime

NY = ZoneInfo("America/New_York")
OK = [sys.executable, "-c", "print('ok')"]
P = "paper_small"
# 2026-10-05 (Mon) to 2026-10-09 (Fri) are NYSE sessions; the cutoff is 09:28 New York.
MON_RUN, MON_NOON = datetime(2026, 10, 5, 8, 30, tzinfo=NY), datetime(2026, 10, 5, 12, 0, tzinfo=NY)


def run(state, now):
    return ops_runner.run_once(state, profile=P, command=OK, now=now, strategy_version="sv@abc")


def lines(state, name):
    path = state / "ops" / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def kinds(state):
    return [(i["kind"], i["detail"]) for i in lines(state, "incidents.jsonl")]


def check_halt_names_unrun_sessions(state):
    assert run(state, MON_RUN)["status"] == "completed"
    ops_runner.set_kill(state, P, reason="operator halt", now=MON_NOON)
    first = run(state, datetime(2026, 10, 7, 8, 30, tzinfo=NY))
    assert first == {"status": "killed", "new_incidents": 1}, "055 KILL HALT: a killed invocation raises one incident"
    again = run(state, datetime(2026, 10, 7, 9, 0, tzinfo=NY))
    assert again["new_incidents"] == 0, "055 KILL HALT: the same halt is not re-sent"
    later = run(state, datetime(2026, 10, 8, 8, 30, tzinfo=NY))
    assert later["new_incidents"] == 1, "055 KILL HALT: a newly unrun session re-sends the halt"
    halts = [d for k, d in kinds(state) if k == "halt"]
    assert len(halts) == 2 and "operator halt" in halts[0], "055 KILL HALT"
    assert halts[0].endswith("sessions not run: 2026-10-06"), "055 KILL HALT: only cutoff-passed sessions"
    assert halts[1].endswith("sessions not run: 2026-10-06, 2026-10-07"), "055 KILL HALT"
    assert [r["session"] for r in lines(state, "runs.jsonl")] == ["2026-10-05"], "055 KILL HALT: nothing ran"


def check_reset_records_skipped_sessions(state):
    run(state, MON_RUN)
    ops_runner.set_kill(state, P, reason="operator halt", now=MON_NOON)
    reset = ops_runner.set_kill(state, P, reason="reviewed", reset=True,
                                now=datetime(2026, 10, 8, 9, 0, tzinfo=NY))
    assert reset["skipped_sessions"] == ["2026-10-06", "2026-10-07"], "055 RESET SKIPPED"
    skipped = lines(state, "skipped.jsonl")
    assert [(s["profile"], s["session"], s["cause"], s["review_note"]) for s in skipped] == [
        (P, "2026-10-06", "killed", "reviewed"), (P, "2026-10-07", "killed", "reviewed")], "055 RESET SKIPPED"
    assert [k for k, _ in kinds(state)] == ["halt_reset"], "055 RESET SKIPPED: the reset is reported"
    assert run(state, datetime(2026, 10, 8, 9, 0, tzinfo=NY))["status"] == "completed", "055 RESET SKIPPED"
    assert "missed_run" not in [k for k, _ in kinds(state)], "055 RESET SKIPPED: recorded sessions are not missed"


def check_pre_kill_miss_stays_missed(state):
    run(state, MON_RUN)
    # 2026-10-06's cutoff passed with no run BEFORE the kill landed: that miss is not the kill's.
    ops_runner.set_kill(state, P, reason="late halt", now=datetime(2026, 10, 6, 12, 0, tzinfo=NY))
    reset = ops_runner.set_kill(state, P, reason="reviewed", reset=True,
                                now=datetime(2026, 10, 7, 8, 0, tzinfo=NY))
    assert reset["skipped_sessions"] == [], "055 PRE-KILL MISS"
    assert run(state, datetime(2026, 10, 7, 8, 30, tzinfo=NY))["status"] == "completed"
    missed = [d for k, d in kinds(state) if k == "missed_run"]
    assert len(missed) == 1 and "2026-10-06" in missed[0], "055 PRE-KILL MISS: still a missed run"


def check_started_session_is_never_skipped(state):
    """A run that claimed its lease and never finished may have sent orders: never "skipped"."""
    run(state, MON_RUN)
    ops_runtime.acquire_lease(state, P, date(2026, 10, 6), run_id="crashed-run")
    ops_runner.set_kill(state, P, reason="halt after crash", now=datetime(2026, 10, 6, 9, 25, tzinfo=NY))
    reset = ops_runner.set_kill(state, P, reason="reviewed", reset=True, now=datetime(2026, 10, 7, 8, 0, tzinfo=NY))
    assert reset["skipped_sessions"] == [], "055 LEASED SESSION: a started session is not skipped"
    run(state, datetime(2026, 10, 7, 8, 30, tzinfo=NY))
    missed = [d for k, d in kinds(state) if k == "missed_run"]
    assert len(missed) == 1 and "2026-10-06" in missed[0], "055 LEASED SESSION: still a missed run"


def check_kill_at_the_cutoff_is_a_miss(state):
    """At exactly 09:28 the session is already past its cutoff (due_run says after_cutoff)."""
    run(state, MON_RUN)
    ops_runner.set_kill(state, P, reason="halt at cutoff", now=datetime(2026, 10, 6, 9, 28, tzinfo=NY))
    reset = ops_runner.set_kill(state, P, reason="reviewed", reset=True, now=datetime(2026, 10, 7, 8, 0, tzinfo=NY))
    assert reset["skipped_sessions"] == [], "055 CUTOFF BOUNDARY: a kill at the cutoff skips nothing"
    one_minute_early = ops_runner._skipped_while_killed(
        state, P, datetime(2026, 10, 6, 9, 27, tzinfo=NY), datetime(2026, 10, 7, 8, 0, tzinfo=NY))
    assert [str(s) for s in one_minute_early] == ["2026-10-06"], "055 CUTOFF BOUNDARY: one minute earlier skips it"


def check_unrecorded_gap_is_still_missed(state):
    """Only a session written to skipped.jsonl is exempt: deleting the record brings the miss back."""
    run(state, MON_RUN)
    ops_runner.set_kill(state, P, reason="operator halt", now=MON_NOON)
    ops_runner.set_kill(state, P, reason="reviewed", reset=True, now=datetime(2026, 10, 7, 8, 0, tzinfo=NY))
    (state / "ops" / "skipped.jsonl").unlink()
    run(state, datetime(2026, 10, 7, 8, 30, tzinfo=NY))
    missed = [d for k, d in kinds(state) if k == "missed_run"]
    assert len(missed) == 1 and "2026-10-06" in missed[0], "055 SKIP RECORD: an unrecorded gap is missed"


def fresh(tmp_path_factory, check):
    return lambda: check(tmp_path_factory.mktemp("state"))


def test_killed_profile_raises_a_halt_incident_naming_unrun_sessions(tmp_path):
    check_halt_names_unrun_sessions(tmp_path)


def test_reset_records_sessions_skipped_while_killed(tmp_path):
    check_reset_records_skipped_sessions(tmp_path)


def test_a_miss_before_the_kill_stays_a_missed_run(tmp_path):
    check_pre_kill_miss_stays_missed(tmp_path)


def test_only_a_recorded_skip_is_exempt_from_missed_run_detection(tmp_path):
    check_unrecorded_gap_is_still_missed(tmp_path)


def test_a_session_started_before_the_kill_is_never_skipped(tmp_path):
    check_started_session_is_never_skipped(tmp_path)


def test_a_kill_at_the_cutoff_is_a_miss_not_a_skip(tmp_path):
    check_kill_at_the_cutoff_is_a_miss(tmp_path)


def test_reset_requires_an_aware_clock(tmp_path):
    ops_runner.set_kill(tmp_path, P, reason="halt", now=MON_NOON)
    try:
        ops_runner.set_kill(tmp_path, P, reason="reviewed", reset=True, now=datetime(2026, 10, 6, 9, 0))
    except ValueError:
        pass
    else:
        raise AssertionError("055 RESET CLOCK: a naive clock is refused")
    assert (tmp_path / "ops" / f"kill-{P}.json").exists(), "055 RESET CLOCK: the kill survives"


# Rule 12: each mutant is a defect a tired reviewer could ship; the control runs first inside killed().
def test_mutant_silent_kill_is_caught(tmp_path_factory):
    killed(ops_runner, "return _killed(state_dir, profile, now)", 'return {"status": "killed", "new_incidents": 0}',
           fresh(tmp_path_factory, check_halt_names_unrun_sessions))


def test_mutant_halt_without_session_list_is_caught(tmp_path_factory):
    killed(ops_runner, "', '.join(map(str, skipped)) or 'none yet'", "'see kills.jsonl'",
           fresh(tmp_path_factory, check_halt_names_unrun_sessions))


def test_mutant_pre_kill_miss_blamed_on_the_kill_is_caught(tmp_path_factory):
    killed(ops_runner, "            if datetime.combine(s, CUTOFF, tzinfo=NY) > kill_at\n", "            if True\n",
           fresh(tmp_path_factory, check_pre_kill_miss_stays_missed))


def test_mutant_leased_session_skipped_is_caught(tmp_path_factory):
    killed(ops_runner, "            and not _lease_path(state_dir, profile, s).exists()]", "            ]",
           fresh(tmp_path_factory, check_started_session_is_never_skipped))


def test_mutant_cutoff_boundary_inclusive_is_caught(tmp_path_factory):
    killed(ops_runner, "if datetime.combine(s, CUTOFF, tzinfo=NY) > kill_at", "if datetime.combine(s, CUTOFF, tzinfo=NY) >= kill_at",
           fresh(tmp_path_factory, check_kill_at_the_cutoff_is_a_miss))


def test_mutant_reset_records_nothing_is_caught(tmp_path_factory):
    killed(ops_runner, '            _append(ops / "skipped.jsonl"', '            (lambda *a: None)(ops / "skipped.jsonl"',
           fresh(tmp_path_factory, check_reset_records_skipped_sessions))


def test_mutant_recorded_skips_ignored_is_caught(tmp_path_factory):
    killed(ops_runner, "completed_sessions={s for _, s in completed} | skipped,",
           "completed_sessions={s for _, s in completed},",
           fresh(tmp_path_factory, check_reset_records_skipped_sessions))


def test_mutant_exemption_read_from_the_kill_log_is_caught(tmp_path_factory):
    killed(ops_runner,
           'skipped = {date.fromisoformat(r["session"]) for r in _jsonl(ops / "skipped.jsonl") if r["profile"] == profile}',
           'skipped = {date.fromisoformat(s) for r in _jsonl(ops / "kills.jsonl") if r["profile"] == profile '
           'for s in r.get("skipped_sessions", [])}',
           fresh(tmp_path_factory, check_unrecorded_gap_is_still_missed))
