"""EXAMPLE — NOT A RESULT. Primary-paper inputs and independent matrix/HAC checks."""
import copy
import json
import math
import numpy as np
import pandas as pd
import pytest
from context import SCRIPTS_DIR
from spec033_support import api, config, rows, SOURCE, META, MATRIX_FIELDS, ledger, start
from trial_registry import canonical_json
import hashlib

FAMILY = {"id": "example", "alignment": "exact_intersection", "min_coverage": .5, "objective": "daily_sharpe", "risk_free": config()["risk_free"]}

def trial(name="a", observations=None, **changes):
    obs = rows() if observations is None else observations
    payload = b"".join(canonical_json(r) + b"\n" for r in obs)
    value = {"trial_id": name, "family": "example", "role": "candidate", "event_type": "completed", "source": SOURCE, "config": config(), "returns": obs,
             "sidecar": {"sha256": hashlib.sha256(payload).hexdigest(), "metadata": copy.deepcopy(META)}}
    value.update(changes)
    return value

def matrix():
    build = api("selection_bias", "build_matrix")
    return build([trial("a"), trial("b", [{**r, "log_return": r["log_return"]*.8-.002} for r in rows()])], family=FAMILY)

def test_matrix_exact_shared_dates_sorted_columns_digest_and_exclusions():
    build = api("selection_bias", "build_matrix")
    a, b = trial("b", rows()[1:]), trial("a", rows()[:-1])
    result = build([a, b, trial("baseline", role="buy_and_hold_baseline")], family=FAMILY)
    assert MATRIX_FIELDS <= result.keys()
    assert result["columns"] == ["a", "b"]
    assert result["dates"] == [r["session"] for r in rows()[1:-1]]
    assert result["values"][0] == [rows()[1]["log_return"]]*2
    assert result["excluded_trials"] == [{"trial_id": "baseline", "reason": "not_candidate"}]
    assert build([b, a, trial("baseline", role="buy_and_hold_baseline")], family=FAMILY)["matrix_hash"] == result["matrix_hash"]
    bad = trial(); bad["sidecar"]["sha256"] = "0"*64
    assert build([bad], family=FAMILY)["excluded_trials"][0]["reason"] == "return_digest_mismatch"

@pytest.mark.parametrize("defect", ["duplicate", "reverse", "aware", "nonmidnight", "nan", "unfunded", "not_oos", "no_costs", "short_purge", "source_missing"])
def test_matrix_rejects_invalid_evidence(defect):
    build = api("selection_bias", "build_matrix")
    value = trial()
    if defect == "duplicate": value["returns"][1] = value["returns"][0]
    elif defect == "reverse": value["returns"].reverse()
    elif defect in {"aware", "nonmidnight"}: value["returns"][0]["session"] += "T01:00:00" + ("+00:00" if defect == "aware" else "")
    elif defect == "nan": value["returns"][0]["log_return"] = float("nan")
    elif defect == "unfunded": value["sidecar"]["metadata"]["return_convention"] = "trade_pnl"
    elif defect == "not_oos": value["sidecar"]["metadata"]["oos"] = False
    elif defect == "no_costs": value["sidecar"]["metadata"]["net_costs"] = False
    elif defect == "short_purge": value["sidecar"]["metadata"]["cv"]["purge"] = 0
    else: value["source"] = {**SOURCE, "git_sha": None}
    result = build([value, trial("control")], family=FAMILY)
    assert result["columns"] == ["control"]
    assert result["excluded_trials"][0]["trial_id"] == "a"

def test_gaps_fold_join_future_perturbation_and_current_row_control():
    build = api("selection_bias", "build_matrix")
    obs = rows(); del obs[8]
    before = build([trial("a", obs), trial("b")], family=FAMILY)
    assert rows()[8]["session"] not in before["dates"]
    assert before["dates"][0] == rows()[0]["session"] and before["dates"][-1] == rows()[-1]["session"]
    future = copy.deepcopy(obs); future[-1]["log_return"] += 1
    after = build([trial("a", future), trial("b")], family=FAMILY)
    assert before["values"][:-1] == after["values"][:-1]
    assert before["matrix_hash"] != after["matrix_hash"]
    current = copy.deepcopy(obs); current[0]["log_return"] += 1
    assert build([trial("a", current), trial("b")], family=FAMILY)["values"][0] != before["values"][0]

def paper_inputs():
    fixture = json.loads((SCRIPTS_DIR.parent / "tests/fixtures/spec_033/paper_inputs.json").read_text(encoding="utf-8"))
    return dict(observed_sharpe=fixture["annualized_sharpe"]/math.sqrt(fixture["days_per_year"]), observations=fixture["observations"], skewness=fixture["skewness"], pearson_kurtosis=fixture["pearson_kurtosis"], trial_sharpe_std=math.sqrt(fixture["annualized_trial_sharpe_variance"]/fixture["days_per_year"]))

def test_paper_formula_required_spec_target():
    dsr = api("selection_bias", "deflated_sharpe")
    result = dsr(**paper_inputs(), n_current=88)
    assert result["value"] == pytest.approx(.910153014744707, abs=.001)
    assert result["value"] < .95
    assert dsr(**paper_inputs(), n_current=46)["value"] >= .95

def test_primary_paper_actual_n100_and_n46():
    dsr = api("selection_bias", "deflated_sharpe")
    assert dsr(**paper_inputs(), n_current=100)["value"] == pytest.approx(.9004, abs=.0001)
    assert dsr(**paper_inputs(), n_current=46)["value"] == pytest.approx(.9505, abs=.0001)

@pytest.mark.parametrize("changes,reason", [({"observations": 1}, "insufficient_observations"), ({"trial_sharpe_std": 0.}, "invalid_trial_dispersion"), ({"n_current": 0}, "invalid_lifetime_count"), ({"skewness": float("nan")}, "nonfinite_moments"), ({"observed_sharpe": 1., "skewness": 10., "pearson_kurtosis": 1.}, "invalid_psr_denominator")])
def test_dsr_invalid_domains(changes, reason):
    dsr = api("selection_bias", "deflated_sharpe")
    result = dsr(**{**paper_inputs(), "n_current": 88, **changes})
    assert result["value"] is None and result["reason"] == reason

def test_matrix_moments_named_inputs_and_raw_lifetime_count(tmp_path):
    analyze = api("selection_bias", "matrix_dsr")
    log = ledger(tmp_path)
    for _ in range(4): start(log)
    log.finish(start(log), "abandoned", reason="EXAMPLE")
    n = 64 + log.verify()["n_post_ledger"]
    m = matrix(); result = analyze(m, selected_trial="a", n_current=n)
    x = np.asarray(m["values"])[:, 0]; centered = x-x.mean(); sd = x.std(ddof=1)
    inputs = result["inputs"]
    assert inputs["observed_sharpe"] == pytest.approx(x.mean()/sd)
    assert inputs["observations"] == len(x)
    assert inputs["skewness"] == pytest.approx(np.mean(centered**3)/np.mean(centered**2)**1.5)
    assert inputs["pearson_kurtosis"] == pytest.approx(np.mean(centered**4)/np.mean(centered**2)**2)
    assert inputs["n_current"] == 69 and inputs["n_current"] != len(m["columns"])
    assert result["matrix_hash"] == m["matrix_hash"]
    assert analyze(m, selected_trial="absent", n_current=n)["reason"] == "selected_candidate_missing"

def test_hac_hand_oracle_horizon_and_risk_free():
    hac = api("selection_bias", "hac_t_stat")
    values = [.01, .02, -.01, .04]
    x = np.asarray(values); centered=x-x.mean()
    variance = centered@centered/4 + (centered[1:]@centered[:-1])/4
    result = hac(values, horizon=2, lags=1, annual_risk_free=0., days_per_year=252)
    assert result["value"] == pytest.approx(x.mean()/math.sqrt(variance/4))
    assert result["hac_lags"] == 1
    assert hac(values, horizon=2, lags=0)["reason"] == "hac_lag_below_horizon"
    shifted = hac(values, horizon=1, lags=0, annual_risk_free=.1)
    assert shifted["mean_excess_log_return"] == pytest.approx(x.mean()-math.log1p(.1)/252)
    assert hac([0.]*32, horizon=1, lags=0)["reason"] == "nonpositive_hac_se"
