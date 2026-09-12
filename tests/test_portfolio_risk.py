"""Tests for the position sizing and portfolio risk layer (spec 017).

Three stories, all P1, in dependency order: a position is sized off
conviction and volatility; correlated names share one risk budget; losses
halt new risk automatically. Every time-indexed computation gets Rule 5's
trio -- off-by-one, boundary, gap -- and every Rule 1 perturbation test is
paired with a control proving the perturbation actually reaches the function,
or the first test would pass on a function that ignored its input.

Exact correlations are put into price series with Hadamard patterns: rows of
a Sylvester Hadamard matrix are mean-zero and mutually orthogonal, so their
sample correlation is exactly zero, and a row paired with itself is exactly
one. Random series would leave the "uncorrelated" case with a sampling error
of about `1/sqrt(window)`, which is larger than several of the effects under
test.
"""

import ast
import dataclasses
import math
import unittest

import numpy as np
import pandas as pd

from context import SCRIPTS_DIR
from constants import TRADING_DAYS_PER_YEAR
from portfolio_risk import (
    RECOMMENDED_CONFIG,
    LossCapGuard,
    RiskConfig,
    apply_entry_halt,
    apply_gross_cap,
    correlation_adjusted_weights,
    log_returns,
    loss_cap_history,
    position_overlap,
    realized_volatility,
    target_weights,
    trailing_correlation,
    volatility_target_weights,
)

ANNUALIZER = math.sqrt(TRADING_DAYS_PER_YEAR)

# Limits for scenario tests whose equity paths are built to stay clear of
# every boundary except the one under test.
LIMITS = {
    "daily_loss_limit": 0.02,
    "weekly_loss_limit": 0.04,
    "weekly_drawdown_limit": 0.05,
}


def sessions(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    """`n` naive, midnight-normalized weekday session labels."""
    return pd.bdate_range(start, periods=n)


def panel_from_returns(returns, columns, start: str = "2024-01-01") -> pd.DataFrame:
    """Closes whose log returns are `returns`; row 0 is the base price.

    Returns row `k` becomes the return *into* closes row `k+1`.
    """
    returns = np.asarray(returns, dtype=float)
    log_prices = np.vstack(
        [np.zeros((1, returns.shape[1])), np.cumsum(returns, axis=0)]
    )
    return pd.DataFrame(
        100.0 * np.exp(log_prices),
        index=sessions(len(log_prices), start),
        columns=columns,
    )


def hadamard(order: int) -> np.ndarray:
    """Sylvester Hadamard matrix of a power-of-two order."""
    matrix = np.array([[1.0]])
    while matrix.shape[0] < order:
        matrix = np.block([[matrix, matrix], [matrix, -matrix]])
    return matrix


def random_panel(n_sessions: int, columns, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return panel_from_returns(
        rng.normal(0.0, 0.015, size=(n_sessions - 1, len(columns))), columns
    )


def config(**overrides) -> RiskConfig:
    values = dataclasses.asdict(RECOMMENDED_CONFIG)
    values.update(overrides)
    return RiskConfig(**values)


def weights(mapping: dict) -> pd.Series:
    return pd.Series(mapping, dtype="float64")


def matrix(rows, tickers) -> pd.DataFrame:
    return pd.DataFrame(rows, index=tickers, columns=tickers, dtype="float64")


def feed(guard: LossCapGuard, dates, values):
    return [guard.observe(pd.Timestamp(d), v) for d, v in zip(dates, values)]


# ---------------------------------------------------------------------------
# Foundational
# ---------------------------------------------------------------------------


class SessionIndexValidationTests(unittest.TestCase):
    """FR-015 -- a session label is naive and midnight; anything else raises."""

    def setUp(self):
        self.closes = random_panel(10, ["AAA", "BBB"], seed=1)

    def test_a_valid_panel_is_accepted(self):
        self.assertEqual(log_returns(self.closes).shape, self.closes.shape)

    def test_timezone_aware_labels_raise(self):
        # The silent one-bar shift CLAUDE.md's timestamp convention exists to
        # prevent: an aware label read in another zone lands on another day.
        with self.assertRaises(ValueError):
            log_returns(self.closes.tz_localize("America/New_York"))

    def test_non_midnight_labels_raise(self):
        shifted = self.closes.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=16)
        with self.assertRaises(ValueError):
            log_returns(shifted)

    def test_repeated_labels_raise(self):
        repeated = self.closes.copy()
        repeated.index = pd.DatetimeIndex(
            [self.closes.index[0], *self.closes.index[:-1]]
        )
        with self.assertRaises(ValueError):
            log_returns(repeated)

    def test_out_of_order_labels_raise(self):
        with self.assertRaises(ValueError):
            log_returns(self.closes.iloc[::-1])

    def test_a_non_datetime_index_raises(self):
        with self.assertRaises(ValueError):
            log_returns(self.closes.reset_index(drop=True))

    def test_a_ticker_listed_twice_raises(self):
        doubled = self.closes.copy()
        doubled.columns = ["AAA", "AAA"]
        with self.assertRaises(ValueError):
            log_returns(doubled)

    def test_an_aware_session_argument_raises(self):
        with self.assertRaises(ValueError):
            trailing_correlation(
                self.closes, self.closes.index[-1].tz_localize("UTC"), window=3
            )

    def test_a_session_absent_from_the_panel_raises(self):
        with self.assertRaises(ValueError):
            trailing_correlation(self.closes, pd.Timestamp("1999-01-04"), window=3)

    def test_the_equity_index_is_held_to_the_same_rule(self):
        equity = pd.Series([1.0, 1.0], index=sessions(2).tz_localize("UTC"))
        with self.assertRaises(ValueError):
            loss_cap_history(equity, **LIMITS)


class LogReturnTests(unittest.TestCase):
    """Positional log returns; a gap is never stitched across."""

    def test_values_are_log_ratios_of_consecutive_rows(self):
        closes = pd.DataFrame({"AAA": [100.0, 110.0, 99.0]}, index=sessions(3))
        returns = log_returns(closes)["AAA"].to_numpy()
        self.assertTrue(np.isnan(returns[0]))
        self.assertAlmostEqual(returns[1], math.log(1.1), places=15)
        self.assertAlmostEqual(returns[2], math.log(0.9), places=15)

    def test_a_missing_close_blanks_both_returns_it_touches(self):
        closes = pd.DataFrame(
            {"AAA": [100.0, 101.0, np.nan, 103.0, 104.0]}, index=sessions(5)
        )
        self.assertEqual(
            log_returns(closes)["AAA"].isna().tolist(),
            [True, False, True, True, False],
        )

    def test_non_positive_or_infinite_closes_raise(self):
        for bad in (0.0, -1.0, np.inf):
            with self.subTest(close=bad):
                closes = pd.DataFrame({"AAA": [100.0, bad]}, index=sessions(2))
                with self.assertRaises(ValueError):
                    log_returns(closes)


class RiskConfigValidationTests(unittest.TestCase):
    """FR-016 -- every parameter validated on construction, never clipped."""

    def test_the_recommended_values_are_the_ones_the_spec_records(self):
        self.assertEqual(
            dataclasses.asdict(RECOMMENDED_CONFIG),
            {
                "target_volatility": 0.10,
                "max_weight": 0.25,
                "max_gross": 1.00,
                "volatility_window": 63,
                "correlation_window": 63,
                "daily_loss_limit": 0.02,
                "weekly_loss_limit": 0.04,
                "weekly_drawdown_limit": 0.05,
            },
        )

    def test_leverage_is_rejected(self):
        with self.assertRaises(ValueError):
            config(max_gross=1.01)

    def test_one_name_cannot_exceed_the_whole_book(self):
        with self.assertRaises(ValueError):
            config(max_weight=0.30, max_gross=0.25)

    def test_non_positive_or_non_finite_sizes_raise(self):
        for field in ("target_volatility", "max_weight", "max_gross"):
            for bad in (0.0, -0.1, float("nan"), float("inf")):
                with self.subTest(field=field, value=bad):
                    with self.assertRaises(ValueError):
                        config(**{field: bad})

    def test_windows_below_their_minimum_raise(self):
        with self.assertRaises(ValueError):
            config(volatility_window=1)
        with self.assertRaises(ValueError):
            config(correlation_window=2)

    def test_windows_must_be_ints(self):
        for bad in (63.0, True):
            with self.subTest(value=bad):
                with self.assertRaises(TypeError):
                    config(volatility_window=bad)

    def test_loss_limits_must_lie_strictly_between_zero_and_one(self):
        for field in ("daily_loss_limit", "weekly_loss_limit", "weekly_drawdown_limit"):
            for bad in (0.0, 1.0, -0.01, float("nan")):
                with self.subTest(field=field, value=bad):
                    with self.assertRaises(ValueError):
                        config(**{field: bad})

    def test_a_bool_is_not_a_number_here(self):
        with self.assertRaises(TypeError):
            config(max_gross=True)

    def test_the_configuration_is_immutable(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            RECOMMENDED_CONFIG.max_weight = 0.5


class ModuleBoundaryTests(unittest.TestCase):
    """FR-013 (Rule 8), asserted by AST rather than by a source grep.

    A substring search would trip on the module's own docstring, which names
    `backtest_harness` precisely to say it does not import it.
    """

    def _imported_modules(self) -> set[str]:
        tree = ast.parse((SCRIPTS_DIR / "portfolio_risk.py").read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        return modules

    def test_the_import_set_is_exactly_the_declared_one(self):
        self.assertEqual(
            self._imported_modules(),
            {"__future__", "dataclasses", "numpy", "pandas", "constants"},
        )

    def test_no_signal_accounting_or_data_module_is_imported(self):
        forbidden = {
            "backtest_harness",
            "metrics",
            "signals",
            "ml_signal",
            "estimators",
            "model_cv",
            "logistic_baseline",
            "ma_crossover_backtest",
            "multi_ticker_comparison",
            "data",
            "sklearn",
        }
        self.assertEqual(self._imported_modules() & forbidden, set())


# ---------------------------------------------------------------------------
# User Story 1 -- sizing
# ---------------------------------------------------------------------------

WINDOW = 5


class RealizedVolatilityTests(unittest.TestCase):
    """FR-003 -- trailing, full-window-or-missing, annualized standard deviation."""

    def setUp(self):
        self.closes = random_panel(40, ["AAA", "BBB"], seed=7)
        # Computed here with numpy, independently of `log_returns`: returns
        # row k is the return into closes row k+1.
        self.returns = np.diff(np.log(self.closes.to_numpy()), axis=0)

    def test_matches_an_independent_recomputation(self):
        vol = realized_volatility(self.closes, window=WINDOW)
        for t in range(WINDOW, len(self.closes)):
            with self.subTest(t=t):
                expected = (
                    np.std(self.returns[t - WINDOW : t], axis=0, ddof=1) * ANNUALIZER
                )
                np.testing.assert_allclose(
                    vol.iloc[t].to_numpy(), expected, rtol=1e-10, atol=0
                )

    def test_the_first_value_is_exactly_one_full_window_in(self):
        # Row `window` is the first with `window` returns behind it (rows 1..window).
        vol = realized_volatility(self.closes, window=WINDOW)
        self.assertTrue(vol.iloc[:WINDOW].isna().all().all())
        self.assertTrue(vol.iloc[WINDOW].notna().all())

    def test_it_is_a_standard_deviation_not_a_variance(self):
        closes = panel_from_returns([[0.01], [-0.01], [0.01], [-0.01]], ["AAA"])
        vol = realized_volatility(closes, window=4).iloc[-1, 0]
        self.assertAlmostEqual(
            vol, 0.01 * math.sqrt(4 / 3) * ANNUALIZER, delta=1e-12
        )

    def test_changing_any_later_close_leaves_every_earlier_value_bit_identical(self):
        base = realized_volatility(self.closes, window=WINDOW)
        for t in (WINDOW, WINDOW + 3, len(self.closes) - 2):
            with self.subTest(t=t):
                perturbed = self.closes.copy()
                perturbed.iloc[t + 1 :] *= 3.7
                moved = realized_volatility(perturbed, window=WINDOW)
                # Bit-identical, not almost-equal: a leak through a rolling
                # step would move the low bits and pass an almost-equal check.
                self.assertEqual(
                    base.iloc[: t + 1].to_numpy().tobytes(),
                    moved.iloc[: t + 1].to_numpy().tobytes(),
                )

    def test_the_control_changing_the_close_at_t_does_change_t(self):
        t = WINDOW + 3
        perturbed = self.closes.copy()
        perturbed.iloc[t] *= 1.05
        base = realized_volatility(self.closes, window=WINDOW).iloc[t]
        moved = realized_volatility(perturbed, window=WINDOW).iloc[t]
        self.assertFalse(np.array_equal(base.to_numpy(), moved.to_numpy()))

    def test_a_missing_bar_re_warms_that_tickers_window(self):
        closes = self.closes.copy()
        gap = 12
        closes.iloc[gap, 0] = np.nan
        vol = realized_volatility(closes, window=WINDOW)
        # Returns at `gap` and `gap+1` are missing, so every window ending in
        # [gap, gap+window] is incomplete.
        self.assertTrue(np.isfinite(vol["AAA"].iloc[gap - 1]))
        self.assertTrue(vol["AAA"].iloc[gap : gap + WINDOW + 1].isna().all())
        self.assertTrue(np.isfinite(vol["AAA"].iloc[gap + WINDOW + 1]))
        self.assertTrue(vol["BBB"].iloc[WINDOW:].notna().all())

    def test_the_window_is_validated(self):
        with self.assertRaises(ValueError):
            realized_volatility(self.closes, window=1)
        with self.assertRaises(TypeError):
            realized_volatility(self.closes, window=True)


class VolatilityTargetSizingTests(unittest.TestCase):
    """FR-001 -- confidence x target volatility / volatility."""

    def test_matches_hand_computed_weights(self):
        confidence = weights({"AAA": 1.0, "BBB": 0.5, "CCC": 0.25})
        volatility = weights({"AAA": 0.2, "BBB": 0.4, "CCC": 0.1})
        result = volatility_target_weights(
            confidence, volatility, target_volatility=0.1
        )
        # Literal expectations, not the formula re-evaluated: recomputing it
        # by the same expression would only prove the code is deterministic.
        for ticker, expected in {"AAA": 0.5, "BBB": 0.125, "CCC": 0.25}.items():
            self.assertAlmostEqual(result[ticker], expected, delta=1e-12)

    def test_doubling_volatility_halves_the_weight(self):
        result = volatility_target_weights(
            weights({"AAA": 0.7, "BBB": 0.7}),
            weights({"AAA": 0.2, "BBB": 0.4}),
            target_volatility=0.1,
        )
        self.assertAlmostEqual(result["BBB"] / result["AAA"], 0.5, delta=1e-15)

    def test_zero_or_missing_confidence_is_exactly_zero(self):
        result = volatility_target_weights(
            weights({"AAA": 0.0, "BBB": np.nan}),
            weights({"AAA": 0.2, "BBB": 0.2}),
            target_volatility=0.1,
        )
        self.assertEqual(result.tolist(), [0.0, 0.0])

    def test_zero_missing_or_infinite_volatility_is_exactly_zero(self):
        # A zero volatility divides into an infinite weight that the per-name
        # cap would silently turn into a maximum-size position.
        result = volatility_target_weights(
            weights({"AAA": 1.0, "BBB": 1.0, "CCC": 1.0}),
            weights({"AAA": 0.0, "BBB": np.nan, "CCC": np.inf}),
            target_volatility=0.1,
        )
        self.assertEqual(result.tolist(), [0.0, 0.0, 0.0])

    def test_confidence_outside_the_unit_interval_raises(self):
        for bad in (1.5, -0.1, np.inf):
            with self.subTest(confidence=bad):
                with self.assertRaises(ValueError):
                    volatility_target_weights(
                        weights({"AAA": bad}),
                        weights({"AAA": 0.2}),
                        target_volatility=0.1,
                    )

    def test_negative_volatility_raises(self):
        with self.assertRaises(ValueError):
            volatility_target_weights(
                weights({"AAA": 1.0}), weights({"AAA": -0.2}), target_volatility=0.1
            )

    def test_mismatched_tickers_raise(self):
        with self.assertRaises(ValueError):
            volatility_target_weights(
                weights({"AAA": 1.0, "BBB": 1.0}),
                weights({"AAA": 0.2, "CCC": 0.2}),
                target_volatility=0.1,
            )

    def test_alignment_is_by_label_not_position(self):
        confidence = weights({"AAA": 1.0, "BBB": 0.5})
        aligned = volatility_target_weights(
            confidence, weights({"AAA": 0.2, "BBB": 0.4}), target_volatility=0.1
        )
        reversed_order = volatility_target_weights(
            confidence, weights({"BBB": 0.4, "AAA": 0.2}), target_volatility=0.1
        )
        pd.testing.assert_series_equal(aligned, reversed_order)

    def test_target_volatility_must_be_positive_and_finite(self):
        for bad in (0.0, -0.1, float("nan")):
            with self.subTest(target_volatility=bad):
                with self.assertRaises(ValueError):
                    volatility_target_weights(
                        weights({"AAA": 1.0}),
                        weights({"AAA": 0.2}),
                        target_volatility=bad,
                    )


class NoKellyPathTests(unittest.TestCase):
    """FR-002 -- there is no Kelly fraction to set, full or otherwise.

    Identifiers only: the module's docstring explains why Kelly was rejected,
    and that explanation is supposed to stay.
    """

    def test_no_identifier_in_the_module_is_a_kelly_anything(self):
        tree = ast.parse((SCRIPTS_DIR / "portfolio_risk.py").read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                names.add(node.arg)
        self.assertEqual({name for name in names if "kelly" in name.lower()}, set())

    def test_the_configuration_has_no_kelly_field(self):
        fields = {field.name for field in dataclasses.fields(RiskConfig)}
        self.assertEqual({name for name in fields if "kelly" in name.lower()}, set())


# ---------------------------------------------------------------------------
# User Story 2 -- correlation
# ---------------------------------------------------------------------------


class TrailingCorrelationTests(unittest.TestCase):
    """FR-004 -- the trailing window ending at the session, and nothing after it."""

    def setUp(self):
        self.closes = random_panel(40, ["AAA", "BBB", "CCC"], seed=11)
        self.returns = np.diff(np.log(self.closes.to_numpy()), axis=0)

    def test_matches_numpy_on_the_trailing_slice(self):
        t, window = 30, 10
        corr = trailing_correlation(self.closes, self.closes.index[t], window=window)
        expected = np.corrcoef(self.returns[t - window : t], rowvar=False)
        np.testing.assert_allclose(corr.to_numpy(), expected, rtol=0, atol=1e-12)

    def test_too_little_history_is_undefined_not_guessed(self):
        corr = trailing_correlation(self.closes, self.closes.index[5], window=10)
        self.assertTrue(corr.isna().all().all())
        self.assertEqual(list(corr.index), ["AAA", "BBB", "CCC"])

    def test_exactly_one_full_window_is_enough_and_one_less_is_not(self):
        full = trailing_correlation(self.closes, self.closes.index[10], window=10)
        short = trailing_correlation(self.closes, self.closes.index[9], window=10)
        self.assertTrue(full.notna().all().all())
        self.assertTrue(short.isna().all().all())

    def test_the_first_session_is_undefined_not_an_error(self):
        corr = trailing_correlation(self.closes, self.closes.index[0], window=10)
        self.assertEqual(corr.shape, (3, 3))
        self.assertTrue(corr.isna().all().all())

    def test_changing_any_later_close_leaves_it_bit_identical(self):
        t = 25
        base = trailing_correlation(self.closes, self.closes.index[t], window=10)
        perturbed = self.closes.copy()
        perturbed.iloc[t + 1 :] *= 3.7
        perturbed.iloc[t + 2, 1] = np.nan
        moved = trailing_correlation(perturbed, perturbed.index[t], window=10)
        self.assertEqual(base.to_numpy().tobytes(), moved.to_numpy().tobytes())

    def test_the_control_changing_the_close_at_t_does_change_it(self):
        t = 25
        perturbed = self.closes.copy()
        perturbed.iloc[t, 0] *= 1.05
        base = trailing_correlation(self.closes, self.closes.index[t], window=10)
        moved = trailing_correlation(perturbed, perturbed.index[t], window=10)
        self.assertNotEqual(base.loc["AAA", "BBB"], moved.loc["AAA", "BBB"])

    def test_a_missing_bar_blanks_only_that_tickers_pairs(self):
        closes = self.closes.copy()
        closes.iloc[28, 1] = np.nan
        corr = trailing_correlation(closes, closes.index[30], window=10)
        self.assertTrue(corr.loc["BBB"].isna().all())
        self.assertTrue(corr["BBB"].isna().all())
        self.assertTrue(np.isfinite(corr.loc["AAA", "CCC"]))

    def test_orthogonal_patterns_are_exactly_zero_and_identical_ones_exactly_one(self):
        h = hadamard(16)
        closes = panel_from_returns(
            0.01 * np.column_stack([h[1], h[2], h[1]]), ["AAA", "BBB", "CCC"]
        )
        corr = trailing_correlation(closes, closes.index[-1], window=16)
        self.assertAlmostEqual(corr.loc["AAA", "BBB"], 0.0, delta=1e-12)
        self.assertAlmostEqual(corr.loc["AAA", "CCC"], 1.0, delta=1e-12)


class CorrelationAdjustmentTests(unittest.TestCase):
    """FR-005 -- each active weight divided by its overlap."""

    TICKERS = ["AAA", "BBB"]

    def test_perfectly_correlated_names_are_one_bet(self):
        adjusted = correlation_adjusted_weights(
            weights({"AAA": 0.2, "BBB": 0.2}), matrix([[1, 1], [1, 1]], self.TICKERS)
        )
        self.assertEqual(adjusted.tolist(), [0.1, 0.1])

    def test_uncorrelated_names_are_untouched(self):
        adjusted = correlation_adjusted_weights(
            weights({"AAA": 0.2, "BBB": 0.3}), matrix([[1, 0], [0, 1]], self.TICKERS)
        )
        self.assertEqual(adjusted.tolist(), [0.2, 0.3])

    def test_a_negative_correlation_earns_no_extra_size(self):
        adjusted = correlation_adjusted_weights(
            weights({"AAA": 0.2, "BBB": 0.3}),
            matrix([[1, -0.8], [-0.8, 1]], self.TICKERS),
        )
        self.assertEqual(adjusted.tolist(), [0.2, 0.3])

    def test_a_name_that_is_not_held_does_not_shrink_anyone(self):
        tickers = ["AAA", "BBB", "CCC"]
        adjusted = correlation_adjusted_weights(
            weights({"AAA": 0.2, "BBB": 0.0, "CCC": 0.2}),
            matrix([[1, 1, 0], [1, 1, 1], [0, 1, 1]], tickers),
        )
        self.assertEqual(adjusted.tolist(), [0.2, 0.0, 0.2])

    def test_overlap_is_one_plus_the_positive_correlations_with_held_names(self):
        tickers = ["AAA", "BBB", "CCC", "DDD"]
        overlap = position_overlap(
            weights({"AAA": 0.1, "BBB": 0.1, "CCC": 0.1, "DDD": 0.0}),
            matrix(
                [
                    [1.0, 0.5, -0.3, 0.9],
                    [0.5, 1.0, 0.2, 0.9],
                    [-0.3, 0.2, 1.0, 0.9],
                    [0.9, 0.9, 0.9, 1.0],
                ],
                tickers,
            ),
        )
        np.testing.assert_allclose(overlap.iloc[:3].to_numpy(), [1.5, 1.7, 1.2], atol=1e-15)
        self.assertTrue(np.isnan(overlap["DDD"]))

    def test_it_never_increases_any_weight(self):
        rng = np.random.default_rng(2026)
        tickers = ["A", "B", "C", "D", "E"]
        for trial in range(200):
            with self.subTest(trial=trial):
                loadings = rng.normal(size=(5, 3))
                covariance = loadings @ loadings.T + np.diag(rng.uniform(0.1, 1.0, 5))
                scale = np.sqrt(np.diag(covariance))
                corr = matrix(covariance / np.outer(scale, scale), tickers)
                held = pd.Series(
                    rng.uniform(0.0, 0.3, 5) * (rng.uniform(size=5) > 0.3),
                    index=tickers,
                )
                adjusted = correlation_adjusted_weights(held, corr)
                self.assertTrue((adjusted.to_numpy() <= held.to_numpy()).all())
                active = held > 0
                self.assertTrue((position_overlap(held, corr)[active] >= 1.0).all())

    def test_a_diagonal_one_ulp_below_one_does_not_grow_an_isolated_name(self):
        below_one = np.nextafter(1.0, 0.0)
        adjusted = correlation_adjusted_weights(
            weights({"AAA": 0.2, "BBB": 0.3}),
            matrix([[below_one, 0.0], [0.0, below_one]], self.TICKERS),
        )
        self.assertEqual(adjusted.tolist(), [0.2, 0.3])

    def test_an_undefined_correlation_between_held_names_raises(self):
        with self.assertRaises(ValueError):
            correlation_adjusted_weights(
                weights({"AAA": 0.2, "BBB": 0.2}),
                matrix([[1, np.nan], [np.nan, 1]], self.TICKERS),
            )

    def test_an_undefined_correlation_with_a_flat_name_is_fine(self):
        adjusted = correlation_adjusted_weights(
            weights({"AAA": 0.2, "BBB": 0.0}),
            matrix([[1, np.nan], [np.nan, np.nan]], self.TICKERS),
        )
        self.assertEqual(adjusted.tolist(), [0.2, 0.0])

    def test_a_correlation_outside_minus_one_to_one_raises(self):
        with self.assertRaises(ValueError):
            correlation_adjusted_weights(
                weights({"AAA": 0.2, "BBB": 0.2}),
                matrix([[1, 1.5], [1.5, 1]], self.TICKERS),
            )

    def test_mismatched_tickers_raise(self):
        with self.assertRaises(ValueError):
            correlation_adjusted_weights(
                weights({"AAA": 0.2, "BBB": 0.2}),
                matrix([[1, 0], [0, 1]], ["AAA", "CCC"]),
            )

    def test_the_matrix_is_matched_by_label(self):
        corr = matrix([[1.0, 0.5], [0.5, 1.0]], self.TICKERS)
        held = weights({"AAA": 0.2, "BBB": 0.1})
        pd.testing.assert_series_equal(
            correlation_adjusted_weights(held, corr),
            correlation_adjusted_weights(held, corr.iloc[::-1, ::-1]),
        )


class ExAnteVolatilityTests(unittest.TestCase):
    """SC-005 -- one bet's volatility per effective independent bet."""

    def test_book_volatility_follows_the_effective_number_of_bets(self):
        k, sigma, size = 5, 0.3, 0.2
        tickers = [f"T{i}" for i in range(k)]
        for rho in (0.0, 0.3, 0.6, 1.0):
            with self.subTest(rho=rho):
                corr = np.full((k, k), rho)
                np.fill_diagonal(corr, 1.0)
                adjusted = correlation_adjusted_weights(
                    pd.Series(size, index=tickers), matrix(corr, tickers)
                ).to_numpy()
                covariance = corr * sigma**2
                book_vol = math.sqrt(adjusted @ covariance @ adjusted)
                expected = size * sigma * math.sqrt(k / (1 + (k - 1) * rho))
                self.assertAlmostEqual(book_vol, expected, delta=1e-12)

    def test_at_perfect_correlation_the_book_is_exactly_one_bet(self):
        k, sigma, size = 5, 0.3, 0.2
        tickers = [f"T{i}" for i in range(k)]
        adjusted = correlation_adjusted_weights(
            pd.Series(size, index=tickers), matrix(np.ones((k, k)), tickers)
        ).to_numpy()
        book_vol = math.sqrt(adjusted @ (np.ones((k, k)) * sigma**2) @ adjusted)
        self.assertAlmostEqual(book_vol, size * sigma, delta=1e-12)


class GrossCapTests(unittest.TestCase):
    """FR-007 -- the whole book, scaled together."""

    def test_below_the_cap_nothing_changes(self):
        held = weights({"AAA": 0.2, "BBB": 0.3})
        self.assertEqual(apply_gross_cap(held, max_gross=1.0).tolist(), [0.2, 0.3])

    def test_above_the_cap_every_weight_scales_by_the_same_factor(self):
        held = weights({"AAA": 0.8, "BBB": 0.4, "CCC": 0.2})
        scaled = apply_gross_cap(held, max_gross=1.0)
        self.assertAlmostEqual(scaled.sum(), 1.0, delta=1e-12)
        np.testing.assert_allclose(
            scaled.to_numpy(), held.to_numpy() / 1.4, rtol=1e-12, atol=0
        )

    def test_leverage_and_non_positive_caps_raise(self):
        for bad in (1.5, 0.0):
            with self.subTest(max_gross=bad):
                with self.assertRaises(ValueError):
                    apply_gross_cap(weights({"AAA": 0.2}), max_gross=bad)

    def test_negative_weights_raise(self):
        with self.assertRaises(ValueError):
            apply_gross_cap(weights({"AAA": -0.2}), max_gross=1.0)


# ---------------------------------------------------------------------------
# User Story 3 -- loss caps
# ---------------------------------------------------------------------------


class EntryHaltTests(unittest.TestCase):
    """FR-010 -- a halt blocks added risk and nothing else."""

    def halt(self, target, current, halted=True):
        return apply_entry_halt(
            weights({"AAA": target}), weights({"AAA": current}), halted=halted
        )["AAA"]

    def test_without_a_halt_the_target_passes_through(self):
        self.assertEqual(self.halt(0.2, 0.0, halted=False), 0.2)

    def test_opening_from_flat_is_blocked(self):
        self.assertEqual(self.halt(0.2, 0.0), 0.0)

    def test_adding_to_an_open_position_is_blocked(self):
        # The loophole a literal reading of "new entries" would leave.
        self.assertEqual(self.halt(0.2, 0.1), 0.1)

    def test_reducing_is_allowed(self):
        self.assertEqual(self.halt(0.05, 0.1), 0.05)

    def test_exiting_is_allowed(self):
        # A halt that trapped the book in its losers would add risk.
        self.assertEqual(self.halt(0.0, 0.1), 0.0)

    def test_current_holdings_must_be_reported(self):
        for bad in (np.nan, -0.1):
            with self.subTest(current=bad):
                with self.assertRaises(ValueError):
                    self.halt(0.2, bad)

    def test_mismatched_tickers_raise(self):
        with self.assertRaises(ValueError):
            apply_entry_halt(
                weights({"AAA": 0.2}), weights({"BBB": 0.2}), halted=True
            )

    def test_the_halt_flag_must_be_a_bool(self):
        for bad in (1, "yes", None):
            with self.subTest(halted=bad):
                with self.assertRaises(TypeError):
                    apply_entry_halt(
                        weights({"AAA": 0.2}), weights({"AAA": 0.1}), halted=bad
                    )


# 2026 calendar used below: 08-28 Fri, 08-31 Mon, 09-01 Tue, 09-02 Wed,
# 09-03 Thu, 09-04 Fri, 09-07 Mon (Labor Day, no session), 09-08 Tue.


class LossCapGuardTests(unittest.TestCase):
    """FR-008/FR-009 -- daily and weekly caps, and how long each halt lasts."""

    def test_the_first_session_has_no_daily_loss_and_anchors_its_week(self):
        status = LossCapGuard(**LIMITS).observe(pd.Timestamp("2026-08-28"), 100.0)
        self.assertTrue(math.isnan(status.daily_return))
        self.assertEqual(status.weekly_return, 0.0)
        self.assertEqual(status.weekly_drawdown, 0.0)
        self.assertFalse(status.entries_halted)

    def test_a_first_week_is_anchored_on_the_first_observed_equity(self):
        statuses = feed(LossCapGuard(**LIMITS), ["2026-09-02", "2026-09-03"], [100.0, 95.5])
        self.assertAlmostEqual(statuses[1].weekly_return, -0.045, delta=1e-12)
        self.assertTrue(statuses[1].weekly_loss_breach)

    def test_a_daily_breach_halts_that_sessions_decision_only(self):
        statuses = feed(
            LossCapGuard(**LIMITS),
            ["2026-08-28", "2026-08-31", "2026-09-01", "2026-09-02"],
            [100.0, 100.0, 97.0, 97.5],
        )
        self.assertEqual([s.entries_halted for s in statuses], [False, False, True, False])
        self.assertTrue(statuses[2].daily_breach)
        self.assertFalse(statuses[2].weekly_latched)

    def test_a_daily_loss_exactly_at_the_limit_halts(self):
        # 75/100 is exactly 0.75, so the return is exactly -0.25: the boundary
        # itself, not a value near it.
        statuses = feed(
            LossCapGuard(daily_loss_limit=0.25, weekly_loss_limit=0.5, weekly_drawdown_limit=0.5),
            ["2026-08-28", "2026-08-31"],
            [100.0, 75.0],
        )
        self.assertEqual(statuses[1].daily_return, -0.25)
        self.assertTrue(statuses[1].daily_breach)
        self.assertTrue(statuses[1].entries_halted)

    def test_a_daily_loss_one_ulp_inside_the_limit_does_not(self):
        statuses = feed(
            LossCapGuard(daily_loss_limit=0.25, weekly_loss_limit=0.5, weekly_drawdown_limit=0.5),
            ["2026-08-28", "2026-08-31"],
            [100.0, float(np.nextafter(75.0, np.inf))],
        )
        self.assertGreater(statuses[1].daily_return, -0.25)
        self.assertFalse(statuses[1].daily_breach)

    def test_a_weekly_loss_exactly_at_the_limit_halts_and_one_ulp_inside_does_not(self):
        limits = {"daily_loss_limit": 0.5, "weekly_loss_limit": 0.25, "weekly_drawdown_limit": 0.5}
        dates = ["2026-08-28", "2026-08-31", "2026-09-01"]
        at = feed(LossCapGuard(**limits), dates, [100.0, 90.0, 75.0])
        inside = feed(
            LossCapGuard(**limits), dates, [100.0, 90.0, float(np.nextafter(75.0, np.inf))]
        )
        self.assertEqual(at[2].weekly_return, -0.25)
        self.assertTrue(at[2].weekly_loss_breach)
        self.assertFalse(at[2].daily_breach)
        self.assertGreater(inside[2].weekly_return, -0.25)
        self.assertFalse(inside[2].weekly_loss_breach)

    def test_a_weekly_drawdown_exactly_at_the_limit_halts_and_one_ulp_inside_does_not(self):
        limits = {"daily_loss_limit": 0.5, "weekly_loss_limit": 0.5, "weekly_drawdown_limit": 0.25}
        dates = ["2026-08-28", "2026-08-31", "2026-09-01"]
        # Monday rallies to a new high of 100 from an anchor of 80; Tuesday's 75
        # is exactly 25% below that high and still inside the weekly loss limit.
        at = feed(LossCapGuard(**limits), dates, [80.0, 100.0, 75.0])
        inside = feed(
            LossCapGuard(**limits), dates, [80.0, 100.0, float(np.nextafter(75.0, np.inf))]
        )
        self.assertEqual(at[2].weekly_drawdown, -0.25)
        self.assertTrue(at[2].weekly_drawdown_breach)
        self.assertFalse(at[2].weekly_loss_breach)
        self.assertFalse(at[2].daily_breach)
        self.assertGreater(inside[2].weekly_drawdown, -0.25)
        self.assertFalse(inside[2].weekly_drawdown_breach)

    def test_a_weekly_halt_stays_on_after_recovery_and_ends_with_the_week(self):
        statuses = feed(
            LossCapGuard(**LIMITS),
            ["2026-08-28", "2026-08-31", "2026-09-01", "2026-09-02",
             "2026-09-03", "2026-09-04", "2026-09-08"],
            [100.0, 98.5, 97.0, 95.5, 99.0, 99.5, 99.6],
        )
        self.assertEqual(
            [s.entries_halted for s in statuses],
            [False, False, False, True, True, True, False],
        )
        wednesday, thursday = statuses[3], statuses[4]
        self.assertTrue(wednesday.weekly_loss_breach)
        self.assertFalse(wednesday.daily_breach)
        # Thursday has recovered inside every limit; only the latch holds it.
        self.assertFalse(thursday.daily_breach)
        self.assertFalse(thursday.weekly_loss_breach)
        self.assertFalse(thursday.weekly_drawdown_breach)
        self.assertTrue(thursday.weekly_latched)

    def test_a_week_that_gives_back_its_gains_hits_the_drawdown_cap(self):
        statuses = feed(
            LossCapGuard(daily_loss_limit=0.5, weekly_loss_limit=0.04, weekly_drawdown_limit=0.05),
            ["2026-08-28", "2026-08-31", "2026-09-01", "2026-09-02"],
            [100.0, 103.0, 104.0, 98.5],
        )
        self.assertTrue(statuses[3].weekly_drawdown_breach)
        self.assertFalse(statuses[3].weekly_loss_breach)
        self.assertTrue(statuses[3].entries_halted)

    def test_the_weeks_high_water_mark_includes_its_anchor(self):
        # A week that only falls has its high at the prior Friday's close.
        statuses = feed(
            LossCapGuard(daily_loss_limit=0.5, weekly_loss_limit=0.5, weekly_drawdown_limit=0.05),
            ["2026-08-28", "2026-08-31"],
            [100.0, 94.9],
        )
        self.assertAlmostEqual(statuses[1].weekly_drawdown, -0.051, delta=1e-12)
        self.assertTrue(statuses[1].weekly_drawdown_breach)

    def test_a_monday_gap_is_inside_the_new_weeks_loss(self):
        statuses = feed(
            LossCapGuard(daily_loss_limit=0.5, weekly_loss_limit=0.04, weekly_drawdown_limit=0.5),
            ["2026-08-27", "2026-08-28", "2026-08-31"],
            [100.0, 100.0, 95.0],
        )
        self.assertAlmostEqual(statuses[2].weekly_return, -0.05, delta=1e-12)
        self.assertTrue(statuses[2].weekly_loss_breach)

    def test_a_holiday_week_is_still_one_week(self):
        # Good Friday 2026 is 04-03: the week of 03-30 has four sessions.
        statuses = feed(
            LossCapGuard(**LIMITS),
            ["2026-03-27", "2026-03-30", "2026-03-31", "2026-04-01", "2026-04-02", "2026-04-06"],
            [100.0, 98.5, 97.0, 95.5, 99.0, 99.5],
        )
        self.assertEqual(
            [s.entries_halted for s in statuses],
            [False, False, False, True, True, False],
        )

    def test_a_week_spanning_new_year_is_one_week(self):
        self.assertEqual(tuple(pd.Timestamp("2025-12-29").isocalendar())[:2], (2026, 1))
        self.assertEqual(tuple(pd.Timestamp("2026-01-02").isocalendar())[:2], (2026, 1))
        statuses = feed(
            LossCapGuard(**LIMITS),
            ["2025-12-26", "2025-12-29", "2025-12-30", "2025-12-31", "2026-01-02", "2026-01-05"],
            [100.0, 98.5, 97.0, 95.5, 99.0, 99.5],
        )
        # Wednesday 12-31 breaches; Friday 01-02 is the same week and stays halted.
        self.assertEqual(
            [s.entries_halted for s in statuses],
            [False, False, False, True, True, False],
        )

    def test_a_missing_week_anchors_on_the_last_observed_close(self):
        statuses = feed(LossCapGuard(**LIMITS), ["2026-08-14", "2026-08-24"], [100.0, 97.0])
        self.assertAlmostEqual(statuses[1].daily_return, -0.03, delta=1e-12)
        self.assertAlmostEqual(statuses[1].weekly_return, -0.03, delta=1e-12)
        self.assertTrue(statuses[1].daily_breach)

    def test_sessions_must_strictly_increase(self):
        guard = LossCapGuard(**LIMITS)
        guard.observe(pd.Timestamp("2026-08-31"), 100.0)
        for bad in ("2026-08-31", "2026-08-28"):
            with self.subTest(session=bad):
                with self.assertRaises(ValueError):
                    guard.observe(pd.Timestamp(bad), 100.0)

    def test_equity_must_be_positive_and_finite(self):
        guard = LossCapGuard(**LIMITS)
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(equity=bad):
                with self.assertRaises(ValueError):
                    guard.observe(pd.Timestamp("2026-08-31"), bad)
        with self.assertRaises(TypeError):
            guard.observe(pd.Timestamp("2026-08-31"), "100")

    def test_a_rejected_observation_leaves_the_guard_unchanged(self):
        guard = LossCapGuard(**LIMITS)
        guard.observe(pd.Timestamp("2026-08-28"), 100.0)
        for session, equity in (("2026-08-27", 100.0), ("2026-08-31", float("nan"))):
            with self.assertRaises(ValueError):
                guard.observe(pd.Timestamp(session), equity)
        after_rejections = guard.observe(pd.Timestamp("2026-08-31"), 97.0)
        fresh = feed(LossCapGuard(**LIMITS), ["2026-08-28", "2026-08-31"], [100.0, 97.0])[1]
        self.assertEqual(after_rejections, fresh)

    def test_session_labels_are_held_to_the_convention(self):
        for bad in (
            pd.Timestamp("2026-08-31", tz="America/New_York"),
            pd.Timestamp("2026-08-31 16:00"),
            pd.NaT,
        ):
            with self.subTest(session=bad):
                with self.assertRaises(ValueError):
                    LossCapGuard(**LIMITS).observe(bad, 100.0)

    def test_limits_are_validated(self):
        for field in LIMITS:
            for bad in (0.0, 1.0, -0.1, float("nan")):
                with self.subTest(field=field, value=bad):
                    with self.assertRaises(ValueError):
                        LossCapGuard(**{**LIMITS, field: bad})
            with self.assertRaises(TypeError):
                LossCapGuard(**{**LIMITS, field: True})

    def test_from_config_reads_the_configured_limits(self):
        guard = LossCapGuard.from_config(RECOMMENDED_CONFIG)
        self.assertEqual(
            (guard.daily_loss_limit, guard.weekly_loss_limit, guard.weekly_drawdown_limit),
            (0.02, 0.04, 0.05),
        )


class LossCapHistoryTests(unittest.TestCase):
    """FR-011 -- the whole-series view is the streaming guard, run in order."""

    COLUMNS = [
        "equity",
        "daily_return",
        "weekly_return",
        "weekly_drawdown",
        "daily_breach",
        "weekly_loss_breach",
        "weekly_drawdown_breach",
        "weekly_latched",
        "entries_halted",
    ]

    def setUp(self):
        rng = np.random.default_rng(17)
        steps = rng.normal(0.0, 0.012, 80)
        steps[20] = -0.05
        steps[47] = -0.03
        self.equity = pd.Series(
            100.0 * np.exp(np.cumsum(steps)), index=sessions(80, "2026-01-05")
        )

    def test_it_equals_feeding_the_guard_one_session_at_a_time(self):
        history = loss_cap_history(self.equity, **LIMITS)
        self.assertEqual(list(history.columns), self.COLUMNS)
        self.assertTrue(history["entries_halted"].any())
        guard = LossCapGuard(**LIMITS)
        for session, value in self.equity.items():
            status = guard.observe(session, value)
            row = history.loc[session]
            for name in self.COLUMNS:
                expected, actual = getattr(status, name), row[name]
                with self.subTest(session=session, field=name):
                    if isinstance(expected, float) and math.isnan(expected):
                        self.assertTrue(math.isnan(actual))
                    else:
                        self.assertEqual(actual, expected)

    def test_changing_later_equity_leaves_every_earlier_row_identical(self):
        base = loss_cap_history(self.equity, **LIMITS)
        for t in (0, 19, 20, 45, 78):
            with self.subTest(t=t):
                perturbed = self.equity.copy()
                perturbed.iloc[t + 1 :] *= 0.5
                moved = loss_cap_history(perturbed, **LIMITS)
                pd.testing.assert_frame_equal(base.iloc[: t + 1], moved.iloc[: t + 1])

    def test_the_control_changing_equity_at_t_does_change_t(self):
        t = 30
        perturbed = self.equity.copy()
        perturbed.iloc[t] *= 0.9
        base = loss_cap_history(self.equity, **LIMITS)
        moved = loss_cap_history(perturbed, **LIMITS)
        self.assertNotEqual(base["daily_return"].iloc[t], moved["daily_return"].iloc[t])
        self.assertTrue(moved["daily_breach"].iloc[t])

    def test_an_empty_series_is_an_empty_history(self):
        empty = pd.Series([], index=pd.DatetimeIndex([]), dtype="float64")
        history = loss_cap_history(empty, **LIMITS)
        self.assertEqual(len(history), 0)
        self.assertEqual(list(history.columns), self.COLUMNS)


# ---------------------------------------------------------------------------
# Composition and end-to-end
# ---------------------------------------------------------------------------

TICKERS5 = ["AAA", "BBB", "CCC", "DDD", "EEE"]


class TargetWeightsCompositionTests(unittest.TestCase):
    """FR-006/FR-012 -- one decision, every step on the record."""

    STEP_COLUMNS = [
        "Confidence",
        "Volatility",
        "Standalone",
        "Capped",
        "Overlap",
        "Adjusted",
        "Gross_Scaled",
        "Current",
        "Target",
    ]

    def setUp(self):
        self.closes = random_panel(200, TICKERS5, seed=23)
        self.config = config(volatility_window=20, correlation_window=20)
        self.confidence = pd.Series([1.0, 0.8, 0.6, 0.4, 0.2], index=TICKERS5)
        self.flat = pd.Series(0.0, index=TICKERS5)

    def decide(self, row=120, closes=None, confidence=None, current=None, cfg=None, halted=False):
        closes = self.closes if closes is None else closes
        return target_weights(
            closes,
            self.confidence if confidence is None else confidence,
            self.flat if current is None else current,
            session=closes.index[row],
            config=self.config if cfg is None else cfg,
            entries_halted=halted,
        )

    def test_every_step_is_a_column_and_the_session_is_recorded(self):
        decision = self.decide()
        self.assertEqual(list(decision.columns), self.STEP_COLUMNS)
        self.assertEqual(list(decision.index), TICKERS5)
        self.assertEqual(decision.attrs["session"], self.closes.index[120])
        self.assertFalse(decision.attrs["entries_halted"])
        self.assertTrue((decision["Target"] > 0).all())

    def test_changing_anything_after_the_session_leaves_the_decision_bit_identical(self):
        base = self.decide()
        perturbed = self.closes.copy()
        perturbed.iloc[121:] *= 3.7
        perturbed.iloc[150, 2] = np.nan
        moved = self.decide(closes=perturbed)
        self.assertEqual(base.to_numpy().tobytes(), moved.to_numpy().tobytes())

    def test_the_control_changing_the_sessions_own_close_changes_the_decision(self):
        perturbed = self.closes.copy()
        perturbed.iloc[120, 0] *= 1.05
        self.assertNotEqual(
            self.decide()["Volatility"]["AAA"],
            self.decide(closes=perturbed)["Volatility"]["AAA"],
        )

    def test_before_a_full_window_nothing_is_sized(self):
        for row in (0, 10, 19):
            with self.subTest(row=row):
                decision = self.decide(row=row)
                self.assertTrue((decision["Target"] == 0.0).all())
                self.assertTrue(decision["Volatility"].isna().all())

    def test_exactly_one_full_window_is_enough(self):
        self.assertTrue((self.decide(row=20)["Target"] > 0).all())

    def test_a_correlation_window_longer_than_the_volatility_window_waits_for_both(self):
        cfg = config(volatility_window=10, correlation_window=40)
        decision = self.decide(row=20, cfg=cfg)
        self.assertTrue((decision["Target"] == 0.0).all())
        self.assertTrue((self.decide(row=40, cfg=cfg)["Target"] > 0).all())

    def test_a_recent_missing_bar_leaves_only_that_name_unsized(self):
        closes = self.closes.copy()
        closes.iloc[115, 1] = np.nan
        decision = self.decide(closes=closes)
        self.assertEqual(decision.loc["BBB", "Target"], 0.0)
        self.assertTrue(np.isnan(decision.loc["BBB", "Volatility"]))
        self.assertTrue((decision.drop(index="BBB")["Target"] > 0).all())

    def test_no_conviction_anywhere_is_an_all_zero_book(self):
        decision = self.decide(confidence=pd.Series(0.0, index=TICKERS5))
        self.assertTrue((decision["Target"] == 0.0).all())

    def test_inputs_are_matched_by_label_not_position(self):
        current = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05], index=TICKERS5)
        aligned = self.decide(current=current, halted=True)
        shuffled = self.decide(
            confidence=self.confidence.iloc[::-1], current=current.iloc[::-1], halted=True
        )
        pd.testing.assert_frame_equal(aligned, shuffled)

    def test_the_step_invariants_hold_across_sessions(self):
        rng = np.random.default_rng(5)
        for row in range(20, 200, 7):
            with self.subTest(row=row):
                confidence = pd.Series(rng.uniform(0, 1, 5), index=TICKERS5)
                decision = self.decide(row=row, confidence=confidence)
                self.assertTrue((decision["Capped"] <= self.config.max_weight).all())
                self.assertTrue((decision["Adjusted"] <= decision["Capped"]).all())
                self.assertLessEqual(decision["Gross_Scaled"].sum(), self.config.max_gross + 1e-12)
                self.assertTrue((decision["Target"] >= 0).all())

    def test_a_halted_decision_never_exceeds_current_holdings(self):
        current = pd.Series([0.30, 0.0, 0.01, 0.02, 0.0], index=TICKERS5)
        decision = self.decide(current=current, halted=True)
        self.assertTrue(decision.attrs["entries_halted"])
        np.testing.assert_array_equal(
            decision["Target"].to_numpy(),
            np.minimum(decision["Gross_Scaled"].to_numpy(), current.to_numpy()),
        )
        self.assertTrue((decision["Target"] <= decision["Current"]).all())

    def test_the_configuration_and_inputs_are_checked(self):
        with self.assertRaises(TypeError):
            self.decide(cfg=dataclasses.asdict(self.config))
        with self.assertRaises(ValueError):
            self.decide(confidence=self.confidence.drop(index="EEE"))


class CapOrderingTests(unittest.TestCase):
    """US2 #6 / FR-006 -- cap first, then share, or the cap undoes the sharing."""

    def test_three_correlated_names_above_the_cap_combine_to_one_cap(self):
        h = hadamard(64)
        cluster = 0.001 * h[1]
        closes = panel_from_returns(
            np.column_stack([cluster, cluster, cluster, 0.001 * h[2]]),
            ["AAA", "BBB", "CCC", "DDD"],
        )
        cfg = config(volatility_window=64, correlation_window=64)
        names = ["AAA", "BBB", "CCC", "DDD"]
        decision = target_weights(
            closes,
            pd.Series(1.0, index=names),
            pd.Series(0.0, index=names),
            session=closes.index[-1],
            config=cfg,
            entries_halted=False,
        )
        # Precondition: the cap binds for every name, or the order is untested.
        self.assertTrue((decision["Standalone"] > cfg.max_weight).all())
        self.assertAlmostEqual(
            decision.loc[["AAA", "BBB", "CCC"], "Target"].sum(), cfg.max_weight, delta=1e-12
        )
        self.assertAlmostEqual(decision.loc["DDD", "Target"], cfg.max_weight, delta=1e-12)


class FiveTickerUniverseTests(unittest.TestCase):
    """SC-004 / FR-017 -- on exactly spec 013's universe.

    AAPL, MSFT and GOOGL share one pattern plus a small orthogonal idiosyncratic
    part (pairwise correlation exactly 1/1.01); NVDA and AMZN are orthogonal to
    everything. The panel's columns are alphabetical, as a pivot of
    `download_market_data` would produce, while the confidence is in universe
    order -- so the test also pins label alignment on the real symbols.
    """

    @classmethod
    def setUpClass(cls):
        from multi_ticker_comparison import TICKER_UNIVERSE

        cls.universe = list(TICKER_UNIVERSE)
        h = hadamard(64)
        patterns = {
            "AAPL": h[1] + 0.1 * h[4],
            "MSFT": h[1] + 0.1 * h[5],
            "GOOGL": h[1] + 0.1 * h[6],
            "NVDA": h[2],
            "AMZN": h[3],
        }
        columns = sorted(cls.universe)
        cls.closes = panel_from_returns(
            0.01 * np.column_stack([patterns[name] for name in columns]), columns
        )
        cls.config = config(
            target_volatility=0.03, volatility_window=64, correlation_window=64
        )
        cls.decision = target_weights(
            cls.closes,
            pd.Series(1.0, index=cls.universe),
            pd.Series(0.0, index=cls.universe),
            session=cls.closes.index[-1],
            config=cls.config,
            entries_halted=False,
        )

    def test_the_universe_is_the_one_spec_013_settled(self):
        self.assertEqual(self.universe, ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"])

    def test_preconditions_no_cap_and_no_gross_scaling_are_in_play(self):
        # Otherwise the assertions below would be about the caps, not about
        # correlation.
        self.assertTrue((self.decision["Standalone"] < self.config.max_weight).all())
        self.assertLessEqual(self.decision["Adjusted"].sum(), self.config.max_gross)

    def test_without_the_adjustment_the_cluster_would_be_three_bets(self):
        # The control for the test below: before the overlap step the cluster
        # holds nearly three times what it holds after it.
        cluster = self.decision.loc[["AAPL", "MSFT", "GOOGL"]]
        self.assertGreater(cluster["Capped"].sum(), 2.9 * cluster["Target"].sum())

    def test_the_correlated_cluster_carries_about_one_standalone_weight(self):
        cluster = self.decision.loc[["AAPL", "MSFT", "GOOGL"]]
        ratio = cluster["Target"].sum() / cluster["Capped"].mean()
        self.assertGreaterEqual(ratio, 0.95)
        self.assertLessEqual(ratio, 1.05)

    def test_the_independent_names_keep_their_standalone_weight(self):
        for name in ("NVDA", "AMZN"):
            with self.subTest(name=name):
                row = self.decision.loc[name]
                self.assertGreaterEqual(row["Target"] / row["Capped"], 0.90)


class AutomaticHaltIntegrationTests(unittest.TestCase):
    """US3 end to end -- a loss halts new risk with nobody setting a flag.

    A synthetic loop over the five-ticker universe. The *test* does a toy
    mark-to-market (weights decided at one close earn the close-to-close
    return to the next); the module under test does none. That split is the
    point: `portfolio_risk` reads equity and holdings, it never produces them.

    Scenario: NVDA's return is replaced by a -0.70 log return on a Wednesday.
    The same close, the signal exits NVDA and goes to full conviction on the
    other four -- the "buy the dip" moment a loss cap exists to refuse. The
    other names stay exactly orthogonal, so the correlation step cannot be
    what holds their size down; only the halt can.
    """

    START = 64
    CRASH = 67

    @classmethod
    def setUpClass(cls):
        from multi_ticker_comparison import TICKER_UNIVERSE

        cls.tickers = list(TICKER_UNIVERSE)
        h = hadamard(64)
        n_returns = 71
        # Periodic continuation keeps every trailing 64-return window one full
        # period, so the patterns stay exactly orthogonal throughout.
        returns = 0.01 * np.column_stack(
            [h[k][np.arange(n_returns) % 64] for k in range(1, 6)]
        )
        returns[cls.CRASH - 1, cls.tickers.index("NVDA")] = -0.70
        cls.closes = panel_from_returns(returns, cls.tickers)
        cfg = config(volatility_window=64, correlation_window=64)
        guard = LossCapGuard.from_config(cfg)

        equity = 1.0
        held = pd.Series(0.0, index=cls.tickers)
        cls.records = {}
        for row in range(cls.START, len(cls.closes)):
            session = cls.closes.index[row]
            if row > cls.START:
                growth = cls.closes.iloc[row] / cls.closes.iloc[row - 1]
                new_equity = equity * (1.0 + float((held * (growth - 1.0)).sum()))
                current = held * growth * (equity / new_equity)
                equity = new_equity
            else:
                current = held.copy()

            status = guard.observe(session, equity)
            if row < cls.CRASH:
                confidence = pd.Series(0.2, index=cls.tickers)
            else:
                confidence = pd.Series(1.0, index=cls.tickers)
                confidence["NVDA"] = 0.0
            decide = lambda halted: target_weights(  # noqa: E731
                cls.closes,
                confidence,
                current,
                session=session,
                config=cfg,
                entries_halted=halted,
            )
            decision = decide(status.entries_halted)
            cls.records[row] = (status, decision, decide(False))
            held = decision["Target"]

    def test_the_calendar_is_the_one_the_scenario_needs(self):
        self.assertEqual(self.closes.index[self.START].day_name(), "Friday")
        self.assertEqual(self.closes.index[self.CRASH].day_name(), "Wednesday")
        self.assertEqual(self.closes.index[self.CRASH + 3].day_name(), "Monday")

    def test_nothing_is_halted_before_the_crash(self):
        for row in range(self.START, self.CRASH):
            self.assertFalse(self.records[row][0].entries_halted)

    def test_the_crash_close_halts_itself(self):
        status = self.records[self.CRASH][0]
        self.assertTrue(status.daily_breach)
        self.assertTrue(status.weekly_loss_breach)
        self.assertTrue(status.entries_halted)

    def test_the_crashed_name_is_still_exited_under_the_halt(self):
        decision = self.records[self.CRASH][1]
        self.assertGreater(decision.loc["NVDA", "Current"], 0.0)
        self.assertEqual(decision.loc["NVDA", "Target"], 0.0)

    def test_no_position_grows_for_the_rest_of_the_week(self):
        for row in (self.CRASH, self.CRASH + 1, self.CRASH + 2):
            with self.subTest(session=self.closes.index[row].date()):
                status, decision, unhalted = self.records[row]
                self.assertTrue(status.entries_halted)
                self.assertTrue((decision["Target"] <= decision["Current"]).all())
                # The halt did something: without it, some name would have grown.
                self.assertTrue((unhalted["Target"] > unhalted["Current"] + 1e-6).any())

    def test_the_days_after_the_crash_are_held_by_the_week_not_the_day(self):
        for row in (self.CRASH + 1, self.CRASH + 2):
            status = self.records[row][0]
            self.assertFalse(status.daily_breach)
            self.assertTrue(status.weekly_latched)

    def test_entries_resume_the_next_week(self):
        status, decision, unhalted = self.records[self.CRASH + 3]
        self.assertFalse(status.entries_halted)
        self.assertTrue((decision["Target"] > decision["Current"] + 1e-6).any())
        pd.testing.assert_frame_equal(decision, unhalted)


if __name__ == "__main__":
    unittest.main()
