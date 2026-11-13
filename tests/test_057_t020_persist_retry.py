"""057 T020 / D-12: the ops-state push is retried, and a persist failure halts with a named reason.

Offline only. The shell contracts run ops/persist_state.sh under a POSIX bash with stand-in `git` and
`sleep` commands first on PATH, so no real repository, remote, network or wait is touched. The
live_loop contracts use the synthetic Fidelity fakes; no credential or broker is real.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import context  # noqa: F401
from test_057_q139 import blocked  # noqa: F401  (autouse: no sockets)
from test_057_q135 import Broker, process  # noqa: F401  (autouse: fresh process)
from test_057_q137 import Gate, execute
from dataclasses import replace
from datetime import timedelta
from mode_config import ArmingRecord
from test_057_q139 import NOW
from test_057_q137 import profile
import paper_loop
import live_loop as loop

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "persist_state.sh"
PY = sys.executable.replace("\\", "/")


def posix_bash():
    """A POSIX bash that keeps the caller's PATH order: on Windows the MSYS bash under Git's usr/bin
    (never Git/bin/bash.exe, which puts its own tools first, nor WSL's System32 bash), else bash on PATH."""
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), r"C:\Program Files"):
            candidate = Path(base or "") / "Git" / "usr" / "bin" / "bash.exe"
            if base and candidate.is_file():
                return str(candidate)
        return None
    return shutil.which("bash")


BASH = posix_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no POSIX bash on this host")

STUB_TOOL = """#!/bin/sh
echo "$*" >> "$STUB_LOG"
case "$1" in
  push)
    n=0
    if [ -f "$STUB_DIR/pushes" ]; then read -r n < "$STUB_DIR/pushes"; fi
    n=$((n + 1))
    echo "$n" > "$STUB_DIR/pushes"
    if [ "$n" -gt "${PUSH_FAILS:-0}" ]; then exit 0; fi
    exit 128 ;;
  config) exit "${CONFIG_EXIT:-0}" ;;
  diff) exit "${DIFF_EXIT:-1}" ;;
  add) exit "${ADD_EXIT:-0}" ;;
  commit) exit "${COMMIT_EXIT:-0}" ;;
esac
exit 0
"""
STUB_SLEEP = """#!/bin/sh
echo "sleep $*" >> "$STUB_LOG"
exit 0
"""


def run_script(tmp_path, **env):
    """Run the real script; return (exit code, logged stand-in calls)."""
    bin_dir, state, stub = tmp_path / "bin", tmp_path / "state", tmp_path / "stub"
    for d in (bin_dir, state, stub):
        d.mkdir(exist_ok=True)
    for name, body in (("git", STUB_TOOL), ("sleep", STUB_SLEEP)):
        path = bin_dir / name
        path.write_bytes(body.encode("utf-8"))
        path.chmod(0o755)
    log = stub / "log"
    # GIT_DIR names a missing directory, so even a real tool that slipped past the stand-in would
    # find no repository; the check below refuses to run the script unless the stand-ins resolve.
    environ = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                   STUB_LOG=str(log).replace("\\", "/"), STUB_DIR=str(stub).replace("\\", "/"),
                   GIT_DIR=str(tmp_path / "no-repository").replace("\\", "/"),
                   **{k: str(v) for k, v in env.items()})
    resolved = subprocess.run([BASH, "-c", "type -P git; type -P sleep"], env=environ,
                              capture_output=True, text=True, timeout=60).stdout.split()
    if len(resolved) != 2 or not all(tmp_path.name in p and p.endswith(("/bin/git", "/bin/sleep"))
                                     for p in resolved):
        pytest.fail(f"stand-in commands not first on PATH; refusing to run the script: {resolved}")
    done = subprocess.run([BASH, "ops/persist_state.sh", str(state).replace("\\", "/"), "fidelity-preview"],
                          cwd=ROOT, env=environ, capture_output=True, text=True, timeout=60)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return done.returncode, calls


def pushes(calls):
    return [c for c in calls if c.split()[:1] == ["push"]]


def sleeps(calls):
    return [c for c in calls if c.startswith("sleep ")]


@needs_bash
def test_first_push_succeeds_with_no_wait(tmp_path):
    code, calls = run_script(tmp_path)
    assert code == 0 and len(pushes(calls)) == 1 and sleeps(calls) == []
    assert any(c.startswith("commit -q -m ops state: fidelity-preview") for c in calls)


@needs_bash
@pytest.mark.parametrize("fails, waits", [(1, ["sleep 5"]), (2, ["sleep 5", "sleep 15"])])
def test_a_failed_push_is_retried_after_a_growing_wait(tmp_path, fails, waits):
    code, calls = run_script(tmp_path, PUSH_FAILS=fails)
    assert code == 0 and len(pushes(calls)) == fails + 1 and sleeps(calls) == waits


@needs_bash
def test_three_failed_pushes_exit_4_and_never_a_fourth(tmp_path):
    code, calls = run_script(tmp_path, PUSH_FAILS=99)
    assert code == 4 and len(pushes(calls)) == 3 and sleeps(calls) == ["sleep 5", "sleep 15"]


@needs_bash
def test_every_attempt_pushes_the_same_ref_without_force(tmp_path):
    _, calls = run_script(tmp_path, PUSH_FAILS=99)
    assert set(pushes(calls)) == {"push -q origin HEAD:ops-state"}
    assert len([c for c in calls if c.startswith("commit")]) == 1  # one commit, pushed again, never re-made


@needs_bash
@pytest.mark.parametrize("failing", ["CONFIG_EXIT", "ADD_EXIT", "COMMIT_EXIT"])
def test_a_failed_add_or_commit_exits_3_before_any_push(tmp_path, failing):
    code, calls = run_script(tmp_path, **{failing: 1})
    assert code == 3 and pushes(calls) == [] and sleeps(calls) == []


@needs_bash
def test_no_change_still_pushes_without_a_commit(tmp_path):
    code, calls = run_script(tmp_path, DIFF_EXIT=0)
    assert code == 0 and len(pushes(calls)) == 1 and not [c for c in calls if c.startswith("commit")]


def test_script_never_forces_fetches_or_rewrites():
    text = SCRIPT.read_text(encoding="utf-8")
    for word in ("--force", " -f ", "+HEAD", "fetch", "pull", "rebase", "reset", "merge"):
        assert word not in text, word


# --- the persist command reports its exit status (paper_loop) ---

def test_persist_command_failure_carries_its_exit_status():
    persist = paper_loop.persist_command(f'"{PY}" -c "import sys; sys.exit(4)"')
    with pytest.raises(RuntimeError) as caught:
        persist()
    assert getattr(caught.value, "returncode", None) == 4
    assert str(caught.value) == "persist command exited 4"


def test_persist_command_success_raises_nothing():
    paper_loop.persist_command(f'"{PY}" -c "pass"')()


# --- live_loop halts a persist failure with a fixed, recorded reason ---

class Rich(Broker):
    """Enough settled cash that the plan holds at least three sleeve orders."""
    def settled_cash(self, now):
        return {"amount": 200.0, "settled_amt": 200.0, "coreBalance": 200.0, "as_of": now.isoformat()}

    def positions(self):
        return {"SPAXX**": 200.0}


def failing_at(n, exc):
    calls = []

    def persist():
        calls.append(True)
        if len(calls) >= n:
            raise exc
    return persist, calls


class Exit(RuntimeError):
    def __init__(self, code):
        super().__init__("remote: secret-looking-output https://example.invalid/token")
        self.returncode = code


@pytest.mark.parametrize("exc, reason", [
    (Exit(4), "push failed after 3 attempts (exit 4)"),
    (Exit(3), "commit step failed (exit 3)"),
    (Exit(7), "exit 7"),
    (FileNotFoundError("bash: /some/path"), "FileNotFoundError"),
])
def test_a_persist_failure_is_recorded_by_name_and_latches_halted(tmp_path, exc, reason):
    persist, _ = failing_at(1, exc)
    r = execute(tmp_path, broker=Rich(), gate=Gate(), persist=persist)
    assert r.get("aborted") and r["place_calls"] == 0
    assert r["failure"]["kind"] == "HaltProfile"
    assert r["failure"]["detail"] == "ops-state persist failed: " + reason
    assert "secret-looking" not in str(r) and "/some/path" not in str(r)
    assert (tmp_path / "HALTED").exists()


def test_the_11_10_shape_names_the_persist_step_mid_allocation(tmp_path):
    """Lease, connect-reconcile, then one reconcile per order: the 4th persist fails after the first
    allocation preview and before the second, as on 2026-11-10 (there, before the third)."""
    b = Rich()
    persist, calls = failing_at(4, Exit(4))
    r = execute(tmp_path, broker=b, gate=Gate(), persist=persist, profile=replace(profile(), fractional=True))
    assert len(calls) == 4 and r.get("aborted") and r["place_calls"] == 0
    assert r["failure"]["stage"] == "allocation"
    assert r["failure"]["detail"] == "ops-state persist failed: push failed after 3 attempts (exit 4)"
    assert [c[0] for c in b.calls].count("preview") == 1 and (tmp_path / "HALTED").exists()


def test_the_real_persist_command_feeds_the_named_reason(tmp_path):
    persist = paper_loop.persist_command(f'"{PY}" -c "import sys; sys.exit(4)"')
    r = execute(tmp_path, broker=Rich(), gate=Gate(), persist=persist)
    assert r["failure"]["detail"] == "ops-state persist failed: push failed after 3 attempts (exit 4)"


def test_armed_persist_failure_never_reaches_placement(tmp_path):
    b = Rich()
    b.status = lambda conf: "WORKING"
    arm = ArmingRecord("live_fidelity", profile().account_fingerprint, "e" * 64, "Camden",
                       NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    persist, _ = failing_at(2, Exit(4))
    r = execute(tmp_path, broker=b, gate=Gate(), arming=arm, persist=persist)
    assert r.get("aborted") and r["place_calls"] == 0
    assert not [c for c in b.calls if c[0] == "place"] and (tmp_path / "HALTED").exists()
    assert r["failure"]["detail"] == "ops-state persist failed: push failed after 3 attempts (exit 4)"


def test_armed_place_time_persist_failure_halts_before_placement(tmp_path):
    """Lease, connect-reconcile and the first order's reconcile persist; the 4th persist, inside
    DurableBroker.place, fails. FidelityLive.submit reports it as SubmissionUnknown (D-12 known limit)."""
    b = Rich()
    b.status = lambda conf: "WORKING"
    arm = ArmingRecord("live_fidelity", profile().account_fingerprint, "e" * 64, "Camden",
                       NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    persist, calls = failing_at(4, Exit(4))
    r = execute(tmp_path, broker=b, gate=Gate(), arming=arm, persist=persist,
                profile=replace(profile(), fractional=True))
    assert len(calls) == 4 and r.get("aborted") and r["place_calls"] == 0
    assert [c[0] for c in b.calls] == ["preview"]  # the order's preview ran; place never did
    assert r["failure"]["kind"] == "SubmissionUnknown" and "HaltProfile" in r["failure"]["detail"]
    assert (tmp_path / "HALTED").exists()


def test_a_working_persist_still_previews_clean(tmp_path):
    persist, calls = failing_at(10_000, Exit(4))
    r = execute(tmp_path, broker=Rich(), gate=Gate(), persist=persist)
    assert not r.get("aborted") and r["clean"] and len(calls) >= 5
    assert not (tmp_path / "HALTED").exists()


def test_armed_without_persist_still_refuses(tmp_path):
    arm = ArmingRecord("live_fidelity", profile().account_fingerprint, "e" * 64, "Camden",
                       NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    r = execute(tmp_path, broker=Rich(), gate=Gate(), arming=arm, persist=None)
    assert r.get("aborted") and r["failure"]["detail"] == "durable persistence required before LIVE"
