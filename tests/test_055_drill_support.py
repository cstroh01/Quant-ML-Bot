"""Spec 055 T007 drill support (queue Q102): injected clock, held-lease fixture, per-profile kill.

Fakes only: the wrapped command is a tiny Python one-liner, never the broker loop. EXAMPLE — NOT A RESULT.
"""
import json
import shlex
import sys

import context  # noqa: F401
from ops_runner import main

OK = shlex.join([sys.executable, "-c", "print('ok')"])
NOW = "2026-10-08T08:30:00-04:00"  # a session day, inside the 08:00-09:28 New York window


def argv(state, profile="paper_small", *extra, command=OK):
    base = ["--state-dir", str(state), "--profile", profile, "--strategy-version", "sv@abc"]
    return base + (["--command", command] if command else []) + list(extra)


def refused(args):
    """True only for argparse's refusal (exit 2); running, or failing any other way, is not refusing."""
    try:
        main(args)
    except SystemExit as exit_info:
        return exit_info.code == 2
    except Exception:
        return False
    return False


def runs(state):
    path = state / "ops" / "runs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_injected_clock_runs_the_drill_session(tmp_path, capsys):
    assert main(argv(tmp_path, "paper_small", "--drill", "--now", NOW)) == 0, "055 DRILL CLOCK"
    assert [r["session"] for r in runs(tmp_path)] == ["2026-10-08"], "055 DRILL CLOCK"
    saturday = "2026-10-10T08:30:00-04:00"
    assert main(argv(tmp_path / "s", "paper_small", "--drill", "--now", saturday)) == 0
    assert not runs(tmp_path / "s"), "055 DRILL CLOCK: a non-session drill runs nothing"


def test_injected_clock_is_drill_only_naive_refused_and_never_with_submit(tmp_path):
    assert refused(argv(tmp_path, "paper_small", "--now", NOW)), "055 DRILL ONLY"
    assert refused(argv(tmp_path, "paper_small", "--drill", "--now", "2026-10-08T08:30:00")), "055 DRILL AWARE"
    submit = OK + " --submit"
    assert refused(argv(tmp_path, "paper_small", "--drill", "--now", NOW, command=submit)), "055 DRILL SUBMIT"
    assert refused(argv(tmp_path, "paper_small", "--drill", command=submit)), "055 DRILL SUBMIT"
    assert not runs(tmp_path), "055 DRILL SUBMIT: a refused invocation runs nothing"


def test_held_lease_fixture_makes_the_drill_report_lease_held(tmp_path, capsys):
    assert refused(argv(tmp_path, "paper_small", "--hold-lease", "2026-10-08", command=None)), "055 LEASE DRILL ONLY"
    assert not (tmp_path / "leases").exists(), "055 LEASE DRILL ONLY"
    assert main(argv(tmp_path, "paper_small", "--drill", "--hold-lease", "2026-10-08", command=None)) == 0
    capsys.readouterr()
    assert main(argv(tmp_path, "paper_small", "--drill", "--now", NOW)) == 1, "055 LEASE HELD"
    assert json.loads(capsys.readouterr().out)["status"] == "lease_held", "055 LEASE HELD"
    assert not runs(tmp_path), "055 LEASE HELD: the held session never runs"


def test_kill_stops_only_the_named_profile(tmp_path, capsys):
    assert main(argv(tmp_path, "paper_large", "--kill", "drill: halt large", command=None)) == 0
    assert main(argv(tmp_path, "paper_small", "--drill", "--now", NOW)) == 0, "055 KILL OTHER PROFILE"
    capsys.readouterr()
    assert main(argv(tmp_path, "paper_large", "--drill", "--now", NOW)) == 1, "055 KILL"
    assert json.loads(capsys.readouterr().out)["status"] == "killed", "055 KILL"
    assert [r["profile"] for r in runs(tmp_path)] == ["paper_small"], "055 KILL"


def test_kill_needs_a_reason_and_reset_needs_explicit_confirmation(tmp_path, capsys):
    try:
        main(argv(tmp_path, "paper_large", "--kill", " ", command=None))
    except ValueError as error:
        assert "reason" in str(error), "055 KILL REASON"
    assert not (tmp_path / "ops" / "kill-paper_large.json").exists(), "055 KILL REASON"
    main(argv(tmp_path, "paper_large", "--kill", "drill", command=None))
    assert refused(argv(tmp_path, "paper_large", "--reset-kill", "reviewed", command=None)), "055 RESET CONFIRM"
    assert refused(argv(tmp_path, "paper_large", "--reset-kill", "reviewed", "--confirm-reset", "paper_small",
                        command=None)), "055 RESET CONFIRM"
    assert (tmp_path / "ops" / "kill-paper_large.json").exists(), "055 RESET CONFIRM: kill survives a refused reset"
    assert main(argv(tmp_path, "paper_large", "--reset-kill", "reviewed", "--confirm-reset", "paper_large",
                     command=None)) == 0
    assert main(argv(tmp_path, "paper_large", "--drill", "--now", NOW)) == 0, "055 RESET"
    log = [json.loads(line) for line in (tmp_path / "ops" / "kills.jsonl").read_text().splitlines()]
    assert [(r["action"], r["reason"]) for r in log] == [("kill", "drill"), ("reset", "reviewed")], "055 KILL LOG"
