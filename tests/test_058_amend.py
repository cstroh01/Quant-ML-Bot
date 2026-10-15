"""Spec 058 T006a: additions-only amendment records and the source drift check.

EXAMPLE — NOT A RESULT. Every write uses an injected temporary root; docs/trials is never touched.
Camden's decision: "A" (chat, 2026-10-12 20:57 CT) — amend rather than redeclare.
"""
import json
import re

from context import SCRIPTS_DIR
import trial_registry
from spec033_support import config, ledger

ROOT = SCRIPTS_DIR.parent
SOURCE = ".specify/specs/058-edge-research-program/declaration.json"
FAMILY = "058-edge"


def refuses(action, witness, match="", errors=(ValueError,)):
    try:
        action()
    except errors as error:
        assert re.search(match, str(error)), f"{witness} wrong refusal: {error}"
        return error
    raise AssertionError(f"{witness} did not refuse")


def committed():
    return json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))


def write_source(root, body):
    target = root / SOURCE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(body), encoding="utf-8")


def frozen_before_d8_d9(tmp_path):
    """A root declared the way 2026-10-09 was (no gate3, no common.sizing), then given today's source."""
    old = committed()
    old.pop("gate3"); old["common"].pop("sizing")
    write_source(tmp_path, old)
    trial_registry.declare_family(FAMILY, root=tmp_path, synthetic=True)
    write_source(tmp_path, committed())
    return tmp_path


def amend(root):
    return trial_registry.amend_family(FAMILY, root=root, synthetic=True)


def test_additions_are_recorded_and_become_the_effective_declaration(tmp_path):
    root = frozen_before_d8_d9(tmp_path)
    record = amend(root)
    assert sorted(record["added"]) == ["common/sizing", "gate3"], f"T006a ADD {sorted(record['added'])}"
    effective = trial_registry.verify_family(FAMILY, root=root)["declaration"]
    assert effective["gate3"] == committed()["gate3"], "T006a ADD gate3 missing from effective declaration"
    assert effective["common"]["sizing"] == committed()["common"]["sizing"], "T006a ADD sizing missing"
    log = ledger(root)
    log.start(config(), role="synthetic_test", family=FAMILY, runner="t")
    assert len(log.verify()["events"]) == 1, "T006a ADD amended family refused a start"


def test_source_drift_without_amendment_is_refused(tmp_path):
    root = frozen_before_d8_d9(tmp_path)
    error = refuses(lambda: trial_registry.verify_family(FAMILY, root=root), "T006a DRIFT", "drifted")
    assert "common/sizing" in str(error) and "amend_family.py" in str(error), f"T006a DRIFT message {error}"
    refuses(lambda: ledger(root).start(config(), role="synthetic_test", family=FAMILY, runner="t"), "T006a DRIFT", "drifted")
    assert ledger(root).verify()["events"] == [], "T006a DRIFT start written"


def test_changing_a_frozen_value_is_refused(tmp_path):
    for key, change in (("holdout_start", lambda b: b.update(holdout_start="2023-01-03")),
                        ("configurations", lambda b: b["configurations"][0].update(k=99)),
                        ("common/asset_vol", lambda b: b["common"].update(asset_vol="changed"))):
        root = frozen_before_d8_d9(tmp_path / key.replace("/", "_"))
        body = committed(); change(body); write_source(root, body)
        refuses(lambda: amend(root), "T006a VALUE", re.escape(key) + ".*changes")
        assert not list((root / trial_registry.FAMILY_DIR).glob("*.amend-*")), "T006a VALUE amendment written"


def test_removing_a_frozen_key_is_refused(tmp_path):
    root = frozen_before_d8_d9(tmp_path)
    body = committed(); body.pop("voiding"); write_source(root, body)
    refuses(lambda: amend(root), "T006a REMOVE", "voiding.*removed")


def test_amendment_after_a_trial_is_refused(tmp_path):
    old = committed(); old.pop("gate3")
    write_source(tmp_path, old)
    trial_registry.declare_family(FAMILY, root=tmp_path, synthetic=True)
    ledger(tmp_path).start(config(), role="synthetic_test", family=FAMILY, runner="t")
    write_source(tmp_path, committed() | {"common": old["common"]})
    refuses(lambda: amend(tmp_path), "T006a TRIAL", "already has trials")
    assert not list((tmp_path / trial_registry.FAMILY_DIR).glob("*.amend-*")), "T006a TRIAL amendment written"


def test_nothing_to_amend_is_refused(tmp_path):
    write_source(tmp_path, committed())
    trial_registry.declare_family(FAMILY, root=tmp_path, synthetic=True)
    refuses(lambda: amend(tmp_path), "T006a EMPTY", "adds nothing")


def test_second_amendment_chains_and_tampering_is_refused(tmp_path):
    root = tmp_path
    old = committed(); old.pop("gate3"); old["common"].pop("sizing")
    write_source(root, old)
    first_record = trial_registry.declare_family(FAMILY, root=root, synthetic=True)
    step = json.loads(json.dumps(old)); step["gate3"] = committed()["gate3"]; write_source(root, step)
    one = amend(root)
    write_source(root, committed())
    two = amend(root)
    assert (one["amendment_index"], two["amendment_index"]) == (1, 2), "T006a CHAIN index"
    assert one["previous_record_hash"] == first_record["record_hash"], "T006a CHAIN first link"
    assert two["previous_record_hash"] == one["record_hash"], "T006a CHAIN second link"
    try:
        verified = trial_registry.verify_family(FAMILY, root=root)
    except ValueError as error:
        raise AssertionError(f"T006a CHAIN valid chain refused: {error}") from error
    assert len(verified["anchors"]) == 3 and "gate3" in verified["declaration"], "T006a CHAIN anchors"
    folder = root / trial_registry.FAMILY_DIR
    first, second = folder / f"{FAMILY}.amend-1.json", folder / f"{FAMILY}.amend-2.json"
    a, b = first.read_bytes(), second.read_bytes()
    forged = json.loads(a); forged.pop("record_hash"); forged["previous_record_hash"] = "0" * 64
    forged["record_hash"] = trial_registry.digest(forged)
    first.write_text(json.dumps(forged), encoding="utf-8")
    refuses(lambda: trial_registry.verify_family(FAMILY, root=root), "T006a CHAIN link", "amendment 1")
    tampered = json.loads(a); tampered["added"]["gate3"]["hac_lags"] = 1
    first.write_text(json.dumps(tampered), encoding="utf-8")
    refuses(lambda: trial_registry.verify_family(FAMILY, root=root), "T006a CHAIN tamper", "amendment 1")
    first.write_bytes(b); second.write_bytes(a)  # swapped order
    refuses(lambda: trial_registry.verify_family(FAMILY, root=root), "T006a CHAIN order", "amendment 1")
    first.write_bytes(a); second.unlink()
    refuses(lambda: trial_registry.verify_family(FAMILY, root=root), "T006a CHAIN missing", "drifted")
    first.unlink(); second.write_bytes(b)
    refuses(lambda: trial_registry.verify_family(FAMILY, root=root), "T006a CHAIN gap", "contiguous")


def test_production_amendment_requires_deliberate_enablement():
    folder = ROOT / trial_registry.FAMILY_DIR
    before = sorted(p.name for p in folder.iterdir())
    try:
        trial_registry.amend_family(FAMILY)
    except Exception as error:  # noqa: BLE001 - any other refusal means the guard did not fire first
        assert isinstance(error, trial_registry.LedgerWriteRefused), f"T006a ENABLE guard did not refuse first: {error!r}"
    else:
        raise AssertionError("T006a ENABLE did not refuse")
    assert sorted(p.name for p in folder.iterdir()) == before, "T006a ENABLE wrote without production recording"


def test_cli_refuses_without_record_flag():
    import amend_family
    folder = ROOT / trial_registry.FAMILY_DIR
    before = sorted(p.name for p in folder.iterdir())
    try:
        code = amend_family.main([FAMILY])
    except Exception as error:  # noqa: BLE001 - reaching the writer at all means the flag was ignored
        raise AssertionError(f"T006a CLI ran without --record: {error!r}") from error
    assert code == 2, "T006a CLI ran without --record"
    assert sorted(p.name for p in folder.iterdir()) == before, "T006a CLI wrote without --record"


def test_committed_state_is_consistent():
    """Before Camden records T006a the real source drifts by exactly D-8/D-9; after, it verifies."""
    folder = ROOT / trial_registry.FAMILY_DIR
    if list(folder.glob(f"{FAMILY}.amend-*.json")):
        trial_registry.verify_family(FAMILY)
        return
    refuses(lambda: trial_registry.verify_family(FAMILY), "T006a REAL", "drifted")
    frozen = trial_registry._verified_family(FAMILY, ROOT)["declaration"]
    assert sorted(trial_registry._additions(frozen, committed(), FAMILY)) == ["common/sizing", "gate3"], "T006a REAL additions"
