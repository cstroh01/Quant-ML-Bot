"""Spec 059 T001 (FR-001): the 059-allocation preregistration record and its declare path.

EXAMPLE — NOT A RESULT. All writes use injected temporary roots; docs/trials is never touched.
"""
import hashlib
import json
import shutil

from context import SCRIPTS_DIR
import trial_registry
from spec033_support import config, ledger

ROOT = SCRIPTS_DIR.parent
FAMILY = "059-allocation"
SOURCE = ".specify/specs/059-live-allocation/declaration.json"


def body():
    return json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))


def seeded(tmp_path):
    target = tmp_path / SOURCE
    target.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / SOURCE, target)
    return tmp_path


def test_family_is_registered_to_its_declaration():
    assert trial_registry.DECLARED_FAMILIES.get(FAMILY) == SOURCE, "T001 REGISTER family missing"
    assert body()["family"] == FAMILY, "T001 REGISTER source names another family"


def test_declaration_matches_the_preregistered_rule():
    from signals import ALLOCATION_SLEEVES
    import portfolio_risk
    from cost_model import CONVENTIONS
    from allocation_report import LABEL
    d = body()
    assert tuple(d["universe"]) == ALLOCATION_SLEEVES, f"T001 RULE sleeves {d['universe']}"
    common = d["common"]
    assert common["portfolio_vol_target_annual"] == portfolio_risk.ALLOCATION_TARGET_VOLATILITY, "T001 RULE vol target"
    assert f"span {portfolio_risk.ALLOCATION_SPAN}" in common["asset_vol"], "T001 RULE span"
    assert (common["gross_cap"], common["long_only"]) == (1.0, True), "T001 RULE gross/long-only"
    assert common["cost_model_version"] == CONVENTIONS["estimator_version"], "T001 RULE cost model version"
    assert d["report"]["label"] == LABEL and LABEL in d["label"], "T001 RULE label"
    assert d["research_end"] == "2023-09-29" and 1 <= d["n_family_cap"] <= 50, "T001 RULE window/cap"
    assert len(d["configurations"]) == 1, "T001 RULE one configuration"
    assert {b["role"] for b in d["baselines"]} == {"buy_and_hold_baseline", "random_signal_baseline"}, "T001 RULE baselines"


def test_declaration_hashes_the_spec_it_preregisters():
    d = body()
    digest = hashlib.sha256((ROOT / d["spec"]).read_bytes()).hexdigest()
    assert d["spec_sha256"] == digest, ("T001 SPEC spec.md changed after preregistration; "
                                        "spec 059 §3 forbids edits without a new spec number")


def test_start_refused_until_declared_then_allowed(tmp_path):
    root = seeded(tmp_path)
    log = ledger(root)
    try:
        log.start(config(), role="synthetic_test", family=FAMILY, runner="t")
    except ValueError as error:
        assert "declaration" in str(error), f"T001 REQUIRE wrong refusal: {error}"
    else:
        raise AssertionError("T001 REQUIRE start before declaration accepted")
    record = trial_registry.declare_family(FAMILY, root=root, synthetic=True)
    assert record["declaration"]["universe"] == body()["universe"], "T001 REQUIRE record body"
    log.start(config(), role="synthetic_test", family=FAMILY, runner="t")
    assert len(log.verify()["events"]) == 1, "T001 REQUIRE declared family refused"


def test_cli_offers_the_family_and_refuses_without_record_flag():
    import declare_family
    target = ROOT / trial_registry.FAMILY_DIR / f"{FAMILY}.json"
    existed = target.exists()
    try:
        code = declare_family.main([FAMILY])
    except BaseException as error:  # noqa: BLE001 - argparse rejection or a write both fail the contract
        raise AssertionError(f"T001 CLI {error!r}") from error
    assert code == 2 and target.exists() == existed, "T001 CLI ran without --record"
