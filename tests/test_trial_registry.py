"""Migrated prototype: the optional compatibility writer is retired."""
from context import SCRIPTS_DIR
import trial_registry
from spec033_support import ledger, start

def test_sole_authority_retains_original_production_path():
    assert trial_registry.DEFAULT_TRIALS_PATH == SCRIPTS_DIR.parent / "docs/trials/trials.jsonl"
    assert not hasattr(trial_registry, "log_trial")

def test_migrated_chain_round_trip(tmp_path):
    log = ledger(tmp_path)
    ids = [start(log) for _ in range(3)]
    assert [e["trial_id"] for e in log.verify()["events"]] == ids
