"""Tests for scripts/logistic_baseline.py's ML signal wiring (spec 005)."""

import unittest

import numpy as np
import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
from logistic_baseline import (
    FEATURE_COLUMNS,
    _signal_from_predictions,
    build_ml_signal,
    evaluate_walk_forward,
    walk_forward_predictions,
)
from walk_forward_cv import walk_forward_splits


def _synthetic_features(start: str, end: str, seed: int = 42) -> pd.DataFrame:
    """A features-shaped frame with random FEATURE_COLUMNS and alternating
    labels, matching what build_features hands to the walk-forward
    functions (Date + FEATURE_COLUMNS + Label, RangeIndex)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D")
    n = len(dates)
    # A simple random-walk price series so run_backtest has real Open/Close
    # to fill against — the walk-forward/prediction logic under test here
    # never looks at price level itself, only at FEATURE_COLUMNS and Label.
    close = 100.0 + np.cumsum(rng.normal(scale=0.5, size=n))
    features = pd.DataFrame({"Date": dates, "Open": close, "Close": close})
    for column in FEATURE_COLUMNS:
        features[column] = rng.normal(size=n)
    features["Label"] = (np.arange(n) % 2).astype(int)
    return features


class TestWalkForwardPredictionsCoverage(unittest.TestCase):
    """T007 — every fold-covered row gets exactly one prediction; earlier
    rows are <NA>. (SC-001)"""

    def test_coverage_matches_fold_test_windows_exactly(self):
        features = _synthetic_features("2024-01-01", "2024-10-31")
        predictions = walk_forward_predictions(features)

        folds = list(walk_forward_splits(features, label_horizon=1, embargo_bars=1))
        self.assertGreater(len(folds), 0)

        covered_positions = np.concatenate([test_idx for _, test_idx in folds])
        # No row covered twice.
        self.assertEqual(len(covered_positions), len(set(covered_positions.tolist())))

        covered_mask = np.zeros(len(features), dtype=bool)
        covered_mask[covered_positions] = True

        self.assertTrue(predictions[covered_mask].notna().all())
        self.assertTrue(predictions[~covered_mask].isna().all())


class TestWalkForwardPredictionsAgreement(unittest.TestCase):
    """T008 — predictions collected here match a fold loop fit/predicted
    the same way evaluate_walk_forward does internally."""

    def test_agrees_with_a_manually_replicated_fold_loop(self):
        from sklearn.linear_model import LogisticRegression

        features = _synthetic_features("2024-01-01", "2024-10-31")
        predictions = walk_forward_predictions(features)

        for train_indices, test_indices in walk_forward_splits(
            features, label_horizon=1, embargo_bars=1
        ):
            model = LogisticRegression(max_iter=1000, random_state=42)
            train_labels = features.iloc[train_indices]["Label"].astype(int)
            model.fit(features.iloc[train_indices][FEATURE_COLUMNS], train_labels)
            expected = model.predict(features.iloc[test_indices][FEATURE_COLUMNS])
            actual = predictions.iloc[test_indices].to_numpy()
            np.testing.assert_array_equal(actual, expected)

    def test_evaluate_walk_forward_still_runs_unchanged(self):
        """FR-006 — evaluate_walk_forward's own behavior is untouched."""
        features = _synthetic_features("2024-01-01", "2024-10-31")
        results = evaluate_walk_forward(features)
        self.assertFalse(results.empty)
        self.assertTrue((results["Train_End"] < results["Test_Start"]).all())


class TestSignalFromPredictions(unittest.TestCase):
    """T009/T010/T011 — transition detection and next-open shifting, tested
    directly against a hand-built prediction series."""

    def test_enter_and_exit_land_one_row_after_the_prediction_changes(self):
        # NA, NA, up, up, down, down, up
        predictions = pd.Series([pd.NA, pd.NA, 1, 1, 0, 0, 1], dtype="Int64")
        buy, sell = _signal_from_predictions(predictions)

        # "up" first appears at position 2 -> Buy_Next_Open fires at 3.
        self.assertFalse(buy.iloc[2])
        self.assertTrue(buy.iloc[3])
        # "down" first appears at position 4 -> Sell_Next_Open fires at 5.
        self.assertFalse(sell.iloc[4])
        self.assertTrue(sell.iloc[5])
        # "up" again at position 6 -> Buy_Next_Open would fire at 7, out of
        # range for a 7-row series, so nothing more should be set.
        self.assertEqual(buy.sum(), 1)
        self.assertEqual(sell.sum(), 1)

    def test_no_repeated_fire_while_already_long(self):
        # up, up, up, up -> exactly one entry, on the transition into "up".
        predictions = pd.Series([1, 1, 1, 1], dtype="Int64")
        buy, sell = _signal_from_predictions(predictions)
        self.assertEqual(buy.sum(), 1)
        self.assertEqual(sell.sum(), 0)

    def test_leading_na_rows_are_flat(self):
        predictions = pd.Series([pd.NA, pd.NA, pd.NA], dtype="Int64")
        buy, sell = _signal_from_predictions(predictions)
        self.assertFalse(buy.any())
        self.assertFalse(sell.any())


class TestBuildMlSignalEndToEnd(unittest.TestCase):
    """T012 — smoke test: build_ml_signal + run_backtest runs cleanly and
    pre-coverage rows are flat."""

    def test_runs_without_error_and_pnl_is_finite(self):
        from backtest_harness import run_backtest

        features = _synthetic_features("2024-01-01", "2024-10-31")
        signalled, first_covered_pos = build_ml_signal(features)

        # Rows before coverage starts are flat (T011 at the build_ml_signal
        # level, not just _signal_from_predictions).
        pre_coverage = signalled.iloc[:first_covered_pos]
        self.assertFalse(pre_coverage["Buy_Next_Open"].any())
        self.assertFalse(pre_coverage["Sell_Next_Open"].any())

        live = signalled.iloc[first_covered_pos:].reset_index(drop=True)
        trade_log = run_backtest(live, commission_per_trade=1.0, slippage_bps=5.0)

        self.assertTrue(np.isfinite(trade_log["Cumulative P&L"]).all())


class TestFirstCoveredPositionIsPositional(unittest.TestCase):
    """T006/T007 (spec 007) — build_ml_signal's second return value is a row
    *position*, not a pandas index label.

    `Series.first_valid_index()` returns a label; `main()` feeds the result
    to `.iloc`, which takes a position. They agree only on a 0-based
    RangeIndex, which every caller happens to pass today. These tests pin
    the distinction so an ordinary pandas operation between `build_features`
    and `build_ml_signal` — a boolean filter, a `dropna`, a per-ticker
    `groupby` slice — cannot silently truncate the backtest window.
    """

    def _frames(self):
        """One frame under three index shapes. Only the index differs."""
        features = _synthetic_features("2024-01-01", "2024-10-31")

        offset = features.copy()
        offset.index = pd.RangeIndex(start=100, stop=100 + len(features))

        dated = features.copy()
        dated.index = pd.DatetimeIndex(features["Date"])

        return {
            "range_index": features,
            "offset_index": offset,
            "datetime_index": dated,
        }

    def test_same_position_regardless_of_index(self):
        """SC-001/SC-002 — all three index shapes return the same position.

        Against the pre-fix code the offset case returns 282 instead of 182,
        and the datetime case raises TypeError.
        """
        positions = {
            name: build_ml_signal(frame)[1]
            for name, frame in self._frames().items()
        }

        self.assertEqual(
            len(set(positions.values())),
            1,
            f"position depends on the index: {positions}",
        )

    def test_returned_position_points_at_the_first_prediction(self):
        """SC-003 — the position is not merely consistent, it is correct.

        Catches an off-by-one that `test_same_position_regardless_of_index`
        would pass: the row at `pos` must have a prediction and the row
        before it must not.
        """
        for name, frame in self._frames().items():
            with self.subTest(index=name):
                _, first_covered_pos = build_ml_signal(frame)
                predictions = walk_forward_predictions(frame)

                self.assertGreater(first_covered_pos, 0)
                self.assertTrue(
                    pd.notna(predictions.iloc[first_covered_pos]),
                    "row at the returned position has no prediction",
                )
                self.assertTrue(
                    predictions.iloc[:first_covered_pos].isna().all(),
                    "a row before the returned position already had one",
                )


if __name__ == "__main__":
    unittest.main()
