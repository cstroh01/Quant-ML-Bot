"""Tests for targets and features under the spec 019 executable-open contract.

The pre-019 `logistic_baseline` control stays frozen. Its shared level features
must agree by date, while its close-based label and retained-row policy have
explicitly pinned differences from the full-calendar 019 frame.
"""

import ast
import unittest

import numpy as np
import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
import features as features_module
import targets as targets_module
from features import (
    LEVEL_FEATURE_COLUMNS,
    SCALE_FREE_FEATURE_COLUMNS,
    build_features,
    feature_columns,
)
from targets import (
    LABEL_COLUMN,
    build_target,
    direction_label,
    forward_log_return_label,
)
from test_ma_crossover_backtest import make_prices


def _walk(n: int, seed: int = 7) -> pd.DataFrame:
    """A price frame with a non-monotonic close, and so a non-monotonic open
    (`make_prices` sets Open = Close + 1), so a direction label has both
    classes and a wrong shift changes the answer.

    `Volume` is added because `Rel_Volume` reads it and `build_features`
    copies it onto the frame — `make_prices` alone gives Date/Open/Close.
    Since 019 (C4) `build_features` drops no row; it flags them instead.
    """
    rng = np.random.default_rng(seed)
    closes = 100.0 + np.cumsum(rng.normal(scale=1.5, size=n))
    prices = make_prices([float(close) for close in closes])
    prices["Volume"] = rng.integers(1_000_000, 5_000_000, size=n)
    return prices


class TestDirectionLabel(unittest.TestCase):
    def test_label_compares_the_exit_open_against_the_entry_open(self):
        """Label at t is the sign of Open[t+h+1] vs Open[t+1] (019 C3).

        Was `..._compares_against_close_at_t_plus_horizon`: before 019 the
        label compared Close[t+h] with Close[t]. The closes here are chosen so
        the close reading gives a different h = 1 answer ([1, 0, 1, 0]).
        """
        # Closes [10, 12, 11, 15, 14]; make_prices sets Open = Close + 1,
        # so Open = [11, 13, 12, 16, 15].
        prices = make_prices([10.0, 12.0, 11.0, 15.0, 14.0])

        one = direction_label(prices, horizon=1)
        # t=0: Open[2]=12 > Open[1]=13? no -> 0.  t=1: 16 > 12 -> 1.
        # t=2: Open[4]=15 > Open[3]=16? no -> 0.  t=3, t=4 need Open[5]: NA.
        self.assertEqual(one.tolist()[:3], [0, 1, 0])
        self.assertTrue(one.iloc[3:].isna().all())

        two = direction_label(prices, horizon=2)
        # t=0: Open[3]=16 > Open[1]=13 -> 1.  t=1: Open[4]=15 > Open[2]=12 -> 1.
        # t=2..4 need Open[5] or later: NA (h + 1 = 3 rows).
        self.assertEqual(two.tolist()[:2], [1, 1])
        self.assertTrue(two.iloc[2:].isna().all())

    def test_a_flat_close_counts_as_down(self):
        # Stated convention, matching logistic_baseline.build_features:47.
        prices = make_prices([10.0, 10.0, 10.0])
        self.assertEqual(direction_label(prices, horizon=1).iloc[0], 0)

    def test_dtype_is_nullable_so_the_tail_cannot_become_false(self):
        """A bool or int64 column cannot hold a null, so the unobservable
        tail would silently become False/0 — a fabricated target.

        Since 019 (C2) the tail is h + 1 rows: at h = 3 the last 4 rows lack
        the exit open Open[t+4].
        """
        label = direction_label(_walk(20), horizon=3)

        self.assertEqual(str(label.dtype), "Int64")
        self.assertTrue(label.iloc[-4:].isna().all())
        self.assertFalse(label.iloc[:-4].isna().any())


class TestForwardLogReturnLabel(unittest.TestCase):
    def test_value_is_the_log_ratio_over_the_horizon(self):
        """log(Open[t+h+1] / Open[t+1]) (019 C3), not log(Close[t+h]/Close[t])."""
        # Closes [100, 110, 121, 133.1]; Open = Close + 1 = [101, 111, 122, 134.1].
        prices = make_prices([100.0, 110.0, 121.0, 133.1])

        label = forward_log_return_label(prices, horizon=1)
        # t=0: log(Open[2]/Open[1]) = log(122/111).
        # t=1: log(Open[3]/Open[2]) = log(134.1/122).
        # t=2, t=3 need Open[4] or later: the last h + 1 = 2 rows are NaN.
        self.assertAlmostEqual(label.iloc[0], np.log(122.0 / 111.0))
        self.assertAlmostEqual(label.iloc[1], np.log(134.1 / 122.0))
        self.assertTrue(label.iloc[2:].isna().all())

        two = forward_log_return_label(prices, horizon=2)
        # t=0: log(Open[3]/Open[1]) = log(134.1/111); last h + 1 = 3 rows NaN.
        self.assertAlmostEqual(two.iloc[0], np.log(134.1 / 111.0))
        self.assertTrue(two.iloc[1:].isna().all())

    def test_log_returns_add_across_the_horizon(self):
        """The property log returns are chosen for: a two-bar return is the
        sum of its two one-bar returns."""
        prices = _walk(30)
        one = forward_log_return_label(prices, horizon=1)
        two = forward_log_return_label(prices, horizon=2)

        # r2[t] == r1[t] + r1[t+1]
        expected = one + one.shift(-1)
        pd.testing.assert_series_equal(
            two.iloc[:-2], expected.iloc[:-2], check_names=False
        )

    def test_a_non_positive_open_endpoint_is_nan_not_infinite(self):
        """Was `test_non_positive_close_is_nan_not_negative_infinity`: since
        019 (C3) the label reads opens, so the zero goes on an *Open*. A zero
        entry open would give log(x) - log(0) = +inf if unguarded.
        """
        # Closes [100, 110, 50, 60]; Open = Close + 1 = [101, 111, 51, 61],
        # then zero Open[1], which is row 0's entry endpoint (h = 1).
        prices = make_prices([100.0, 110.0, 50.0, 60.0])
        prices.loc[1, "Open"] = 0.0
        label = forward_log_return_label(prices, horizon=1)

        self.assertTrue(np.isnan(label.iloc[0]))
        # Row 1 does not touch Open[1]: log(Open[3]/Open[2]) = log(61/51).
        self.assertAlmostEqual(label.iloc[1], np.log(61.0 / 51.0))
        self.assertFalse(np.isinf(label.to_numpy()).any())


def _leaky_forward_log_return(prices: pd.DataFrame, *, horizon: int) -> pd.Series:
    """A deliberately wrong label that reads one bar past its exit open.

    Not production code and never imported by it: this exists so the guards
    below can be shown firing (Rule 12). It is the exact bug they exist to
    catch — `Open[t + h + 2]` instead of `Open[t + h + 1]` — and it is the
    kind of bug that raises nothing, produces a plausible column, and simply
    scores better.
    """
    entry = prices.Open.shift(-1)
    exit_open = prices.Open.shift(-(horizon + 2))  # the planted defect
    return pd.Series(
        np.log(exit_open.to_numpy(dtype=float) / entry.to_numpy(dtype=float)),
        index=prices.index,
        name=LABEL_COLUMN,
    )


def _leaky_direction(prices: pd.DataFrame, *, horizon: int) -> pd.Series:
    """The direction half of the same planted defect."""
    returns = _leaky_forward_log_return(prices, horizon=horizon)
    label = (returns > 0).astype("Int64")
    label[returns.isna()] = pd.NA
    return label.rename(LABEL_COLUMN)


#: The horizon and the row the two guards below are written around.
_GUARD_HORIZON = 2
_GUARD_ROW = 5
#: The exit open the label is allowed to read, as an offset from the row.
_EXIT_OFFSET = _GUARD_HORIZON + 1
#: One bar past it — the first bar the label must be blind to.
_PAST_EXIT_OFFSET = _GUARD_HORIZON + 2


def _straddling_perturbations(offset: int) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """`(base, [below, above])`, each moving one **open** across the entry open.

    `Open`, not `Close`: under spec 019 the label is built from the
    executable open, so perturbing `Close` would touch nothing the label
    reads and every assertion built on it would hold vacuously.

    Two perturbations, not one, and absolute rather than scaled. A single
    upward scaling cannot flip a direction label that already read "up", so
    a leaky *direction* label can absorb it and look blind. Placing the bar
    once below and once above the entry open removes that escape: any label
    that reads this bar returns opposite directions in the two frames, so it
    cannot match an unperturbed original in both.
    """
    base = _walk(20)
    entry_open = base.loc[_GUARD_ROW + 1, "Open"]
    frames = []
    for factor in (0.5, 2.0):
        perturbed = base.copy()
        perturbed.loc[_GUARD_ROW + offset, "Open"] = entry_open * factor
        frames.append(perturbed)
    return base, frames


def assert_blind_past_the_exit_open(builder) -> None:
    """Raise `AssertionError` unless `builder` ignores `Open[t + h + 2]`.

    Written as a module-level assertion rather than a test method so the
    red-evidence class can run this exact code against a known-leaky label
    (Rule 12) instead of a re-implementation of it that could drift.
    """
    base, perturbations = _straddling_perturbations(_PAST_EXIT_OFFSET)
    original = builder(base, horizon=_GUARD_HORIZON)
    for perturbed in perturbations:
        changed = builder(perturbed, horizon=_GUARD_HORIZON)
        pd.testing.assert_series_equal(
            original.iloc[: _GUARD_ROW + 1], changed.iloc[: _GUARD_ROW + 1]
        )


def assert_reads_the_exit_open(builder) -> None:
    """Raise `AssertionError` unless `builder` reads `Open[t + h + 1]`.

    The other half: without it, a label that ignored the future entirely
    would pass the blindness check above.

    The exit open is moved to the far side of the *entry* open rather than
    merely scaled — scaling an already-up bar further up leaves a direction
    label unchanged, which would make this assertion vacuous for one of the
    two builders.
    """
    base = _walk(20)
    entry_open = base.loc[_GUARD_ROW + 1, "Open"]
    original = builder(base, horizon=_GUARD_HORIZON)

    perturbed = base.copy()
    # If the label read "up", force the exit open below the entry open; if
    # it read "down", force it above.
    went_up = direction_label(base, horizon=_GUARD_HORIZON).iloc[_GUARD_ROW] == 1
    perturbed.loc[_GUARD_ROW + _EXIT_OFFSET, "Open"] = (
        entry_open * 0.5 if went_up else entry_open * 2.0
    )

    changed = builder(perturbed, horizon=_GUARD_HORIZON)
    assert original.iloc[_GUARD_ROW] != changed.iloc[_GUARD_ROW], (
        f"{builder.__name__} ignored its own exit open at "
        f"row {_GUARD_ROW + _EXIT_OFFSET}"
    )


class TestOffByOne(unittest.TestCase):
    """SC-004 (Rule 1) — the label reaches exactly its two executable opens.

    Spec 019 (`spec.md:40,46`) makes the label
    `log(Open[t + h + 1] / Open[t + 1])`. It therefore reads exactly two
    bars: the entry open at `t + 1` and the exit open at `t + h + 1`. Nothing
    between them enters it, so "one bar too far" is `t + h + 2` — not
    `t + h + 1`, which is the exit open itself.

    A label that reached one bar further would still look plausible and
    would raise nothing; it would just score better. These two tests are the
    only thing standing between that bug and a green suite, so
    `TestOffByOneGuardsFireOnARealBug` below proves they can go red.
    """

    def test_perturbing_the_bar_just_past_the_exit_open_changes_nothing(self):
        for builder in (direction_label, forward_log_return_label):
            with self.subTest(builder=builder.__name__):
                assert_blind_past_the_exit_open(builder)

    def test_perturbing_the_exit_open_does_change_it(self):
        for builder in (direction_label, forward_log_return_label):
            with self.subTest(builder=builder.__name__):
                assert_reads_the_exit_open(builder)


class TestOffByOneGuardsFireOnARealBug(unittest.TestCase):
    """Rule 12 — the red evidence for the two guards above.

    These run the *same* assertion helpers `TestOffByOne` runs, against a
    label carrying the planted one-bar-too-far defect, and assert they
    raise. If a future edit weakens a helper into something a leaky label
    can satisfy, this class fails and says so. A guard that has never been
    seen failing is not evidence that the thing it guards holds.
    """

    def test_the_blindness_guard_catches_a_label_that_reads_too_far(self):
        for builder in (_leaky_direction, _leaky_forward_log_return):
            with self.subTest(builder=builder.__name__):
                with self.assertRaises(AssertionError):
                    assert_blind_past_the_exit_open(builder)

    def test_the_planted_bug_is_otherwise_a_plausible_label(self):
        """The defect is invisible to everything except the guard.

        If the leaky label were obviously broken — all null, all one class —
        the guard above would prove nothing: any check at all would catch
        it. It reads a real future open and produces a real column; only its
        reach is wrong.
        """
        leaky = _leaky_forward_log_return(_walk(20), horizon=_GUARD_HORIZON)
        self.assertTrue(np.isfinite(leaky.iloc[:_GUARD_ROW + 1]).all())
        self.assertGreater(
            _leaky_direction(_walk(20), horizon=_GUARD_HORIZON).nunique(), 1
        )

    def test_the_other_half_of_the_pair_also_catches_it(self):
        """A one-bar-too-far label does not read the exit open it should.

        Recorded because it is not obvious: the leaky label reads
        `Open[t + h + 2]`, so moving `Open[t + h + 1]` leaves it untouched
        and `assert_reads_the_exit_open` fires too. Both halves catch this
        particular defect; they are kept separate because they fail on
        different ones (reaching too far vs. not reaching at all).
        """
        with self.assertRaises(AssertionError):
            assert_reads_the_exit_open(_leaky_forward_log_return)


class TestBoundaries(unittest.TestCase):
    """SC-003 / SC-006 — the unobservable h + 1 tail, and an over-long horizon."""

    def test_exactly_the_last_span_rows_are_null(self):
        """Was `test_exactly_the_last_horizon_rows_are_null`: since 019 (C2)
        row t needs Open[t+h+1], so the last h + 1 rows are unobservable."""
        n = 25
        prices = _walk(n)
        for horizon in (1, 2, 3, 7):
            span = horizon + 1
            with self.subTest(horizon=horizon):
                for label in (
                    direction_label(prices, horizon=horizon),
                    forward_log_return_label(prices, horizon=horizon),
                ):
                    self.assertEqual(int(label.isna().sum()), span)
                    self.assertTrue(label.iloc[-span:].isna().all())
                    self.assertFalse(label.iloc[:-span].isna().any())

    def test_first_row_has_a_label(self):
        label = direction_label(_walk(10), horizon=1)
        self.assertFalse(pd.isna(label.iloc[0]))

    def test_horizon_at_least_as_long_as_the_frame_is_all_null(self):
        prices = _walk(5)
        self.assertTrue(direction_label(prices, horizon=5).isna().all())
        self.assertTrue(direction_label(prices, horizon=99).isna().all())

    def test_an_over_long_horizon_keeps_every_row_and_trains_on_none(self):
        """SC-006 — a 300-bar horizon on 60 bars is not an exception.

        Was `test_over_long_horizon_yields_an_empty_feature_frame_not_an_error`:
        before 019 the frame came back empty. Since 019 (C4) no row is
        dropped, so all 60 stay and none is `Train_Eligible` (every label is
        unknown); the third value is the span 300 + 1 = 301 (C2).
        """
        frame, task, span = build_features(
            _walk(60), target_kind="direction", label_horizon=300  # SC-002: forecast h, not a purge width
        )
        self.assertEqual(len(frame), 60)
        self.assertFalse(frame.Train_Eligible.any())
        self.assertEqual((task, span), ("classification", 301))


class TestValidation(unittest.TestCase):
    """SC-005 — degenerate targets are rejected, never silently produced."""

    def test_zero_horizon_raises(self):
        # Close[t] > Close[t] is False on every row, and log(1) is 0.0
        # everywhere. Both are valid columns nothing can be learned from.
        prices = _walk(10)
        for builder in (direction_label, forward_log_return_label):
            with self.subTest(builder=builder.__name__):
                with self.assertRaises(ValueError):
                    builder(prices, horizon=0)

    def test_negative_horizon_raises(self):
        prices = _walk(10)
        for builder in (direction_label, forward_log_return_label):
            with self.subTest(builder=builder.__name__):
                with self.assertRaises(ValueError):
                    builder(prices, horizon=-1)

    def test_unknown_target_kind_raises_and_does_not_default(self):
        with self.assertRaises(ValueError) as caught:
            build_target(_walk(10), kind="momentum", horizon=1)
        self.assertIn("direction", str(caught.exception))
        self.assertIn("return", str(caught.exception))

    def test_missing_open_column_raises(self):
        """Was `test_missing_close_column_raises`: since 019 (C3) the label
        reads opens, so `Open` is the required column. A Close-only frame
        must raise, and the message must name the missing column."""
        with self.assertRaisesRegex(ValueError, "Open"):
            direction_label(pd.DataFrame({"Close": [1.0, 2.0]}), horizon=1)


class TestBuildTargetContract(unittest.TestCase):
    """SC-005 / FR-004 — the availability-span handback.

    Since 019 (C2) the third value is the label availability span h + 1, not
    the horizon: the label at t is known only at the exit open Open[t+h+1].
    """

    def test_direction_is_a_classification_task(self):
        label, task, span = build_target(_walk(20), kind="direction", horizon=1)
        self.assertEqual(task, "classification")
        self.assertEqual(str(label.dtype), "Int64")
        self.assertEqual(span, 2)  # h + 1 = 1 + 1

    def test_return_is_a_regression_task(self):
        label, task, span = build_target(_walk(20), kind="return", horizon=3)
        self.assertEqual(task, "regression")
        self.assertEqual(label.dtype, float)
        self.assertEqual(span, 4)  # h + 1 = 3 + 1

    def test_the_third_value_is_the_availability_span(self):
        """FR-004 — this is what lets a caller pass one number to both purge
        and embargo instead of writing the literal twice.

        Was `test_the_returned_horizon_is_what_was_asked_for`: before 019 the
        third value was the horizon itself; now it is h + 1 (C2).
        """
        for horizon in (1, 2, 5):
            for kind in ("direction", "return"):
                with self.subTest(kind=kind, horizon=horizon):
                    _, _, returned = build_target(
                        _walk(30), kind=kind, horizon=horizon
                    )
                    self.assertEqual(returned, horizon + 1)

    def test_passing_the_span_back_as_horizon_builds_a_different_label(self):
        """REVIEW_019 R-10 — the span is not a horizon. Fed back as
        `horizon=`, it builds a longer label, so the mistake is visible."""
        # Closes [10, 12, 11, 15, 14]; Open = Close + 1 = [11, 13, 12, 16, 15].
        prices = make_prices([10.0, 12.0, 11.0, 15.0, 14.0])
        # Row 0 at h = 1: Open[2]/Open[1] = 12/13, down (0), log(12/13).
        # Row 0 at h = span = 2: Open[3]/Open[1] = 16/13, up (1), log(16/13).
        expected = {
            "direction": (0, 1),
            "return": (np.log(12.0 / 13.0), np.log(16.0 / 13.0)),
        }
        for kind, (at_one, at_span) in expected.items():
            with self.subTest(kind=kind):
                right, _, span = build_target(prices, kind=kind, horizon=1)
                wrong = build_target(prices, kind=kind, horizon=span)[0]
                self.assertAlmostEqual(float(right.iloc[0]), at_one)
                self.assertAlmostEqual(float(wrong.iloc[0]), at_span)
                self.assertNotEqual(right.iloc[0], wrong.iloc[0])


class TestGapCase(unittest.TestCase):
    """SC-007 — labels are positional, matching the purge (spec 003 FR-005).

    If a label were sized in calendar days and the purge in rows, the two
    would disagree at every holiday — and the purge exists to cover exactly
    this label.
    """

    def test_label_spans_rows_not_calendar_days(self):
        """Re-derived on opens for 019 (C3). Before 019 this compared closes;
        the closes are left as they were and are not read by the label."""
        prices = pd.DataFrame(
            {
                "Date": pd.to_datetime(
                    ["2024-01-02", "2024-01-03", "2024-01-08", "2024-01-09"]
                ),
                "Open": [10.0, 11.0, 14.0, 8.0],
                "Close": [10.0, 20.0, 5.0, 30.0],
            }
        )
        label = direction_label(prices, horizon=1)

        # Row 0: entry Open[1] = 11 (01-03), exit Open[2] = 14 (01-08) — a
        # five-calendar-day jump but one bar. Row reading: 14 > 11, up (1).
        # A calendar-day reading of h = 1 would exit at the last open on or
        # before 01-04, which is 01-03's own 11: 11 > 11 is false, down (0).
        self.assertEqual(label.iloc[0], 1)
        # Row 1: Open[3]/Open[2] = 8/14, down (0). Rows 2-3 lack Open[t+2].
        self.assertEqual(label.iloc[1], 0)
        self.assertTrue(label.iloc[2:].isna().all())

        returns = forward_log_return_label(prices, horizon=1)
        # Row 0: log(Open[2]/Open[1]) = log(14/11); calendar reading: log(11/11) = 0.
        self.assertAlmostEqual(returns.iloc[0], np.log(14.0 / 11.0))


class TestEquivalenceWithLogisticBaseline(unittest.TestCase):
    """Pin the exact contract divergence from the frozen pre-019 control."""

    def setUp(self):
        self.prices = _walk(200)

    def test_level_feature_columns_match(self):
        """The anti-drift guard, now pointed at the set it applies to.

        Spec 014 made the scale-free set the default, so a blanket
        `features.FEATURE_COLUMNS == logistic_baseline.FEATURE_COLUMNS` is no
        longer the property to hold — but the level set is still the control's
        own five columns, and it still must not drift from them.
        """
        from logistic_baseline import FEATURE_COLUMNS as baseline_columns

        self.assertEqual(LEVEL_FEATURE_COLUMNS, baseline_columns)

    def test_the_default_feature_set_is_not_the_level_set(self):
        """The point of spec 014: the default is the scale-free set."""
        self.assertEqual(feature_columns(), SCALE_FREE_FEATURE_COLUMNS)
        self.assertNotEqual(feature_columns(), LEVEL_FEATURE_COLUMNS)

    def test_label_divergence_from_the_pre_019_control_is_exactly_the_open_basis(self):
        """The control reads next Close; 019 reads entry and exit Open."""
        import logistic_baseline

        prices = pd.DataFrame({
            "Date": pd.bdate_range("2024-01-02", periods=80),
            "Close": 100.0 + np.arange(80, dtype=float),
            "Open": 101.0 + np.arange(80, dtype=float),
            "Volume": np.full(80, 1_000_000),
        })
        prices.loc[32, "Open"] = 90.0
        old = logistic_baseline.build_features(prices)
        new_label = direction_label(prices, horizon=1)
        positions = pd.Index(prices["Date"]).get_indexer(old["Date"])
        self.assertTrue((positions >= 0).all())
        old_label = old[LABEL_COLUMN].reset_index(drop=True)
        aligned = new_label.iloc[positions].reset_index(drop=True)

        # At t=30, Close[31]=131 > Close[30]=130, while
        # Open[32]=90 < Open[31]=132. The sole changed Open reverses that row.
        self.assertEqual(int(old_label.iloc[0]), 1)
        self.assertEqual(int(aligned.iloc[0]), 0)
        expected_old = (prices.Close.shift(-1) > prices.Close).astype("Int64")
        expected_new = (prices.Open.shift(-2) > prices.Open.shift(-1)).astype("Int64")
        expected_new[prices.Open.shift(-2).isna()] = pd.NA
        pd.testing.assert_series_equal(
            old_label,
            expected_old.iloc[positions].reset_index(drop=True),
            check_names=False,
        )
        pd.testing.assert_series_equal(
            aligned,
            expected_new.iloc[positions].reset_index(drop=True),
            check_names=False,
        )
        self.assertEqual(
            np.flatnonzero(old_label.ne(aligned).fillna(False).to_numpy()).tolist(),
            [0],
        )
        self.assertEqual(aligned.isna().sum(), 1)  # t=78 lacks Open[80].

    def test_baseline_rows_are_a_date_subset_of_the_full_calendar_frame(self):
        """019 retains every session; common level features still agree."""
        import logistic_baseline

        old = logistic_baseline.build_features(self.prices)
        new, task, span = build_features(
            self.prices,
            target_kind="direction",
            label_horizon=1,  # SC-002: forecast h, not a purge width
            short_window=logistic_baseline.SHORT_WINDOW,
            long_window=logistic_baseline.LONG_WINDOW,
            volatility_window=logistic_baseline.VOLATILITY_WINDOW,
            feature_set="levels",
        )

        self.assertEqual((task, span), ("classification", 2))
        self.assertEqual(len(new), len(self.prices))
        self.assertLess(len(old), len(new))
        positions = pd.Index(new["Date"]).get_indexer(old["Date"])
        self.assertTrue((positions >= 0).all())
        pd.testing.assert_frame_equal(
            new.iloc[positions][LEVEL_FEATURE_COLUMNS].reset_index(drop=True),
            old[LEVEL_FEATURE_COLUMNS].reset_index(drop=True),
        )


class TestRuleOneShape(unittest.TestCase):
    """FR-009 — the label is never a feature."""

    def test_label_is_not_in_feature_columns(self):
        for name in sorted(features_module.FEATURE_SETS):
            with self.subTest(feature_set=name):
                self.assertNotIn(LABEL_COLUMN, feature_columns(name))

    def test_features_are_computable_from_the_past(self):
        """Perturbing a future close must not move any feature at t.

        The label may change — that is its job — but a feature that moved
        would be reading the future.
        """
        base = _walk(120)
        perturbed = base.copy()
        perturbed.loc[100:, "Close"] *= 2.0

        kwargs = {"target_kind": "return", "label_horizon": 1}
        base_frame, _, _ = build_features(base, **kwargs)
        changed_frame, _, _ = build_features(perturbed, **kwargs)

        # Compare the rows before the perturbation, which survive in both.
        rows = 60
        pd.testing.assert_frame_equal(
            base_frame[SCALE_FREE_FEATURE_COLUMNS].iloc[:rows],
            changed_frame[SCALE_FREE_FEATURE_COLUMNS].iloc[:rows],
        )


class TestModuleBoundaries(unittest.TestCase):
    """FR-010 (Rule 8) — signal layer stays out of execution."""

    @staticmethod
    def _imported_module_names(module) -> set[str]:
        """Top-level module names this module actually imports.

        Parsed from the AST rather than grepped from the source: the source
        text mentions `backtest_harness` in a docstring explaining that it is
        *not* imported, and a substring check would fail on the very comment
        that documents the rule.
        """
        with open(module.__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())

        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        return names

    def test_neither_module_imports_the_harness(self):
        forbidden = {"backtest_harness", "plotting", "data", "yfinance"}
        for module in (targets_module, features_module):
            with self.subTest(module=module.__name__):
                self.assertEqual(
                    self._imported_module_names(module) & forbidden, set()
                )

    def test_targets_imports_nothing_from_the_project(self):
        """`targets.py` knows only about prices and a horizon."""
        self.assertEqual(
            self._imported_module_names(targets_module), {"numpy", "pandas"}
        )

    def test_features_imports_only_signals_and_targets(self):
        self.assertEqual(
            self._imported_module_names(features_module),
            {"numpy", "pandas", "signals", "targets"},
        )


if __name__ == "__main__":
    unittest.main()
