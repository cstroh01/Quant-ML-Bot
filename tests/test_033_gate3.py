"""EXAMPLE — NOT A RESULT. Spec 033 T056/T057: Gate 3 artifact schema, reason codes, decision table.

Tests first; T062 implements `scripts/generate_gate3_evidence.py` to this contract:

- ``compose(evidence) -> artifact`` is pure. ``evidence`` carries the existing
  ``selection_bias`` outputs (``counts`` from ``lifetime_count``, ``matrix`` from
  ``build_matrix``, ``dsr`` from ``counted_dsr``, ``t_stat`` from ``hac_t_stat``,
  ``pbo`` from ``matrix_pbo``) plus selection, CV, cost and source metadata. It
  recomputes no statistic; it maps operands to a status and ordered reason codes.
- ``assess(artifact, current) -> {"status", "reason_codes"}`` re-checks currentness
  against the current ledger head, backfill, matrix and source identity (FR-043).
- ``write_artifact(artifact, root) -> str`` returns a repository-relative path and
  refuses a fixture-labelled artifact in the production directory (FR-048).

Family N (2026-10-09 amendment): the gating DSR is the family-N DSR while the family
is within its cap, else the lifetime-N DSR; the lifetime DSR is always published.
"""
import copy
import math
from pathlib import PurePosixPath

import pytest

from spec033_support import CONFIG, GATE_FIELDS, LABEL, META, REASONS, SOURCE, api, rows

pytestmark = pytest.mark.xfail(strict=True, raises=AssertionError,
                               reason="spec 033 T062 not implemented: generate_gate3_evidence missing (remove in T062)")
PRODUCTION = "reports/artifacts/capital_gate/gate3/"
UNKNOWN = {"evidence_missing", "evidence_corrupt", "ledger_invalid", "backfill_incomplete", "candidate_ineligible",
           "matrix_undefined", "dsr_undefined", "t_stat_undefined", "pbo_undefined"}


def evidence(dsr=.97, t=3.4, pbo=.25, family_dsr=None, within_cap=True):
    counts = {"reason": None, "n_backfill": 40, "n_post_ledger": 6, "n_current": 46,
              "backfill_hash": "c" * 64, "ledger_head_hash": "e" * 64, "family": None}
    family = None
    if family_dsr is not None:
        counts["family"] = {"family": "example", "n_family": 3, "cap": 50, "within_cap": within_cap,
                            "n_dsr": 3 if within_cap else 46, "reverted_to_lifetime": not within_cap}
        family = {"value": family_dsr, "reason": None, "inputs": {"n_current": 3}, "matrix_hash": "f" * 64}
    sessions = [r["session"] for r in rows()]
    return {"selected_trial": "a", "family": "example", "generated_at_utc": "2026-10-11T00:00:00Z", "label": LABEL,
            "counts": counts,
            "matrix": {"matrix_hash": "f" * 64, "dates": sessions, "columns": ["a", "b"], "excluded_trials": [], "reason": None},
            "dsr": {"lifetime": {"value": dsr, "reason": None, "inputs": {"n_current": 46}, "matrix_hash": "f" * 64},
                    "family": family, "counts": counts},
            "t_stat": {"value": t, "reason": None, "hac_lags": 5},
            "pbo": {"value": pbo, "reason": None, "S": 16, "total_splits": 12870, "valid_splits": 12870, "rank_logit_summary": None,
                    "matrix_hash": "f" * 64},
            "cv": copy.deepcopy(CONFIG["cv"]), "costs": copy.deepcopy(META["costs"]), "source_identity": copy.deepcopy(SOURCE)}


def compose(value):
    return api("generate_gate3_evidence", "compose")(value)


def current(art):
    return {k: copy.deepcopy(art[k]) for k in ("ledger_head_hash", "backfill_hash", "matrix_hash", "source_identity")}


def failed_count(e, reason):
    """Real error shapes: lifetime_count and counted_dsr return undefined(), not a partial dict."""
    e["counts"] = e["dsr"] = {"value": None, "reason": reason}


def undefined_family(e):
    """A within-cap family whose DSR is undefined must not quietly fall back to lifetime N."""
    e.update(evidence(family_dsr=.97))
    e["dsr"]["family"] = {"value": None, "reason": "matrix_family_mismatch"}


# T056 — artifact schema, ordered reason codes, evidence path and fixture labelling.

def test_artifact_carries_every_fr040_field_and_threshold_operand():
    art = compose(evidence())
    assert GATE_FIELDS <= art.keys()
    assert art["selected_trial"] == "a" and art["generated_at_utc"].endswith("Z") and art["artifact_id"]
    assert (art["dsr"]["value"], art["dsr"]["threshold"]) == (.97, .95)
    assert (art["t_stat"]["value"], art["t_stat"]["threshold"], art["t_stat"]["hac_lags"]) == (3.4, 3.0, 5)
    assert (art["pbo"]["value"], art["pbo"]["S"], art["pbo"]["valid_splits"]) == (.25, 16, 12870)
    assert (art["n_backfill"], art["n_post_ledger"], art["n_current"]) == (40, 6, 46)
    assert (art["ledger_head_hash"], art["backfill_hash"], art["matrix_hash"]) == ("e" * 64, "c" * 64, "f" * 64)
    assert (art["matrix_rows"], art["matrix_columns"]) == (32, 2)
    assert art["date_range"] == [rows()[0]["session"], rows()[-1]["session"]]
    assert (art["cv"], art["costs"], art["source_identity"]) == (CONFIG["cv"], META["costs"], SOURCE)
    assert art["dsr_lifetime"]["value"] == .97 and art["family"] is None


def test_reason_codes_are_known_and_in_frozen_order():
    value = evidence(dsr=.50)
    value["t_stat"] = {"value": None, "reason": "nonpositive_hac_se", "hac_lags": 5}
    value["pbo"].update(value=None, reason="rejected_cscv_splits")
    art = compose(value)  # frozen order differs from alphabetical on purpose
    assert art["reason_codes"] == ["t_stat_undefined", "pbo_undefined", "dsr_below_threshold"]
    assert set(art["reason_codes"]) <= set(REASONS) and art["status"] == "unknown"
    assert compose(evidence())["reason_codes"] == []


@pytest.mark.parametrize("plant, reason", [
    (lambda e: failed_count(e, "backfill_incomplete"), "backfill_incomplete"),
    (lambda e: failed_count(e, "ledger_invalid"), "ledger_invalid"),
    (lambda e: failed_count(e, "evidence_corrupt"), "evidence_corrupt"),
    (undefined_family, "dsr_undefined"),
    (lambda e: e["matrix"].update(reason="insufficient_matrix"), "matrix_undefined"),
    (lambda e: e.update(selected_trial="z"), "candidate_ineligible"),
    (lambda e: e.pop("pbo"), "evidence_missing"),
    (lambda e: e.pop("dsr"), "evidence_missing"),
])
def test_incomplete_or_unverifiable_inputs_are_unknown(plant, reason):
    value = evidence()
    plant(value)
    art = compose(value)
    assert art["status"] == "unknown" and reason in art["reason_codes"]
    assert GATE_FIELDS <= art.keys()


@pytest.mark.parametrize("stat", ["dsr", "pbo"])
def test_statistics_from_another_matrix_are_not_evidence(stat):
    value = evidence()
    (value["dsr"]["lifetime"] if stat == "dsr" else value["pbo"])["matrix_hash"] = "0" * 64
    art = compose(value)
    assert art["status"] == "unknown" and set(art["reason_codes"]) & UNKNOWN


def test_fixture_label_travels_and_production_path_is_repository_relative(tmp_path):
    labelled = compose(evidence())
    assert labelled["label"] == LABEL
    with pytest.raises(ValueError):
        api("generate_gate3_evidence", "write_artifact")(labelled, root=tmp_path)
    assert not (tmp_path / PRODUCTION).exists() or not any((tmp_path / PRODUCTION).iterdir())
    value = evidence()
    del value["label"]
    real = compose(value)
    assert "label" not in real
    path = api("generate_gate3_evidence", "write_artifact")(real, root=tmp_path)
    assert isinstance(path, str) and path.startswith(PRODUCTION) and "\\" not in path
    assert not PurePosixPath(path).is_absolute() and (tmp_path / path).is_file()


def test_family_dsr_gates_within_cap_and_lifetime_dsr_is_always_published():
    within = compose(evidence(dsr=.40, family_dsr=.97))
    assert (within["status"], within["dsr"]["value"], within["dsr_lifetime"]["value"]) == ("passed", .97, .40)
    assert within["family"]["n_dsr"] == 3 and within["n_current"] == 46
    reverted = compose(evidence(dsr=.40, family_dsr=.97, within_cap=False))
    assert (reverted["status"], reverted["reason_codes"]) == ("failed", ["dsr_below_threshold"])
    assert reverted["dsr"]["value"] == reverted["dsr_lifetime"]["value"] == .40
    assert reverted["family"]["reverted_to_lifetime"] is True


# T057 — decision table (spec "Gate Decision Table", FR-041..FR-043).

@pytest.mark.parametrize("dsr, t, pbo, status, reasons", [
    (.95, 3.0, .25, "passed", []),
    (.97, 3.4, .90, "passed", []),
    (math.nextafter(.95, 0), 3.4, .25, "failed", ["dsr_below_threshold"]),
    (.97, math.nextafter(3.0, 0), .25, "failed", ["t_stat_below_threshold"]),
    (.50, 1.0, .25, "failed", ["dsr_below_threshold", "t_stat_below_threshold"]),
    (float("nan"), 3.4, .25, "unknown", ["dsr_undefined"]),
    (.97, float("inf"), .25, "unknown", ["t_stat_undefined"]),
    (.97, 3.4, float("nan"), "unknown", ["pbo_undefined"]),
])
def test_decision_table(dsr, t, pbo, status, reasons):
    art = compose(evidence(dsr=dsr, t=t, pbo=pbo))
    assert (art["status"], art["reason_codes"]) == (status, reasons)


def test_pbo_must_be_s16_and_has_no_invented_cutoff():
    value = evidence(pbo=.99)
    assert compose(value)["status"] == "passed"
    value["pbo"]["S"] = 8
    assert (compose(value)["status"], compose(value)["reason_codes"]) == ("unknown", ["pbo_undefined"])


@pytest.mark.parametrize("field, reason", [
    ("ledger_head_hash", "ledger_changed"), ("backfill_hash", "backfill_changed"), ("matrix_hash", "matrix_changed"),
    (("source_identity", "git_sha"), "source_changed"), (("source_identity", "source_tree_hash"), "source_changed"),
])
@pytest.mark.parametrize("dsr", [.97, .50])
def test_input_mismatch_is_stale_for_passed_and_failed_evidence(field, reason, dsr):
    assess = api("generate_gate3_evidence", "assess")
    art = compose(evidence(dsr=dsr))
    assert assess(art, current(art))["status"] == art["status"] in {"passed", "failed"}
    now = current(art)
    if isinstance(field, tuple): now[field[0]][field[1]] = "9" * len(now[field[0]][field[1]])
    else: now[field] = "9" * 64
    assert assess(art, now) == {"status": "stale", "reason_codes": [reason]}


def test_unknown_evidence_stays_unknown_when_inputs_also_moved():
    assess = api("generate_gate3_evidence", "assess")
    value = evidence()
    failed_count(value, "backfill_incomplete")
    art = compose(value)
    now = current(art) | {"ledger_head_hash": "9" * 64}
    assert assess(art, now)["status"] == "unknown"
    assert set(assess(art, now)["reason_codes"]) & UNKNOWN
