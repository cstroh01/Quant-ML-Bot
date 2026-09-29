"""Spec 037: observable paired outcomes, with semantic mutation controls."""

import math
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401
import feature_set_comparison as fsc
from mutation_support_019 import killed


def classification_case():
    dates = pd.bdate_range("2024-01-02", periods=7)
    return (
        pd.Series([1., np.nan, 0., 1., 0., np.nan, np.nan], index=dates),
        pd.Series([0, 1, 0, 1, 1, 0, 1], index=dates),
        pd.Series([1, 0, 1, 1, 0, 1, 0], index=dates),
    )


def test_unknown_truth_is_excluded_jointly_without_fabricating_a_class():
    labels, a, b = classification_case()
    known = labels.notna()
    try:
        result = fsc.compare_classification(labels, a, b)
    except pd.errors.IntCastingNaNError as error:
        raise AssertionError("unsafe integer cast of legitimate unknown truth") from error
    expected = fsc.compare_classification(labels[known], a[known], b[known])
    assert result == expected
    correct_a = a[known].to_numpy() == labels[known].to_numpy()
    correct_b = b[known].to_numpy() == labels[known].to_numpy()
    assert result["n"] == int(known.sum())
    assert result["discordant"] == int(np.count_nonzero(correct_a != correct_b))
    assert result["accuracy_a"] == correct_a.mean()
    assert result["accuracy_b"] == correct_b.mean()
    # Unknown rows' predictions cannot affect either count or p-value.
    a.loc[~known], b.loc[~known] = 0, 0
    assert fsc.compare_classification(labels, a, b) == result


def test_nullable_unknown_truth_uses_the_same_observation_mask():
    labels, a, b = classification_case()
    assert fsc.compare_classification(labels.astype("Int64"), a, b) == (
        fsc.compare_classification(labels[labels.notna()], a[labels.notna()], b[labels.notna()])
    )


def test_regression_unknown_truth_does_not_poison_wilcoxon():
    truth = pd.Series([.2, np.nan, -.1, .4, np.nan])
    a = pd.Series([.1, 100., .2, .2, -100.])
    b = pd.Series([.2, -100., -.1, .3, 100.])
    known = truth.notna()
    result = fsc.compare_regression(truth, a, b)
    assert result == fsc.compare_regression(truth[known], a[known], b[known])
    assert result["n"] == int(known.sum())
    assert math.isfinite(result["p_one_sided"])


@pytest.mark.parametrize("compare", [fsc.compare_classification, fsc.compare_regression])
def test_no_observable_pair_is_an_error(compare):
    with pytest.raises(ValueError, match="no observable paired outcomes"):
        compare(pd.Series([np.nan]), pd.Series([0.]), pd.Series([1.]))


@pytest.mark.parametrize("field", range(3))
@pytest.mark.parametrize("value", [np.inf, -np.inf])
def test_infinity_is_invalid_not_an_unknown_outcome(field, value):
    series = [pd.Series([0., 1.]) for _ in range(3)]
    series[field].iloc[0] = value
    with pytest.raises(ValueError, match="finite"):
        fsc.compare_classification(*series)


@pytest.mark.parametrize("field", [1, 2])
def test_missing_prediction_on_observable_truth_fails(field):
    series = [pd.Series([0., 1.]) for _ in range(3)]
    series[field].iloc[0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        fsc.compare_classification(*series)


@pytest.mark.parametrize("field", range(3))
def test_fractional_classes_are_not_silently_truncated(field):
    series = [pd.Series([0., 1.]) for _ in range(3)]
    series[field].iloc[0] = .75
    with pytest.raises(ValueError, match="binary"):
        fsc.compare_classification(*series)


def test_pairing_intersects_dates_then_reports_scored_sample_size():
    labels, a, b = classification_case()
    result = fsc.pair_results(
        name="logistic", task="classification",
        result_a=(a.iloc[1:], labels.iloc[1:], 2),
        result_b=(b.iloc[:-1], labels.iloc[:-1], 3),
    )
    shared = a.iloc[1:].index.intersection(b.iloc[:-1].index)
    known = labels.loc[shared].dropna().index
    expected = fsc.compare_classification(labels.loc[known], a.loc[known], b.loc[known])
    assert result["shared_bars"] == result["n"] == len(known)
    for key, value in expected.items():
        assert result[key] == value


def test_misaligned_or_duplicate_series_cannot_be_compared_positionally():
    labels, a, b = classification_case()
    with pytest.raises(ValueError, match="same unique index"):
        fsc.compare_classification(labels, a.iloc[::-1], b)
    repeated = pd.Series([0., 1.], index=[0, 0])
    with pytest.raises(ValueError, match="same unique index"):
        fsc.compare_classification(repeated, repeated, repeated)


def test_unsafe_cast_mutant_is_killed():
    killed(
        fsc,
        '    truth, values_a, values_b = _scoreable_pairs(labels, predicted_a, predicted_b)\n',
        '    truth = labels.astype(int).to_numpy()  # MUTANT: original unsafe cast\n'
        '    truth, values_a, values_b = _scoreable_pairs(labels, predicted_a, predicted_b)\n',
        test_unknown_truth_is_excluded_jointly_without_fabricating_a_class,
    )


def test_orchestrator_uses_spawn_before_native_libraries_initialize():
    """Fork inherits an already sized OpenMP pool; later env edits cannot resize it."""
    class InspectedPool(Exception):
        pass

    def inspect_pool(*args, **kwargs):
        selected = kwargs.get("mp_context")
        assert selected is not None, "implicit platform start method can fork initialized OpenMP"
        assert selected.get_start_method() == "spawn"
        raise InspectedPool

    with patch.object(fsc.concurrent.futures, "ProcessPoolExecutor", inspect_pool):
        with pytest.raises(InspectedPool):
            fsc.compare_all_entries_parallel(pd.DataFrame(), max_workers=2)


def test_implicit_fork_context_mutant_is_killed():
    killed(
        fsc,
        '            mp_context=multiprocessing.get_context("spawn"),\n',
        '',
        test_orchestrator_uses_spawn_before_native_libraries_initialize,
    )


def test_equivalence_guard_rejects_a_single_ulp_prediction_change():
    from test_feature_set_comparison import TestSerialParallelEquivalence
    case = TestSerialParallelEquivalence("test_prediction_series_are_identical")
    predicted = pd.Series([.1, .2], index=pd.bdate_range("2024-01-02", periods=2))
    labels = pd.Series([.3, .4], index=predicted.index)
    key = ("ridge", "regression", "levels")
    case.serial_units = {key: (predicted, labels, 1)}
    changed = predicted.copy()
    case.parallel_units = {key: (changed, labels.copy(), 1)}
    case.test_prediction_series_are_identical()  # green control
    changed.iloc[0] = np.nextafter(changed.iloc[0], np.inf)
    with pytest.raises(AssertionError, match="different"):
        case.test_prediction_series_are_identical()


def test_all_baselines_receive_the_callers_account_policy():
    import multi_ticker_comparison as mtc
    from test_multi_ticker_comparison import _price_walk
    prices = _price_walk(60)
    capital = float(prices.Open.max() * 5)  # synthetic input, not a reported result
    real = mtc.run_backtest
    trade_log = real(mtc.buy_and_hold_signal(prices), starting_capital=capital,
                     liquidate=True, commission_per_trade=1.)
    seen = []

    def ledger(frame, **kwargs):
        seen.append((kwargs.get("starting_capital"), kwargs.get("liquidate")))
        return real(frame, **kwargs)

    seeds = 2
    with patch.object(mtc, "run_backtest", ledger):
        mtc._baseline_rows("SYNTHETIC", prices, trade_log,
                           starting_capital=capital, liquidate=True,
                           commission_per_trade=1., slippage_bps=0., seed_count=seeds)
    assert seen == [(capital, True)] * (seeds + 1)


def test_changed_baseline_funding_mutant_is_killed():
    import multi_ticker_comparison as mtc
    killed(
        mtc,
        'hold_log = run_backtest(\n'
        '            buy_and_hold_signal(ml_prices),\n'
        '            **costs,\n'
        '            starting_capital=starting_capital,\n'
        '            liquidate=liquidate,\n'
        '        )',
        'hold_log = run_backtest(\n'
        '            buy_and_hold_signal(ml_prices),\n'
        '            **costs,\n'
        '            starting_capital=starting_capital * 2,\n'
        '            liquidate=liquidate,\n'
        '        )',
        test_all_baselines_receive_the_callers_account_policy,
    )
