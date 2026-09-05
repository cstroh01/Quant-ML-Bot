"""Tests for scripts/walk_forward_cv.py (spec 003: purge + embargo)."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from walk_forward_cv import walk_forward_splits  # noqa: E402


def _daily_frame(start: str, end: str) -> pd.DataFrame:
    """A minimal DataFrame with one row per calendar day, positions 0..N-1."""
    dates = pd.date_range(start, end, freq="D")
    return pd.DataFrame({"Date": dates})


class TestPurge(unittest.TestCase):
    """T008/T009 — purge boundary and off-by-one-at-equality."""

    def setUp(self):
        # Jan 1 - Apr 30, 2024. initial_train_months=1 -> fold 1's test
        # window is February, starting at position 31 (Jan has 31 days).
        self.data = _daily_frame("2024-01-01", "2024-04-30")
        self.test_start_pos = 31

    def test_purge_boundary_and_off_by_one(self):
        label_horizon = 5
        train_indices, test_indices = next(
            walk_forward_splits(
                self.data,
                initial_train_months=1,
                test_months=1,
                label_horizon=label_horizon,
                embargo_bars=label_horizon,
            )
        )
        purge_threshold = self.test_start_pos - label_horizon  # 26

        # The row exactly at the purge threshold is dropped (FR-008's
        # explicit off-by-one-at-equality case)...
        self.assertNotIn(purge_threshold, train_indices)
        # ...while the row one position earlier survives.
        self.assertIn(purge_threshold - 1, train_indices)
        # No training row reaches within label_horizon of the test window.
        self.assertTrue(np.all(train_indices < purge_threshold))
        self.assertEqual(test_indices.min(), self.test_start_pos)

    def test_label_horizon_zero_matches_pre_fix_positions(self):
        """T013 — label_horizon=0 purges nothing; fold 1 is unaffected by
        embargo (nothing has been embargoed yet), so training is exactly
        every row before the test window, as it was before this spec."""
        train_indices, test_indices = next(
            walk_forward_splits(
                self.data,
                initial_train_months=1,
                test_months=1,
                label_horizon=0,
                embargo_bars=0,
            )
        )
        np.testing.assert_array_equal(
            train_indices, np.arange(self.test_start_pos)
        )


class TestEmbargo(unittest.TestCase):
    """T010/T011 — embargo applied immediately and persisted across folds."""

    def setUp(self):
        # Jan 1 - Apr 30, 2024, three monthly folds: Feb, Mar, Apr.
        self.data = _daily_frame("2024-01-01", "2024-04-30")

    def test_embargo_excludes_fold_one_zone_from_fold_two(self):
        label_horizon = 1
        embargo_bars = 3
        folds = list(
            walk_forward_splits(
                self.data,
                initial_train_months=1,
                test_months=1,
                label_horizon=label_horizon,
                embargo_bars=embargo_bars,
            )
        )
        self.assertGreaterEqual(len(folds), 2)

        _, fold1_test = folds[0]
        fold2_train, _ = folds[1]

        embargo_start = int(fold1_test.min())
        embargo_end = int(fold1_test.max()) + 1 + embargo_bars

        embargoed_positions = np.arange(embargo_start, embargo_end)
        overlap = np.intersect1d(fold2_train, embargoed_positions)
        self.assertEqual(overlap.size, 0)

    def test_embargo_persists_to_later_folds(self):
        """T011 (SC-002) — fold 1's embargo zone is still excluded from
        fold 3's training set, not just fold 2's."""
        label_horizon = 1
        embargo_bars = 3
        folds = list(
            walk_forward_splits(
                self.data,
                initial_train_months=1,
                test_months=1,
                label_horizon=label_horizon,
                embargo_bars=embargo_bars,
            )
        )
        self.assertGreaterEqual(len(folds), 3)

        _, fold1_test = folds[0]
        fold3_train, _ = folds[2]

        embargo_start = int(fold1_test.min())
        embargo_end = int(fold1_test.max()) + 1 + embargo_bars

        embargoed_positions = np.arange(embargo_start, embargo_end)
        overlap = np.intersect1d(fold3_train, embargoed_positions)
        self.assertEqual(overlap.size, 0)


class TestValidation(unittest.TestCase):
    """T012 — embargo_bars < label_horizon raises ValueError."""

    def test_embargo_shorter_than_label_horizon_raises(self):
        data = _daily_frame("2024-01-01", "2024-04-30")
        with self.assertRaises(ValueError):
            list(
                walk_forward_splits(
                    data,
                    initial_train_months=1,
                    test_months=1,
                    label_horizon=5,
                    embargo_bars=4,
                )
            )


class TestEmptyAfterPurge(unittest.TestCase):
    """T014 — a fold whose training set is purged/embargoed to nothing is
    skipped, not raised."""

    def test_fully_purged_fold_is_skipped(self):
        # Jan 1 - Feb 28, 2024: exactly one fold (test window = February),
        # starting at position 31. A label_horizon that reaches back past
        # position 0 purges every training row for that single fold.
        data = _daily_frame("2024-01-01", "2024-02-28")
        folds = list(
            walk_forward_splits(
                data,
                initial_train_months=1,
                test_months=1,
                label_horizon=31,
                embargo_bars=31,
            )
        )
        self.assertEqual(folds, [])


class TestLogisticBaselineIntegration(unittest.TestCase):
    """T015 — evaluate_walk_forward runs end-to-end with label_horizon=1,
    embargo_bars=1 and its own ordering assertion still holds."""

    def test_evaluate_walk_forward_runs_without_error(self):
        sys.path.insert(
            0, str(Path(__file__).resolve().parent.parent / "scripts")
        )
        from logistic_baseline import FEATURE_COLUMNS, evaluate_walk_forward

        rng = np.random.default_rng(42)
        # evaluate_walk_forward calls walk_forward_splits with its defaults
        # (initial_train_months=6), so the range must extend well past 6
        # months to produce at least one fold.
        dates = pd.date_range("2024-01-01", "2024-10-31", freq="D")
        n = len(dates)
        features = pd.DataFrame(
            {"Date": dates},
        )
        for column in FEATURE_COLUMNS:
            features[column] = rng.normal(size=n)
        # Alternate labels deterministically so both classes are present
        # in every fold's training data.
        features["Label"] = (np.arange(n) % 2).astype(int)

        results = evaluate_walk_forward(features)

        self.assertFalse(results.empty)
        self.assertTrue((results["Train_End"] < results["Test_Start"]).all())


if __name__ == "__main__":
    unittest.main()
