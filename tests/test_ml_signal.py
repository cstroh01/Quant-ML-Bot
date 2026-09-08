"""Tests for the cost-aware entry rule (spec 012).

The headline concerns, in the order the spec ranks them: the hurdle is the
real break-even and not its first-order approximation; the comparison happens
in log units against a log prediction; the comparison happens *before* the
shift; and the rule holds a position rather than re-paying a round-trip cost
every bar.
"""

import ast
import math
import unittest

import numpy as np
import pandas as pd

from context import SCRIPTS_DIR
from backtest_harness import run_backtest
from ml_signal import (
    cost_hurdle,
    log_hurdle,
    positions_from_direction,
    positions_from_predicted_return,
    signal_from_positions,
)

# The worked example from the spec's Background: a $250 share, a $1 commission
# per fill, 5 bps of slippage. Named once so a test that changes one of them
# has to say so.
PRICE = 250.0
COMMISSION = 1.0
SLIPPAGE_BPS = 5.0


def hand_hurdle(
    price: float = PRICE,
    commission: float = COMMISSION,
    slippage_bps: float = SLIPPAGE_BPS,
    shares: int = 1,
) -> float:
    """The break-even simple return, written out independently of the module.

    Deliberately not a call into `cost_hurdle`: a test that recomputes the
    formula by calling the code under test asserts only that the function is
    deterministic.
    """
    s = slippage_bps / 10_000.0
    return (2 * s + 2 * commission / (shares * price)) / (1 - s)


def constant_price(n: int, price: float = PRICE) -> pd.Series:
    return pd.Series([price] * n, dtype="float64")


class CostHurdleArithmeticTests(unittest.TestCase):
    """T006 — the hurdle at known prices and costs, divisor included."""

    def test_matches_the_hand_computed_break_even(self):
        hurdle = cost_hurdle(
            constant_price(3),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        )
        for value in hurdle:
            self.assertAlmostEqual(value, hand_hurdle(), places=15)

    def test_the_worked_example_is_about_ninety_basis_points(self):
        # The number the spec's Background states, and the reason the rule is
        # expected to decline nearly every trade: 90 bps against a daily sigma
        # of roughly 181 bps.
        hurdle = cost_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        ).iloc[0]
        self.assertAlmostEqual(hurdle * 10_000, 90.045, places=3)

    def test_the_divisor_is_not_dropped(self):
        # The first-order approximation the first draft used. It is close --
        # 90.000 bps against 90.045 -- which is exactly why only an explicit
        # assertion catches its return. SC-003's 1e-9 reconciliation is the
        # criterion the approximation cannot meet.
        s = SLIPPAGE_BPS / 10_000.0
        first_order = 2 * s + 2 * COMMISSION / PRICE
        hurdle = cost_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        ).iloc[0]
        self.assertNotAlmostEqual(hurdle, first_order, places=7)
        self.assertAlmostEqual(hurdle, first_order / (1 - s), places=15)

    def test_commission_dominates_slippage_at_a_two_hundred_fifty_dollar_share(self):
        # The 9:1 ratio the spec names as the root cause. Asserted because it
        # is the argument for the recorded position-sizing follow-up, not a
        # passing remark.
        commission_only = cost_hurdle(
            constant_price(1), commission_per_trade=COMMISSION, slippage_bps=0.0
        ).iloc[0]
        slippage_only = cost_hurdle(
            constant_price(1), commission_per_trade=0.0, slippage_bps=SLIPPAGE_BPS
        ).iloc[0]
        self.assertGreater(commission_only, 5 * slippage_only)

    def test_the_hurdle_varies_with_price_row_by_row(self):
        # Not a constant. A cheaper share carries a larger commission hurdle,
        # so a full-sample average price would misstate both ends.
        hurdle = cost_hurdle(
            pd.Series([100.0, 250.0, 500.0]),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        )
        self.assertGreater(hurdle.iloc[0], hurdle.iloc[1])
        self.assertGreater(hurdle.iloc[1], hurdle.iloc[2])

    def test_shares_divide_the_commission_term_only(self):
        one = cost_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
            shares=1,
        ).iloc[0]
        hundred = cost_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
            shares=100,
        ).iloc[0]
        self.assertAlmostEqual(hundred, hand_hurdle(shares=100), places=15)
        self.assertLess(hundred, one)

    def test_the_index_is_preserved(self):
        prices = pd.Series([100.0, 200.0], index=[7, 11])
        self.assertTrue(
            cost_hurdle(
                prices, commission_per_trade=COMMISSION, slippage_bps=SLIPPAGE_BPS
            ).index.equals(prices.index)
        )

    def test_non_positive_price_raises_rather_than_emitting_inf(self):
        # An inf hurdle blocks every trade and looks exactly like the finding
        # this spec expects to report, which is the worst possible failure
        # mode for it.
        for bad in (0.0, -1.0):
            with self.subTest(price=bad):
                with self.assertRaises(ValueError):
                    cost_hurdle(
                        pd.Series([PRICE, bad]),
                        commission_per_trade=COMMISSION,
                        slippage_bps=SLIPPAGE_BPS,
                    )

    def test_non_finite_price_raises(self):
        for bad in (np.nan, np.inf):
            with self.subTest(price=bad):
                with self.assertRaises(ValueError):
                    cost_hurdle(
                        pd.Series([PRICE, bad]),
                        commission_per_trade=COMMISSION,
                        slippage_bps=SLIPPAGE_BPS,
                    )

    def test_negative_costs_are_rejected_like_the_harness_rejects_them(self):
        with self.assertRaises(ValueError):
            cost_hurdle(
                constant_price(1), commission_per_trade=-1.0, slippage_bps=0.0
            )
        with self.assertRaises(ValueError):
            cost_hurdle(
                constant_price(1), commission_per_trade=0.0, slippage_bps=-1.0
            )

    def test_a_total_haircut_has_no_finite_break_even(self):
        with self.assertRaises(ValueError):
            cost_hurdle(
                constant_price(1),
                commission_per_trade=0.0,
                slippage_bps=10_000.0,
            )

    def test_shares_must_be_a_positive_int(self):
        with self.assertRaises(ValueError):
            cost_hurdle(
                constant_price(1),
                commission_per_trade=COMMISSION,
                slippage_bps=SLIPPAGE_BPS,
                shares=0,
            )
        with self.assertRaises(TypeError):
            cost_hurdle(
                constant_price(1),
                commission_per_trade=COMMISSION,
                slippage_bps=SLIPPAGE_BPS,
                shares=1.5,
            )


class LogHurdleTests(unittest.TestCase):
    """T002/T013's first half — the unit conversion itself."""

    def test_is_the_log_of_one_plus_the_simple_hurdle(self):
        simple = cost_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        ).iloc[0]
        log = log_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        ).iloc[0]
        self.assertAlmostEqual(log, math.log(1 + simple), places=15)

    def test_the_log_hurdle_is_strictly_the_smaller_of_the_two(self):
        # The direction matters: a rule that compared a log prediction against
        # the simple hurdle would be too strict, declining trades it should
        # take, which is a failure that hides inside the expected "declines
        # nearly everything" result.
        simple = cost_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        ).iloc[0]
        log = log_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        ).iloc[0]
        self.assertLess(log, simple)


class EntryBoundaryTests(unittest.TestCase):
    """T007 — the boundary is exclusive."""

    def setUp(self):
        self.hurdle = log_hurdle(
            constant_price(4),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        )

    def test_a_prediction_exactly_at_the_hurdle_does_not_enter(self):
        predictions = pd.Series([self.hurdle.iloc[0]] * 4)
        desired = positions_from_predicted_return(
            predictions, self.hurdle, exit_threshold=0.0
        )
        self.assertFalse(desired.any())

    def test_one_ulp_above_the_hurdle_does_enter(self):
        # Pinned at the smallest representable step, so the assertion is about
        # the comparison operator rather than about a margin someone chose.
        above = np.nextafter(self.hurdle.iloc[0], np.inf)
        predictions = pd.Series([above] * 4)
        desired = positions_from_predicted_return(
            predictions, self.hurdle, exit_threshold=0.0
        )
        self.assertTrue(desired.iloc[0])

    def test_one_ulp_below_the_hurdle_does_not_enter(self):
        below = np.nextafter(self.hurdle.iloc[0], -np.inf)
        predictions = pd.Series([below] * 4)
        desired = positions_from_predicted_return(
            predictions, self.hurdle, exit_threshold=0.0
        )
        self.assertFalse(desired.any())


class NullPredictionTests(unittest.TestCase):
    """T008 — null is flat, and is not `0.0`."""

    def test_a_null_prediction_is_flat(self):
        desired = positions_from_predicted_return(
            pd.Series([np.nan, np.nan, np.nan]), 0.0, exit_threshold=0.0
        )
        self.assertFalse(desired.any())

    def test_a_null_exits_an_open_position(self):
        # "The model has nothing to say" is not "hold". The pre-first-fold
        # window is null, and so is any gap the walk-forward loop leaves.
        desired = positions_from_predicted_return(
            pd.Series([0.5, 0.5, np.nan, 0.5, 0.0]),
            0.1,
            exit_threshold=0.0,
        )
        self.assertEqual(list(desired), [True, True, False, True, False])

    def test_zero_is_distinct_from_null(self):
        # The mutation SC-007 names: null treated as 0.0. Under a negative
        # exit threshold a 0.0 prediction holds the position, while a null
        # closes it -- so the two are only distinguishable here.
        held = positions_from_predicted_return(
            pd.Series([0.5, 0.0, 0.5, -1.0]), 0.1, exit_threshold=-0.1
        )
        closed = positions_from_predicted_return(
            pd.Series([0.5, np.nan, 0.5, -1.0]), 0.1, exit_threshold=-0.1
        )
        self.assertTrue(held.iloc[1])
        self.assertFalse(closed.iloc[1])


class ZeroCostLimitTests(unittest.TestCase):
    """T009 — at zero cost the rule degrades to 'any positive prediction'."""

    def test_the_hurdle_is_exactly_zero(self):
        # Exact equality, not almost-equal: this is what preserves the
        # harness's bit-for-bit uncosted property.
        simple = cost_hurdle(
            constant_price(3), commission_per_trade=0.0, slippage_bps=0.0
        )
        log = log_hurdle(
            constant_price(3), commission_per_trade=0.0, slippage_bps=0.0
        )
        self.assertTrue((simple.to_numpy() == 0.0).all())
        self.assertTrue((log.to_numpy() == 0.0).all())

    def test_the_mask_matches_strictly_positive(self):
        predictions = pd.Series([-1e-12, 0.0, 1e-12, 5.0, -5.0, 0.0])
        hurdle = log_hurdle(
            constant_price(len(predictions)),
            commission_per_trade=0.0,
            slippage_bps=0.0,
        )
        desired = positions_from_predicted_return(
            predictions, hurdle, exit_threshold=0.0
        )
        # Hysteresis and "strictly positive" agree here because the entry
        # hurdle and the exit threshold coincide at 0.0.
        self.assertEqual(list(desired), list(predictions > 0))


class PointInTimeTests(unittest.TestCase):
    """T010 — Rule 1: the hurdle at t cannot see t+1."""

    def test_perturbing_a_future_close_leaves_the_hurdle_bit_identical(self):
        closes = pd.Series([100.0, 150.0, 200.0, 250.0, 300.0])
        base = cost_hurdle(
            closes, commission_per_trade=COMMISSION, slippage_bps=SLIPPAGE_BPS
        )
        for t in range(len(closes) - 1):
            with self.subTest(t=t):
                perturbed_closes = closes.copy()
                perturbed_closes.iloc[t + 1 :] *= 3.7
                perturbed = cost_hurdle(
                    perturbed_closes,
                    commission_per_trade=COMMISSION,
                    slippage_bps=SLIPPAGE_BPS,
                )
                # Bit-identical, not almost-equal. A leak through a rolling or
                # aggregate step would move the low bits and pass an
                # almost-equal check.
                self.assertEqual(
                    base.to_numpy()[: t + 1].tobytes(),
                    perturbed.to_numpy()[: t + 1].tobytes(),
                )

    def test_the_control_half_the_perturbation_actually_changes_something(self):
        # Without this the test above would pass on a function that ignored
        # its argument entirely.
        closes = pd.Series([100.0, 150.0, 200.0])
        perturbed = closes.copy()
        perturbed.iloc[1:] *= 3.7
        base = cost_hurdle(
            closes, commission_per_trade=COMMISSION, slippage_bps=SLIPPAGE_BPS
        )
        moved = cost_hurdle(
            perturbed, commission_per_trade=COMMISSION, slippage_bps=SLIPPAGE_BPS
        )
        self.assertNotEqual(base.iloc[1], moved.iloc[1])


class HysteresisTests(unittest.TestCase):
    """T011 — one round trip, not two."""

    def setUp(self):
        self.h = log_hurdle(
            constant_price(1),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        ).iloc[0]

    def _desired(self, multipliers):
        predictions = pd.Series([m * self.h for m in multipliers])
        hurdle = log_hurdle(
            constant_price(len(predictions)),
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        )
        return positions_from_predicted_return(
            predictions, hurdle, exit_threshold=0.0
        )

    def test_the_spec_sequence_gives_exactly_one_entry_and_one_exit(self):
        # SC-004, verbatim: [+2h, +0.5h, +0.5h, -h].
        desired = self._desired([2.0, 0.5, 0.5, -1.0])
        self.assertEqual(list(desired), [True, True, True, False])

        enters = desired & ~desired.shift(1, fill_value=False)
        exits = ~desired & desired.shift(1, fill_value=False)
        self.assertEqual(int(enters.sum()), 1)
        self.assertEqual(int(exits.sum()), 1)

    def test_a_per_bar_gate_would_have_produced_two_round_trips(self):
        # The control that gives the test above its meaning. Under the
        # mutation SC-007 names -- re-test the round-trip hurdle every bar --
        # rows 1 and 2 fall below h and the rule churns.
        desired = self._desired([2.0, 0.5, 0.5, -1.0])
        per_bar_gate = pd.Series([2.0, 0.5, 0.5, -1.0]) > 1.0
        self.assertNotEqual(list(desired), list(per_bar_gate))
        self.assertTrue(desired.iloc[1] and desired.iloc[2])

    def test_the_shifted_signals_carry_one_buy_and_one_sell(self):
        # Padded so the exit's shifted sell lands on a real row rather than
        # falling off the end.
        desired = self._desired([2.0, 0.5, 0.5, -1.0, -1.0, -1.0])
        buy, sell = signal_from_positions(desired)
        self.assertEqual(int(buy.sum()), 1)
        self.assertEqual(int(sell.sum()), 1)
        self.assertEqual(buy.to_numpy().nonzero()[0].tolist(), [1])
        self.assertEqual(sell.to_numpy().nonzero()[0].tolist(), [4])

    def test_the_exit_threshold_is_looser_than_the_entry_hurdle(self):
        # A prediction between the exit threshold and the entry hurdle holds a
        # position but would not open one.
        desired = self._desired([0.5, 2.0, 0.5, -1.0])
        self.assertFalse(desired.iloc[0])
        self.assertTrue(desired.iloc[1])
        self.assertTrue(desired.iloc[2])

    def test_a_still_long_final_bar_is_forced_flat(self):
        desired = self._desired([2.0, 2.0, 2.0, 2.0])
        self.assertFalse(desired.iloc[-1])

    def test_an_empty_series_is_an_empty_mask(self):
        desired = positions_from_predicted_return(
            pd.Series([], dtype="float64"), 0.0, exit_threshold=0.0
        )
        self.assertEqual(len(desired), 0)

    def test_a_misaligned_hurdle_index_raises(self):
        predictions = pd.Series([0.5, 0.5], index=[0, 1])
        hurdle = pd.Series([0.1, 0.1], index=[5, 6])
        with self.assertRaises(ValueError):
            positions_from_predicted_return(predictions, hurdle, exit_threshold=0.0)


class OrderingTests(unittest.TestCase):
    """FR-007 — compare on row t, then shift. Never the other way round."""

    def test_the_decision_pairs_each_prediction_with_its_own_rows_hurdle(self):
        # Prices chosen so the hurdle moves enough between rows to flip the
        # answer if the two series were offset by one: at a $1 commission a
        # $1000 share's hurdle is ~20 bps and a $20 share's is ~1000 bps, and
        # the prediction sits between them. The alternating -1.0 forces the
        # position flat before each entry decision, so every row is judged
        # from the same state and hysteresis cannot mask the offset.
        closes = pd.Series([1000.0, 20.0, 1000.0, 20.0, 1000.0])
        hurdle = log_hurdle(
            closes, commission_per_trade=COMMISSION, slippage_bps=0.0
        )
        predictions = pd.Series([0.01, -1.0, 0.01, -1.0, 0.01])
        desired = positions_from_predicted_return(
            predictions, hurdle, exit_threshold=0.0
        )
        self.assertEqual(list(desired), [True, False, True, False, False])

        # The mutation SC-007 names -- the shift applied before the
        # comparison -- pairs row t's decision with row t-1's price. It must
        # be observable here, or the assertion above proves nothing.
        shifted_hurdle = hurdle.shift(1)
        shifted_hurdle.iloc[0] = hurdle.iloc[0]
        offset = positions_from_predicted_return(
            predictions, shifted_hurdle, exit_threshold=0.0
        )
        self.assertNotEqual(list(desired), list(offset))

    def test_a_signal_never_fires_on_the_bar_that_decided_it(self):
        desired = pd.Series([False, True, True, False, False])
        buy, sell = signal_from_positions(desired)
        # Row 1 is where the position is first desired; the buy must land on
        # row 2, filled at row 2's open.
        self.assertFalse(bool(buy.iloc[1]))
        self.assertTrue(bool(buy.iloc[2]))
        self.assertTrue(bool(sell.iloc[4]))


class HarnessReconciliationTests(unittest.TestCase):
    """T012 — a pair of opens at exactly g* nets zero through the real harness."""

    def _round_trip_pnl(self, commission: float, slippage_bps: float) -> float:
        g_star = cost_hurdle(
            constant_price(1),
            commission_per_trade=commission,
            slippage_bps=slippage_bps,
        ).iloc[0]
        opens = [PRICE, PRICE, PRICE * (1 + g_star), PRICE * (1 + g_star)]
        prices = pd.DataFrame(
            {
                "Date": pd.date_range("2024-01-01", periods=4, freq="B"),
                "Open": opens,
                "Close": opens,
                "Buy_Next_Open": [False, True, False, False],
                "Sell_Next_Open": [False, False, True, False],
            }
        )
        trade_log = run_backtest(
            prices,
            commission_per_trade=commission,
            slippage_bps=slippage_bps,
        )
        self.assertEqual(len(trade_log), 1)
        return float(trade_log["P&L"].iloc[0])

    def test_break_even_reconciles_within_floating_point_tolerance(self):
        # SC-003 / FR-008. This is the criterion the first-order hurdle could
        # not meet, and the reason the 1/(1-s) divisor is in the formula.
        self.assertLess(
            abs(self._round_trip_pnl(COMMISSION, SLIPPAGE_BPS)), 1e-9
        )

    def test_it_reconciles_across_several_cost_settings(self):
        for commission, slippage in [
            (0.0, 0.0),
            (0.0, 25.0),
            (1.0, 0.0),
            (0.65, 5.0),
            (5.0, 50.0),
        ]:
            with self.subTest(commission=commission, slippage=slippage):
                self.assertLess(abs(self._round_trip_pnl(commission, slippage)), 1e-9)

    def test_the_first_order_hurdle_would_not_have_reconciled(self):
        # The control. Without it, "within 1e-9" reads as a loose bar rather
        # than one the dropped divisor actually fails.
        s = SLIPPAGE_BPS / 10_000.0
        approximate = 2 * s + 2 * COMMISSION / PRICE
        opens = [PRICE, PRICE, PRICE * (1 + approximate), PRICE * (1 + approximate)]
        prices = pd.DataFrame(
            {
                "Date": pd.date_range("2024-01-01", periods=4, freq="B"),
                "Open": opens,
                "Close": opens,
                "Buy_Next_Open": [False, True, False, False],
                "Sell_Next_Open": [False, False, True, False],
            }
        )
        trade_log = run_backtest(
            prices, commission_per_trade=COMMISSION, slippage_bps=SLIPPAGE_BPS
        )
        self.assertGreater(abs(float(trade_log["P&L"].iloc[0])), 1e-9)


class LogVersusSimpleHurdleTests(unittest.TestCase):
    """T013 — the test that catches the unit error directly.

    Because `ln(1+g*) < g*`, a log-return prediction strictly between the two
    is the discriminating case: the correct comparison takes the trade, and a
    comparison against the simple hurdle declines it. The task list words this
    as "correctly declined", which reads the inequality the other way round;
    the assertion below follows the arithmetic and the spec's FR-002, and the
    discrepancy is flagged rather than silently reinterpreted.
    """

    def setUp(self):
        self.prices = constant_price(3)
        self.simple = cost_hurdle(
            self.prices,
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        )
        self.log = log_hurdle(
            self.prices,
            commission_per_trade=COMMISSION,
            slippage_bps=SLIPPAGE_BPS,
        )

    def test_a_prediction_in_the_band_is_taken_and_not_declined(self):
        midpoint = (self.log.iloc[0] + self.simple.iloc[0]) / 2
        self.assertLess(self.log.iloc[0], midpoint)
        self.assertLess(midpoint, self.simple.iloc[0])

        predictions = pd.Series([midpoint] * 3)
        taken = positions_from_predicted_return(
            predictions, self.log, exit_threshold=0.0
        )
        declined = positions_from_predicted_return(
            predictions, self.simple, exit_threshold=0.0
        )
        self.assertTrue(taken.iloc[0])
        self.assertFalse(declined.any())

    def test_a_prediction_below_the_log_hurdle_is_declined(self):
        below = np.nextafter(self.log.iloc[0], -np.inf)
        desired = positions_from_predicted_return(
            pd.Series([below] * 3), self.log, exit_threshold=0.0
        )
        self.assertFalse(desired.any())


class DirectionPathTests(unittest.TestCase):
    """FR-004 — the classification counterpart reaches the same shift."""

    def test_long_on_one_flat_on_zero_flat_on_null(self):
        predictions = pd.Series([1, 0, pd.NA, 1], dtype="Int64")
        desired = positions_from_direction(predictions)
        self.assertEqual(list(desired), [True, False, False, True])
        self.assertEqual(desired.dtype, np.dtype("bool"))

    def test_both_paths_produce_the_same_kind_of_mask(self):
        from_direction = positions_from_direction(
            pd.Series([1, 1, 0, 0], dtype="Int64")
        )
        from_return = positions_from_predicted_return(
            pd.Series([1.0, 1.0, -1.0, -1.0]), 0.5, exit_threshold=0.0
        )
        self.assertEqual(from_direction.dtype, from_return.dtype)
        self.assertEqual(
            list(signal_from_positions(from_direction)[0]),
            list(signal_from_positions(from_return)[0]),
        )


class ShiftDisciplineIsACopyTests(unittest.TestCase):
    """FR-005 — the copy is pinned to the original it was copied from.

    `logistic_baseline._signal_from_predictions` is imported *here*, in a
    test, which is the whole point: the test may depend on the high-level ML
    script, and `ml_signal.py` may not.
    """

    def test_it_matches_logistic_baselines_own_shift_logic(self):
        from logistic_baseline import _signal_from_predictions

        for raw in (
            [1, 0, 1, 1, 0, 0, 1],
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [1, pd.NA, 1, 0, pd.NA],
        ):
            with self.subTest(raw=raw):
                predictions = pd.Series(raw, dtype="Int64")
                original_buy, original_sell = _signal_from_predictions(predictions)
                copied_buy, copied_sell = signal_from_positions(
                    positions_from_direction(predictions)
                )
                pd.testing.assert_series_equal(
                    original_buy, copied_buy, check_names=False
                )
                pd.testing.assert_series_equal(
                    original_sell, copied_sell, check_names=False
                )


class ModuleBoundaryTests(unittest.TestCase):
    """T014 — Rule 8 and FR-012, asserted by AST rather than by a source grep.

    A substring search trips on this module's own docstring, which names
    `backtest_harness` and `estimators` precisely in order to say it does not
    import them -- the opposite of the property under test.
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

    def test_ml_signal_imports_only_numpy_and_pandas(self):
        self.assertEqual(
            self._imported_modules("ml_signal.py"),
            {"__future__", "numpy", "pandas"},
        )

    def test_ml_signal_imports_no_forbidden_project_module(self):
        # `backtest_harness` and `logistic_baseline` are FR-009; `estimators`
        # is FR-012, the estimator-agnostic requirement -- this module needs
        # the predictions, not the registry.
        forbidden = {
            "backtest_harness",
            "logistic_baseline",
            "estimators",
            "model_cv",
            "ma_crossover_backtest",
            "sklearn",
        }
        self.assertEqual(
            self._imported_modules("ml_signal.py") & forbidden, set()
        )


def _synthetic_frame(periods: int = 500, seed: int = 42) -> pd.DataFrame:
    """A small, deterministic frame the whole registry can be fit on.

    No network, no cache: the point of the sweep below is the code path, not
    the predictive content, so a random walk with two features is enough and
    keeps the test suite offline (Rule 5).
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=periods, freq="B")
    steps = rng.normal(0.0, 0.01, size=periods)
    close = 100.0 * np.exp(np.cumsum(steps))
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Close": close,
            "Feature_A": pd.Series(steps).rolling(5).mean().to_numpy(),
            "Feature_B": pd.Series(steps).rolling(10).std().to_numpy(),
        }
    )
    return frame.dropna().reset_index(drop=True)


class EstimatorAgnosticTests(unittest.TestCase):
    """SC-008 / FR-012 — every registry entry reaches the harness this way.

    Parameterized over `ESTIMATOR_REGISTRY` itself rather than over a list of
    names, so a new entry is covered by registering it and nothing else. This
    is the requirement recorded in the spec's *Scope decision* on 2026-09-08:
    `hgb` did not clear spec 014's screening bar on AAPL alone, and scoping
    the entry rule to the two entries that did would only mean rebuilding it
    when spec 013's multi-ticker run reports.

    The registry is imported here, in the test. `ml_signal.py` must not import
    it, which is `ModuleBoundaryTests`' job.
    """

    @classmethod
    def setUpClass(cls):
        cls.frame = _synthetic_frame()

    def _predictions(self, name: str, task: str) -> pd.Series:
        from estimators import CLASSIFICATION, fit_predict_walk_forward
        from targets import direction_label, forward_log_return_label

        if task == CLASSIFICATION:
            label = direction_label(self.frame, horizon=1)
        else:
            label = forward_log_return_label(self.frame, horizon=1)
        frame = self.frame.assign(Label=label).dropna(subset=["Label"])
        frame = frame.reset_index(drop=True)
        return fit_predict_walk_forward(
            frame,
            feature_columns=["Feature_A", "Feature_B"],
            label_column="Label",
            task=task,
            name=name,
            label_horizon=1,
            embargo_bars=1,
            random_state=42,
            initial_train_months=6,
            test_months=3,
        )

    def test_every_registry_entry_produces_a_signal_through_one_path(self):
        from estimators import CLASSIFICATION, ESTIMATOR_REGISTRY

        for name, task in sorted(ESTIMATOR_REGISTRY):
            with self.subTest(name=name, task=task):
                predictions = self._predictions(name, task)
                if task == CLASSIFICATION:
                    desired = positions_from_direction(predictions)
                else:
                    hurdle = log_hurdle(
                        pd.Series(
                            np.full(len(predictions), PRICE),
                            index=predictions.index,
                        ),
                        commission_per_trade=COMMISSION,
                        slippage_bps=SLIPPAGE_BPS,
                    )
                    desired = positions_from_predicted_return(
                        predictions, hurdle, exit_threshold=0.0
                    )

                buy, sell = signal_from_positions(desired)
                self.assertEqual(len(buy), len(predictions))
                self.assertEqual(buy.dtype, np.dtype("bool"))
                self.assertEqual(sell.dtype, np.dtype("bool"))
                # No entry-specific branch exists to test directly, so the
                # assertion is that the invariant every entry must satisfy
                # holds for every entry: a sell only ever follows a buy.
                open_position = False
                for is_buy, is_sell in zip(buy, sell):
                    if is_sell:
                        self.assertTrue(open_position)
                        open_position = False
                    if is_buy:
                        open_position = True

    def test_the_registry_sweep_covers_more_than_one_entry(self):
        # Guards against a registry import that silently returns nothing,
        # which would make the sweep above vacuously green.
        from estimators import ESTIMATOR_REGISTRY

        self.assertGreater(len(ESTIMATOR_REGISTRY), 1)


if __name__ == "__main__":
    unittest.main()
