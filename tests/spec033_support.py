"""EXAMPLE — NOT A RESULT. Frozen spec-033 contracts and synthetic inputs."""
import copy
import importlib
import importlib.util
from pathlib import Path

LABEL = "EXAMPLE — NOT A RESULT"
EVENT_FIELDS = set("schema_version event_id trial_id event_type timestamp_utc role family runner config config_hash source prev_hash record_hash".split())
RETURN_FIELDS = {"session", "log_return"}
BACKFILL_FIELDS = set("campaign_id description evidence dimensions cartesian_upper_bound rerun_upper_bound remembered_range chosen_upper_bound unresolved_reason".split())
MATRIX_FIELDS = set("dates columns values excluded_trials family matrix_hash convention".split())
GATE_FIELDS = set("schema_version artifact_id generated_at_utc selected_trial status reason_codes ledger_head_hash n_backfill n_post_ledger n_current backfill_hash matrix_hash matrix_rows matrix_columns date_range excluded_trials dsr t_stat pbo cv costs source_identity".split())
REASONS = ("evidence_missing", "evidence_corrupt", "ledger_invalid", "backfill_incomplete", "candidate_ineligible", "matrix_undefined", "dsr_undefined", "t_stat_undefined", "pbo_undefined", "ledger_changed", "backfill_changed", "matrix_changed", "source_changed", "dsr_below_threshold", "t_stat_below_threshold")
CONFIG = dict(data={"sha256": "d" * 64, "price_basis": "unadjusted_dollars", "corporate_actions_verified": True}, universe=["AAPL"], date_range=["2020-01-02", "2020-02-18"], features=["momentum"], transforms=[], target={"label": "return", "horizon": 1}, model={"name": "example", "params": {}}, cv={"scheme": "purged_embargoed_walk_forward", "folds": 2, "purge": 1, "embargo": 1}, seed=42, initial_capital=10000., commission=1., slippage={"model": "spread_plus_sqrt_impact", "source": "synthetic fixture"}, liquidation=False, risk_free={"annual_rate": 0., "days_per_year": 252, "source": LABEL})
SOURCE = {"git_sha": "a" * 40, "workspace_state": "unknown", "source_tree_hash": "b" * 64}
META = {"frequency": "daily", "return_convention": "funded_account_log", "net_costs": True, "oos": True, "cv": CONFIG["cv"], "costs": {"commission": 1., "slippage": CONFIG["slippage"]}}

def api(module, name):
    assert importlib.util.find_spec(module), f"missing spec-033 behavior: {module}.{name}"
    obj = getattr(importlib.import_module(module), name, None)
    assert callable(obj), f"missing spec-033 behavior: {module}.{name}"
    return obj

def config(**changes):
    value = copy.deepcopy(CONFIG)
    value.update(changes)
    return value

def ledger(tmp_path):
    return api("trial_registry", "TrialLedger")(tmp_path, synthetic=True)

def rows(n=32):
    import pandas as pd
    return [{"session": d.strftime("%Y-%m-%d"), "log_return": .01 + (-1)**i * .02} for i, d in enumerate(pd.bdate_range("2020-01-02", periods=n))]

def start(log, role="candidate", **changes):
    return log.start(config(**changes), role=role, family="example", runner="fixture", source=SOURCE)
