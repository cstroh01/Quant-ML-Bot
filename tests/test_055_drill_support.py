"""Spec 055 T007 drill support (queue Q102): injected clock, held-lease fixture, per-profile kill.

Fakes only: the wrapped command is a tiny Python one-liner, never the broker loop. EXAMPLE — NOT A RESULT.
"""
import json
import shlex
import sys

import pytest

import context  # noqa: F401
from ops_runner import main

OK = shlex.join([sys.executable, "-c", "print('ok')"])
NOW = "2026-10-08T08:30:00-04:00"  # a session day, inside the 08:00-09:28 New York window


@pytest.fixture
def drill_dir(tmp_path):
    (tmp_path / "DRILL").write_text("supervised drill state; never the real ops-state")
    return tmp_path


def argv(state, profile="paper_small", *extra, command=OK):
    base = ["--state-dir", str(state), "--profile", profile, "--strategy-version", "sv@abc"]
    return base + (["--command", command] if command else []) + list(extra)


def drill(state, profile="paper_small", *extra, command=OK):
    return argv(state, profile, "--drill", *extra, command=command)


def refused(args):
    """True only for argparse's refusal (exit 2); running, or failing any other way, is not refusing."""
    try:
        main(args)
    except SystemExit as exit_info:
        return exit_info.code == 2
    except Exception:
        return False
    return False


def exit_code(args):
    try:
        return main(args)
    except SystemExit as exit_info:
        return exit_info.code


def runs(state):
    path = state / "ops" / "runs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_injected_clock_runs_the_drill_session(drill_dir, tmp_path_factory, capsys):
    assert main(drill(drill_dir, "paper_small", "--now", NOW)) == 0, "055 DRILL CLOCK"
    assert [r["session"] for r in runs(drill_dir)] == ["2026-10-08"], "055 DRILL CLOCK"
    other = tmp_path_factory.mktemp("saturday")
    (other / "DRILL").write_text("drill")
    assert main(drill(other, "paper_small", "--now", "2026-10-10T08:30:00-04:00")) == 0
    assert not runs(other), "055 DRILL CLOCK: a non-session drill runs nothing"


def test_injected_clock_is_drill_only_naive_refused_and_never_with_submit(drill_dir, tmp_path_factory):
    real = tmp_path_factory.mktemp("real")
    assert refused(argv(real, "paper_small", "--now", NOW)), "055 DRILL ONLY"
    assert not runs(real), "055 DRILL ONLY"
    assert refused(drill(drill_dir, "paper_small", "--now", "2026-10-08T08:30:00")), "055 DRILL AWARE"
    for submit in (OK + " --submit", OK + " --sub", f"sh -c {shlex.quote(OK + ' --submit')}"):
        assert refused(drill(drill_dir, "paper_small", "--now", NOW, command=submit)), f"055 DRILL SUBMIT {submit}"
    assert refused(drill(drill_dir, "paper_small", "--now", NOW, "--persist-command", OK + " --submit")), \
        "055 DRILL PERSIST"
    assert not runs(drill_dir), "055 DRILL SUBMIT: a refused invocation runs nothing"


def test_drill_and_real_state_never_mix(tmp_path, drill_dir, capsys):
    real = tmp_path / "real"
    assert refused(drill(real, "paper_small", "--now", NOW)), "055 DRILL MARKER"
    assert refused(argv(drill_dir, "paper_small")), "055 DRILL MARKER: a real run refuses drill state"
    assert not runs(real) and not runs(drill_dir), "055 DRILL MARKER"


def test_a_real_submit_run_is_not_refused(tmp_path, capsys):
    import ops_runner
    saved = ops_runner._now
    try:
        ops_runner._now = lambda: ops_runner.datetime.fromisoformat(NOW)
        assert exit_code(argv(tmp_path, "paper_small", command=OK + " --submit")) == 0, "055 REAL SUBMIT"
    finally:
        ops_runner._now = saved
    assert [r["status"] for r in runs(tmp_path)] == ["completed"], "055 REAL SUBMIT"


def test_held_lease_fixture_makes_the_drill_report_lease_held(drill_dir, tmp_path_factory, capsys):
    real = tmp_path_factory.mktemp("real")
    assert refused(argv(real, "paper_small", "--hold-lease", "2026-10-08", command=None)), "055 LEASE DRILL ONLY"
    assert not (real / "leases").exists(), "055 LEASE DRILL ONLY"
    assert main(drill(drill_dir, "paper_small", "--hold-lease", "2026-10-08", command=None)) == 0
    capsys.readouterr()
    assert main(drill(drill_dir, "paper_small", "--now", NOW)) == 1, "055 LEASE HELD"
    assert json.loads(capsys.readouterr().out)["status"] == "lease_held", "055 LEASE HELD"
    assert not runs(drill_dir), "055 LEASE HELD: the held session never runs"


def test_kill_stops_only_the_named_profile(drill_dir, capsys):
    assert main(drill(drill_dir, "paper_large", "--kill", "drill: halt large", command=None)) == 0
    assert main(drill(drill_dir, "paper_small", "--now", NOW)) == 0, "055 KILL OTHER PROFILE"
    capsys.readouterr()
    assert main(drill(drill_dir, "paper_large", "--now", NOW)) == 1, "055 KILL"
    assert json.loads(capsys.readouterr().out)["status"] == "killed", "055 KILL"
    assert [r["profile"] for r in runs(drill_dir)] == ["paper_small"], "055 KILL"


def test_kill_needs_a_reason_and_reset_needs_explicit_confirmation(drill_dir, capsys):
    kill_large = drill_dir / "ops" / "kill-paper_large.json"
    assert refused(drill(drill_dir, "paper_large", "--kill", " ", command=None)), "055 KILL REASON"
    assert not kill_large.exists(), "055 KILL REASON"
    main(drill(drill_dir, "paper_large", "--kill", "drill", command=None))
    main(drill(drill_dir, "paper_small", "--kill", "drill small", command=None))
    assert refused(drill(drill_dir, "paper_large", "--kill", "again", command=None)), "055 KILL TWICE"
    assert refused(drill(drill_dir, "paper_large", "--reset-kill", "reviewed", command=None)), "055 RESET CONFIRM"
    assert refused(drill(drill_dir, "paper_large", "--reset-kill", "reviewed", "--confirm-reset", "paper_small",
                         command=None)), "055 RESET CONFIRM"
    assert kill_large.exists(), "055 RESET CONFIRM: kill survives a refused reset"
    assert main(drill(drill_dir, "paper_large", "--reset-kill", "reviewed", "--confirm-reset", "paper_large",
                      command=None)) == 0
    assert main(drill(drill_dir, "paper_large", "--now", NOW)) == 0, "055 RESET"
    assert (drill_dir / "ops" / "kill-paper_small.json").exists(), "055 RESET: the other profile stays killed"
    log = [json.loads(line) for line in (drill_dir / "ops" / "kills.jsonl").read_text().splitlines()]
    assert [(r["profile"], r["action"], r["reason"]) for r in log] == [
        ("paper_large", "kill", "drill"), ("paper_small", "kill", "drill small"),
        ("paper_large", "reset", "reviewed")], "055 KILL LOG"
