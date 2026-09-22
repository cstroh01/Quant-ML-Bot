"""EXAMPLE — NOT A RESULT. Analytic CSCV oracles, not simulated alpha."""
import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from spec033_support import api, rows
from test_033_dsr import FAMILY, trial
from trial_registry import digest

FIXTURE = json.loads((Path(__file__).parent / "fixtures/spec_033/cscv_oracle.json").read_text(encoding="utf-8"))


def committed(values, columns=("a", "b")):
    """Use the existing eligible trial-matrix builder, including real digests."""
    return api("selection_bias", "build_matrix")([
        trial(name, [{**r, "log_return": float(values[i][j])} for i, r in enumerate(rows(len(values)))])
        for j, name in enumerate(columns)
    ], family=copy.deepcopy(FAMILY))


def persistent():
    raw = np.asarray(FIXTURE["block_rows"]) + FIXTURE["column_offsets"]
    return committed(np.tile(raw * .01, (16, 1)))


def reseal(matrix):
    matrix["matrix_hash"] = digest({k: v for k, v in matrix.items() if k != "matrix_hash"})
    return matrix


@pytest.mark.parametrize("n", [16, 17, 31, 32, 1250])
def test_contiguous_blocks_cover_exact_chronological_rows(n):
    blocks = api("selection_bias", "cscv_blocks")
    dates = [r["session"] for r in rows(n + 1)]
    del dates[5]  # Explicit missing session, never filled or redistributed by dates.
    result = blocks(dates)
    assert result == blocks(dates) and len(result) == 16
    quotient, remainder = divmod(n, 16)
    sizes = [b["row_stop"] - b["row_start"] for b in result]
    assert sizes == [quotient + (i < remainder) for i in range(16)]
    assert [j for b in result for j in range(b["row_start"], b["row_stop"])] == list(range(n))
    for i, block in enumerate(result):
        assert block["block_id"] == i
        assert block["first_session"] == dates[block["row_start"]]
        assert block["last_session"] == dates[block["row_stop"] - 1]


@pytest.mark.parametrize("defect", ["short", "reverse", "duplicate", "aware", "intraday"])
def test_blocks_reject_invalid_time_contract(defect):
    blocks = api("selection_bias", "cscv_blocks")
    dates = [r["session"] for r in rows()]
    if defect == "short": dates = dates[:15]
    elif defect == "reverse": dates.reverse()
    elif defect == "duplicate": dates[1] = dates[0]
    else: dates[0] += "T01:00:00" + ("+00:00" if defect == "aware" else "")
    with pytest.raises(ValueError):
        blocks(dates)


def test_all_combinations_and_complements_without_sampling():
    splits = list(api("selection_bias", "cscv_splits")())
    assert len(splits) == math.comb(16, 8) == 12870
    choices = {tuple(a) for a, _ in splits}
    assert len(choices) == len(splits)
    assert splits[0] == (tuple(range(8)), tuple(range(8, 16)))
    for a, b in splits:
        assert len(a) == len(b) == 8
        assert not set(a) & set(b) and set(a) | set(b) == set(range(16))
        assert tuple(b) in choices


def test_persistent_winner_independent_oracle_and_recomputable_evidence():
    result = api("selection_bias", "matrix_pbo")(persistent())
    assert result["value"] == FIXTURE["expected_pbo"] == 0
    assert result["reason"] is None and result["S"] == 16
    assert result["matrix_rows"] == 32 and result["matrix_columns"] == 2
    assert result["total_splits"] == result["valid_splits"] == 12870
    assert result["rejected_splits"] == 0
    sd = math.sqrt(16 / 15)  # Sixteen IS observations, population variance 1.
    for record in result["splits"]:
        assert record["winner_trial_id"] == "a"
        assert record["is_sharpes"] == pytest.approx([2 / sd, 1 / sd])
        assert record["oos_sharpes"] == pytest.approx([2 / sd, 1 / sd])
        assert record["relative_rank"] == pytest.approx(2 / 3)
        assert record["rank_logit"] == pytest.approx(math.log(2))
        assert record["degradation"] == pytest.approx(0)
    assert result["value"] == sum(s["rank_logit"] <= 0 for s in result["splits"]) / 12870
    assert result["rank_logit_summary"]["mean"] == pytest.approx(math.log(2))
    assert result["degradation_summary"]["mean"] == pytest.approx(0)
    assert result["conventions"]["is_ties"] == "lexicographic_trial_id"
    assert result["conventions"]["oos_rank"] == "ascending_average_rank_divided_by_M_plus_1"
    json.dumps(result, allow_nan=False)


def test_overfit_oracle_winner_carry_through_ties_sign_and_column_order():
    pbo = api("selection_bias", "matrix_pbo")
    fixture = FIXTURE["overfit_counterexample"]
    matrix = committed(np.asarray(fixture["values"]) * .01)
    result = pbo(matrix)
    assert result["value"] == fixture["expected_pbo_at_logit_lte_zero"] == 1
    ties = 0
    for record in result["splits"]:
        k = sum(i < 8 for i in record["is_blocks"])
        mu = (k - 4) / 4
        sd = math.sqrt((2 - mu * mu) * 16 / 15)
        is_scores = [mu / sd, -mu / sd]
        assert record["is_sharpes"] == pytest.approx(is_scores)
        assert record["oos_sharpes"] == pytest.approx([-v for v in is_scores])
        assert record["winner_trial_id"] == ("a" if k >= 4 else "b")
        assert record["degradation"] == pytest.approx(2 * abs(mu) / sd)
        assert record["relative_rank"] == pytest.approx(.5 if k == 4 else 1 / 3)
        assert record["rank_logit"] == pytest.approx(0 if k == 4 else -math.log(2))
        ties += k == 4
    assert ties == math.comb(8, 4) ** 2 == fixture["tie_splits"]
    permuted = copy.deepcopy(matrix)
    permuted["columns"].reverse()
    for row in permuted["values"]: row.reverse()
    reverse = pbo(reseal(permuted))
    assert reverse["splits"] == result["splits"]
    assert reverse["value"] == result["value"]


def test_same_matrix_as_dsr_and_history_never_adds_columns():
    pbo = api("selection_bias", "matrix_pbo")
    dsr = api("selection_bias", "matrix_dsr")
    matrix = persistent(); original = copy.deepcopy(matrix)
    result = pbo(matrix)
    for n in (46, 88, 10000):
        observed = dsr(matrix, selected_trial="a", n_current=n)
        assert observed["matrix_hash"] == result["matrix_hash"] == matrix["matrix_hash"]
        assert observed["inputs"]["n_current"] == n
    assert result["columns"] == ["a", "b"] and result["matrix_columns"] == 2
    assert matrix == original


@pytest.mark.parametrize("defect,reason", [
    ("short", "insufficient_pbo_rows"), ("single", "insufficient_pbo_columns"),
    ("corrupt", "matrix_digest_mismatch"), ("nan", "nonfinite_matrix"),
    ("ineligible", "insufficient_shared_coverage"), ("objective", "invalid_pbo_objective"),
    ("reverse", "invalid_matrix"), ("shape", "invalid_matrix"),
])
def test_preflight_undefined_never_reports_a_computed_probability(defect, reason):
    pbo = api("selection_bias", "matrix_pbo")
    matrix = persistent()
    if defect == "short": matrix["values"] = matrix["values"][:15]; matrix["dates"] = matrix["dates"][:15]
    elif defect == "single": matrix["columns"] = ["a"]; matrix["values"] = [[r[0]] for r in matrix["values"]]
    elif defect == "corrupt": matrix["matrix_hash"] = "0" * 64
    elif defect == "nan": matrix["values"][0][0] = float("nan")
    elif defect == "ineligible": matrix["reason"] = "insufficient_shared_coverage"
    elif defect == "objective": matrix["family"]["objective"] = "choose_after_seeing_results"
    elif defect == "reverse": matrix["dates"].reverse()
    else: matrix["values"][0].append(0)
    if defect not in {"corrupt", "nan"}: reseal(matrix)
    result = pbo(matrix)
    assert result["value"] is None and result["reason"] == reason
    assert result["expected_splits"] == 12870
    assert result["total_splits"] == result["valid_splits"] == result["rejected_splits"] == 0


@pytest.mark.parametrize("mode", ["all_zero", "two_bad_splits", "overflow"])
def test_rejected_splits_retained_and_invalidate_aggregate(mode):
    pbo = api("selection_bias", "matrix_pbo")
    values = np.tile([[-.01, -.02], [.03, .01]], (16, 1))
    if mode == "all_zero": values[:] = 0
    elif mode == "two_bad_splits": values[:16, 0] = 0
    else: values[:, 0] *= 1e308
    result = pbo(committed(values))
    expected = 2 if mode == "two_bad_splits" else 12870
    assert result["value"] is None
    assert result["reason"] == ("rejected_cscv_splits" if expected == 2 else "no_valid_cscv_splits")
    assert result["total_splits"] == len(result["splits"]) == 12870
    assert result["rejected_splits"] == expected
    assert result["valid_splits"] + result["rejected_splits"] == 12870
    rejected = [s for s in result["splits"] if s["reason"]]
    assert len(rejected) == expected
    assert all(s["rank_logit"] is None for s in rejected)
    expected_columns = ["a", "b"] if mode == "all_zero" else ["a"]
    assert all(s["invalid_columns"] == expected_columns for s in rejected)
    json.dumps(result, allow_nan=False)


def test_risk_free_and_is_selection_do_not_read_complement_rows():
    pbo = api("selection_bias", "matrix_pbo")
    matrix = persistent()
    rf = .01
    matrix["family"]["risk_free"]["annual_rate"] = math.expm1(rf * 252)
    base = pbo(reseal(matrix))
    sd = math.sqrt(16 / 15)
    assert base["splits"][0]["is_sharpes"] == pytest.approx([1 / sd, 0])
    future = copy.deepcopy(matrix)
    for row in future["values"][16:]: row[0] -= .1
    changed = pbo(reseal(future))
    assert changed["splits"][0]["is_sharpes"] == base["splits"][0]["is_sharpes"]
    assert changed["splits"][0]["winner_trial_id"] == base["splits"][0]["winner_trial_id"]
    assert changed["splits"][0]["oos_sharpes"] != base["splits"][0]["oos_sharpes"]
    assert changed["matrix_hash"] != base["matrix_hash"]


def test_extreme_finite_returns_retain_all_rejected_splits_instead_of_raising():
    pbo = api("selection_bias", "matrix_pbo")
    values = [[1e308 if i < 16 else -1e308, .01 + (-1) ** i * .02] for i in range(32)]
    try:
        result = pbo(committed(values))
    except (ValueError, OverflowError) as error:
        pytest.fail(f"finite input must retain rejected split evidence, not raise: {error}")
    assert result["value"] is None and result["reason"] == "no_valid_cscv_splits"
    assert result["rejected_splits"] == len(result["splits"]) == 12870
    json.dumps(result, allow_nan=False)


def test_unequal_blocks_three_columns_match_direct_row_oracle():
    pbo = api("selection_bias", "matrix_pbo")
    x = np.array([[.001 + math.sin(i + j) * .02 + j * .001 for j in range(3)] for i in range(37)])
    matrix = committed(x, columns=("a", "b", "c"))
    result = pbo(matrix)
    assert result["reason"] is None
    bad_ranks = 0
    # Independent per-row reference; no production block or Sharpe helpers.
    boundaries = [0, 3, 6, 9, 12, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37]
    for record in result["splits"]:
        chosen = {j for b in record["is_blocks"] for j in range(boundaries[b], boundaries[b + 1])}
        inside, outside = x[sorted(chosen)], x[[i for i in range(37) if i not in chosen]]
        sr_in = inside.mean(axis=0) / inside.std(axis=0, ddof=1)
        sr_out = outside.mean(axis=0) / outside.std(axis=0, ddof=1)
        winner = int(np.argmax(sr_in))
        rank = (np.argsort(sr_out).tolist().index(winner) + 1) / 4
        assert record["is_sharpes"] == pytest.approx(sr_in)
        assert record["oos_sharpes"] == pytest.approx(sr_out)
        assert record["winner_trial_id"] == matrix["columns"][winner]
        assert record["relative_rank"] == rank
        assert record["degradation"] == pytest.approx(sr_in[winner] - sr_out[winner])
        bad_ranks += rank <= .5
    assert result["value"] == bad_ranks / 12870
