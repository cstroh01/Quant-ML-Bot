"""Spec 058 T005: the preregistered family declaration gates every 058-edge trial.

EXAMPLE — NOT A RESULT. All ledger writes use injected temporary roots.
"""
import json
import re

import pytest
from context import SCRIPTS_DIR
import trial_registry
from spec033_support import config, ledger

ROOT = SCRIPTS_DIR.parent
SOURCE = ".specify/specs/058-edge-research-program/declaration.json"
FAMILY = "058-edge"


def refuses(action, witness, match="", errors=(ValueError,)):
    """Fail with the named witness unless `action` raises one of `errors` matching `match`."""
    try:
        action()
    except errors as error:
        assert re.search(match, str(error)), f"{witness} wrong refusal: {error}"
        return error
    raise AssertionError(f"{witness} did not refuse")


def seeded(tmp_path, **changes):
    """A synthetic root holding a copy of the committed declaration source."""
    target = tmp_path / SOURCE
    target.parent.mkdir(parents=True)
    body = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    body.update(changes)
    target.write_text(json.dumps(body), encoding="utf-8")
    return tmp_path


def test_committed_declaration_is_the_preregistered_table():
    body = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    ids = [c["id"] for c in body["configurations"]]
    assert body["family"] == FAMILY and body["label"].startswith("EXAMPLE"), "T005 PREREG label"
    assert len(ids) == 15 and len(set(ids)) == 15, "T005 PREREG count"
    assert len(body["universe"]) == 25 and len(set(body["universe"])) == 25, "T005 PREREG universe"
    assert (body["n_family_cap"], body["holdout_start"], body["research_end"]) == (50, "2023-10-02", "2023-09-29"), "T005 PREREG seal"
    assert {b["role"] for b in body["baselines"]} == {"buy_and_hold_baseline", "random_signal_baseline"}, "T005 PREREG baselines"


def test_start_in_family_is_refused_until_declared_then_allowed(tmp_path):
    root = seeded(tmp_path)
    log = ledger(root)
    refuses(lambda: log.start(config(), role="synthetic_test", family=FAMILY, runner="t"), "T005 REQUIRE", "declaration")
    assert log.verify()["events"] == [], "T005 REQUIRE wrote before refusing"
    record = trial_registry.declare_family(FAMILY, root=root, synthetic=True)
    assert record["declaration"]["family"] == FAMILY
    log.start(config(), role="synthetic_test", family=FAMILY, runner="t")
    assert len(log.verify()["events"]) == 1, "T005 REQUIRE declared family refused"


def test_other_families_need_no_declaration(tmp_path):
    log = ledger(tmp_path)
    log.start(config(), role="synthetic_test", family="legacy-research", runner="t")
    assert len(log.verify()["events"]) == 1, "T005 CONTROL unrelated family refused"


def test_declaration_is_write_once(tmp_path):
    root = seeded(tmp_path)
    trial_registry.declare_family(FAMILY, root=root, synthetic=True)
    before = (root / trial_registry.FAMILY_DIR / f"{FAMILY}.json").read_bytes()
    refuses(lambda: trial_registry.declare_family(FAMILY, root=root, synthetic=True), "T005 ONCE", errors=(ValueError, FileExistsError))
    assert (root / trial_registry.FAMILY_DIR / f"{FAMILY}.json").read_bytes() == before, "T005 ONCE record replaced"


def test_tampered_record_is_refused(tmp_path):
    root = seeded(tmp_path)
    trial_registry.declare_family(FAMILY, root=root, synthetic=True)
    path = root / trial_registry.FAMILY_DIR / f"{FAMILY}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["declaration"]["n_family_cap"] = 5000
    path.write_text(json.dumps(record), encoding="utf-8")
    refuses(lambda: trial_registry.verify_family(FAMILY, root=root), "T005 TAMPER", "declaration")
    refuses(lambda: ledger(root).start(config(), role="synthetic_test", family=FAMILY, runner="t"), "T005 TAMPER", "declaration")
    assert ledger(root).verify()["events"] == [], "T005 TAMPER accepted"


def test_source_naming_another_family_is_refused(tmp_path):
    root = seeded(tmp_path, family="other-family")
    refuses(lambda: trial_registry.declare_family(FAMILY, root=root, synthetic=True), "T005 FAMILY", "family")
    assert not (root / trial_registry.FAMILY_DIR).exists(), "T005 FAMILY mismatched source declared"


def test_unknown_family_cannot_be_declared(tmp_path):
    root = seeded(tmp_path)
    refuses(lambda: trial_registry.declare_family("made-up", root=root, synthetic=True), "T005 UNKNOWN", "family")


def test_production_declaration_requires_deliberate_enablement():
    target = ROOT / trial_registry.FAMILY_DIR / f"{FAMILY}.json"
    existed = target.exists()
    refuses(lambda: trial_registry.declare_family(FAMILY), "T005 ENABLE", errors=(trial_registry.LedgerWriteRefused,))
    assert target.exists() == existed, "T005 ENABLE wrote without production recording"


def test_family_status_counts_candidate_starts_against_cap(tmp_path):
    root = seeded(tmp_path, n_family_cap=2)
    trial_registry.declare_family(FAMILY, root=root, synthetic=True)
    log = ledger(root)
    for _ in range(2):
        log.start(config(), role="synthetic_test", family=FAMILY, runner="t")
    status = trial_registry.family_status(FAMILY, log)
    assert (status["n_family"], status["cap"], status["within_cap"]) == (2, 2, True), f"T005 CAP {status}"
    log.start(config(), role="synthetic_test", family=FAMILY, runner="t")
    status = trial_registry.family_status(FAMILY, log)
    assert (status["n_family"], status["within_cap"]) == (3, False), f"T005 CAP not voided {status}"


def test_cli_refuses_without_record_flag():
    import declare_family
    target = ROOT / trial_registry.FAMILY_DIR / f"{FAMILY}.json"
    existed = target.exists()
    assert declare_family.main([FAMILY]) == 2, "T005 CLI ran without --record"
    assert target.exists() == existed, "T005 CLI wrote without --record"
