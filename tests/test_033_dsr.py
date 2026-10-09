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


# --- T034: one committed matrix hash. Every expected value below is declared bytes plus a SHA-256
# computed from those bytes with hashlib alone, never with trial_registry.digest or build_matrix.
T034_PAYLOAD = {  # each return sidecar's declared canonical bytes: sorted keys, no spaces, one row per line
    "a": b'{"log_return":0.25,"session":"2020-01-03"}\n{"log_return":-0.125,"session":"2020-01-06"}\n'
         b'{"log_return":0.0625,"session":"2020-01-07"}\n',
    "b": b'{"log_return":0.5,"session":"2020-01-02"}\n{"log_return":-0.25,"session":"2020-01-03"}\n'
         b'{"log_return":0.125,"session":"2020-01-06"}\n{"log_return":-0.0625,"session":"2020-01-07"}\n'}
T034_SIDECAR = {"a": "894bafae1fba20f525a18b9866e63d4b8e8efbe62fed5e632a70e492a1313cc7",
                "b": "9086b9382b2074a5018216e37f3bcb9e1d3d9651cb3e9cb63af661cc66595c58"}
T034_BODY = (  # the matrix body's declared canonical bytes; UTF-8 em dash, null reason, dyadic exact floats
    b'{"columns":["a","b"],"convention":"daily_funded_net_log_returns","dates":["2020-01-03","2020-01-06",'
    b'"2020-01-07"],"excluded_trials":[{"reason":"not_candidate","trial_id":"c"}],"family":{"alignment":'
    b'"exact_intersection","id":"t034","min_coverage":0.5,"objective":"daily_sharpe","risk_free":{"annual_rate":'
    b'0.0,"days_per_year":252,"source":"EXAMPLE \xe2\x80\x94 NOT A RESULT"}},"reason":null,"return_digests":'
    b'{"a":"894bafae1fba20f525a18b9866e63d4b8e8efbe62fed5e632a70e492a1313cc7","b":'
    b'"9086b9382b2074a5018216e37f3bcb9e1d3d9651cb3e9cb63af661cc66595c58"},"values":[[0.25,-0.25],'
    b'[-0.125,0.125],[0.0625,-0.0625]]}')
T034_MATRIX_SHA = "74f80225120fc7d7bcd7ca08478a3ca078c67d4128911b7a03f8f1ebf41f7308"
T034_FAMILY = {**FAMILY, "id": "t034"}


def t034_trial(name, role="candidate"):
    obs = [json.loads(line) for line in T034_PAYLOAD["b" if name == "c" else name].splitlines()]
    return {"trial_id": name, "family": "t034", "role": role, "event_type": "completed", "source": SOURCE,
            "config": config(), "returns": obs,
            "sidecar": {"sha256": T034_SIDECAR["b" if name == "c" else name], "metadata": copy.deepcopy(META)}}


def test_t034_committed_literal_matrix_hash_and_canonical_body():
    """EXAMPLE — NOT A RESULT. Unsorted input, one shared-date drop, one excluded baseline."""
    for name, payload in T034_PAYLOAD.items():
        assert hashlib.sha256(payload).hexdigest() == T034_SIDECAR[name], f"T034 DECLARED: sidecar {name}"
    assert hashlib.sha256(T034_BODY).hexdigest() == T034_MATRIX_SHA, "T034 DECLARED: matrix body"
    expected = json.loads(T034_BODY.decode("utf-8"))
    result = api("selection_bias", "build_matrix")(
        [t034_trial("b"), t034_trial("c", role="buy_and_hold_baseline"), t034_trial("a")], family=T034_FAMILY)
    assert set(result) == set(expected) | {"matrix_hash"}, f"T034 KEYS: {sorted(result)}"
    assert result["columns"] == expected["columns"], f"T034 COLUMNS: {result['columns']}"
    assert result["dates"] == expected["dates"], f"T034 DATES: {result['dates']}"
    assert result["values"] == expected["values"], f"T034 VALUES: {result['values']}"
    assert result["excluded_trials"] == expected["excluded_trials"], f"T034 EXCLUDED: {result['excluded_trials']}"
    assert result["return_digests"] == expected["return_digests"], f"T034 DIGESTS: {result['return_digests']}"
    rest = ("family", "convention", "reason")
    assert {k: result[k] for k in rest} == {k: expected[k] for k in rest}, "T034 BODY: family/convention/reason"
    actual = canonical_json({k: v for k, v in result.items() if k != "matrix_hash"})
    assert actual == T034_BODY, f"T034 CANONICAL: {actual!r}"
    assert result["matrix_hash"] == T034_MATRIX_SHA, f"T034 HASH: {result['matrix_hash']}"
