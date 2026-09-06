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
    """T005/T006 (spec 006) — the embargo is a *gap after* each test window.

    Spec 003 recorded `[test_start, test_end + embargo_bars)` and so excluded
    each test window from training permanently. Because consecutive test
    windows tile without gaps, the union of those ranges swallowed the whole
    expanding region and every fold trained on the same first
    `initial_train_months` of data. Spec 006 narrows the recorded range to
    `[test_end, test_end + embargo_bars)`.

    These two tests are the rewrite of spec 003's
    `test_embargo_excludes_fold_one_zone_from_fold_two` and
    `test_embargo_persists_to_later_folds`, which asserted the old semantics
    directly. They are rewritten rather than deleted so the embargo keeps its
    coverage across the change (FR-009).
    """

    def setUp(self):
        # Jan 1 - Apr 30, 2024, three monthly folds: Feb, Mar, Apr.
        # One row per calendar day, so position == day offset and every
        # expected value below is hand-computable:
        #   fold 1  test [31, 60)   gap [60, 63)
        #   fold 2  test [60, 91)   gap [91, 94)
        #   fold 3  test [91, 121)
        self.data = _daily_frame("2024-01-01", "2024-04-30")
        self.label_horizon = 1
        self.embargo_bars = 3

    def _folds(self):
        return list(
            walk_forward_splits(
                self.data,
                initial_train_months=1,
                test_months=1,
                label_horizon=self.label_horizon,
                embargo_bars=self.embargo_bars,
            )
        )

    def test_embargo_gap_excluded_from_later_folds(self):
        """SC-003 — the `embargo_bars` rows after a test window stay out of
        every later fold's training set."""
        folds = self._folds()
        self.assertGreaterEqual(len(folds), 3)

        for earlier, (_, earlier_test) in enumerate(folds):
            gap_start = int(earlier_test.max()) + 1
            gap = np.arange(gap_start, gap_start + self.embargo_bars)
            for later in range(earlier + 1, len(folds)):
                later_train, _ = folds[later]
                overlap = np.intersect1d(later_train, gap)
                self.assertEqual(
                    overlap.size,
                    0,
                    f"fold {later + 1}'s training set contains fold "
                    f"{earlier + 1}'s embargo gap at {overlap.tolist()}",
                )

    def test_prior_test_window_re_enters_training(self):
        """SC-002 — the inverse of what spec 003 asserted: a fold's test
        data is ordinary history to a later fold and *is* trained on.

        Fold 1 tests positions [31, 60). Fold 3 purges at
        `91 - label_horizon = 90` and excludes only the gaps [60, 63) and
        [91, 94), so all of 31..59 must be present in its training set.
        Under spec 003's semantics every one of them was excluded forever.
        """
        folds = self._folds()
        self.assertGreaterEqual(len(folds), 3)

        _, fold1_test = folds[0]
        fold3_train, _ = folds[2]

        np.testing.assert_array_equal(fold1_test.min(), 31)
        np.testing.assert_array_equal(fold1_test.max(), 59)

        readmitted = np.intersect1d(fold3_train, fold1_test)
        np.testing.assert_array_equal(readmitted, np.arange(31, 60))

    def test_training_set_grows_across_folds(self):
        """SC-001 — the window actually expands. This is the assertion that
        fails outright under spec 003's ledger, where every fold trained on a
        constant number of rows."""
        folds = self._folds()
        self.assertGreaterEqual(len(folds), 3)

        sizes = [len(train) for train, _ in folds]
        for earlier, later in zip(sizes, sizes[1:]):
            self.assertGreater(later, earlier, f"training sizes: {sizes}")

    def test_every_fold_trains_strictly_before_it_tests(self):
        """SC-004 / FR-005 — the chronological guarantee, checked on every
        fold rather than only the first.

        This is the test that would catch a 'fix' that restored growth by
        letting training data reach into or past a test window.
        """
        folds = self._folds()
        self.assertGreaterEqual(len(folds), 3)

        for fold, (train, test) in enumerate(folds, start=1):
            self.assertLess(
                int(train.max()),
                int(test.min()),
                f"fold {fold} trains at or after its own test window",
            )
            # And the purge still holds a label_horizon of clearance.
            self.assertLess(
                int(train.max()),
                int(test.min()) - self.label_horizon,
                f"fold {fold} trains within label_horizon of its test window",
            )

    def test_all_prior_gaps_still_excluded_from_final_fold(self):
        """SC-003 / FR-002 — the ledger is still cumulative. Spec 006 changes
        what each entry covers, not how long it is honored."""
        data = _daily_frame("2024-01-01", "2024-08-31")
        folds = list(
            walk_forward_splits(
                data,
                initial_train_months=1,
                test_months=1,
                label_horizon=self.label_horizon,
                embargo_bars=self.embargo_bars,
            )
        )
        self.assertGreaterEqual(len(folds), 5)

        final_train, _ = folds[-1]
        every_prior_gap = np.concatenate(
            [
                np.arange(
                    int(test.max()) + 1,
                    int(test.max()) + 1 + self.embargo_bars,
                )
                for _, test in folds[:-1]
            ]
        )
        overlap = np.intersect1d(final_train, every_prior_gap)
        self.assertEqual(overlap.size, 0, f"leaked gap positions: {overlap.tolist()}")

        # The gaps are real holes inside the final fold's training range,
        # not positions that fell off the end of it.
        interior_gaps = every_prior_gap[every_prior_gap < int(final_train.max())]
        self.assertGreater(interior_gaps.size, 0)

    def test_zero_embargo_records_an_empty_gap(self):
        """Edge case — `embargo_bars=0` records `[e, e)`, which excludes
        nothing and must not error."""
        folds = list(
            walk_forward_splits(
                self.data,
                initial_train_months=1,
                test_months=1,
                label_horizon=0,
                embargo_bars=0,
            )
        )
        self.assertGreaterEqual(len(folds), 3)

        for fold, (train, test) in enumerate(folds, start=1):
            np.testing.assert_array_equal(
                train,
                np.arange(int(test.min())),
                f"fold {fold} should train on every row before its test window",
            )


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
