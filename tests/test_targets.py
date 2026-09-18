"""Tests for scripts/targets.py and scripts/features.py (spec 009).

The equivalence tests against `logistic_baseline` are the load-bearing ones:
its AAPL result is the control every Phase 3 comparison is measured against,
so a silent divergence here would move the goalpost without anything saying
so.
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
    """A price frame with a non-monotonic close, so a direction label has
    both classes and a wrong shift changes the answer.

    `Volume` is added because every feature set needs it, and
    `build_features` drops on it — `make_prices` alone gives Date/Open/Close.
    """
    rng = np.random.default_rng(seed)
    closes = 100.0 + np.cumsum(rng.normal(scale=1.5, size=n))
    prices = make_prices([float(close) for close in closes])
    prices["Volume"] = rng.integers(1_000_000, 5_000_000, size=n)
    return prices


class TestDirectionLabel(unittest.TestCase):
    def test_label_at_t_compares_against_close_at_t_plus_horizon(self):
        prices = make_prices([10.0, 12.0, 11.0, 15.0, 14.0])

        one = direction_label(prices, horizon=1)
        # 10->12 up, 12->11 down, 11->15 up, 15->14 down, last unobservable.
        self.assertEqual(one.tolist()[:4], [1, 0, 1, 0])
        self.assertTrue(pd.isna(one.iloc[4]))

        two = direction_label(prices, horizon=2)
        # 10->11 up, 12->15 up, 11->14 up, last two unobservable.
        self.assertEqual(two.tolist()[:3], [1, 1, 1])
        self.assertTrue(two.iloc[3:].isna().all())

    def test_a_flat_close_counts_as_down(self):
        # Stated convention, matching logistic_baseline.build_features:47.
        prices = make_prices([10.0, 10.0, 10.0])
        self.assertEqual(direction_label(prices, horizon=1).iloc[0], 0)

    def test_dtype_is_nullable_so_the_tail_cannot_become_false(self):
        """A bool or int64 column cannot hold a null, so the unobservable
        tail would silently become False/0 — a fabricated target."""
        label = direction_label(_walk(20), horizon=3)

        self.assertEqual(str(label.dtype), "Int64")
        self.assertTrue(label.iloc[-3:].isna().all())
        self.assertFalse(label.iloc[:-3].isna().any())


class TestForwardLogReturnLabel(unittest.TestCase):
    def test_value_is_the_log_ratio_over_the_horizon(self):
        prices = make_prices([100.0, 110.0, 121.0])

        label = forward_log_return_label(prices, horizon=1)
        self.assertAlmostEqual(label.iloc[0], np.log(110.0 / 100.0))
        self.assertAlmostEqual(label.iloc[1], np.log(121.0 / 110.0))
        self.assertTrue(np.isnan(label.iloc[2]))

        two = forward_log_return_label(prices, horizon=2)
        self.assertAlmostEqual(two.iloc[0], np.log(121.0 / 100.0))

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

    def test_non_positive_close_is_nan_not_negative_infinity(self):
        prices = make_prices([100.0, 0.0, 50.0])
        label = forward_log_return_label(prices, horizon=1)

        self.assertTrue(np.isnan(label.iloc[0]))
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
    """SC-003 / SC-006 — the unobservable tail, and an over-long horizon."""

    def test_exactly_the_last_horizon_rows_are_null(self):
        n = 25
        prices = _walk(n)
        for horizon in (1, 2, 3, 7):
            with self.subTest(horizon=horizon):
                for label in (
                    direction_label(prices, horizon=horizon),
                    forward_log_return_label(prices, horizon=horizon),
                ):
                    self.assertEqual(int(label.isna().sum()), horizon)
                    self.assertTrue(label.iloc[-horizon:].isna().all())
                    self.assertFalse(label.iloc[:-horizon].isna().any())

    def test_first_row_has_a_label(self):
        label = direction_label(_walk(10), horizon=1)
        self.assertFalse(pd.isna(label.iloc[0]))

    def test_horizon_at_least_as_long_as_the_frame_is_all_null(self):
        prices = _walk(5)
        self.assertTrue(direction_label(prices, horizon=5).isna().all())
        self.assertTrue(direction_label(prices, horizon=99).isna().all())

    def test_over_long_horizon_yields_an_empty_feature_frame_not_an_error(self):
        """SC-006 — asking for a 300-bar horizon on 60 bars gets nothing,
        which is correct, not an exception."""
        frame, task, horizon = build_features(
            _walk(60), target_kind="direction", label_horizon=300
        )
        self.assertTrue(frame.empty)
        self.assertEqual((task, horizon), ("classification", 300))


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

    def test_missing_close_column_raises(self):
        with self.assertRaises(ValueError):
            direction_label(pd.DataFrame({"Open": [1.0, 2.0]}), horizon=1)


class TestBuildTargetContract(unittest.TestCase):
    """SC-005 / FR-004 — the horizon handback."""

    def test_direction_is_a_classification_task(self):
        label, task, horizon = build_target(_walk(20), kind="direction", horizon=1)
        self.assertEqual(task, "classification")
        self.assertEqual(str(label.dtype), "Int64")
        self.assertEqual(horizon, 1)

    def test_return_is_a_regression_task(self):
        label, task, horizon = build_target(_walk(20), kind="return", horizon=3)
        self.assertEqual(task, "regression")
        self.assertEqual(label.dtype, float)
        self.assertEqual(horizon, 3)

    def test_the_returned_horizon_is_what_was_asked_for(self):
        """FR-004 — this is what lets a caller pass one number to both the
        label and the purge instead of writing the literal twice."""
        for horizon in (1, 2, 5):
            for kind in ("direction", "return"):
                with self.subTest(kind=kind, horizon=horizon):
                    _, _, returned = build_target(
                        _walk(30), kind=kind, horizon=horizon
                    )
                    self.assertEqual(returned, horizon)


class TestGapCase(unittest.TestCase):
    """SC-007 — labels are positional, matching the purge (spec 003 FR-005).

    If a label were sized in calendar days and the purge in rows, the two
    would disagree at every holiday — and the purge exists to cover exactly
    this label.
    """

    def test_label_spans_rows_not_calendar_days(self):
        prices = pd.DataFrame(
            {
                "Date": pd.to_datetime(
                    ["2024-01-02", "2024-01-03", "2024-01-08", "2024-01-09"]
                ),
                "Open": [10.0, 11.0, 12.0, 13.0],
                "Close": [10.0, 20.0, 5.0, 30.0],
            }
        )
        label = direction_label(prices, horizon=1)

        # Row 1 -> row 2 is a five-calendar-day jump but one bar. The label
        # compares 20 against 5 and reads down.
        self.assertEqual(label.iloc[1], 0)
        self.assertEqual(label.iloc[2], 1)

        returns = forward_log_return_label(prices, horizon=1)
        self.assertAlmostEqual(returns.iloc[1], np.log(5.0 / 20.0))


class TestEquivalenceWithLogisticBaseline(unittest.TestCase):
    """SC-001 / SC-002 — the committed control result is not moved.

    `docs/PROJECT_CONTEXT.md` quotes an AAPL result produced by
    `logistic_baseline.build_features`. If the new path diverges from it,
    every Phase 3 comparison is against a moved goalpost and nothing says so.
    """

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

    def test_direction_label_matches_the_baseline_label(self):
        """SC-001 — element for element, dtype included."""
        import logistic_baseline

        old = logistic_baseline.build_features(self.prices)
        new_label = direction_label(self.prices, horizon=1)

        # The old frame drops warm-up rows; compare over the rows it kept, by
        # matching on Date rather than assuming a shared offset.
        aligned = new_label.reindex(
            pd.Index(self.prices["Date"]).get_indexer(old["Date"])
        ).reset_index(drop=True)

        pd.testing.assert_series_equal(
            old[LABEL_COLUMN].reset_index(drop=True),
            aligned,
            check_names=False,
        )

    def test_build_features_reproduces_the_baseline_frame(self):
        """SC-002 — every shared column, row for row."""
        import logistic_baseline

        old = logistic_baseline.build_features(self.prices)
        new, task, horizon = build_features(
            self.prices,
            target_kind="direction",
            label_horizon=1,
            short_window=logistic_baseline.SHORT_WINDOW,
            long_window=logistic_baseline.LONG_WINDOW,
            volatility_window=logistic_baseline.VOLATILITY_WINDOW,
            feature_set="levels",
        )

        self.assertEqual((task, horizon), ("classification", 1))
        self.assertEqual(len(new), len(old))

        shared = [column for column in old.columns if column in new.columns]
        self.assertIn(LABEL_COLUMN, shared)
        self.assertTrue(set(LEVEL_FEATURE_COLUMNS).issubset(shared))
        pd.testing.assert_frame_equal(new[shared], old[shared])


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
