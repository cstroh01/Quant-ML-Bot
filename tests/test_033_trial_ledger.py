"""Migration path 2: upgrade trial_registry in place; retire its optional writer.

EXAMPLE — NOT A RESULT. All ledger writes use injected temporary roots.
"""
import copy
import hashlib
import inspect
import json
import multiprocessing
from pathlib import Path
import subprocess
import os
import unittest

import pytest
from context import SCRIPTS_DIR
import trial_registry
from spec033_support import CONFIG, SOURCE, META, EVENT_FIELDS, api, config, ledger, rows, start

@pytest.mark.parametrize("field", list(CONFIG))
def test_every_result_choice_changes_hash(tmp_path, field):
    canonical = api("trial_registry", "canonical_config")
    original = canonical(config(), root=tmp_path)
    altered = config()
    altered[field] = {"changed": altered[field]}
    assert canonical(altered, root=tmp_path)[1] != original[1]

def test_canonical_defaults_order_sets_paths_and_finiteness(tmp_path):
    canonical = api("trial_registry", "canonical_config")
    partial = config(); partial.pop("seed")
    assert canonical(partial, root=tmp_path, defaults={"seed": 42}) == canonical(config(), root=tmp_path)
    assert canonical(config(universe={"B", "A"}), root=tmp_path) == canonical(config(universe={"A", "B"}), root=tmp_path)
    assert canonical(config(features=["A", "B"]), root=tmp_path) != canonical(config(features=["B", "A"]), root=tmp_path)
    obj, digest = canonical(config(path=tmp_path / "input.json"), root=tmp_path)
    assert obj["path"] == "input.json"
    assert digest == hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    for bad in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="finite"):
            canonical(config(commission=bad), root=tmp_path)
    with pytest.raises(ValueError, match="relative|outside"):
        canonical(config(path=tmp_path.parent / "outside.json"), root=tmp_path)

def test_lifecycle_before_callback_duplicate_error_abandoned_and_interrupted(tmp_path):
    log = ledger(tmp_path)
    run = api("trial_runner", "run_trial")
    seen = []
    def callback():
        seen.append(log.verify()["n_post_ledger"])
        return rows()
    for _ in range(2):
        run(callback, config(), ledger=log, family="example", runner="fixture", source=SOURCE, metadata=META)
    def broken():
        assert log.verify()["n_post_ledger"] == 3
        raise RuntimeError("planted error")
    with pytest.raises(RuntimeError, match="planted error"):
        run(broken, config(), ledger=log, family="example", runner="fixture", source=SOURCE, metadata=META)
    abandoned = start(log); log.finish(abandoned, "abandoned", reason="fixture")
    start(log)
    for role in ("buy_and_hold_baseline", "random_signal_baseline", "synthetic_test"):
        start(log, role)
    verified = log.verify()
    assert seen == [1, 2]
    assert verified["n_post_ledger"] == 5
    events = verified["events"]
    assert EVENT_FIELDS <= events[0].keys()
    assert events[0]["config_hash"] == events[2]["config_hash"]
    assert events[0]["trial_id"] != events[2]["trial_id"]

def test_sidecar_complete_atomic_and_bound(tmp_path):
    log = ledger(tmp_path); trial = start(log)
    result = log.finish(trial, "completed", returns=rows(), metadata=META)
    side = result["sidecar"]
    path = tmp_path / side["path"]
    assert side["rows"] == 32 and side["first_session"] == rows()[0]["session"]
    assert side["last_session"] == rows()[-1]["session"]
    assert side["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert [json.loads(x) for x in path.read_text().splitlines()] == rows()
    assert not list(path.parent.glob("*.tmp"))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="terminal|exists"):
        log.finish(trial, "completed", returns=rows(), metadata=META)
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="data/cache"):
        api("trial_registry", "TrialLedger")(tmp_path, relative_path="data/cache/trials.jsonl", synthetic=True)

@pytest.mark.parametrize("defect", ["edit", "delete", "delete_tail", "reorder", "duplicate", "truncate", "disconnect", "missing_sidecar", "corrupt_sidecar"])
def test_chain_defects_name_record_or_path(tmp_path, defect):
    log = ledger(tmp_path)
    for _ in range(3):
        log.finish(start(log), "completed", returns=rows(), metadata=META)
    assert log.verify()["n_post_ledger"] == 3  # clean control
    lines = log.path.read_bytes().splitlines(keepends=True)
    if defect == "edit":
        obj = json.loads(lines[2]); obj["runner"] = "edited"; lines[2] = json.dumps(obj).encode() + b"\n"
    elif defect == "delete": del lines[2]
    elif defect == "delete_tail": lines.pop()
    elif defect == "reorder": lines[2], lines[3] = lines[3], lines[2]
    elif defect == "duplicate": lines.insert(2, lines[2])
    elif defect == "truncate": lines[-1] = lines[-1][:-4]
    elif defect == "disconnect":
        obj = json.loads(lines[2]); obj["prev_hash"] = "0" * 64; lines[2] = json.dumps(obj).encode() + b"\n"
    else:
        side = tmp_path / json.loads(lines[1])["sidecar"]["path"]
        if defect == "missing_sidecar": side.unlink()
        else: side.write_text("corrupt")
    log.path.write_bytes(b"".join(lines))
    with pytest.raises(ValueError, match="record|returns/|anchor|partial"):
        log.verify()
    before = log.path.read_bytes()
    with pytest.raises(ValueError):
        start(log)
    assert log.path.read_bytes() == before, "recovery cannot silently truncate history"

@pytest.mark.parametrize("mode", ["detached", "loose", "packed", "missing"])
def test_source_identity_full_sha_no_subprocess(tmp_path, monkeypatch, mode):
    identity = api("trial_registry", "source_identity")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("git subprocess prohibited"))
    sha = "1" * 40
    gitdir = tmp_path / ".git"; gitdir.mkdir()
    if mode != "missing":
        (gitdir / "HEAD").write_text(sha if mode == "detached" else "ref: refs/heads/main")
    if mode == "loose":
        (gitdir / "refs/heads").mkdir(parents=True); (gitdir / "refs/heads/main").write_text(sha)
    if mode == "packed": (gitdir / "packed-refs").write_text(sha + " refs/heads/main\n")
    (tmp_path / "scripts").mkdir(); src = tmp_path / "scripts/source.py"; src.write_text("x = 1")
    before = identity(tmp_path)
    assert before["git_sha"] == (None if mode == "missing" else sha)
    assert before["workspace_state"] == "unknown"
    assert len(before["source_tree_hash"]) == 64
    src.write_text("x = 2")
    assert identity(tmp_path)["source_tree_hash"] != before["source_tree_hash"]
    assert identity(tmp_path, git_sha=sha, workspace_state="dirty")["workspace_state"] == "dirty"

def _append_worker(root):
    from spec033_support import ledger, start
    start(ledger(Path(root)))


def _crash_after_start(root):
    _append_worker(root)
    os._exit(23)


def test_process_crash_after_fsync_retains_start_without_fake_terminal(tmp_path):
    log = ledger(tmp_path)
    process = multiprocessing.get_context("spawn").Process(target=_crash_after_start, args=(str(tmp_path),))
    process.start(); process.join(30)
    assert process.exitcode == 23
    state = log.verify()
    assert state["n_post_ledger"] == 1
    assert [e["event_type"] for e in state["events"]] == ["started"]


class TestUnittestClassSetupIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from trial_runner import current_ledger
        cls.log = current_ledger()
        assert cls.log.synthetic, "class setup must receive injected ledger before any run"
        assert cls.log.root != SCRIPTS_DIR.parent

    def test_class_setup_uses_synthetic_root(self):
        self.assertTrue(self.log.synthetic)

def test_multiprocess_append_and_stale_lock(tmp_path):
    log = ledger(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    processes = [ctx.Process(target=_append_worker, args=(str(tmp_path),)) for _ in range(4)]
    for p in processes: p.start()
    for p in processes: p.join(30); assert p.exitcode == 0
    assert log.verify()["n_post_ledger"] == 4
    lock = log.path.with_suffix(".lock"); lock.write_text('{"pid": -1}')
    before = log.path.read_bytes()
    with pytest.raises(ValueError, match="lock.*recovery"):
        start(log)
    assert log.path.read_bytes() == before

def test_production_default_and_explicit_synthetic_injection(tmp_path):
    cls = api("trial_registry", "TrialLedger")
    assert cls().path == SCRIPTS_DIR.parent / "docs/trials/trials.jsonl"
    assert ledger(tmp_path).synthetic
    run = api("trial_runner", "run_trial")
    assert "record" not in inspect.signature(run).parameters
    assert not hasattr(trial_registry, "log_trial"), "retire optional compatibility writer"
    with pytest.raises(ValueError, match="synthetic"):
        cls(tmp_path)


def test_implicit_synthetic_attempts_do_not_accumulate_unrelated_class_history():
    from trial_runner import current_ledger, injected_ledger
    first, second = current_ledger(), current_ledger()
    assert first.synthetic and second.synthetic
    assert first.path != second.path
    with injected_ledger(first):
        assert current_ledger() is first
        assert current_ledger() is first
