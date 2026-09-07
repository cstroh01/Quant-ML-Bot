"""Tests for scale-free features and fold-fit standardization (spec 014).

Two claims are under test here, and they are not the same claim:

1. The features are **scale-free** — multiplying every price and volume by a
   constant leaves them unchanged. This is what makes a fold's training
   support cover its test window instead of extrapolating past it.
2. The features are **not collinear** — which scaling cannot fix and only a
   change of feature can. `TestCollinearity` asserts this directly on the two
   ratios rather than only through the whole-matrix condition number, because
   a condition number can improve for reasons that have nothing to do with
   the pair spec 014 was opened over.

Plus the leakage property the `Pipeline` is there to guarantee: the scaler's
mean and variance come from training rows only.
"""

import unittest

import numpy as np
import pandas as pd

# First, for the sys.path effect: every project import below depends on it.
from context import SCRIPTS_DIR  # noqa: F401

from estimators import (
    CLASSIFICATION,
    REGRESSION,
    build_estimator,
    fit_predict_walk_forward,
    fitted_scaler,
)
from feature_set_comparison import (
    compare_classification,
    compare_regression,
)
from feature_diagnostics import (
    condition_number,
    max_abs_offdiagonal_correlation,
    variance_inflation_factors,
)
from features import (
    DERIVED_RATIO_COLUMNS,
    LEVEL_FEATURE_COLUMNS,
    SCALE_FREE_FEATURE_COLUMNS,
    build_features,
    feature_columns,
)
from walk_forward_cv import walk_forward_splits

# The pairwise-collinearity bar. VIF above 5 is the conventional "worth
# looking at" line; the two ratios must sit clearly under it. The
# correlation bound is looser than the VIF bound on purpose — 0.5 is a long
# way from the 0.972 the pair they replace measured, and pinning it tighter
# would be pinning noise from one fixture.
MAX_ACCEPTABLE_VIF = 5.0
MAX_ACCEPTABLE_PAIRWISE_CORRELATION = 0.5


def _trending_prices(n: int = 600, seed: int = 3) -> pd.DataFrame:
    """An OHLCV frame with real drift, which is what makes levels misbehave.

    A driftless walk would understate the problem: `Short_SMA` and `Long_SMA`
    are collinear on any series, but it is the *trend* that puts a later
    fold's prices outside an earlier fold's training range. The drift here is
    deliberate and is what the condition-number comparison rests on.
    """
    rng = np.random.default_rng(seed)
    drift = 0.0006
    steps = rng.normal(loc=drift, scale=0.011, size=n)
    close = 40.0 * np.exp(np.cumsum(steps))
    return pd.DataFrame(
        {
            "Date": pd.bdate_range("2019-01-02", periods=n),
            "Open": close,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, size=n),
        }
    )


def _rescaled(prices: pd.DataFrame, *, price: float, volume: float) -> pd.DataFrame:
    """The same frame in different units."""
    rescaled = prices.copy()
    for column in ("Open", "Close"):
        rescaled[column] = rescaled[column] * price
    rescaled["Volume"] = rescaled["Volume"] * volume
    return rescaled


def _frame(prices: pd.DataFrame, *, feature_set: str, kind: str = "return"):
    frame, _task, _horizon = build_features(
        prices, target_kind=kind, label_horizon=1, feature_set=feature_set
    )
    return frame


class TestFeatureSetRegistry(unittest.TestCase):
    """FR-001 — the sets are declared, selectable, and validated."""

    def test_default_is_the_scale_free_set(self):
        self.assertEqual(feature_columns(), SCALE_FREE_FEATURE_COLUMNS)

    def test_unknown_feature_set_raises_naming_the_valid_ones(self):
        with self.assertRaises(ValueError) as caught:
            feature_columns("standardised")
        message = str(caught.exception)
        self.assertIn("standardised", message)
        self.assertIn("levels", message)
        self.assertIn("scale_free", message)

    def test_build_features_rejects_an_unknown_set_too(self):
        with self.assertRaises(ValueError):
            build_features(
                _trending_prices(120),
                target_kind="return",
                label_horizon=1,
                feature_set="nope",
            )

    def test_the_returned_list_is_a_copy(self):
        """A caller that sorts the list must not reorder it for everyone."""
        columns = feature_columns("scale_free")
        columns.sort()
        self.assertEqual(feature_columns("scale_free"), SCALE_FREE_FEATURE_COLUMNS)

    def test_both_sets_are_computed_whichever_is_selected(self):
        """The diagnostics scripts rely on one frame carrying both."""
        frame = _frame(_trending_prices(), feature_set="levels")
        for column in SCALE_FREE_FEATURE_COLUMNS + LEVEL_FEATURE_COLUMNS:
            with self.subTest(column=column):
                self.assertIn(column, frame.columns)


class TestScaleInvariance(unittest.TestCase):
    """FR-002 / SC-001 — the property the whole spec exists for."""

    def setUp(self):
        self.prices = _trending_prices()
        self.rescaled = _rescaled(self.prices, price=10.0, volume=1000.0)

    def test_scale_free_features_are_unchanged_by_a_change_of_units(self):
        base = _frame(self.prices, feature_set="scale_free")
        moved = _frame(self.rescaled, feature_set="scale_free")

        self.assertEqual(len(base), len(moved))
        for column in SCALE_FREE_FEATURE_COLUMNS:
            with self.subTest(column=column):
                np.testing.assert_allclose(
                    base[column].to_numpy(),
                    moved[column].to_numpy(),
                    rtol=1e-9,
                    atol=1e-12,
                )

    def test_the_level_features_are_not(self):
        """The control half of the claim: without it, the test above could
        pass on a frame where nothing depends on price at all."""
        base = _frame(self.prices, feature_set="levels")
        moved = _frame(self.rescaled, feature_set="levels")

        for column in ("Short_SMA", "Long_SMA", "Volume"):
            with self.subTest(column=column):
                self.assertFalse(
                    np.allclose(
                        base[column].to_numpy(), moved[column].to_numpy()
                    ),
                    f"{column} should move with a change of units",
                )


class TestRatioDefinitions(unittest.TestCase):
    """FR-003 — each ratio is the quantity it claims to be."""

    def setUp(self):
        self.frame = _frame(_trending_prices(), feature_set="scale_free")

    def test_sma_spread_is_the_short_long_ratio_minus_one(self):
        np.testing.assert_allclose(
            self.frame["SMA_Spread"].to_numpy(),
            (self.frame["Short_SMA"] / self.frame["Long_SMA"] - 1.0).to_numpy(),
        )

    def test_close_to_short_is_the_close_short_ratio_minus_one(self):
        """Against the *short* average, not the long one.

        `Close/Long` is the product of the other two ratios, so using it here
        would re-measure what `SMA_Spread` already carries — the 0.865
        correlation `TestCollinearity` exists to rule out.
        """
        np.testing.assert_allclose(
            self.frame["Close_To_Short"].to_numpy(),
            (self.frame["Close"] / self.frame["Short_SMA"] - 1.0).to_numpy(),
        )

    def test_the_decomposition_closes(self):
        """(1+Close_To_Short)(1+SMA_Spread) == Close/Long_SMA, exactly.

        This is the identity that justifies dropping a direct
        price-against-long-average column: it is not missing information, it
        is the product of the two columns that are there.
        """
        np.testing.assert_allclose(
            (
                (1.0 + self.frame["Close_To_Short"])
                * (1.0 + self.frame["SMA_Spread"])
            ).to_numpy(),
            (self.frame["Close"] / self.frame["Long_SMA"]).to_numpy(),
        )

    def test_rel_volume_is_volume_over_its_trailing_mean(self):
        """The `- 1` is deliberately absent here, and that must stay true.

        A ratio around 1.0 and a difference around 0.0 are the same
        information, but `Rel_Volume` is the one column whose natural zero is
        "no volume at all" rather than "at its average". Asserting the exact
        form is what catches an over-eager tidy-up that makes all three
        columns look alike.
        """
        prices = _trending_prices()
        expected = (
            prices["Volume"] / prices["Volume"].rolling(30).mean()
        ).to_numpy()
        # Align by Date: the frame has dropped warm-up and unlabelled rows.
        offset = len(prices) - len(self.frame) - 1
        np.testing.assert_allclose(
            self.frame["Rel_Volume"].to_numpy(),
            expected[offset : offset + len(self.frame)],
        )

    def test_volume_window_is_configurable_and_defaults_to_long_window(self):
        prices = _trending_prices()
        default = _frame(prices, feature_set="scale_free")
        explicit, _task, _horizon = build_features(
            prices, target_kind="return", label_horizon=1, volume_window=30
        )
        np.testing.assert_allclose(
            default["Rel_Volume"].to_numpy(), explicit["Rel_Volume"].to_numpy()
        )

        different, _task, _horizon = build_features(
            prices, target_kind="return", label_horizon=1, volume_window=90
        )
        self.assertLess(len(different), len(default))

    def test_volume_window_below_one_raises(self):
        with self.assertRaises(ValueError):
            build_features(
                _trending_prices(120),
                target_kind="return",
                label_horizon=1,
                volume_window=0,
            )


class TestPointInTimeCorrectness(unittest.TestCase):
    """FR-004 / Rule 1 — no ratio reads a bar it could not have seen."""

    def test_perturbing_a_future_close_moves_no_earlier_feature(self):
        prices = _trending_prices()
        changed = prices.copy()
        changed.loc[changed.index[300:], "Close"] *= 1.5
        changed.loc[changed.index[300:], "Open"] *= 1.5

        base = _frame(prices, feature_set="scale_free")
        moved = _frame(changed, feature_set="scale_free")

        rows = 200
        pd.testing.assert_frame_equal(
            base[SCALE_FREE_FEATURE_COLUMNS].iloc[:rows],
            moved[SCALE_FREE_FEATURE_COLUMNS].iloc[:rows],
        )

    def test_perturbing_a_future_volume_moves_no_earlier_feature(self):
        """`Rel_Volume` has its own trailing window and its own way to leak."""
        prices = _trending_prices()
        changed = prices.copy()
        changed.loc[changed.index[300:], "Volume"] *= 7

        base = _frame(prices, feature_set="scale_free")
        moved = _frame(changed, feature_set="scale_free")

        rows = 200
        np.testing.assert_allclose(
            base["Rel_Volume"].to_numpy()[:rows],
            moved["Rel_Volume"].to_numpy()[:rows],
        )

    def test_the_label_is_in_no_feature_set(self):
        for name in ("levels", "scale_free"):
            with self.subTest(feature_set=name):
                self.assertNotIn("Label", feature_columns(name))


class TestCollinearity(unittest.TestCase):
    """FR-005 / SC-002 — the specific design claim, asserted directly.

    The condition number in `TestConditioning` is a whole-matrix statistic. It
    can improve because the units got fixed, which the scaler would have done
    anyway, and that is not the claim spec 014 makes. The claim is that
    `SMA_Spread` and `Close_To_Short` are meaningfully less collinear than the
    `Short_SMA`/`Long_SMA` pair they replace — measured at 0.972 — because one
    is a difference *between* the averages and the other a difference *from*
    them. That claim is about those two columns, so it is tested on those two
    columns.
    """

    def setUp(self):
        self.frame = _frame(_trending_prices(), feature_set="scale_free")
        self.levels = _frame(_trending_prices(), feature_set="levels")

    def test_the_pair_being_replaced_is_as_collinear_as_claimed(self):
        """Without this, the thresholds below have nothing to beat."""
        correlation = abs(
            float(self.levels["Short_SMA"].corr(self.levels["Long_SMA"]))
        )
        self.assertGreater(correlation, 0.9)

    def test_the_two_ratios_have_acceptable_vif(self):
        vif = variance_inflation_factors(self.frame, SCALE_FREE_FEATURE_COLUMNS)
        for column in ("SMA_Spread", "Close_To_Short"):
            with self.subTest(column=column):
                self.assertLess(
                    float(vif[column]),
                    MAX_ACCEPTABLE_VIF,
                    f"{column} VIF {vif[column]:.3f} is above "
                    f"{MAX_ACCEPTABLE_VIF}",
                )

    def test_the_two_ratios_are_not_strongly_correlated_with_each_other(self):
        correlation = abs(
            float(self.frame["SMA_Spread"].corr(self.frame["Close_To_Short"]))
        )
        self.assertLess(
            correlation,
            MAX_ACCEPTABLE_PAIRWISE_CORRELATION,
            f"SMA_Spread vs Close_To_Short correlation {correlation:.3f} is "
            f"above {MAX_ACCEPTABLE_PAIRWISE_CORRELATION}",
        )

    def test_no_scale_free_column_is_badly_collinear(self):
        vif = variance_inflation_factors(self.frame, SCALE_FREE_FEATURE_COLUMNS)
        self.assertLess(float(vif.max()), MAX_ACCEPTABLE_VIF)

    def test_the_worst_scale_free_pair_beats_the_worst_level_pair(self):
        scale_free, _pair = max_abs_offdiagonal_correlation(
            self.frame, SCALE_FREE_FEATURE_COLUMNS
        )
        levels, _level_pair = max_abs_offdiagonal_correlation(
            self.levels, LEVEL_FEATURE_COLUMNS
        )
        self.assertLess(scale_free, levels)


class TestConditioning(unittest.TestCase):
    """FR-005 / SC-003 — the aggregate improvement, as an inequality.

    Asserted with a margin rather than against a pinned constant: the exact
    number depends on the fixture, and a pinned value would fail on any
    innocuous change to it while proving nothing extra.
    """

    def setUp(self):
        prices = _trending_prices()
        self.levels = _frame(prices, feature_set="levels")
        self.scale_free = _frame(prices, feature_set="scale_free")

    def test_the_scale_free_matrix_is_better_conditioned(self):
        levels = condition_number(self.levels, LEVEL_FEATURE_COLUMNS)
        scale_free = condition_number(self.scale_free, SCALE_FREE_FEATURE_COLUMNS)
        self.assertLess(
            scale_free * 2.0,
            levels,
            f"expected a material improvement; got {levels:.2f} -> "
            f"{scale_free:.2f}",
        )

    def test_max_vif_drops(self):
        levels = variance_inflation_factors(self.levels, LEVEL_FEATURE_COLUMNS)
        scale_free = variance_inflation_factors(
            self.scale_free, SCALE_FREE_FEATURE_COLUMNS
        )
        self.assertLess(float(scale_free.max()), float(levels.max()))

    def test_standardizing_alone_does_not_fix_the_level_set(self):
        """The reason this spec changes features and not only the estimator.

        `condition_number` already standardizes, so the number it reports for
        the level set *is* the post-scaler number. If a scaler were enough,
        this would already be near 1 — the value for perfectly uncorrelated
        columns — and it is an order of magnitude away from it.

        The threshold is 10 rather than the conventional 30 because this is a
        600-bar synthetic fixture with one seed. The real-data figure is what
        `feature_diagnostics.py` reports and what the PR quotes; this test
        exists to pin the *direction*, not to stand in for that measurement.
        """
        self.assertGreater(
            condition_number(self.levels, LEVEL_FEATURE_COLUMNS), 10.0
        )


class TestNonFiniteGuard(unittest.TestCase):
    """FR-006 — a zero denominator becomes a dropped row, not an infinity."""

    def test_zero_volume_rows_are_dropped_rather_than_infinite(self):
        prices = _trending_prices()
        prices.loc[prices.index[100:140], "Volume"] = 0

        frame = _frame(prices, feature_set="scale_free")
        self.assertTrue(np.isfinite(frame["Rel_Volume"].to_numpy()).all())
        self.assertFalse(frame["Rel_Volume"].isna().any())

    def test_a_level_run_keeps_those_rows(self):
        """Zero volume is a valid level feature; only the ratio is undefined.

        This is the control that shows the drop above is the ratio's doing and
        not a blanket filter that quietly shortens every run.
        """
        prices = _trending_prices()
        prices.loc[prices.index[100:140], "Volume"] = 0

        levels = _frame(prices, feature_set="levels")
        scale_free = _frame(prices, feature_set="scale_free")
        self.assertGreater(len(levels), len(scale_free))


class TestScalerIsFitOnTrainingRowsOnly(unittest.TestCase):
    """FR-007 / SC-004 / Rule 2 — the leakage test.

    A `StandardScaler` fitted once on the whole frame would leak the test
    window's mean and variance into every fold. Because `build_estimator`
    returns a `Pipeline` and every fit site fits per fold, it cannot — and
    this asserts the statistics are the training slice's, not the frame's.
    """

    def setUp(self):
        self.frame = _frame(_trending_prices(), feature_set="scale_free")
        self.columns = SCALE_FREE_FEATURE_COLUMNS
        self.folds = list(
            walk_forward_splits(self.frame, label_horizon=1, embargo_bars=1)
        )
        self.assertGreater(len(self.folds), 1)

    def test_scaler_statistics_are_the_training_slice_statistics(self):
        for fold, (train_indices, _test_indices) in enumerate(self.folds, start=1):
            with self.subTest(fold=fold):
                model = build_estimator(
                    "ridge", task=REGRESSION, params=None, random_state=42
                )
                training = self.frame.iloc[train_indices][self.columns]
                model.fit(training, self.frame.iloc[train_indices]["Label"])

                scaler = fitted_scaler(model)
                self.assertIsNotNone(scaler)
                np.testing.assert_allclose(
                    scaler.mean_, training.to_numpy(dtype=float).mean(axis=0)
                )

    def test_scaler_statistics_differ_from_the_whole_frame(self):
        """Without this, the test above would pass on a leaking scaler whose
        training slice happened to be the whole frame."""
        train_indices, _test = self.folds[0]
        model = build_estimator(
            "ridge", task=REGRESSION, params=None, random_state=42
        )
        training = self.frame.iloc[train_indices][self.columns]
        model.fit(training, self.frame.iloc[train_indices]["Label"])

        whole_frame = self.frame[self.columns].to_numpy(dtype=float).mean(axis=0)
        self.assertFalse(
            np.allclose(fitted_scaler(model).mean_, whole_frame),
            "the first fold's scaler matches the whole frame; that is leakage",
        )

    def test_later_folds_see_different_statistics(self):
        """A scaler fitted once and reused would give itself away here."""
        means = []
        for train_indices, _test in self.folds:
            model = build_estimator(
                "ridge", task=REGRESSION, params=None, random_state=42
            )
            model.fit(
                self.frame.iloc[train_indices][self.columns],
                self.frame.iloc[train_indices]["Label"],
            )
            means.append(fitted_scaler(model).mean_.copy())
        self.assertFalse(np.allclose(means[0], means[-1]))


class TestRegistryScaling(unittest.TestCase):
    """FR-008 — which entries scale, and what the override is for."""

    def test_linear_entries_are_wrapped(self):
        for name, task in (("ridge", REGRESSION), ("logistic", CLASSIFICATION)):
            with self.subTest(name=name, task=task):
                model = build_estimator(
                    name, task=task, params=None, random_state=0
                )
                self.assertIsNotNone(fitted_scaler(model))

    def test_tree_entries_are_not(self):
        for task in (CLASSIFICATION, REGRESSION):
            with self.subTest(task=task):
                model = build_estimator(
                    "hgb", task=task, params=None, random_state=0
                )
                self.assertIsNone(fitted_scaler(model))

    def test_the_override_wins_in_both_directions(self):
        unscaled = build_estimator(
            "ridge", task=REGRESSION, params=None, random_state=0, scale=False
        )
        self.assertIsNone(fitted_scaler(unscaled))

        scaled = build_estimator(
            "hgb", task=REGRESSION, params=None, random_state=0, scale=True
        )
        self.assertIsNotNone(fitted_scaler(scaled))

    def test_grids_keep_plain_parameter_names(self):
        """A `Pipeline` would normally force `model__alpha`. It must not here:
        a registry entry describes its model, not the plumbing around it."""
        from estimators import param_grid_points

        for point in param_grid_points("ridge", task=REGRESSION):
            with self.subTest(point=point):
                self.assertEqual(list(point), ["alpha"])
                # And the name still reaches the estimator through the wrapper.
                model = build_estimator(
                    "ridge", task=REGRESSION, params=point, random_state=0
                )
                model.fit(
                    np.arange(20, dtype=float).reshape(10, 2),
                    np.arange(10, dtype=float),
                )
                self.assertTrue(np.isfinite(model.predict([[1.0, 2.0]])).all())


class TestScalingChangesTheAnswer(unittest.TestCase):
    """SC-005 — scaling is not a no-op on a penalized linear model.

    If `scale=True` and `scale=False` produced the same predictions, the
    whole `Pipeline` change would be ceremony. On the *level* set, where the
    column magnitudes differ by orders of magnitude, a single `alpha` cannot
    mean the same thing before and after standardization.
    """

    def test_ridge_predictions_move_when_the_scaler_is_applied(self):
        frame = _frame(_trending_prices(), feature_set="levels")
        common = dict(
            feature_columns=LEVEL_FEATURE_COLUMNS,
            label_column="Label",
            task=REGRESSION,
            name="ridge",
            label_horizon=1,
            embargo_bars=1,
            random_state=42,
        )
        scaled = fit_predict_walk_forward(frame, scale=True, **common)
        unscaled = fit_predict_walk_forward(frame, scale=False, **common)

        covered = scaled.notna() & unscaled.notna()
        self.assertTrue(covered.any())
        self.assertFalse(
            np.allclose(
                scaled[covered].to_numpy(dtype=float),
                unscaled[covered].to_numpy(dtype=float),
            ),
            "standardization changed nothing; the pipeline is not being used",
        )

    def test_hgb_predictions_do_not_move(self):
        """The justification for `scale=False` on the tree entries.

        A split threshold is chosen per column, so a monotone rescaling moves
        the threshold and leaves the partition — and every prediction —
        identical. If this ever failed, the registry's tree entries would need
        revisiting rather than this test relaxing.
        """
        frame = _frame(_trending_prices(), feature_set="levels")
        common = dict(
            feature_columns=LEVEL_FEATURE_COLUMNS,
            label_column="Label",
            task=REGRESSION,
            name="hgb",
            label_horizon=1,
            embargo_bars=1,
            random_state=42,
        )
        scaled = fit_predict_walk_forward(frame, scale=True, **common)
        unscaled = fit_predict_walk_forward(frame, scale=False, **common)

        covered = scaled.notna() & unscaled.notna()
        self.assertTrue(covered.any())
        np.testing.assert_allclose(
            scaled[covered].to_numpy(dtype=float),
            unscaled[covered].to_numpy(dtype=float),
            rtol=1e-6,
            atol=1e-9,
        )


class TestScaleReachesEveryFit(unittest.TestCase):
    """FR-010 / SC-008 — the tuner and the outer fit must agree.

    `nested_walk_forward` selects hyperparameters on inner folds and then
    fits the outer fold with the winner. If `scale` reached only one of
    those, the configuration selected would not be the configuration
    reported — the inner folds would rank grid points for a model the outer
    fold never fits.

    This is asserted by recording the `scale` every `build_estimator` call
    receives, rather than by comparing predictions: forwarding to one site
    and not the other changes the answer only slightly and only sometimes,
    which is exactly the kind of defect an output comparison misses. It was
    written because a mutation test found the gap — the suite passed with
    `scale` forwarded to the outer fit alone.
    """

    def setUp(self):
        self.frame = _frame(_trending_prices(), feature_set="scale_free")

    def _record_scale_arguments(self, *, scale):
        import model_cv

        seen = []
        original = model_cv.build_estimator

        def recording(name, **kwargs):
            seen.append(kwargs.get("scale"))
            return original(name, **kwargs)

        model_cv.build_estimator = recording
        try:
            model_cv.nested_walk_forward(
                self.frame,
                feature_columns=SCALE_FREE_FEATURE_COLUMNS,
                label_column="Label",
                task=REGRESSION,
                name="ridge",
                label_horizon=1,
                embargo_bars=1,
                random_state=42,
                scale=scale,
            )
        finally:
            model_cv.build_estimator = original
        return seen

    def test_every_fit_receives_the_same_scale(self):
        for scale in (True, False):
            with self.subTest(scale=scale):
                seen = self._record_scale_arguments(scale=scale)
                # Far more than one: one per grid point per inner fold, plus
                # one per outer fold. If only the outer fits were reached,
                # the inner ones would show None.
                self.assertGreater(len(seen), len(SCALE_FREE_FEATURE_COLUMNS))
                self.assertEqual(
                    set(seen),
                    {scale},
                    "some fit did not receive the requested scale; the tuner "
                    "and the outer fit must agree",
                )

    def test_the_default_reaches_every_fit_as_none(self):
        """`None` must be forwarded too, not silently replaced somewhere."""
        seen = self._record_scale_arguments(scale=None)
        self.assertEqual(set(seen), {None})


class TestDerivedColumnsAreDeclared(unittest.TestCase):
    """FR-003 — the non-finite guard covers exactly the derived columns."""

    def test_every_derived_column_is_in_the_scale_free_set(self):
        for column in DERIVED_RATIO_COLUMNS:
            self.assertIn(column, SCALE_FREE_FEATURE_COLUMNS)

    def test_the_scale_free_set_adds_nothing_undeclared(self):
        added = set(SCALE_FREE_FEATURE_COLUMNS) - set(LEVEL_FEATURE_COLUMNS)
        self.assertEqual(added, set(DERIVED_RATIO_COLUMNS))


class TestComparisonStatistics(unittest.TestCase):
    """FR-012 — the paired tests in `feature_set_comparison.py`.

    Written after an invalid `zero_method` argument reached a 45-minute real
    data run: the script was an entry point with no tests, so nothing
    executed its statistics until the run itself did. These call the two
    comparison functions on constructed arrays where the right answer is
    known, which is enough to catch a bad argument or an inverted
    alternative — the two ways this file can be wrong without looking wrong.
    """

    @staticmethod
    def _regression_case(*, scale_a, scale_b, seed=0, n=200):
        rng = np.random.default_rng(seed)
        truth = rng.normal(size=n)
        predicted_a = truth + rng.normal(scale=scale_a, size=n)
        predicted_b = truth + rng.normal(scale=scale_b, size=n)
        return (
            pd.Series(truth),
            pd.Series(predicted_a),
            pd.Series(predicted_b),
        )

    def test_wilcoxon_favours_b_when_b_has_the_smaller_error(self):
        truth, a, b = self._regression_case(scale_a=1.0, scale_b=0.4)
        result = compare_regression(truth, a, b)
        self.assertTrue(result["favours_b"])
        self.assertLess(result["p_one_sided"], 0.01)

    def test_the_one_sided_alternative_is_not_inverted(self):
        """The same data with the arguments swapped must not also 'win'.

        A one-sided test stated in the wrong direction passes the test above
        and reports every result as significant. This is the assertion that
        distinguishes the two.
        """
        truth, a, b = self._regression_case(scale_a=0.4, scale_b=1.0)
        result = compare_regression(truth, a, b)
        self.assertFalse(result["favours_b"])
        self.assertGreater(result["p_one_sided"], 0.9)

    def test_identical_predictions_rank_nothing(self):
        truth, a, _ = self._regression_case(scale_a=1.0, scale_b=1.0)
        result = compare_regression(truth, a, a.copy())
        self.assertEqual(result["discordant"], 0)
        self.assertEqual(result["p_one_sided"], 1.0)

    def test_mcnemar_favours_b_when_b_is_right_more_often(self):
        labels = pd.Series([1] * 200)
        predicted_a = pd.Series([1] * 60 + [0] * 140)
        predicted_b = pd.Series([1] * 140 + [0] * 60)
        result = compare_classification(labels, predicted_a, predicted_b)
        self.assertGreater(result["accuracy_b"], result["accuracy_a"])
        self.assertLess(result["p_one_sided"], 0.01)

    def test_mcnemar_is_not_inverted_either(self):
        labels = pd.Series([1] * 200)
        predicted_a = pd.Series([1] * 140 + [0] * 60)
        predicted_b = pd.Series([1] * 60 + [0] * 140)
        result = compare_classification(labels, predicted_a, predicted_b)
        self.assertLess(result["accuracy_b"], result["accuracy_a"])
        self.assertGreater(result["p_one_sided"], 0.9)

    def test_identical_classifications_have_no_discordant_pairs(self):
        labels = pd.Series([1] * 100 + [0] * 100)
        predicted = pd.Series([1] * 120 + [0] * 80)
        result = compare_classification(labels, predicted, predicted.copy())
        self.assertEqual(result["discordant"], 0)
        self.assertEqual(result["p_one_sided"], 1.0)


if __name__ == "__main__":
    unittest.main()
