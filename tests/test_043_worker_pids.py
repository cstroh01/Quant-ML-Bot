"""043 T037: independent spawned-worker PID evidence. Synthetic; no research or broker calls."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
import context  # noqa: F401
from ledger_guard_child import _read_worker_pids, _record_worker_pid

ROOT = Path(__file__).resolve().parents[1]


def test_two_actual_processes_each_leave_exact_pid_evidence(tmp_path):
    code = ("from pathlib import Path; import os, sys; sys.path.insert(0, sys.argv[1]); "
            "from ledger_guard_child import _record_worker_pid; print(os.getpid()); "
            "_record_worker_pid(Path(sys.argv[2]))")
    workers = [subprocess.Popen([sys.executable, "-B", "-c", code, str(ROOT / "tests"), str(tmp_path)],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    actual_pids = []
    try:
        for worker in workers:
            output, error = worker.communicate(timeout=30)
            assert worker.returncode == 0, error.decode(errors="replace")
            actual_pids.append(int(output.strip()))  # Windows venv launcher PID can differ from Python's
        assert len(set(actual_pids)) == 2
        assert _read_worker_pids(tmp_path) == sorted(actual_pids)
        assert os.getpid() not in _read_worker_pids(tmp_path)
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
            worker.wait()


def test_unchanged_valid_pid_record_round_trips(tmp_path):
    _record_worker_pid(tmp_path)
    assert _read_worker_pids(tmp_path) == [os.getpid()]


@pytest.mark.parametrize("text", ["", "not-a-pid", "-1", "999"])
def test_malformed_or_mismatched_record_is_never_silently_ignored(tmp_path, text):
    folder = tmp_path / "guard-worker-pids"
    folder.mkdir()
    (folder / "123.pid").write_text(text, encoding="ascii")
    with pytest.raises(ValueError, match="invalid worker PID evidence"):
        _read_worker_pids(tmp_path)
