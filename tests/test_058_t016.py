"""Spec 058 T016 (D-3, D-4, D-7): holdout spend in the ledger, holdout data check, D-4 verdict.

EXAMPLE — NOT A RESULT. Synthetic ledgers under tmp_path and synthetic frames only.
"""
from datetime import date
import math

import pandas as pd
import pytest

import context  # noqa: F401
import data_sources
import run_058_t016 as t016
from data_sources import HoldoutSealError
from spec033_support import config, ledger, rows, start


def test_holdout_start_is_one_shot_per_family(tmp_path):
    log = ledger(tmp_path)
    start(log, role="holdout")
    with pytest.raises(ValueError, match="already spent"):
        start(log, role="holdout")


def test_a_holdout_start_never_counts_toward_n(tmp_path):
    log = ledger(tmp_path)
    start(log)
    start(log, role="holdout")
    assert log.verify()["n_post_ledger"] == 1, "D-7 holdout counted as a candidate"


def test_verify_rejects_a_second_holdout_start_written_around_the_api(tmp_path):
    import json
    import trial_registry
    log = ledger(tmp_path)
    start(log, role="holdout")
    events = log.verify()["events"]
    forged = {k: v for k, v in events[0].items() if k != "record_hash"}
    forged.update(trial_id="00000000-0000-4000-8000-000000000001", event_id="00000000-0000-4000-8000-000000000002",
                  prev_hash=events[-1]["record_hash"])
    forged["record_hash"] = trial_registry.digest(forged)
    with log.path.open("ab") as handle:
        handle.write(trial_registry.canonical_json(forged) + b"\n")
    log.anchor.write_bytes(trial_registry.canonical_json({"head": forged["record_hash"], "records": 2}))
    with pytest.raises(ValueError, match="second holdout"):
        log.verify()


def test_open_holdout_requires_one_unfinished_spend_bound_to_the_hash(tmp_path):
    log = ledger(tmp_path)
    with pytest.raises(HoldoutSealError, match="no holdout-spend"):
        data_sources._require_open_holdout(log, family="example", config_hash="x" * 64)
    trial = start(log, role="holdout")
    spend = log.verify()["events"][0]
    with pytest.raises(HoldoutSealError, match="different configuration"):
        data_sources._require_open_holdout(log, family="example", config_hash="0" * 64)
    assert data_sources._require_open_holdout(log, family="example", config_hash=spend["config_hash"])["trial_id"] == trial
    log.finish(trial, "errored", reason="fixture")
    with pytest.raises(HoldoutSealError, match="already been run"):
        data_sources._require_open_holdout(log, family="example", config_hash=spend["config_hash"])


def _tiingo(sessions, closes, div=None):
    index = pd.DatetimeIndex(pd.to_datetime(sessions))
    return pd.DataFrame({"open": closes, "close": closes, "divCash": div or [0.0] * len(closes),
                         "splitFactor": [1.0] * len(closes)}, index=index)


def test_holdout_check_flags_gaps_mismatches_and_single_source_actions():
    sessions = ["2023-10-02", "2023-10-03", "2023-10-05", "2023-10-07"]  # 10-04 missing; 10-07 is a Saturday
    tiingo = {"SPY": _tiingo(sessions, [100.0, 101.0, 102.0, 103.0], div=[0.0, 0.0, 1.0, 0.0])}
    alpaca = {"SPY": pd.Series([100.0, 101.5, 102.0], index=pd.DatetimeIndex(pd.to_datetime(sessions[:3])))}
    check = data_sources.check_058_holdout_rows(tiingo, alpaca, holdout_end=date(2023, 10, 6))
    spy = check["tickers"]["SPY"]
    assert spy["calendar_gaps"] == ["2023-10-04", "2023-10-06"], f"holdout GAP {spy}"
    assert spy["close_mismatched_sessions"] == ["2023-10-03"], f"holdout CLOSE {spy}"
    assert spy["single_source_action_sessions"] == ["2023-10-05"], f"holdout ACTION {spy}"
    assert spy["excluded_sessions"] == ["2023-10-03"] and spy["rows"] == 3, f"holdout EXCLUDE {spy}"
    assert "price" not in str(check).lower().replace("price_", ""), "holdout check must carry counts/dates only"


def test_d4_needs_positive_sharpe_and_one_sided_t():
    policy = {"risk_free": {"annual_rate": 0.0, "days_per_year": 252}, "horizon": 1, "hac_lags": 21}
    days = pd.bdate_range("2023-10-02", periods=500)
    strong = [{"session": d.strftime("%Y-%m-%d"), "log_return": 0.002 + 0.001 * math.sin(i)} for i, d in enumerate(days)]
    flat = [{"session": d.strftime("%Y-%m-%d"), "log_return": 0.0001 * (-1) ** i} for i, d in enumerate(days)]
    import numpy as np
    noise = np.random.default_rng(20261016).normal(0.0, 0.01, len(days))
    noise = noise - noise.mean() + 0.0002  # positive mean, tiny relative to the noise: Sharpe > 0, t well under 1.645
    weak = [{"session": d.strftime("%Y-%m-%d"), "log_return": float(x)} for d, x in zip(days, noise)]
    assert t016.d4(strong, policy)["pass"], "D-4 strong series failed"
    assert not t016.d4(flat, policy)["pass"], "D-4 zero-mean series passed"
    verdict = t016.d4(weak, policy)
    assert verdict["annualized_net_excess_sharpe"] > 0 and verdict["hac_t"]["value"] < 1.645 and not verdict["pass"], \
        f"D-4 must need BOTH conditions {verdict}"


def test_selection_picks_highest_family_dsr_and_breaks_ties_by_declared_order(monkeypatch, tmp_path):
    table = {"H1-3": 0.2, "H4": 0.5, "H10": 0.5}
    order = {c: i for i, c in enumerate(t016.RUN_ORDER)}
    rows_ = [{"order": order[c], "config": c, "family_dsr": v} for c, v in table.items()]
    assert t016.pick(rows_)["config"] == "H4", "selection tie must go to the lower declared ID"
    assert t016.pick(list(reversed(rows_)))["config"] == "H4", "selection must not depend on row order"


def test_holdout_config_binds_the_selected_trial_and_window():
    selected = {"config": config(model={"name": "H10", "params": {}})}
    chosen = {"rule": t016.SELECTION_RULE, "rows": [], "n_family": 15, "ledger_head_hash": "h" * 64,
              "selected": {"trial_id": "t", "config": "H10", "config_hash": "c" * 64}}
    cfg = t016.holdout_config(selected, chosen=chosen, holdout_end=date(2026, 10, 8), data_check_name="dc.json")
    assert cfg["date_range"] == ["2023-10-02", "2026-10-08"] and cfg["model"]["name"] == "H10", "T016 window/model"
    assert cfg["holdout"]["selected_config_hash"] == "c" * 64 and cfg["runner"] == t016.RUNNER, "T016 binding"
    assert cfg["holdout"]["d4"] == {"annualized_net_sharpe_gt": 0.0, "one_sided_hac_t_ge": 1.645}, "T016 D-4 fixed in the spend"
