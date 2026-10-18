"""061 T006: EXAMPLE — NOT A RESULT. Fake PAPER and input fetches only."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from context import SCRIPTS_DIR

from allocation_policy import DECLARATION_HASH, POLICY_ID, TRIAL_ID, policy_evidence
from buffered_allocation import buffered_weights
from paper_targets import plan_allocation
from test_110_paper_allocation import ALL_FRACTIONAL, Client, SESSION, plan, run, sleeve_closes
from paper_loop import AllocationPlanner, RunAborted


def test_paper_targets_use_exact_buffered_rule_once():
    closes = sleeve_closes()
    frame, orders, _ = plan(closes)
    expected = buffered_weights(closes.loc[:SESSION]).loc["2026-10-01"]
    pd.testing.assert_series_equal(frame["Target"], expected, check_names=False)
    assert len(orders) == 8 and all(o.target_weight == pytest.approx(0.11625) for o in orders)
    with pytest.raises(ValueError, match="frozen spec 061 reserve"):
        plan(cash_buffer=0.0)
    with pytest.raises(ValueError, match="frozen spec 061 reserve"):
        plan(cash_buffer=0.05)


def test_policy_identity_matches_the_frozen_recorded_candidate():
    declaration = json.loads((SCRIPTS_DIR.parent / ".specify/specs/061-buffered-allocation/declaration.json").read_text(encoding="utf-8"))
    from trial_registry import digest
    assert DECLARATION_HASH == digest(declaration), "061 BINDING declaration"
    assert TRIAL_ID == "8d4dfeda-10ef-4951-bf0e-147090ea9731", "061 BINDING trial"
    assert POLICY_ID == "061-b7-ew-v1"


@pytest.mark.parametrize("allocation", [None, {}, {"policy_id": "059-a1"}])
def test_legacy_or_wrong_policy_state_refuses_without_mutation(tmp_path, allocation):
    path = tmp_path / "allocation-state.json"
    path.write_text(json.dumps({"executed_decision": "2026-10-01", "allocation": allocation}), encoding="utf-8")
    before = path.read_bytes()
    planner = AllocationPlanner(path, ALL_FRACTIONAL)
    with pytest.raises(RunAborted, match="allocation policy mismatch"):
        planner.plan(sleeve_closes(), SESSION, equity=5000.0, positions={})
    assert path.read_bytes() == before, "061 STATE no implicit migration or deletion"


def test_completed_state_and_paper_record_bind_the_new_trial(tmp_path):
    record, planner = run(tmp_path, Client())
    assert record["allocation"] == policy_evidence(), "061 RECORD allocation identity missing"
    saved = json.loads(planner.state_path.read_text(encoding="utf-8"))
    assert saved["allocation"] == policy_evidence(), "061 STATE allocation identity missing"
    again = planner.plan(sleeve_closes(), SESSION, equity=100000.0, positions={})
    assert again.orders == [] and again.allocation == policy_evidence()
    assert "7%" in record["disclosure"] and "post-hoc" in record["disclosure"]


def test_input_bundle_binds_same_trial_and_monthly_targets(tmp_path):
    import fidelity_inputs as inputs
    from test_057_q138_inputs import Fetcher, NOW, RUN
    inputs.build_bundle(tmp_path, now=NOW, session=RUN, fetcher=Fetcher())
    saved = json.loads((tmp_path / "sources.json").read_text(encoding="utf-8"))["allocation"]
    assert saved.get("trial_id") == TRIAL_ID, "061 INPUT trial binding missing"
    assert {key: saved[key] for key in policy_evidence()} == policy_evidence(), "061 INPUT binding missing"
    assert saved["decision_session"] == "2026-10-01"
    assert np.allclose(list(saved["targets"].values()), 0.11625), "061 INPUT target differs from the costed rule"
