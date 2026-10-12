"""Queue Q106: the ledger lock waits out a Windows delete-pending lock instead of crashing.

test-windows on #168 (head 0b2b7ec) failed in a parallel ledger write with
``PermissionError: [Errno 13]`` raised by ``os.open(trials.lock, O_CREAT | O_EXCL)`` in
``trial_registry.serialized``: Windows reports a lock that another process has just unlinked, while
a reader still holds it open, as access denied rather than as existing. These tests replay that
sequence on any OS by faking ``os.open`` inside ``trial_registry``. Rule 12: each guard is shown red
by an in-memory mutant with a clean control (``mutation_support_019.killed``).
"""
import os
import time

import pytest

import context  # noqa: F401
from mutation_support_019 import killed
import trial_registry


def delete_pending_then_free(monkeypatch, denials):
    """``os.open`` on the lock raises PermissionError ``denials`` times, then behaves normally."""
    real_open, calls = os.open, []

    def fake_open(path, flags, *args):
        if str(path).endswith(".lock"):
            calls.append(path)
            if len(calls) <= denials:
                raise PermissionError(13, "Permission denied", str(path))
        return real_open(path, flags, *args)

    monkeypatch.setattr(trial_registry.os, "open", fake_open)
    return calls


def check_windows_waits_out_delete_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(trial_registry, "_RETRY_DELETE_PENDING", True, raising=False)
    calls = delete_pending_then_free(monkeypatch, denials=3)
    ledger = tmp_path / "trials.jsonl"
    try:
        with trial_registry.serialized(ledger, timeout=5.):
            assert ledger.with_suffix(".lock").exists(), "043 LOCK RETRY: the lock is held inside the block"
    except PermissionError as error:
        raise AssertionError(f"043 LOCK RETRY: a delete-pending lock crashed the writer: {error}") from error
    assert len(calls) == 4, "043 LOCK RETRY: three denials, then one successful create"
    assert not ledger.with_suffix(".lock").exists(), "043 LOCK RETRY: the lock is released"


def check_windows_denial_past_deadline_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(trial_registry, "_RETRY_DELETE_PENDING", True, raising=False)
    delete_pending_then_free(monkeypatch, denials=10**9)
    started = time.monotonic()
    with pytest.raises(PermissionError):
        with trial_registry.serialized(tmp_path / "trials.jsonl", timeout=.2):
            raise AssertionError("043 LOCK DEADLINE: entered without the lock")
    assert time.monotonic() - started < 3., "043 LOCK DEADLINE: a permanent denial stops at the deadline"


def check_posix_denial_raises_at_once(tmp_path, monkeypatch):
    monkeypatch.setattr(trial_registry, "_RETRY_DELETE_PENDING", False, raising=False)
    calls = delete_pending_then_free(monkeypatch, denials=1)
    with pytest.raises(PermissionError):
        with trial_registry.serialized(tmp_path / "trials.jsonl", timeout=5.):
            raise AssertionError("043 LOCK POSIX: entered without the lock")
    assert len(calls) == 1, "043 LOCK POSIX: a real EACCES is not retried"


def test_windows_delete_pending_lock_is_waited_out(tmp_path, monkeypatch):
    check_windows_waits_out_delete_pending(tmp_path, monkeypatch)


def test_windows_denial_past_the_deadline_still_raises(tmp_path, monkeypatch):
    check_windows_denial_past_deadline_raises(tmp_path, monkeypatch)


def test_posix_permission_error_is_not_retried(tmp_path, monkeypatch):
    check_posix_denial_raises_at_once(tmp_path, monkeypatch)


def test_retry_is_windows_only():
    assert trial_registry._RETRY_DELETE_PENDING is (os.name == "nt"), "043 LOCK PLATFORM"


def oracle(check, tmp_path_factory):
    def run():
        with pytest.MonkeyPatch.context() as monkeypatch:
            check(tmp_path_factory.mktemp("ledger"), monkeypatch)
    return run


# Rule 12. Each mutant is the bug a tired reviewer could ship. killed() runs the control first.
def test_mutant_denial_not_retried_is_caught(tmp_path_factory):
    killed(trial_registry, "            if not _RETRY_DELETE_PENDING or time.monotonic() >= deadline:\n                raise",
           "            raise", oracle(check_windows_waits_out_delete_pending, tmp_path_factory))


def test_mutant_denial_retried_without_deadline_is_caught(tmp_path_factory):
    # The deadline overshot by 5 s: a permanent denial then blocks well past the caller's timeout.
    killed(trial_registry, "            if not _RETRY_DELETE_PENDING or time.monotonic() >= deadline:\n                raise",
           "            if not _RETRY_DELETE_PENDING or time.monotonic() >= deadline + 5.:\n                raise",
           oracle(check_windows_denial_past_deadline_raises, tmp_path_factory))


def test_mutant_posix_denial_retried_is_caught(tmp_path_factory):
    killed(trial_registry, "            if not _RETRY_DELETE_PENDING or time.monotonic() >= deadline:",
           "            if time.monotonic() >= deadline:",
           oracle(check_posix_denial_raises_at_once, tmp_path_factory))
