"""EXAMPLE — NOT A RESULT. Hand-calculated campaign arithmetic."""
import copy
import json
import pytest
from context import SCRIPTS_DIR
from spec033_support import api, BACKFILL_FIELDS

def campaign(name="grid"):
    return dict(campaign_id=name, description="EXAMPLE — NOT A RESULT", evidence=["tests/test_033_backfill.py"], dimensions={"models": 2, "features": 3}, cartesian_upper_bound=6, rerun_upper_bound=2, remembered_range=[10, 15], chosen_upper_bound=15, unresolved_reason=None)

def manifest():
    return {"campaigns": [campaign(), campaign("same-config-other-campaign")], "approval": {"author": "synthetic Camden", "approved_at_utc": "2026-09-22T00:00:00+00:00"}, "label": "EXAMPLE — NOT A RESULT"}

@pytest.mark.parametrize("missing", sorted(BACKFILL_FIELDS))
def test_campaign_schema(missing):
    calculate = api("trial_backfill", "calculate_backfill")
    value = manifest(); del value["campaigns"][0][missing]
    with pytest.raises(ValueError, match=missing): calculate(value)

def test_cartesian_add_upper_endpoint_round_then_double():
    calculate = api("trial_backfill", "calculate_backfill")
    result = calculate(manifest())
    assert result["campaign_bounds"] == [15, 15]
    assert result["raw_upper_bound"] == 30
    assert result["rounded_upper_bound"] == 32
    assert result["n_backfill"] == 64
    assert result["status"] == "complete"

def test_no_downward_supersession_no_optimistic_unknown_fallback():
    calculate = api("trial_backfill", "calculate_backfill")
    assert calculate(manifest(), previous_counts=[128, 64])["n_backfill"] == 128
    value = manifest(); value["campaigns"][0].update(rerun_upper_bound=None, chosen_upper_bound=None, unresolved_reason="forgotten reruns")
    result = calculate(value)
    assert result["status"] == "incomplete" and result["n_backfill"] is None
    value = manifest(); value["approval"] = None
    assert calculate(value)["status"] == "incomplete"

def test_invalid_cartesian_and_understated_chosen_bound():
    calculate = api("trial_backfill", "calculate_backfill")
    for field, value in (("cartesian_upper_bound", 5), ("chosen_upper_bound", 12)):
        m = manifest(); m["campaigns"][0][field] = value
        with pytest.raises(ValueError, match="bound"): calculate(m)


def test_immutable_supersession_reads_prior_counts_without_caller_reminder(tmp_path):
    write = api("trial_backfill", "write_backfill")
    first = write(tmp_path, manifest(), previous_counts=[128])
    original = first.read_bytes()
    second = write(tmp_path, manifest())
    assert second != first
    assert first.read_bytes() == original
    assert json.loads(second.read_bytes())["n_backfill"] == 128
    assert not list(tmp_path.rglob("*.jsonl")), "backfill must create no return sidecars"


def test_t033_backfill_changes_count_without_inventing_return_evidence(tmp_path):
    """EXAMPLE — NOT A RESULT. Two candidate starts; backfill 64 -> 128."""
    import hashlib
    from spec033_support import ledger, start, rows, META, CONFIG
    from selection_bias import build_matrix, lifetime_count
    from trial_backfill import write_backfill

    log = ledger(tmp_path)
    for seed in (1, 2):
        identity = start(log, seed=seed)
        log.finish(identity, "completed", returns=rows(), metadata=META)

    def matrix():
        trials = []
        for event in log.verify()["events"]:
            if event["event_type"] == "completed":
                payload = (tmp_path / event["sidecar"]["path"]).read_bytes()
                trials.append({**event, "returns": [json.loads(line) for line in payload.splitlines()]})
        return build_matrix(trials, family={"id": "example", "alignment": "exact_intersection",
                            "min_coverage": .95, "objective": "daily_sharpe", "risk_free": CONFIG["risk_free"]})

    def sidecars():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (tmp_path / "docs/trials/returns").rglob("*") if p.is_file()}

    first_path = write_backfill(tmp_path, manifest())
    first_bytes = first_path.read_bytes()
    first = json.loads(first_bytes)
    before = lifetime_count(first, log)
    original_matrix, original_sidecars, original_ledger = matrix(), sidecars(), log.path.read_bytes()
    assert original_matrix["reason"] is None and len(original_matrix["columns"]) == 2, "T033 MATRIX control"
    assert len(original_sidecars) == 2, "T033 RETURNS control"
    assert (before["n_backfill"], before["n_post_ledger"], before["n_current"]) == (64, 2, 66), "T033 COUNT before"

    updated = json.loads(write_backfill(tmp_path, manifest(), previous_counts=[128]).read_bytes())
    after = lifetime_count(updated, log)
    assert (after["n_backfill"], after["n_post_ledger"], after["n_current"]) == (128, 2, 130), "T033 COUNT after"
    assert before["reason"] is None and after["reason"] is None
    assert first_path.read_bytes() == first_bytes, "T033 IMMUTABLE prior backfill"
    assert matrix() == original_matrix, "T033 MATRIX backfill invented return columns or changed identity"
    assert sidecars() == original_sidecars, "T033 RETURNS backfill fabricated or changed a sidecar"
    assert log.path.read_bytes() == original_ledger, "T033 LEDGER backfill changed selection history"
