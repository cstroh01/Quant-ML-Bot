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


if __name__ == "__main__":
    unittest.main()
