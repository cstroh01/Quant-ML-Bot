"""Tests for the execution and accounting layer."""

import unittest

import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
from backtest_harness import run_backtest, summarize_trades


def make_signalled_prices(rows: list[tuple]) -> pd.DataFrame:
    """Build a price frame from (day, open, close, buy, sell) tuples."""
    return pd.DataFrame(
        [
            {
                "Date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=day),
                "Open": open_price,
                "Close": close_price,
                "Buy_Next_Open": buy,
                "Sell_Next_Open": sell,
            }
            for day, open_price, close_price, buy, sell in rows
        ]
    )


class RunBacktestTests(unittest.TestCase):
    def test_round_trip_is_filled_at_the_open_on_both_sides(self):
        # Open and Close differ on every bar, so a fill taken from the wrong
        # column would change the P&L rather than pass unnoticed.
        prices = make_signalled_prices(
            [
                (0, 10.0, 99.0, False, False),
                (1, 20.0, 99.0, True, False),
                (2, 30.0, 99.0, False, False),
                (3, 50.0, 99.0, False, True),
            ]
        )

        trade_log = run_backtest(prices)

        self.assertEqual(len(trade_log), 1)
        trade = trade_log.iloc[0]
        self.assertEqual(trade["Entry Price"], 20.0)
        self.assertEqual(trade["Exit Price"], 50.0)
        self.assertEqual(trade["P&L"], 30.0)

    def test_open_position_is_marked_to_the_final_close(self):
        # An unclosed position is bookkeeping, not a prediction: it settles at
        # the last price we actually know, and it still counts as a trade.
        prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, True, False),
                (1, 12.0, 25.0, False, False),
            ]
        )

        trade_log = run_backtest(prices)

        self.assertEqual(len(trade_log), 1)
        self.assertEqual(trade_log.iloc[0]["Exit Price"], 25.0)

    def test_repeated_buy_signals_do_not_stack_a_position(self):
        # The harness models exactly one share. A second buy while already long
        # must be ignored, or the accounting silently becomes multi-share.
        prices = make_signalled_prices(
            [
                (0, 10.0, 10.0, True, False),
                (1, 20.0, 20.0, True, False),
                (2, 30.0, 30.0, True, False),
                (3, 40.0, 40.0, False, True),
            ]
        )

        trade_log = run_backtest(prices)

        self.assertEqual(len(trade_log), 1)
        self.assertEqual(trade_log.iloc[0]["Entry Price"], 10.0)

    def test_sell_while_flat_does_nothing(self):
        # Long-only means a sell signal with no position is not a short entry.
        prices = make_signalled_prices(
            [
                (0, 10.0, 10.0, False, True),
                (1, 20.0, 20.0, False, True),
            ]
        )

        self.assertTrue(run_backtest(prices).empty)

    def test_cumulative_pnl_accumulates_across_trades(self):
        prices = make_signalled_prices(
            [
                (0, 10.0, 10.0, True, False),
                (1, 15.0, 15.0, False, True),
                (2, 20.0, 20.0, True, False),
                (3, 18.0, 18.0, False, True),
            ]
        )

        trade_log = run_backtest(prices)

        self.assertEqual(list(trade_log["P&L"]), [5.0, -2.0])
        self.assertEqual(list(trade_log["Cumulative P&L"]), [5.0, 3.0])

    def test_empty_result_keeps_the_full_column_layout(self):
        # "No trades" is a normal outcome, so the empty frame has to be usable
        # by the same reporting code as a populated one.
        prices = make_signalled_prices([(0, 10.0, 10.0, False, False)])

        trade_log = run_backtest(prices)

        self.assertTrue(trade_log.empty)
        self.assertIn("Cumulative P&L", trade_log.columns)
        self.assertEqual(summarize_trades(trade_log)["total_pnl"], 0.0)

    def test_missing_signal_columns_fail_loudly(self):
        prices = pd.DataFrame({"Date": [pd.Timestamp("2024-01-01")], "Open": [1.0]})

        with self.assertRaises(ValueError):
            run_backtest(prices)


class CostTests(unittest.TestCase):
    """Cost math, which fails by printing a wrong number rather than raising."""

    def two_round_trips(self) -> pd.DataFrame:
        # Entries at 100 and 200, exits at 110 and 190: one winner, one loser,
        # with round numbers so the expected values can be worked out by hand.
        return make_signalled_prices(
            [
                (0, 100.0, 101.0, True, False),
                (1, 110.0, 111.0, False, True),
                (2, 200.0, 201.0, True, False),
                (3, 190.0, 191.0, False, True),
            ]
        )

    def test_defaults_reproduce_the_uncosted_arithmetic_exactly(self):
        # SC-001. The costed code path runs on every call, so this is what
        # pins that adding costs did not perturb the zero-cost numbers: the
        # multiplications are by exactly 1.0 and the subtraction by exactly
        # 0.0, which is an identity in floating point, not an approximation.
        trade_log = run_backtest(self.two_round_trips())

        self.assertEqual(list(trade_log["Entry Price"]), [100.0, 200.0])
        self.assertEqual(list(trade_log["Exit Price"]), [110.0, 190.0])
        self.assertEqual(list(trade_log["P&L"]), [10.0, -10.0])

    def test_hand_computed_costs_match_exactly(self):
        # SC-002, with the spec's own example values. Trade 1: buy 100 slipped
        # up to 100.05, sell 110 slipped down to 109.945, minus $1 on each of
        # the two fills -> 7.895. Trade 2: buy 200 -> 200.10, sell 190 ->
        # 189.905, minus $2 -> -12.195.
        trade_log = run_backtest(
            self.two_round_trips(), commission_per_trade=1.00, slippage_bps=5.0
        )

        self.assertAlmostEqual(trade_log.iloc[0]["Entry Price"], 100.05, places=10)
        self.assertAlmostEqual(trade_log.iloc[0]["Exit Price"], 109.945, places=10)
        self.assertAlmostEqual(trade_log.iloc[0]["P&L"], 7.895, places=10)
        self.assertAlmostEqual(trade_log.iloc[1]["Entry Price"], 200.10, places=10)
        self.assertAlmostEqual(trade_log.iloc[1]["Exit Price"], 189.905, places=10)
        self.assertAlmostEqual(trade_log.iloc[1]["P&L"], -12.195, places=10)
        self.assertAlmostEqual(trade_log.iloc[1]["Cumulative P&L"], -4.30, places=10)

    def test_commission_is_charged_once_per_fill_not_once_per_round_trip(self):
        # A round trip is two fills, so a $1 commission costs the trade $2.
        # Charging it once would understate every strategy's costs by half.
        costed = run_backtest(self.two_round_trips(), commission_per_trade=1.00)
        free = run_backtest(self.two_round_trips())

        difference = free["P&L"].to_numpy() - costed["P&L"].to_numpy()
        self.assertAlmostEqual(difference[0], 2.00, places=10)
        self.assertAlmostEqual(difference[1], 2.00, places=10)

    def test_slippage_worsens_both_sides_of_a_losing_trade_too(self):
        # The direction test that matters: on a loser, slippage must make the
        # loss bigger. Applying it with the trade instead of against it would
        # shrink the loss here while still enlarging it on the winner, so a
        # winner-only test would pass with the sign inverted.
        costed = run_backtest(self.two_round_trips(), slippage_bps=100.0)

        self.assertGreater(costed.iloc[0]["Entry Price"], 100.0)
        self.assertLess(costed.iloc[0]["Exit Price"], 110.0)
        self.assertGreater(costed.iloc[1]["Entry Price"], 200.0)
        self.assertLess(costed.iloc[1]["Exit Price"], 190.0)
        self.assertLess(costed.iloc[0]["P&L"], 10.0)
        self.assertLess(costed.iloc[1]["P&L"], -10.0)

    def test_enough_slippage_turns_a_winner_into_a_loser(self):
        # Expected behaviour, not a bug: a two-point edge on a 100-point stock
        # does not survive 200 bps of slippage. Exercised rather than assumed
        # because it is the whole reason Rule 3 exists.
        prices = make_signalled_prices(
            [
                (0, 100.0, 100.0, True, False),
                (1, 102.0, 102.0, False, True),
            ]
        )

        self.assertEqual(run_backtest(prices).iloc[0]["P&L"], 2.0)
        self.assertLess(run_backtest(prices, slippage_bps=200.0).iloc[0]["P&L"], 0.0)

    def test_costs_apply_to_the_end_of_data_close_exit(self):
        # The second exit path. Missing it would leave every still-open final
        # position costed on one side only.
        prices = make_signalled_prices(
            [
                (0, 100.0, 100.0, True, False),
                (1, 120.0, 200.0, False, False),
            ]
        )

        trade_log = run_backtest(
            prices, commission_per_trade=1.00, slippage_bps=100.0
        )

        self.assertAlmostEqual(trade_log.iloc[0]["Entry Price"], 101.0, places=10)
        self.assertAlmostEqual(trade_log.iloc[0]["Exit Price"], 198.0, places=10)
        self.assertAlmostEqual(trade_log.iloc[0]["P&L"], 95.0, places=10)

    def test_negative_costs_are_rejected(self):
        # A negative cost is a fill that improved, which is exactly what the
        # slippage model exists to forbid.
        with self.assertRaises(ValueError):
            run_backtest(self.two_round_trips(), commission_per_trade=-1.0)
        with self.assertRaises(ValueError):
            run_backtest(self.two_round_trips(), slippage_bps=-5.0)


class SummarizeTradesTests(unittest.TestCase):
    def test_summary_counts_wins_and_totals(self):
        trade_log = pd.DataFrame({"P&L": [5.0, -2.0, 3.0, -1.0]})

        summary = summarize_trades(trade_log)

        self.assertEqual(summary["total_trades"], 4)
        self.assertAlmostEqual(summary["total_pnl"], 5.0)
        self.assertAlmostEqual(summary["win_rate"], 50.0)

    def test_breakeven_trade_is_not_counted_as_a_win(self):
        summary = summarize_trades(pd.DataFrame({"P&L": [0.0, 1.0]}))

        self.assertAlmostEqual(summary["win_rate"], 50.0)

    def test_empty_log_reports_zeroes_rather_than_dividing_by_zero(self):
        summary = summarize_trades(pd.DataFrame({"P&L": []}))

        self.assertEqual(summary["total_trades"], 0)
        self.assertEqual(summary["win_rate"], 0.0)

    def test_summary_carries_the_cost_parameters_it_was_given(self):
        # A net P&L cannot be decomposed back into the costs that produced it,
        # so the summary has to carry them or the number becomes unreportable
        # the moment it leaves this function.
        summary = summarize_trades(
            pd.DataFrame({"P&L": [1.0]}),
            commission_per_trade=1.00,
            slippage_bps=5.0,
        )

        self.assertEqual(summary["commission_per_trade"], 1.00)
        self.assertEqual(summary["slippage_bps"], 5.0)

    def test_summary_reports_zero_costs_when_none_were_given(self):
        # Defaulting to 0.0 rather than omitting the keys means a caller that
        # prints them never has to branch on their absence.
        summary = summarize_trades(pd.DataFrame({"P&L": [1.0]}))

        self.assertEqual(summary["commission_per_trade"], 0.0)
        self.assertEqual(summary["slippage_bps"], 0.0)


if __name__ == "__main__":
    unittest.main()
