"""EXAMPLE — NOT A RESULT. Primary-paper inputs and independent matrix/HAC checks."""
import copy
import json
import math
from fractions import Fraction
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


# --- T040: hand-calculated HAC t-stat oracle at the Gate 3 boundary (t >= 3.0). The oracle is exact
# rational Newey-West/Bartlett arithmetic on dyadic inputs, never metrics.mean_log_return_se itself.
def t040_exact_t_squared(values, lags):
    x = [Fraction(v) for v in values]; n = len(x); mean = sum(x) / n; c = [v - mean for v in x]
    gamma = [sum(c[i] * c[i - j] for i in range(j, n)) / n for j in range(lags + 1)]
    variance = gamma[0] + 2 * sum((1 - Fraction(j, lags + 1)) * gamma[j] for j in range(1, lags + 1))
    return mean * mean / (variance / n)


def test_t040_hac_gate_boundary_oracle():
    """EXAMPLE — NOT A RESULT. Exact 3.0, one value below, lag floor, undefined SE, log risk-free."""
    hac = api("selection_bias", "hac_t_stat")
    exact, lagged = [1.25, .25, 1.25, .25], [.875, -.125, .875, -.125]  # centered +/-0.5, all dyadic
    assert t040_exact_t_squared(exact, 0) == 9 and t040_exact_t_squared(lagged, 1) == 9, "T040 DECLARED"
    assert hac(exact, horizon=3, lags=1)["reason"] == "hac_lag_below_horizon", "T040 GATE: lags = horizon-2"
    floor = hac(exact, horizon=3, lags=2, annual_risk_free=0.)  # exact t^2 = 27 with Bartlett weights 2/3, 1/3
    assert floor["reason"] is None and floor["hac_lags"] == 2, f"T040 GATE: lags = horizon-1 {floor}"
    result = hac(exact, horizon=1, lags=0, annual_risk_free=0.)
    assert result["value"] == 3.0, f"T040 EXACT: {result['value']!r}"
    assert result["standard_error"] == .25 and result["hac_lags"] == 0, f"T040 EXACT: {result}"
    result = hac(lagged, horizon=2, lags=1, annual_risk_free=0.)
    assert result["value"] == 3.0 and result["standard_error"] == .125, f"T040 LAG: {result}"
    assert t040_exact_t_squared(exact, 2) == 27 and floor["value"] == pytest.approx(math.sqrt(27), abs=1e-12), f"T040 LAG: {floor}"
    below = [1.25, .25, 1.25, .25 - 2**-51]  # exact t^2 = 9 - 2^-47: t sits about 2.5 ulps under 3
    assert 0 < 9 - t040_exact_t_squared(below, 0) < 2**-46, "T040 DECLARED: below"
    value = hac(below, horizon=1, lags=0, annual_risk_free=0.)["value"]
    assert value < 3.0 and value == 3. - 2 * math.ulp(3.), f"T040 BELOW: {value!r}"  # stable for every sum order
    for values, lags in (([.25] * 8, 0), (exact, 4), ([.25, float("nan"), .5, .75], 0)):
        undefined_se = hac(values, horizon=1, lags=lags, annual_risk_free=0.)
        assert undefined_se["value"] is None and undefined_se["reason"] == "nonpositive_hac_se", f"T040 SE: {undefined_se}"
    daily = math.log1p(.1) / 252  # log-return convention: subtract log1p(annual) / days, not annual / days
    shifted = hac([v + daily for v in exact], horizon=1, lags=0, annual_risk_free=.1, days_per_year=252)
    assert shifted["value"] == pytest.approx(3.0, abs=1e-9), f"T040 RISKFREE: {shifted['value']!r}"
    assert shifted["mean_excess_log_return"] == pytest.approx(.75, abs=1e-12), f"T040 RISKFREE: {shifted}"


# --- T037: every named DSR input and convention, against a hand oracle. Moments are exact rational
# arithmetic on dyadic inputs; the normal CDF/quantile come from the standard library's NormalDist,
# never from SciPy or NumPy, so the oracle shares no code with selection_bias.
T037_COLUMNS = {"a": [.5, -.5, .5, -.5], "b": [-.75, .25, -.25, .25], "c": [.25, .25, .25, -.25]}  # select "b": not column 0,
T037_SKEW, T037_SHARPE = -math.sqrt(324 / 1331), -math.sqrt(3 / 44)  # and negative mean and skew, so a sign drop shows
T037_N, T037_EULER = 69, 0.5772156649015329  # N_current is not the 3 matrix columns


def t037_matrix(annual_rate=0., shift=0., days=252):
    columns = list(T037_COLUMNS)
    values = [[T037_COLUMNS[k][i] + shift for k in columns] for i in range(4)]
    rf = {"annual_rate": annual_rate, "days_per_year": days, "source": "EXAMPLE — NOT A RESULT"}
    return {"columns": columns, "values": values, "reason": None, "matrix_hash": "EXAMPLE", "family": {**FAMILY, "risk_free": rf}}


def t037_moments(values):
    """Exact (mean, ddof=1 variance, population m2, m3, m4) of one column."""
    x = [Fraction(v) for v in values]; n = len(x); mean = sum(x) / n; c = [v - mean for v in x]
    return mean, sum(v * v for v in c) / (n - 1), *(sum(v ** k for v in c) / n for k in (2, 3, 4))


def test_t037_named_dsr_inputs_and_conventions():
    """EXAMPLE — NOT A RESULT. Daily Sharpe, T, skew, Pearson kurtosis, dispersion, benchmark, CDF, N."""
    from statistics import NormalDist
    phi = NormalDist()
    mean, var1, m2, m3, m4 = t037_moments(T037_COLUMNS["b"])
    assert (mean, mean * mean / var1, m3 < 0, m3 * m3 / m2 ** 3, m4 / m2 ** 2) == (Fraction(-1, 8), Fraction(3, 44), True, Fraction(324, 1331), Fraction(197, 121)), "T037 DECLARED"
    sharpes = [float(mu) / math.sqrt(v) for mu, v, *_ in map(t037_moments, T037_COLUMNS.values())]
    assert sharpes[0] == 0. and sharpes[1] == pytest.approx(T037_SHARPE) and sharpes[2] == .5, "T037 DECLARED: trial Sharpes"
    base = api("selection_bias", "matrix_dsr")(t037_matrix(), selected_trial="b", n_current=T037_N)
    inputs, near = base["inputs"], (lambda v: pytest.approx(v, rel=1e-12, abs=1e-15))
    assert inputs["observations"] == 4, f"T037 OBSERVATIONS: {inputs}"
    assert inputs["observed_sharpe"] == near(T037_SHARPE), f"T037 SHARPE: daily ddof=1, not annualized {inputs}"
    assert base["trial_sharpes"] == [near(s) for s in sharpes], f"T037 SHARPE: {base['trial_sharpes']}"
    assert inputs["skewness"] == near(T037_SKEW), f"T037 SKEW: signed, population central moments {inputs}"
    assert inputs["pearson_kurtosis"] == near(197 / 121), f"T037 KURTOSIS: Pearson, not excess {inputs}"
    dispersion = math.sqrt(sum((s - sum(sharpes) / 3) ** 2 for s in sharpes) / 2)
    assert inputs["trial_sharpe_std"] == near(dispersion), f"T037 DISPERSION: ddof=1 {inputs}"
    assert inputs["n_current"] == T037_N, f"T037 NCURRENT: {inputs}"
    benchmark = dispersion * ((1 - T037_EULER) * phi.inv_cdf(1 - 1 / T037_N) + T037_EULER * phi.inv_cdf(1 - 1 / (T037_N * math.e)))
    assert base["benchmark_sharpe"] == near(benchmark), f"T037 BENCHMARK: {base}"
    denominator = 1 - T037_SKEW * T037_SHARPE + (197 / 121 - 1) / 4 * (3 / 44)
    z = (T037_SHARPE - benchmark) * math.sqrt(4 - 1) / math.sqrt(denominator)
    assert base["psr_denominator"] == near(denominator) and base["z"] == near(z), f"T037 Z: sqrt(T-1) {base}"
    assert base["value"] == pytest.approx(phi.cdf(z), rel=1e-9, abs=1e-12), f"T037 CDF: {base['value']!r} vs {phi.cdf(z)!r}"
    single = api("selection_bias", "deflated_sharpe")(**{k: v for k, v in inputs.items() if k != "n_current"}, n_current=1)
    assert single["benchmark_sharpe"] == 0. and single["value"] == pytest.approx(phi.cdf(T037_SHARPE * math.sqrt(3) / math.sqrt(denominator)), rel=1e-9, abs=1e-12), f"T037 BENCHMARK: N=1 {single}"
    shifted = api("selection_bias", "matrix_dsr")(t037_matrix(.1, math.log1p(.1) / 250, 250), selected_trial="b", n_current=T037_N)
    assert shifted["inputs"] == {k: near(v) if isinstance(v, float) else v for k, v in inputs.items()}, f"T037 RISKFREE: log1p(annual)/days {shifted['inputs']}"


# --- T035: Rule 1/5 matrix alignment. Each cell is its own trial's return on that row's own session:
# no fill, no positional join, no read of another row. Sessions are declared literals, never pd.bdate_range.
T035_JAN = [f"2020-01-{d:02d}" for d in (2, 3, 6, 7, 8, 9, 10, 13, 14, 15, 16, 17, 20, 21, 22, 23, 24, 27, 28, 29, 30, 31)]
T035_A = [s for s in T035_JAN[:-1] if s != "2020-01-09"]  # weekdays 01-02..01-30: missing 01-09, MLK holiday 01-20 kept
T035_B = [s for s in T035_JAN[1:] if s not in {"2020-01-13", "2020-01-14", "2020-01-20"}]  # NYSE days 01-03..01-31;
# fold 1 ends 01-10, embargo 01-13/14, fold 2 starts 01-15. Crossing edges: b sets the first row, a the last.
T035_DATES = [f"2020-01-{d:02d}" for d in (3, 6, 7, 8, 10, 15, 16, 17, 21, 22, 23, 24, 27, 28, 29, 30)]


def t035_rows(sessions, scale):  # distinct dyadic returns, so any shifted or positional read changes a cell
    return [{"session": s, "log_return": scale * (i + 1) / 64} for i, s in enumerate(sessions)]


def test_t035_session_alignment_boundaries_and_perturbation():
    """EXAMPLE — NOT A RESULT. First/last row, unequal boundaries, holiday, gap, fold join, bad labels."""
    build = api("selection_bias", "build_matrix")
    a_rows, b_rows = t035_rows(T035_A, 1.), t035_rows(T035_B, -.5)
    cell = {"a": {r["session"]: r["log_return"] for r in a_rows}, "b": {r["session"]: r["log_return"] for r in b_rows}}
    base = build([trial("b", b_rows), trial("a", a_rows)], family=FAMILY)
    assert base["reason"] is None and base["columns"] == ["a", "b"], f"T035 DATES: {base['reason']}"
    assert base["dates"] == T035_DATES, f"T035 DATES: {base['dates']}"
    moves = {}  # perturb every a row; only that session's own matrix row may move
    for k, row in enumerate(a_rows):
        bumped = copy.deepcopy(a_rows); bumped[k]["log_return"] += 1
        values = build([trial("a", bumped), trial("b", b_rows)], family=FAMILY)["values"]
        moves[row["session"]] = [d for d, old, new in zip(base["dates"], base["values"], values) if old != new]
    assert all(d >= s for s, moved in moves.items() for d in moved), f"T035 FUTURE: a later bump moved an earlier row {moves}"
    assert all((s in moved) == (s in T035_DATES) for s, moved in moves.items()), f"T035 CURRENT: {moves}"
    assert all(set(moved) <= {s} for s, moved in moves.items()), f"T035 LATER: {moves}"
    assert base["values"] == [[cell["a"][d], cell["b"][d]] for d in T035_DATES], f"T035 CELLS: {base['values']}"
    for name, k, edit in (("duplicate", 5, lambda r, k: r[k].update(session=r[k - 1]["session"])),  # fold 2 restates 01-10
                          ("swapped", 4, lambda r, k: r.__setitem__(slice(k, k + 2), [r[k + 1], r[k]])),  # folds out of order
                          ("compact last", -1, lambda r, k: r[k].update(session=r[k]["session"].replace("-", ""))),  # ISO, not a label
                          ("aware midnight last", -1, lambda r, k: r[k].update(session=r[k]["session"] + "T00:00:00+00:00")),
                          ("non-midnight first", 0, lambda r, k: r[k].update(session=r[k]["session"] + "T16:00:00"))):
        bad = copy.deepcopy(b_rows); edit(bad, k)
        result = build([trial("a", a_rows), trial("b", bad)], family=FAMILY)
        assert result["columns"] == ["a"] and result["excluded_trials"] == [{"trial_id": "b", "reason": "invalid_return_evidence"}], f"T035 REJECT {name}: {result['excluded_trials']}"
