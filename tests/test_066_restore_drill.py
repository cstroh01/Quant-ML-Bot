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
    connection.execute("PRAGMA journal_mode=WAL")  # as LiveSafetyGate opens it
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
    def spy(*args, **kw):  # records the drill's own scratch; SQLite copies use TemporaryDirectory
        path = real(*args, **kw)
        if kw.get("prefix") == "qmb-restore-":
            made.append(path)
        return path
    monkeypatch.setattr(rd.tempfile, "mkdtemp", spy)
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


def _write(rel, data):
    return lambda s: (s / rel).write_bytes(data)


LEASE = f"leases/{PROFILE}-2026-10-22.json"
BOTH_BROKEN = {  # the same refusable state in both copies; the runtime would not read it
    "gate db corrupt": (_corrupt_sqlite, "live-gate.sqlite"),
    "torn intent log": (_tear_intents, "intents.jsonl"),
    "intent log missing final newline": (_write("intents.jsonl", b'{"client_order_id": "x", "intent": {}}'),
                                         "intents.jsonl"),  # valid JSON, yet open_intents refuses it
    "torn lease": (_write(LEASE, b"{"), LEASE),
    "lease without run_id": (_write(LEASE, b'{"state": "running"}'), LEASE),
    "torn ownership": (_write("bot-positions.json", b'{"positions": '), "bot-positions.json"),
    "non-utf8 json": (_write("cash-basis.json", b'{"x": "\xff"}'), "cash-basis.json"),
    "torn run log": (_write("ops/runs.jsonl", b'{"profile": "live_fidelity", "session": "2026-10-22"}\n{"pro'),
                     "ops/runs.jsonl"),
    "run row without session": (_write("ops/runs.jsonl", b'{"profile": "live_fidelity"}\n'), "ops/runs.jsonl"),
    "torn incident log": (_write("ops/incidents.jsonl", b'{"kind": '), "ops/incidents.jsonl"),
}


@pytest.mark.parametrize("name", sorted(BOTH_BROKEN))
def test_identically_broken_copies_still_fail(tmp_path, primary, backup, name):
    plant, unhealthy = BOTH_BROKEN[name]
    plant(primary)
    plant(backup)
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    assert evidence["verdict"] == "FAIL" and not evidence["differing_files"], evidence
    assert unhealthy in evidence["unhealthy"], evidence


def test_wal_resident_rows_count_and_inputs_gain_no_side_files(tmp_path, primary):
    """A persisted -wal is read (rows only in the WAL change the dump); inputs never gain -wal/-shm."""
    db = primary / "live-gate.sqlite"
    clean = rd._sqlite(db)["dump_sha256"]
    writer = sqlite3.connect(db)
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("INSERT INTO reservations VALUES ('r50', 500.0)")
    writer.commit()
    copy = tmp_path / "with-wal"
    copy.mkdir()
    for suffix in ("", "-wal"):
        shutil.copyfile(db.with_name(db.name + suffix), copy / (db.name + suffix))
    writer.close()
    before = rd.manifest(copy)
    assert rd._sqlite(copy / db.name)["dump_sha256"] == rd._sqlite(db)["dump_sha256"] != clean
    assert rd.manifest(copy) == before


def test_input_changed_during_drill_refuses(tmp_path, primary, backup, monkeypatch):
    real = rd.consumer_view

    def writer_meanwhile(state, profile, now):
        (primary / "late.json").write_text("{}", encoding="utf-8")
        return real(state, profile, now)
    monkeypatch.setattr(rd, "consumer_view", writer_meanwhile)
    with pytest.raises(rd.DrillRefused, match="changed during the drill"):
        rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")


def test_due_run_counts_only_this_profiles_rows(tmp_path, primary, backup):
    for state in (primary, backup):
        (state / "ops" / "runs.jsonl").write_text(json.dumps({"profile": "paper_small", "session": "2026-10-22"})
                                                  + "\n", encoding="utf-8")
    evidence = rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    assert evidence["verdict"] == "PASS" and evidence["due_run"]["status"] == "after_cutoff"


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


def test_symlink_in_backup_or_as_root_refuses(tmp_path, primary, backup):
    try:
        os.symlink(primary / "HALTED", backup / "link")
        os.symlink(primary, tmp_path / "root-link", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(rd.DrillRefused, match="symlink"):
        rd.drill(primary, backup, profile=PROFILE, now=NOW, scratch=tmp_path / "scratch")
    (backup / "link").unlink()
    with pytest.raises(rd.DrillRefused, match="not a directory"):
        rd.drill(tmp_path / "root-link", backup, profile=PROFILE, now=NOW, scratch=tmp_path / "s2")


def test_cli_writes_evidence_and_exit_code(tmp_path, primary, backup, capsys):
    out = tmp_path / "evidence.json"
    args = ["--primary", str(primary), "--backup", str(backup), "--profile", PROFILE, "--evidence", str(out)]
    assert rd.main(args) == 0 and json.loads(out.read_text(encoding="utf-8"))["verdict"] == "PASS"
    _drop(backup / "HALTED")
    assert rd.main(args) == 1 and json.loads(out.read_text(encoding="utf-8"))["verdict"] == "FAIL"
    assert rd.main(args[:-4] + ["--profile", "../x", "--evidence", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "REFUSED"


def test_cli_records_unexpected_errors_as_refused(tmp_path, monkeypatch):
    out = tmp_path / "evidence.json"
    monkeypatch.setattr(rd, "drill", lambda *a, **k: (_ for _ in ()).throw(KeyError("session")))
    assert rd.main(["--primary", "a", "--backup", "b", "--profile", PROFILE, "--evidence", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["reason"] == "internal: KeyError"


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
