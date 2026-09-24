"""Tests for scripts/model_cv.py — nested, leakage-safe tuning (spec 011).

The load-bearing test in this file is `TestInnerSplitMembership`: it is what
catches a regression to the tempting `features.iloc[:outer_test_start]`
prefix slice, which would silently re-admit every row an earlier outer fold
embargoed and report a better score for it.
"""

import ast
import contextlib
import dataclasses
import unittest

import numpy as np
import pandas as pd

# First, for the sys.path effect: every project import below depends on it.
from context import SCRIPTS_DIR

import estimators
from estimators import CLASSIFICATION, ESTIMATOR_REGISTRY, REGRESSION
from features import (
    LEVEL_FEATURE_COLUMNS,
    SCALE_FREE_FEATURE_COLUMNS,
    build_features,
)
from logistic_baseline import FEATURE_COLUMNS as BASELINE_FEATURE_COLUMNS
from model_cv import (
    INNER_SCORE_COLUMNS,
    inner_splits_over,
    nested_walk_forward,
    score_fold,
    tune_on_fold,
)
from walk_forward_cv import walk_forward_splits
from test_logistic_baseline import _synthetic_features

import model_cv


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


def _learnable_frame(
    n: int = 600, *, kind: str, feature_set: str = "scale_free"
) -> pd.DataFrame:
    """A features frame from a real price walk, where candidates differ.

    `_synthetic_features` pairs random features with alternating labels, so
    every candidate scores alike on it and a selection test would pass
    vacuously — the trap spec 010's plan recorded. Selection tests use this
    instead.

    `feature_set` defaults to the project default. The one-point tuner check
    passes `"levels"` to match its in-contract untuned reference; those are
    also the frozen pre-019 control's feature columns.
    """
    frame, _task, _horizon = build_features(
        _price_walk(n), target_kind=kind, label_horizon=1, feature_set=feature_set  # SC-002: forecast h, not a purge width
    )
    return frame


@contextlib.contextmanager
def _grid(name: str, task: str, param_grid: dict):
    """Temporarily replace one registry entry's grid.

    Grid *contents* live in `estimators.py` (spec 010 FR-001); this spec
    searches a grid, it does not author one. Tests that need a specific grid
    shape — a single point, for FR-011's equivalence check — say so here
    rather than by adding a test-only entry to the registry.
    """
    original = ESTIMATOR_REGISTRY[(name, task)]
    ESTIMATOR_REGISTRY[(name, task)] = dataclasses.replace(
        original, param_grid=param_grid
    )
    try:
        yield
    finally:
        ESTIMATOR_REGISTRY[(name, task)] = original


@contextlib.contextmanager
def _counting_build_estimator():
    """Count `build_estimator` calls made *by model_cv*.

    Patches `model_cv.build_estimator`, not `estimators.build_estimator`:
    `model_cv` imported the name, so rebinding it in its source module would
    not be seen here.
    """
    calls: list[dict] = []
    real = model_cv.build_estimator

    def counting(*args, **kwargs):
        calls.append(kwargs.get("params"))
        return real(*args, **kwargs)

    model_cv.build_estimator = counting
    try:
        yield calls
    finally:
        model_cv.build_estimator = real


def _fragmented_positions() -> np.ndarray:
    """A training-position array with one deliberate internal hole."""
    return np.concatenate([np.arange(0, 120), np.arange(150, 330)])


class TestStrictlyIncreasingAssertion(unittest.TestCase):
    """T001 — the positional back-map is unsound without it. (FR-002)"""

    def setUp(self):
        self.frame = _synthetic_features("2024-01-01", "2024-12-31")

    def test_unsorted_positions_raise(self):
        positions = np.array([0, 5, 3, 9])
        with self.assertRaises(ValueError) as caught:
            inner_splits_over(
                self.frame, positions, label_horizon=1, embargo_bars=1  # R-9 exemption: label-free synthetic splitter fixture
            )
        self.assertIn("strictly increasing", str(caught.exception))

    def test_duplicate_positions_raise(self):
        positions = np.array([0, 1, 1, 2])
        with self.assertRaises(ValueError):
            inner_splits_over(
                self.frame, positions, label_horizon=1, embargo_bars=1  # R-9 exemption: label-free synthetic splitter fixture
            )

    def test_the_check_is_eager_not_deferred_to_first_next(self):
        """A generator would defer the raise past the call site.

        Recorded as its own test because the fix (validate, then return an
        inner generator) is invisible in the function's signature and easy to
        undo by adding a `yield` to `inner_splits_over` itself.
        """
        with self.assertRaises(ValueError):
            inner_splits_over(
                self.frame,
                np.array([9, 3, 1]),
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            )

    def test_two_dimensional_positions_raise(self):
        with self.assertRaises(ValueError):
            inner_splits_over(
                self.frame,
                np.arange(20).reshape(4, 5),
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            )

    def test_empty_positions_yield_no_folds_without_raising(self):
        splits = list(
            inner_splits_over(
                self.frame,
                np.array([], dtype=int),
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            )
        )
        self.assertEqual(splits, [])


class TestInnerSplitMembership(unittest.TestCase):
    """T007 — every inner position came from `outer_train_indices`. (SC-001)

    This is the regression test for prefix slicing. A tuner that sliced
    `features.iloc[:outer_test_start]` would place positions 120-149 —
    the hole — into an inner training set, and those are precisely the rows
    an earlier outer fold's embargo removed.
    """

    def setUp(self):
        self.frame = _synthetic_features("2024-01-01", "2024-12-31")

    def test_fragmented_array_yields_only_member_positions(self):
        positions = _fragmented_positions()
        member = set(positions.tolist())
        splits = list(
            inner_splits_over(
                self.frame,
                positions,
                initial_train_months=3,
                test_months=1,
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            )
        )
        self.assertGreater(len(splits), 0)
        for inner_train, inner_val in splits:
            self.assertTrue(set(inner_train.tolist()) <= member)
            self.assertTrue(set(inner_val.tolist()) <= member)

    def test_no_hole_position_ever_appears(self):
        positions = _fragmented_positions()
        hole = set(range(120, 150))
        for inner_train, inner_val in inner_splits_over(
            self.frame,
            positions,
            initial_train_months=3,
            test_months=1,
            label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
            embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
        ):
            self.assertEqual(set(inner_train.tolist()) & hole, set())
            self.assertEqual(set(inner_val.tolist()) & hole, set())

    def test_real_outer_folds_produce_member_only_inner_folds(self):
        """The same property against folds the real splitter produced."""
        outer = list(walk_forward_splits(self.frame, label_horizon=1, embargo_bars=1))  # R-9 exemption: label-free synthetic splitter fixture
        self.assertGreater(len(outer), 2)
        # Later outer folds genuinely carry holes; if they did not, this test
        # would be checking the contiguous case under another name.
        last_train = outer[-1][0]
        self.assertGreater(int(np.sum(np.diff(last_train) > 1)), 0)

        for fold, (train_indices, _test_indices) in enumerate(outer, start=1):
            member = set(train_indices.tolist())
            for inner_train, inner_val in inner_splits_over(
                self.frame,
                train_indices,
                initial_train_months=3,
                test_months=1,
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            ):
                with self.subTest(fold=fold):
                    self.assertTrue(set(inner_train.tolist()) <= member)
                    self.assertTrue(set(inner_val.tolist()) <= member)


class TestInnerSplitOrderingAndSeparation(unittest.TestCase):
    """T008 — ordering in calendar time, separation in real bars. (SC-002)"""

    def setUp(self):
        self.frame = _synthetic_features("2024-01-01", "2024-12-31")
        self.positions = _fragmented_positions()
        self.splits = list(
            inner_splits_over(
                self.frame,
                self.positions,
                initial_train_months=3,
                test_months=1,
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            )
        )
        self.assertGreater(len(self.splits), 0)

    def test_training_precedes_validation_in_calendar_time(self):
        for fold, (inner_train, inner_val) in enumerate(self.splits, start=1):
            train_dates = pd.to_datetime(self.frame.iloc[inner_train]["Date"])
            val_dates = pd.to_datetime(self.frame.iloc[inner_val]["Date"])
            with self.subTest(fold=fold):
                self.assertLess(train_dates.max(), val_dates.min())

    def test_separation_across_a_hole_is_at_least_the_label_horizon(self):
        """The conservative direction claimed in the spec's *Design constraint*.

        Sub-frame rows span at least as many real bars as themselves, so a
        purge measured in sub-frame rows over-purges across a hole. It can
        never under-purge, which is the only direction that would leak.
        """
        label_horizon = 1
        for fold, (inner_train, inner_val) in enumerate(self.splits, start=1):
            separation = int(inner_val.min()) - int(inner_train.max())
            with self.subTest(fold=fold):
                self.assertGreaterEqual(separation, label_horizon)

    def test_a_longer_horizon_still_separates(self):
        splits = list(
            inner_splits_over(
                self.frame,
                self.positions,
                initial_train_months=3,
                test_months=1,
                label_horizon=5,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=5,  # R-9 exemption: label-free synthetic splitter fixture
            )
        )
        self.assertGreater(len(splits), 0)
        for inner_train, inner_val in splits:
            self.assertGreaterEqual(
                int(inner_val.min()) - int(inner_train.max()), 5
            )


class TestContiguousEquivalence(unittest.TestCase):
    """T009 — the general case subsumes the simple one. (SC-003)"""

    def test_contiguous_positions_reproduce_walk_forward_splits(self):
        frame = _synthetic_features("2024-01-01", "2024-12-31")
        cutoff = 300
        positions = np.arange(cutoff)

        actual = list(
            inner_splits_over(
                frame,
                positions,
                initial_train_months=3,
                test_months=1,
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            )
        )
        expected = list(
            walk_forward_splits(
                frame.iloc[:cutoff].reset_index(drop=True),
                3,
                1,
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            )
        )
        self.assertGreater(len(expected), 0)
        self.assertEqual(len(actual), len(expected))
        for (a_train, a_val), (e_train, e_val) in zip(actual, expected):
            np.testing.assert_array_equal(a_train, e_train)
            np.testing.assert_array_equal(a_val, e_val)


class TestScoreFold(unittest.TestCase):
    """T003 — lower is better, in both tasks. (FR-004)"""

    def test_classification_better_probabilities_score_lower(self):
        y_true = np.array([0, 1, 0, 1])
        good = np.array([0.05, 0.95, 0.05, 0.95])
        bad = np.array([0.95, 0.05, 0.95, 0.05])
        self.assertLess(
            score_fold(y_true, good, task=CLASSIFICATION),
            score_fold(y_true, bad, task=CLASSIFICATION),
        )

    def test_regression_better_predictions_score_lower(self):
        y_true = np.array([1.0, 2.0, 3.0])
        self.assertLess(
            score_fold(y_true, np.array([1.0, 2.0, 3.0]), task=REGRESSION),
            score_fold(y_true, np.array([3.0, 1.0, 5.0]), task=REGRESSION),
        )

    def test_single_class_truth_does_not_raise_or_reshape(self):
        """Why `labels=[0, 1]` is passed explicitly (spec Edge Cases).

        Without it, `log_loss` infers the label set from `y_true`, and a
        single-class fold is either an error or a score on a different scale
        from every other fold's — which makes the mean across inner folds
        meaningless rather than wrong-looking.
        """
        all_ones = np.ones(5, dtype=int)
        confident = score_fold(all_ones, np.full(5, 0.99), task=CLASSIFICATION)
        wrong = score_fold(all_ones, np.full(5, 0.01), task=CLASSIFICATION)
        self.assertLess(confident, wrong)

        all_zeros = np.zeros(5, dtype=int)
        self.assertLess(
            score_fold(all_zeros, np.full(5, 0.01), task=CLASSIFICATION),
            score_fold(all_zeros, np.full(5, 0.99), task=CLASSIFICATION),
        )

    def test_unknown_task_raises(self):
        with self.assertRaises(ValueError):
            score_fold(np.array([0, 1]), np.array([0.5, 0.5]), task="ranking")


class TestPredictForScoring(unittest.TestCase):
    """The `predict_proba` column is found by class, not by position.

    Added after a mutation check: replacing `proba[:, classes.index(1)]` with
    `proba[:, 1]` survived every other test in this file, because no fixture
    happens to produce a single-class inner training fold and `classes_` is
    `[0, 1]` everywhere else. The spec lists that fold as an edge case, so a
    green suite that could not tell the two apart was under-testing it.
    """

    def test_a_single_class_training_fold_does_not_break_scoring(self):
        """`hgb` is the registered estimator that reaches this state.

        `LogisticRegression` refuses a single-class fit outright — it raises
        "needs samples of at least 2 classes" — so the surviving-model case
        belongs to gradient boosting, which fits happily with
        `classes_ == [0]`.
        """
        model = estimators.build_estimator(
            "hgb",
            task=CLASSIFICATION,
            params={"max_depth": 2, "min_samples_leaf": 1},
            random_state=42,
        )
        X = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [1.0, 0.0, 1.0, 0.0]})
        model.fit(X, pd.Series([0, 0, 0, 0]))
        self.assertEqual(list(model.classes_), [0])

        predicted = model_cv._predict_for_scoring(model, X, task=CLASSIFICATION)
        self.assertEqual(predicted.shape, (4,))
        # Class 1 was never seen, so its probability is 0 — read from the
        # class list, not from a column that happens to exist.
        np.testing.assert_array_equal(predicted, np.zeros(4))
        # log_loss's own clipping keeps the score finite rather than infinite.
        self.assertTrue(
            np.isfinite(
                score_fold(np.zeros(4, dtype=int), predicted, task=CLASSIFICATION)
            )
        )

    def test_the_positive_class_column_is_located_by_class_not_index(self):
        class _ReversedClasses:
            """A model whose `classes_` is ordered `[1, 0]`."""

            classes_ = np.array([1, 0])

            def predict_proba(self, X):
                # Column 0 is P(class 1) here; column 1 is P(class 0).
                return np.array([[0.9, 0.1], [0.2, 0.8]])

        predicted = model_cv._predict_for_scoring(
            _ReversedClasses(), pd.DataFrame(index=[0, 1]), task=CLASSIFICATION
        )
        np.testing.assert_allclose(predicted, [0.9, 0.2])


class TestTuneOnFoldIsolation(unittest.TestCase):
    """T010 — the selection cannot depend on a non-member row. (SC-004)"""

    def setUp(self):
        self.frame = _learnable_frame(kind="direction")
        # Purge and embargo are the label availability span (spec 019 C2),
        # read from the frame rather than written as a literal (FR-003).
        span = self.frame.attrs["label_availability_span"]
        outer = list(
            walk_forward_splits(self.frame, label_horizon=span, embargo_bars=span)
        )
        self.assertGreater(len(outer), 3)
        # A late fold: long enough to support several inner folds, and one
        # whose training positions genuinely carry embargo holes.
        self.train_indices = outer[-1][0]
        self.assertGreater(int(np.sum(np.diff(self.train_indices) > 1)), 0)
        self.kwargs = dict(
            name="logistic",
            task=CLASSIFICATION,
            feature_columns=SCALE_FREE_FEATURE_COLUMNS,
            label_column="Label",
            label_horizon=span,
            embargo_bars=span,
            random_state=42,
            inner_initial_train_months=6,
            inner_test_months=2,
        )

    def _corrupted(self) -> pd.DataFrame:
        """Sentinel values in every row outside the outer training positions.

        Features are overwritten on every outside row. The label is flipped
        only where it is known: under spec 019 (C4) the final `span` rows
        keep an unknown `<NA>` label, which has no flip, and casting it to
        int raises. Those rows are never train-eligible, so leaving their
        label unknown hides nothing a leak could read.
        """
        corrupt = self.frame.copy()
        outside = np.setdiff1d(
            np.arange(len(corrupt)), self.train_indices, assume_unique=False
        )
        self.assertGreater(outside.size, 0)
        for column in SCALE_FREE_FEATURE_COLUMNS:
            corrupt.iloc[outside, corrupt.columns.get_loc(column)] = 1e9
        label_position = corrupt.columns.get_loc("Label")
        known = outside[corrupt.iloc[outside, label_position].notna().to_numpy()]
        self.assertGreater(known.size, 0)
        corrupt.iloc[known, label_position] = (
            1 - corrupt.iloc[known, label_position].astype(int)
        )
        return corrupt

    def test_selection_is_unchanged_by_corrupting_every_outside_row(self):
        clean_params, clean_tuned, clean_scores = tune_on_fold(
            self.frame, self.train_indices, **self.kwargs
        )
        dirty_params, dirty_tuned, dirty_scores = tune_on_fold(
            self._corrupted(), self.train_indices, **self.kwargs
        )
        self.assertTrue(clean_tuned)
        self.assertEqual(clean_params, dirty_params)
        self.assertEqual(clean_tuned, dirty_tuned)
        # Not just the winner: every candidate's score on every inner fold.
        pd.testing.assert_frame_equal(clean_scores, dirty_scores)

    def test_the_corruption_would_be_visible_if_it_leaked(self):
        """Guards the test above from passing because the sentinels are inert.

        If corrupted rows changed nothing anywhere, the isolation assertion
        would hold for an implementation that read them. Scoring the same
        candidates over inner folds drawn from the *whole* frame — the prefix
        slice, in effect — must produce different numbers.
        """
        everything = np.arange(len(self.frame))
        _, _, clean = tune_on_fold(self.frame, everything, **self.kwargs)
        _, _, dirty = tune_on_fold(self._corrupted(), everything, **self.kwargs)
        self.assertFalse(clean.empty)
        self.assertFalse(
            np.allclose(clean["Score"].to_numpy(), dirty["Score"].to_numpy())
        )


class TestZeroInnerFoldFallback(unittest.TestCase):
    """T011 — `default_params` and `tuned=False`, never `grid[0]`. (SC-005)"""

    def setUp(self):
        self.frame = _synthetic_features("2024-01-01", "2024-12-31")
        self.kwargs = dict(
            name="logistic",
            task=CLASSIFICATION,
            feature_columns=BASELINE_FEATURE_COLUMNS,
            label_column="Label",
            label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
            embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            random_state=42,
        )

    def test_short_training_window_falls_back_to_the_registry_default(self):
        # Two months of positions cannot support a six-month inner training
        # window, so no inner fold exists.
        params, tuned, scores = tune_on_fold(
            self.frame, np.arange(60), **self.kwargs
        )
        self.assertFalse(tuned)
        self.assertEqual(
            params, ESTIMATOR_REGISTRY[("logistic", CLASSIFICATION)].default_params
        )
        self.assertTrue(scores.empty)
        self.assertEqual(list(scores.columns), INNER_SCORE_COLUMNS)

    def test_the_fallback_is_the_declared_default_not_the_first_grid_point(self):
        """Asserted against the registry, not against a grid position.

        With the real `logistic` grid, `default_params` is `C=1.0` and
        `grid[0]` is `C=0.01` — so this distinguishes the two. If a future
        grid made them coincide the assertion below would stop having teeth,
        which is why the grid is pinned here explicitly.
        """
        spec = ESTIMATOR_REGISTRY[("logistic", CLASSIFICATION)]
        grid = estimators.param_grid_points("logistic", task=CLASSIFICATION)
        self.assertNotEqual(spec.default_params, grid[0])

        params, tuned, _ = tune_on_fold(self.frame, np.arange(60), **self.kwargs)
        self.assertFalse(tuned)
        self.assertEqual(params, spec.default_params)
        self.assertNotEqual(params, grid[0])

    def test_zero_inner_folds_does_not_raise(self):
        # A short early fold is an expected condition, not a broken
        # configuration — unlike zero *outer* folds, which does raise.
        params, tuned, _ = tune_on_fold(self.frame, np.arange(30), **self.kwargs)
        self.assertFalse(tuned)
        self.assertIsInstance(params, dict)

    def test_the_returned_default_is_a_copy(self):
        params, _, _ = tune_on_fold(self.frame, np.arange(60), **self.kwargs)
        params["C"] = 999.0
        self.assertEqual(
            ESTIMATOR_REGISTRY[("logistic", CLASSIFICATION)].default_params,
            {"C": 1.0},
        )


class TestSingleCandidateGrid(unittest.TestCase):
    """T012 — one candidate still runs the whole inner loop."""

    def test_no_short_circuit_on_a_one_point_grid(self):
        frame = _synthetic_features("2024-01-01", "2024-12-31")
        outer = list(walk_forward_splits(frame, label_horizon=1, embargo_bars=1))  # R-9 exemption: label-free synthetic splitter fixture
        train_indices = outer[-1][0]
        expected_inner = len(
            list(
                inner_splits_over(
                    frame,
                    train_indices,
                    initial_train_months=6,
                    test_months=1,
                    label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                    embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
                )
            )
        )
        self.assertGreater(expected_inner, 1)

        with _grid("logistic", CLASSIFICATION, {"C": [1.0]}):
            with _counting_build_estimator() as calls:
                params, tuned, scores = tune_on_fold(
                    frame,
                    train_indices,
                    name="logistic",
                    task=CLASSIFICATION,
                    feature_columns=BASELINE_FEATURE_COLUMNS,
                    label_column="Label",
                    label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                    embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
                    random_state=42,
                )

        # One fit per grid point per inner fold — not one, and not zero.
        self.assertEqual(len(calls), expected_inner)
        self.assertEqual(len(scores), expected_inner)
        self.assertTrue(tuned)
        self.assertEqual(params, {"C": 1.0})

    def test_the_full_grid_costs_one_fit_per_point_per_inner_fold(self):
        frame = _synthetic_features("2024-01-01", "2024-12-31")
        outer = list(walk_forward_splits(frame, label_horizon=1, embargo_bars=1))  # R-9 exemption: label-free synthetic splitter fixture
        train_indices = outer[-1][0]
        grid_points = len(estimators.param_grid_points("logistic", task=CLASSIFICATION))
        expected_inner = len(
            list(
                inner_splits_over(
                    frame,
                    train_indices,
                    initial_train_months=6,
                    test_months=1,
                    label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                    embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
                )
            )
        )

        with _counting_build_estimator() as calls:
            _, _, scores = tune_on_fold(
                frame,
                train_indices,
                name="logistic",
                task=CLASSIFICATION,
                feature_columns=BASELINE_FEATURE_COLUMNS,
                label_column="Label",
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
                random_state=42,
            )

        self.assertEqual(len(calls), grid_points * expected_inner)
        self.assertEqual(len(scores), grid_points * expected_inner)


class TestSelectionActuallySelects(unittest.TestCase):
    """The tuner picks the lowest mean score, and the grid matters."""

    def test_the_winner_has_the_lowest_mean_inner_score(self):
        frame = _learnable_frame(kind="return")
        span = frame.attrs["label_availability_span"]  # C2; never a literal
        outer = list(
            walk_forward_splits(frame, label_horizon=span, embargo_bars=span)
        )
        train_indices = outer[-1][0]
        params, tuned, scores = tune_on_fold(
            frame,
            train_indices,
            name="ridge",
            task=REGRESSION,
            feature_columns=SCALE_FREE_FEATURE_COLUMNS,
            label_column="Label",
            label_horizon=span,
            embargo_bars=span,
            random_state=42,
        )
        self.assertTrue(tuned)
        means = scores.groupby("Grid_Point")["Score"].mean()
        best_point = int(means.idxmin())
        grid = estimators.param_grid_points("ridge", task=REGRESSION)
        self.assertEqual(params, grid[best_point])

    def test_scores_differ_across_candidates(self):
        """Otherwise the selection test above would pass on any implementation."""
        frame = _learnable_frame(kind="return")
        span = frame.attrs["label_availability_span"]  # C2; never a literal
        outer = list(
            walk_forward_splits(frame, label_horizon=span, embargo_bars=span)
        )
        _, _, scores = tune_on_fold(
            frame,
            outer[-1][0],
            name="ridge",
            task=REGRESSION,
            feature_columns=SCALE_FREE_FEATURE_COLUMNS,
            label_column="Label",
            label_horizon=span,
            embargo_bars=span,
            random_state=42,
        )
        means = scores.groupby("Grid_Point")["Score"].mean().to_numpy()
        self.assertGreater(len(means), 1)
        self.assertFalse(np.allclose(means, means[0]))


class TestNestedWalkForward(unittest.TestCase):
    """T014 — coverage, dtypes, and the per-fold record. (FR-007, FR-008)"""

    def setUp(self):
        self.frame = _synthetic_features("2024-01-01", "2024-12-31")
        self.predictions, self.covered, self.fold_results = nested_walk_forward(
            self.frame,
            feature_columns=BASELINE_FEATURE_COLUMNS,
            label_column="Label",
            task=CLASSIFICATION,
            name="logistic",
            label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
            embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            random_state=42,
        )

    def test_covered_positions_equal_the_concatenated_outer_test_indices(self):
        outer = list(walk_forward_splits(self.frame, label_horizon=1, embargo_bars=1))  # R-9 exemption: label-free synthetic splitter fixture
        expected = np.concatenate([test_idx for _, test_idx in outer])
        np.testing.assert_array_equal(self.covered, expected)

    def test_no_position_is_covered_twice(self):
        self.assertEqual(len(self.covered), len(set(self.covered.tolist())))

    def test_predictions_are_present_exactly_where_covered(self):
        covered_mask = np.zeros(len(self.frame), dtype=bool)
        covered_mask[self.covered] = True
        self.assertTrue(self.predictions[covered_mask].notna().all())
        self.assertTrue(self.predictions[~covered_mask].isna().all())
        self.assertEqual(str(self.predictions.dtype), "Int64")

    def test_one_result_row_per_outer_fold(self):
        outer = list(walk_forward_splits(self.frame, label_horizon=1, embargo_bars=1))  # R-9 exemption: label-free synthetic splitter fixture
        self.assertEqual(len(self.fold_results), len(outer))
        self.assertEqual(
            self.fold_results["Fold"].tolist(), list(range(1, len(outer) + 1))
        )

    def test_the_tuned_flag_is_recorded_per_fold(self):
        # The first fold's training data is exactly the initial training
        # window, which cannot support a six-month inner window — so the
        # fallback is not a hypothetical path, it fires here.
        self.assertIn("Tuned", self.fold_results.columns)
        self.assertFalse(bool(self.fold_results.iloc[0]["Tuned"]))
        self.assertTrue(bool(self.fold_results.iloc[-1]["Tuned"]))
        self.assertEqual(int(self.fold_results.iloc[0]["Inner_Folds"]), 0)

    def test_the_untuned_fold_records_the_registry_default(self):
        first = self.fold_results.iloc[0]
        self.assertEqual(
            first["Params"],
            ESTIMATOR_REGISTRY[("logistic", CLASSIFICATION)].default_params,
        )
        self.assertTrue(np.isnan(first["Inner_Best_Score"]))

    def test_regression_path_produces_finite_floats(self):
        frame = _learnable_frame(kind="return")
        span = frame.attrs["label_availability_span"]  # C2; never a literal
        predictions, covered, results = nested_walk_forward(
            frame,
            feature_columns=SCALE_FREE_FEATURE_COLUMNS,
            label_column="Label",
            task=REGRESSION,
            name="ridge",
            label_horizon=span,
            embargo_bars=span,
            random_state=42,
        )
        self.assertEqual(str(predictions.dtype), "float64")
        self.assertTrue(np.isfinite(predictions.iloc[covered].to_numpy()).all())
        self.assertTrue(results["Tuned"].any())

    def test_a_frame_too_short_for_any_outer_fold_raises(self):
        short = _synthetic_features("2024-01-01", "2024-02-10")
        with self.assertRaises(RuntimeError) as caught:
            nested_walk_forward(
                short,
                feature_columns=BASELINE_FEATURE_COLUMNS,
                label_column="Label",
                task=CLASSIFICATION,
                name="logistic",
                label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
                embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
                random_state=42,
            )
        self.assertIn("no folds", str(caught.exception))

    def test_unknown_task_and_unregistered_name_raise(self):
        common = dict(
            feature_columns=BASELINE_FEATURE_COLUMNS,
            label_column="Label",
            label_horizon=1,  # R-9 exemption: label-free synthetic splitter fixture
            embargo_bars=1,  # R-9 exemption: label-free synthetic splitter fixture
            random_state=42,
        )
        with self.assertRaises(ValueError):
            nested_walk_forward(
                self.frame, task="ranking", name="logistic", **common
            )
        with self.assertRaises(ValueError):
            nested_walk_forward(
                self.frame, task=CLASSIFICATION, name="lightgbm", **common
            )


class TestDeterminism(unittest.TestCase):
    """T013 — same seed, same answer. (Conventions → Determinism)"""

    def test_repeated_nested_runs_agree(self):
        frame = _learnable_frame(kind="return")
        span = frame.attrs["label_availability_span"]  # C2; never a literal
        kwargs = dict(
            feature_columns=SCALE_FREE_FEATURE_COLUMNS,
            label_column="Label",
            task=REGRESSION,
            name="ridge",
            label_horizon=span,
            embargo_bars=span,
            random_state=13,
        )
        first_pred, first_cov, first_results = nested_walk_forward(frame, **kwargs)
        second_pred, second_cov, second_results = nested_walk_forward(frame, **kwargs)
        pd.testing.assert_series_equal(first_pred, second_pred)
        np.testing.assert_array_equal(first_cov, second_cov)
        pd.testing.assert_frame_equal(first_results, second_results)

    def test_repeated_tuning_selects_the_same_candidate(self):
        frame = _learnable_frame(kind="return")
        span = frame.attrs["label_availability_span"]  # C2; never a literal
        outer = list(
            walk_forward_splits(frame, label_horizon=span, embargo_bars=span)
        )
        kwargs = dict(
            name="ridge",
            task=REGRESSION,
            feature_columns=SCALE_FREE_FEATURE_COLUMNS,
            label_column="Label",
            label_horizon=span,
            embargo_bars=span,
            random_state=13,
        )
        first = tune_on_fold(frame, outer[-1][0], **kwargs)
        second = tune_on_fold(frame, outer[-1][0], **kwargs)
        self.assertEqual(first[0], second[0])
        pd.testing.assert_frame_equal(first[2], second[2])


class TestEquivalenceWithLogisticBaseline(unittest.TestCase):
    """A one-point tuner matches the in-contract untuned logistic loop.

    `test_estimators.py::test_matches_logistic_baseline_element_for_element`
    links that untuned loop to the frozen pre-019 control on label-agnostic
    synthetic frames. This price-derived fixture uses the 019 full calendar,
    train-eligible masks, level columns, and returned label span. It separates
    first and last fold fits so output equality cannot pass vacuously.
    """

    def setUp(self):
        self.frame = _learnable_frame(kind="direction", feature_set="levels")
        self.span = self.frame.attrs["label_availability_span"]
        self.outer = list(
            walk_forward_splits(
                self.frame, label_horizon=self.span, embargo_bars=self.span
            )
        )
        self.assertGreater(len(self.outer), 1)

    def test_the_fixture_discriminates_between_folds(self):
        """If every fold fit alike, the equality tests below prove nothing."""
        coefficients = []
        for train_indices, _ in self.outer:
            eligible = self.frame["Train_Eligible"].to_numpy(dtype=bool)
            train_indices = train_indices[eligible[train_indices]]
            model = estimators.build_estimator(
                "logistic",
                task=CLASSIFICATION,
                params={"C": 1.0},
                random_state=42,
                scale=False,
            )
            model.fit(
                self.frame.iloc[train_indices][LEVEL_FEATURE_COLUMNS],
                self.frame.iloc[train_indices]["Label"].astype(int),
            )
            coefficients.append(model.coef_.copy())
        self.assertFalse(
            np.allclose(coefficients[0], coefficients[-1]),
            "fixture is not discriminating: first and last fold fit alike",
        )

    def _untuned_predictions(self):
        return estimators.fit_predict_walk_forward(
            self.frame,
            feature_columns=LEVEL_FEATURE_COLUMNS,
            label_column="Label",
            task=CLASSIFICATION,
            name="logistic",
            params={"C": 1.0},
            scale=False,
            label_horizon=self.span,
            embargo_bars=self.span,
            random_state=42,
        )

    def test_single_point_grid_reproduces_the_untuned_loop_element_for_element(self):
        expected = self._untuned_predictions()

        with _grid("logistic", CLASSIFICATION, {"C": [1.0]}):
            actual, _covered, results = nested_walk_forward(
                self.frame,
                feature_columns=BASELINE_FEATURE_COLUMNS,
                label_column="Label",
                task=CLASSIFICATION,
                name="logistic",
                label_horizon=self.span,
                embargo_bars=self.span,
                random_state=42,
                scale=False,
            )

        self.assertEqual(str(actual.dtype), "Int64")
        pd.testing.assert_series_equal(actual, expected, check_names=False)
        # Both classes are predicted somewhere, so the equality is not the
        # trivial agreement of two constant series.
        self.assertEqual(set(actual.dropna().astype(int).unique()), {0, 1})
        # Every fold selected C=1.0, whether by tuning or by fallback.
        for params in results["Params"]:
            self.assertEqual(params, {"C": 1.0})

    def test_one_outer_fit_per_fold_on_top_of_the_tuning_fits(self):
        """The structural half: a fit-once loop cannot pass this.

        With a one-point grid, the call budget is exactly one estimator per
        (grid point, inner fold) plus one per outer fold. Anything reusing a
        model across outer folds comes in under it.
        """
        expected_inner = sum(
            len(
                list(
                    inner_splits_over(
                        self.frame,
                        train_indices,
                        label_horizon=self.span,
                        embargo_bars=self.span,
                    )
                )
            )
            for train_indices, _ in self.outer
        )
        self.assertGreater(expected_inner, 0)

        with _grid("logistic", CLASSIFICATION, {"C": [1.0]}):
            with _counting_build_estimator() as calls:
                nested_walk_forward(
                    self.frame,
                    feature_columns=BASELINE_FEATURE_COLUMNS,
                    label_column="Label",
                    task=CLASSIFICATION,
                    name="logistic",
                    label_horizon=self.span,
                    embargo_bars=self.span,
                    random_state=42,
                    scale=False,
                )

        self.assertEqual(len(calls), expected_inner + len(self.outer))

    def test_null_placement_matches_too(self):
        # Separate from value equality: a loop that predicted everywhere
        # would still match on the covered rows.
        expected = self._untuned_predictions()
        with _grid("logistic", CLASSIFICATION, {"C": [1.0]}):
            actual, _covered, _results = nested_walk_forward(
                self.frame,
                feature_columns=BASELINE_FEATURE_COLUMNS,
                label_column="Label",
                task=CLASSIFICATION,
                name="logistic",
                label_horizon=self.span,
                embargo_bars=self.span,
                random_state=42,
                scale=False,
            )
        self.assertTrue(actual.isna().any())
        np.testing.assert_array_equal(
            actual.isna().to_numpy(), expected.isna().to_numpy()
        )


class TestModuleBoundaries(unittest.TestCase):
    """T016 — Rule 8, asserted by AST rather than by a source grep. (FR-009)

    A substring search trips on this module's own docstring, which names
    `signals` and `backtest_harness` in order to say they are *not* imported.
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

    def test_model_cv_imports_exactly_the_declared_set(self):
        self.assertEqual(
            self._imported_modules("model_cv.py"),
            {
                "__future__",
                "collections",
                "typing",
                "numpy",
                "pandas",
                "sklearn",
                "estimators",
                "walk_forward_cv",
                # Spec 033 records opaque search intent before each grid point;
                # the separate forbidden-module guard still bans accounting,
                # fills, signals, data loading, and feature generation here.
                "trial_runner",
            },
        )

    def test_model_cv_imports_no_forbidden_project_module(self):
        forbidden = {
            "signals",
            "backtest_harness",
            "features",
            "targets",
            "logistic_baseline",
            "metrics",
            "ma_crossover_backtest",
            "data",
        }
        self.assertEqual(self._imported_modules("model_cv.py") & forbidden, set())


if __name__ == "__main__":
    unittest.main()
