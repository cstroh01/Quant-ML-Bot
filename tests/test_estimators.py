"""Tests for scripts/estimators.py — the registry and the untuned loop (spec 010)."""

import ast
import unittest

import numpy as np
import pandas as pd

from context import SCRIPTS_DIR
from estimators import (
    CLASSIFICATION,
    ESTIMATOR_REGISTRY,
    MAX_GRID_POINTS,
    REGRESSION,
    build_estimator,
    fit_predict_walk_forward,
    get_spec,
    param_grid_points,
)
from features import FEATURE_COLUMNS, build_features
from logistic_baseline import FEATURE_COLUMNS as BASELINE_FEATURE_COLUMNS
from logistic_baseline import walk_forward_predictions
from walk_forward_cv import walk_forward_splits
from test_logistic_baseline import _synthetic_features


def _price_walk(n: int, seed: int = 11) -> pd.DataFrame:
    """An OHLCV frame long enough to build features and several folds from."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n)
    close = 100.0 + np.cumsum(rng.normal(scale=0.8, size=n))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, size=n),
        }
    )


class TestRegistryShape(unittest.TestCase):
    """T002, T013 — the registry declares what it claims to declare."""

    def test_exactly_the_four_expected_pairs_are_registered(self):
        self.assertEqual(
            sorted(ESTIMATOR_REGISTRY),
            [
                ("hgb", CLASSIFICATION),
                ("hgb", REGRESSION),
                ("logistic", CLASSIFICATION),
                ("ridge", REGRESSION),
            ],
        )

    def test_every_entry_reports_its_own_name_and_task(self):
        # A copy-paste slip in the registry literal would otherwise leave an
        # entry keyed under one pair while describing another.
        for (name, task), spec in ESTIMATOR_REGISTRY.items():
            with self.subTest(name=name, task=task):
                self.assertEqual(spec.name, name)
                self.assertEqual(spec.task, task)

    def test_default_params_is_always_a_declared_grid_point(self):
        """FR-009 — spec 011's fallback must land on a tested configuration."""
        for name, task in ESTIMATOR_REGISTRY:
            with self.subTest(name=name, task=task):
                points = param_grid_points(name, task=task)
                self.assertIn(ESTIMATOR_REGISTRY[(name, task)].default_params, points)

    def test_every_grid_point_builds_without_raising(self):
        for name, task in ESTIMATOR_REGISTRY:
            for params in param_grid_points(name, task=task):
                with self.subTest(name=name, task=task, params=params):
                    self.assertIsNotNone(
                        build_estimator(
                            name, task=task, params=params, random_state=0
                        )
                    )

    def test_grids_stay_under_the_cap(self):
        for name, task in ESTIMATOR_REGISTRY:
            with self.subTest(name=name, task=task):
                self.assertLessEqual(
                    len(param_grid_points(name, task=task)), MAX_GRID_POINTS
                )

    def test_grid_point_order_is_deterministic(self):
        first = param_grid_points("hgb", task=CLASSIFICATION)
        second = param_grid_points("hgb", task=CLASSIFICATION)
        self.assertEqual(first, second)
        # Keys sorted, so the dicts are comparable across runs and machines.
        for point in first:
            self.assertEqual(list(point), sorted(point))


class TestBuildEstimator(unittest.TestCase):
    """T003, T014, T015 — construction, seeds, and the params=None contract."""

    def test_logistic_matches_the_pinned_baseline_construction(self):
        model = build_estimator(
            "logistic", task=CLASSIFICATION, params=None, random_state=42
        )
        # These three are exactly what logistic_baseline.py constructs. If any
        # drifts, the equivalence test below is the thing that will fail, and
        # this test says why.
        self.assertEqual(model.max_iter, 1000)
        self.assertEqual(model.random_state, 42)
        self.assertEqual(model.C, 1.0)

    def test_seed_is_forwarded_to_every_entry(self):
        for name, task in ESTIMATOR_REGISTRY:
            with self.subTest(name=name, task=task):
                model = build_estimator(
                    name, task=task, params=None, random_state=7
                )
                self.assertEqual(model.random_state, 7)

    def test_params_none_means_default_params_not_empty(self):
        """The mutation this catches: `params or {}` instead of the default."""
        spec = ESTIMATOR_REGISTRY[("ridge", REGRESSION)]
        self.assertEqual(spec.default_params, {"alpha": 1.0})
        defaulted = build_estimator(
            "ridge", task=REGRESSION, params=None, random_state=0
        )
        explicit = build_estimator(
            "ridge", task=REGRESSION, params={"alpha": 100.0}, random_state=0
        )
        self.assertEqual(defaulted.alpha, 1.0)
        self.assertEqual(explicit.alpha, 100.0)

    def test_declared_defaults_are_actually_applied_to_every_entry(self):
        """`params or {}` would pass the ridge/logistic check above by luck.

        scikit-learn's own defaults for `alpha` and `C` both happen to be
        1.0, which is what this registry declares — so an implementation that
        ignored `default_params` entirely would still produce the right
        estimator for those two. `hgb`'s `max_depth=3` differs from
        scikit-learn's `None`, so checking every entry against its own
        declaration is what actually pins the contract.
        """
        for (name, task), spec in ESTIMATOR_REGISTRY.items():
            model = build_estimator(name, task=task, params=None, random_state=0)
            for key, expected in spec.default_params.items():
                with self.subTest(name=name, task=task, param=key):
                    self.assertEqual(getattr(model, key), expected)

    def test_hgb_params_reach_the_estimator(self):
        model = build_estimator(
            "hgb",
            task=REGRESSION,
            params={"max_depth": 2, "min_samples_leaf": 50},
            random_state=0,
        )
        self.assertEqual(model.max_depth, 2)
        self.assertEqual(model.min_samples_leaf, 50)

    def test_caller_params_are_not_mutated(self):
        params = {"alpha": 10.0}
        build_estimator("ridge", task=REGRESSION, params=params, random_state=0)
        self.assertEqual(params, {"alpha": 10.0})


class TestUnregisteredPairs(unittest.TestCase):
    """T011 — never a silent default. (SC-004)"""

    def test_unknown_name_raises_naming_the_registered_pairs(self):
        with self.assertRaises(ValueError) as caught:
            get_spec("lightgbm", task=CLASSIFICATION)
        message = str(caught.exception)
        self.assertIn("lightgbm", message)
        self.assertIn("logistic", message)

    def test_right_name_wrong_task_raises(self):
        # 'logistic' is registered, but only for classification. A registry
        # keyed on name alone would wrongly hand back a classifier here.
        with self.assertRaises(ValueError):
            get_spec("logistic", task=REGRESSION)
        with self.assertRaises(ValueError):
            get_spec("ridge", task=CLASSIFICATION)

    def test_unknown_task_raises_from_the_loop(self):
        frame = _synthetic_features("2024-01-01", "2024-10-31")
        with self.assertRaises(ValueError):
            fit_predict_walk_forward(
                frame,
                feature_columns=BASELINE_FEATURE_COLUMNS,
                label_column="Label",
                task="ranking",
                name="logistic",
                label_horizon=1,
                embargo_bars=1,
                random_state=42,
            )


class TestClassificationEquivalence(unittest.TestCase):
    """T008 — the anti-regression test against the pinned Phase 2 control.

    (SC-001)
    """

    def test_matches_logistic_baseline_element_for_element(self):
        frame = _synthetic_features("2024-01-01", "2024-10-31")
        expected = walk_forward_predictions(frame)
        actual = fit_predict_walk_forward(
            frame,
            feature_columns=BASELINE_FEATURE_COLUMNS,
            label_column="Label",
            task=CLASSIFICATION,
            name="logistic",
            label_horizon=1,
            embargo_bars=1,
            random_state=42,
        )
        self.assertEqual(str(actual.dtype), "Int64")
        pd.testing.assert_series_equal(actual, expected, check_names=False)

    def test_null_placement_matches_too(self):
        # Asserted separately from the value equality above: a loop that
        # predicted everywhere would still match on the covered rows.
        frame = _synthetic_features("2024-01-01", "2024-10-31")
        expected = walk_forward_predictions(frame)
        actual = fit_predict_walk_forward(
            frame,
            feature_columns=BASELINE_FEATURE_COLUMNS,
            label_column="Label",
            task=CLASSIFICATION,
            name="logistic",
            label_horizon=1,
            embargo_bars=1,
            random_state=42,
        )
        self.assertTrue(actual.isna().any())
        np.testing.assert_array_equal(
            actual.isna().to_numpy(), expected.isna().to_numpy()
        )


class TestOneFitPerFold(unittest.TestCase):
    """Rule 2 — the loop refits per fold and never reuses or pre-fits.

    `_synthetic_features` gives a model nothing learnable (random features,
    alternating labels), so every fold predicts the same constant and a
    fit-once implementation would slip past a pure output comparison. These
    assertions are structural for that reason.
    """

    def test_one_estimator_is_constructed_per_fold(self):
        frame = _synthetic_features("2024-01-01", "2024-10-31")
        folds = list(walk_forward_splits(frame, label_horizon=1, embargo_bars=1))
        self.assertGreater(len(folds), 1)

        import estimators

        calls = []
        real = estimators.build_estimator

        def counting(*args, **kwargs):
            calls.append(kwargs.get("params"))
            return real(*args, **kwargs)

        estimators.build_estimator = counting
        try:
            fit_predict_walk_forward(
                frame,
                feature_columns=BASELINE_FEATURE_COLUMNS,
                label_column="Label",
                task=CLASSIFICATION,
                name="logistic",
                label_horizon=1,
                embargo_bars=1,
                random_state=42,
            )
        finally:
            estimators.build_estimator = real

        self.assertEqual(len(calls), len(folds))

    def test_each_fold_sees_a_freshly_fitted_model(self):
        """A learnable, drifting frame: a reused model gives itself away."""
        prices = _price_walk(500)
        frame, task, horizon = build_features(
            prices, target_kind="return", label_horizon=1
        )
        folds = list(
            walk_forward_splits(frame, label_horizon=horizon, embargo_bars=1)
        )
        self.assertGreater(len(folds), 1)

        per_fold_coefs = []
        for train_indices, _ in folds:
            model = build_estimator(
                "ridge", task=task, params=None, random_state=42
            )
            model.fit(
                frame.iloc[train_indices][FEATURE_COLUMNS],
                frame.iloc[train_indices]["Label"],
            )
            per_fold_coefs.append(model.coef_.copy())

        # If every fold fitted the same coefficients, this test could not
        # distinguish refitting from reuse and would be worthless.
        self.assertFalse(
            np.allclose(per_fold_coefs[0], per_fold_coefs[-1]),
            "fixture is not discriminating: first and last fold fit alike",
        )


class TestRegressionPath(unittest.TestCase):
    """T009 — the path that did not exist before this spec. (SC-002)"""

    def setUp(self):
        prices = _price_walk(500)
        self.frame, self.task, self.horizon = build_features(
            prices, target_kind="return", label_horizon=1
        )

    def test_task_and_horizon_come_through_from_build_features(self):
        self.assertEqual(self.task, REGRESSION)
        self.assertEqual(self.horizon, 1)

    def test_predictions_are_finite_floats_where_covered(self):
        predictions = fit_predict_walk_forward(
            self.frame,
            feature_columns=FEATURE_COLUMNS,
            label_column="Label",
            task=self.task,
            name="ridge",
            label_horizon=self.horizon,
            embargo_bars=1,
            random_state=42,
        )
        self.assertEqual(str(predictions.dtype), "float64")
        covered = predictions.notna()
        self.assertTrue(covered.any())
        self.assertTrue(np.isfinite(predictions[covered].to_numpy()).all())

    def test_rows_before_the_first_fold_are_null(self):
        predictions = fit_predict_walk_forward(
            self.frame,
            feature_columns=FEATURE_COLUMNS,
            label_column="Label",
            task=self.task,
            name="ridge",
            label_horizon=self.horizon,
            embargo_bars=1,
            random_state=42,
        )
        first_covered = int(np.flatnonzero(predictions.notna().to_numpy())[0])
        self.assertGreater(first_covered, 0)
        self.assertTrue(predictions.iloc[:first_covered].isna().all())

    def test_a_continuous_label_would_break_the_classification_path(self):
        # The reason the task branch exists at all: proving the old loop
        # genuinely could not have served this target.
        with self.assertRaises(Exception):
            fit_predict_walk_forward(
                self.frame,
                feature_columns=FEATURE_COLUMNS,
                label_column="Label",
                task=CLASSIFICATION,
                name="logistic",
                label_horizon=self.horizon,
                embargo_bars=1,
                random_state=42,
            )


class TestGradientBoosting(unittest.TestCase):
    """T010 — the registry key selects a genuinely different model. (SC-003)"""

    def test_hgb_regression_runs_and_differs_from_ridge(self):
        prices = _price_walk(500)
        frame, task, horizon = build_features(
            prices, target_kind="return", label_horizon=1
        )
        common = dict(
            feature_columns=FEATURE_COLUMNS,
            label_column="Label",
            task=task,
            label_horizon=horizon,
            embargo_bars=1,
            random_state=42,
        )
        ridge = fit_predict_walk_forward(frame, name="ridge", **common)
        hgb = fit_predict_walk_forward(frame, name="hgb", **common)

        covered = ridge.notna() & hgb.notna()
        self.assertTrue(covered.any())
        self.assertTrue(np.isfinite(hgb[covered].to_numpy()).all())
        # If the registry silently returned one family for everything, these
        # would be identical.
        self.assertFalse(np.allclose(ridge[covered], hgb[covered]))

    def test_hgb_classification_runs_and_predicts_labels(self):
        prices = _price_walk(500)
        frame, task, horizon = build_features(
            prices, target_kind="direction", label_horizon=1
        )
        predictions = fit_predict_walk_forward(
            frame,
            feature_columns=FEATURE_COLUMNS,
            label_column="Label",
            task=task,
            name="hgb",
            label_horizon=horizon,
            embargo_bars=1,
            random_state=42,
        )
        self.assertEqual(str(predictions.dtype), "Int64")
        covered = predictions.dropna()
        self.assertTrue(len(covered) > 0)
        self.assertTrue(set(covered.astype(int).unique()) <= {0, 1})


class TestDeterminism(unittest.TestCase):
    """T014 — same seed, same answer. (SC-006)"""

    def test_repeated_runs_agree(self):
        prices = _price_walk(400)
        frame, task, horizon = build_features(
            prices, target_kind="return", label_horizon=1
        )
        kwargs = dict(
            feature_columns=FEATURE_COLUMNS,
            label_column="Label",
            task=task,
            name="hgb",
            label_horizon=horizon,
            embargo_bars=1,
            random_state=13,
        )
        first = fit_predict_walk_forward(frame, **kwargs)
        second = fit_predict_walk_forward(frame, **kwargs)
        pd.testing.assert_series_equal(first, second)

    def test_different_params_change_the_answer(self):
        # Guards the mutation where `params` is accepted and then ignored.
        prices = _price_walk(400)
        frame, task, horizon = build_features(
            prices, target_kind="return", label_horizon=1
        )
        common = dict(
            feature_columns=FEATURE_COLUMNS,
            label_column="Label",
            task=task,
            name="ridge",
            label_horizon=horizon,
            embargo_bars=1,
            random_state=13,
        )
        weak = fit_predict_walk_forward(frame, params={"alpha": 0.1}, **common)
        strong = fit_predict_walk_forward(frame, params={"alpha": 100.0}, **common)
        covered = weak.notna() & strong.notna()
        self.assertFalse(np.allclose(weak[covered], strong[covered]))


class TestZeroFolds(unittest.TestCase):
    """T012 — a broken configuration must not look like 'no signal yet'."""

    def test_frame_too_short_raises_rather_than_returning_nulls(self):
        short = _synthetic_features("2024-01-01", "2024-02-10")
        with self.assertRaises(RuntimeError) as caught:
            fit_predict_walk_forward(
                short,
                feature_columns=BASELINE_FEATURE_COLUMNS,
                label_column="Label",
                task=CLASSIFICATION,
                name="logistic",
                label_horizon=1,
                embargo_bars=1,
                random_state=42,
            )
        self.assertIn("no folds", str(caught.exception))


class TestModuleBoundaries(unittest.TestCase):
    """T016 — Rule 8, asserted by AST rather than by a source grep.

    A substring search trips on any docstring that names a module in order to
    say it is *not* imported, which is the opposite of the property under
    test.
    """

    def _imported_modules(self, filename: str) -> set[str]:
        tree = ast.parse((SCRIPTS_DIR / filename).read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        return modules

    def test_estimators_imports_only_walk_forward_cv_and_sklearn(self):
        self.assertEqual(
            self._imported_modules("estimators.py"),
            {
                "__future__",
                "itertools",
                "collections",
                "dataclasses",
                "typing",
                "numpy",
                "pandas",
                "sklearn",
                "walk_forward_cv",
            },
        )

    def test_estimators_imports_no_forbidden_project_module(self):
        forbidden = {
            "signals",
            "backtest_harness",
            "features",
            "targets",
            "logistic_baseline",
            "metrics",
            "ma_crossover_backtest",
        }
        self.assertEqual(
            self._imported_modules("estimators.py") & forbidden, set()
        )


if __name__ == "__main__":
    unittest.main()
