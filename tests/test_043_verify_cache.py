"""Ledger verification reuses only sidecars that are byte-for-byte unchanged (stat + recorded claim)."""
import os

import pytest
from context import SCRIPTS_DIR  # noqa: F401 -- makes scripts importable

import trial_registry as tr
from trial_registry import TrialLedger


def _config(i):
    return {"runner": "fixture", "data": None, "universe": None, "date_range": None, "features": [], "transforms": [],
            "target": None, "model": {"name": f"m{i}"}, "cv": None, "seed": i, "initial_capital": None,
            "commission": None, "slippage": None, "liquidation": False, "risk_free": None}


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "_VERIFIED_SIDECARS", {})
    log = TrialLedger(tmp_path, synthetic=True)
    for i in range(3):
        trial = log.start(_config(i), role="synthetic_test", family="legacy-research", runner="fixture")
        log.finish(trial, "completed", returns=[{"session": "2020-01-02", "log_return": 0.001 * i},
                                                {"session": "2020-01-03", "log_return": 0.0}], metadata={})
    return log


def sidecars(log):
    return sorted((log.root / "docs/trials/returns").glob("*.jsonl")) or sorted(log.path.parent.glob("returns/*.jsonl"))


def test_unchanged_sidecars_are_not_reparsed(ledger, monkeypatch):
    ledger.verify()
    calls = []
    real = tr.validate_rows
    monkeypatch.setattr(tr, "validate_rows", lambda rows: calls.append(1) or real(rows))
    ledger.verify()
    assert calls == [], "VERIFY CACHE: an unchanged, already verified sidecar was re-parsed"


@pytest.mark.parametrize("tamper", ["bytes", "same_size", "deleted"])
def test_any_change_to_a_sidecar_is_caught_after_a_cached_verify(ledger, tamper):
    ledger.verify()
    path = sidecars(ledger)[0]
    data = path.read_bytes()
    if tamper == "bytes":
        path.write_bytes(data + b"\n")
    elif tamper == "same_size":
        os.chmod(path, 0o644)
        path.write_bytes(data.replace(b"0.0", b"0.1", 1) if b"0.0" in data else data[::-1])
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    else:
        path.unlink()
    with pytest.raises(ValueError, match="sidecar"):
        ledger.verify()


def test_a_changed_claim_rechecks_the_file(ledger):
    ledger.verify()
    key = next(iter(tr._VERIFIED_SIDECARS))
    claim, stamp = tr._VERIFIED_SIDECARS[key]
    tr._VERIFIED_SIDECARS[key] = (("0" * 64, *claim[1:]), stamp)
    ledger.verify()
    assert tr._VERIFIED_SIDECARS[key] == (claim, stamp), "VERIFY CACHE: a claim mismatch must force a full re-check"
