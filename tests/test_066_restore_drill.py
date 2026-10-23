"""066: restore drill — a backup restores into an isolated copy every consumer reads identically.

EXAMPLE — NOT A RESULT. Synthetic state built with the real lease/intent writers and a real
SQLite file; no network, no broker.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import restore_drill as rd  # noqa: E402
from ops_runtime import acquire_lease, complete_lease, record_intent  # noqa: E402

PROFILE = "live_fidelity"
SESSION = date(2026, 10, 22)  # Thursday, an NYSE session
NOW = datetime(2026, 10, 22, 14, 10, tzinfo=timezone.utc)  # 10:10 ET: after the PAPER cutoff


def build_state(root: Path) -> Path:
    state = root / PROFILE
    state.mkdir(parents=True)
    acquire_lease(state, PROFILE, SESSION, run_id="run-1")
    complete_lease(state, PROFILE, SESSION, run_id="run-1")
    record_intent(state, "live_fidelity-20261022-SPY-B", {"ticker": "SPY", "side": "buy", "qty": 0.04})
    (state / "bot-positions.json").write_text(json.dumps({"positions": {"SPY": 0.04}, "orders": {}}), encoding="utf-8")
    (state / "cash-basis.json").write_text(json.dumps({"session": "2026-10-22", "settled_cash": 181.4}),
                                           encoding="utf-8")
    (state / "HALTED").write_text("daily loss cap\n", encoding="utf-8")
    (state / "ops").mkdir()
    (state / "ops" / "runs.jsonl").write_text(json.dumps({"profile": PROFILE, "session": "2026-10-22"}) + "\n",
                                              encoding="utf-8")
    connection = sqlite3.connect(state / "live-gate.sqlite")
    connection.execute("CREATE TABLE reservations (id TEXT PRIMARY KEY, notional REAL)")
    connection.executemany("INSERT INTO reservations VALUES (?, ?)", [(f"r{i}", 10.0 * i) for i in range(50)])
    connection.commit()
    connection.close()
    return state


@pytest.fixture
def primary(tmp_path):
    return build_state(tmp_path / "ops-state")


@pytest.fixture
def backup(tmp_path, primary):
    target = tmp_path / "artifact"
    shutil.copytree(primary, target)
    return target


def test_faithful_backup_passes_and_leaves_inputs_untouched(tmp_path, primary, backup):
    before = (rd.manifest(primary), rd.manifest(backup))
    scratch = tmp_path / "scratch"
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=scratch)
    assert evidence["verdict"] == "PASS", evidence
    assert evidence["latches"] == ["HALTED"] and evidence["leases"] == [f"{PROFILE}-2026-10-22.json"]
    assert evidence["open_intents"] == 1 and evidence["due_run"] == {"status": "done", "session": "2026-10-22"}
    assert evidence["sqlite"] == ["live-gate.sqlite"] and evidence["files"] == len(before[0])
    assert (rd.manifest(primary), rd.manifest(backup)) == before
    assert rd.manifest(scratch / PROFILE) == before[0]  # the restored copy itself is byte-identical


def test_owned_scratch_is_removed(primary, backup, monkeypatch, tmp_path):
    made = []
    real = rd.tempfile.mkdtemp
    monkeypatch.setattr(rd.tempfile, "mkdtemp", lambda **kw: made.append(real(dir=tmp_path, **kw)) or made[-1])
    assert rd.drill(primary, backup, profile=PROFILE, now=NOW)["verdict"] == "PASS"
    assert len(made) == 1 and not Path(made[0]).exists()


def _drop(path):
    path.unlink()


def _tear_intents(state):
    with open(state / "intents.jsonl", "a", encoding="utf-8") as stream:
        stream.write('{"client_order_id": "x"')


def _corrupt_sqlite(state):
    data = bytearray((state / "live-gate.sqlite").read_bytes())
    data[4096:4200] = b"\xff" * 104  # inside the table's b-tree page
    (state / "live-gate.sqlite").write_bytes(bytes(data))


DEFECTS = {
    "latch lost": (lambda s: _drop(s / "HALTED"), "latches"),
    "lease lost": (lambda s: _drop(s / "leases" / f"{PROFILE}-2026-10-22.json"), "leases"),
    "torn intent log": (_tear_intents, "open_intents"),
    "ownership changed": (lambda s: (s / "bot-positions.json").write_text(
        json.dumps({"positions": {"SPY": 0.05}, "orders": {}}), encoding="utf-8"), "json"),
    "run log lost": (lambda s: (s / "ops" / "runs.jsonl").write_text("", encoding="utf-8"), "due_run"),
    "gate db corrupt": (_corrupt_sqlite, "sqlite"),
}


@pytest.mark.parametrize("name", sorted(DEFECTS))
def test_each_defective_backup_fails_on_its_consumer(tmp_path, primary, backup, name):
    plant, view = DEFECTS[name]
    plant(backup)
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    assert evidence["verdict"] == "FAIL" and evidence["differing_files"], evidence
    assert view in evidence["differing_views"], evidence


def test_extra_file_in_backup_fails_byte_comparison(tmp_path, primary, backup):
    (backup / "stray.txt").write_text("x", encoding="utf-8")
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    assert evidence["verdict"] == "FAIL" and evidence["differing_files"] == ["stray.txt"]


def test_corrupt_gate_in_both_copies_still_fails(tmp_path, primary, backup):
    _corrupt_sqlite(primary)
    _corrupt_sqlite(backup)
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    assert evidence["verdict"] == "FAIL" and evidence["unhealthy_sqlite"] == ["live-gate.sqlite"]


@pytest.mark.parametrize("profile", ["../paper_small", "Live", "con"])
def test_non_portable_profile_refuses(tmp_path, primary, backup, profile):
    with pytest.raises(ValueError):
        rd.drill(primary, backup, profile=profile, now=NOW, scratch=tmp_path / "scratch")


def test_naive_clock_and_empty_backup_refuse(tmp_path, primary):
    with pytest.raises(rd.DrillRefused):
        rd.drill(primary, primary, profile=PROFILE, now=NOW.replace(tzinfo=None))
    (tmp_path / "empty").mkdir()
    with pytest.raises(rd.DrillRefused, match="empty"):
        rd.drill(primary, tmp_path / "empty", profile=PROFILE, now=NOW)


def test_symlink_in_backup_refuses(tmp_path, primary, backup):
    try:
        os.symlink(primary / "HALTED", backup / "link")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(rd.DrillRefused, match="symlink"):
        rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")


def test_cli_writes_evidence_and_exit_code(tmp_path, primary, backup, capsys):
    out = tmp_path / "evidence.json"
    args = ["--primary", str(primary), "--backup", str(backup), "--profile", PROFILE, "--evidence", str(out)]
    assert rd.main(args) == 0 and json.loads(out.read_text(encoding="utf-8"))["verdict"] == "PASS"
    _drop(backup / "HALTED")
    assert rd.main(args) == 1 and json.loads(out.read_text(encoding="utf-8"))["verdict"] == "FAIL"
    assert rd.main(args[:-4] + ["--profile", "../x", "--evidence", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "REFUSED"


def test_torn_intent_log_in_both_copies_still_fails(tmp_path, primary, backup):
    _tear_intents(primary)
    _tear_intents(backup)
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    assert evidence["verdict"] == "FAIL" and evidence["open_intents"] == "corrupt"


def test_restore_that_reads_differently_at_its_new_location_fails(tmp_path, primary, backup, monkeypatch):
    """Byte-identical but path-dependent state (e.g. an absolute path inside) must still fail."""
    real = rd.consumer_view

    def located(state, profile, now):
        view = real(state, profile, now)
        return dict(view, leases={}) if "scratch" in str(state) else view
    monkeypatch.setattr(rd, "consumer_view", located)
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    assert evidence["verdict"] == "FAIL" and evidence["differing_files"] == []
    assert evidence["differing_views"] == ["leases"]


def test_workflow_template_is_dispatch_only_and_read_only():
    text = (ROOT / "ops" / "workflows" / "restore-drill.yml").read_text(encoding="utf-8")
    body = "\n".join(line.split("#", 1)[0] for line in text.splitlines())  # comments may name what is absent
    assert "workflow_dispatch:" in body and "schedule:" not in body and "concurrency:" not in body
    assert "permissions:\n  contents: read\n  actions: read\n" in body and ": write" not in body
    for forbidden in ("secrets.", "persist_state", "git push", "issue create", "--submit", "exec/"):
        assert forbidden not in body, forbidden
    uses = [line.split("uses:", 1)[1].strip() for line in body.splitlines() if "uses:" in line]
    assert uses and all(len(u.split("@", 1)[1]) == 40 for u in uses), uses
    assert body.count("persist-credentials: false") == 2
    assert "scripts/restore_drill.py" in body
