"""Tests for the reporting layer that puts a strategy beside its baselines.

`main()` downloads, so it is not what these tests call. The comparison itself
is pure — a price frame in, a report string out — and that is the part Rule 4
is about: the strategy and both baselines measured over the same bars with the
same costs.
"""

import unittest

import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
from backtest_harness import run_backtest, summarize_trades
from ma_crossover_backtest import (
    baseline_results,
    format_comparison,
    mean_holding_bars,
)
from signals import sma_crossover_signal

COSTS = {"commission_per_trade": 1.00, "slippage_bps": 5.0}


def make_prices(closes: list[float]) -> pd.DataFrame:
    """Build a minimal one-ticker price frame with Open offset from Close."""
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": [close + 1 for close in closes],
            "Close": closes,
        }
    )


def sawtooth_prices(n_bars: int = 200) -> pd.DataFrame:
    """A repeating rise-and-fall series, so the SMA rule actually crosses."""
    closes = [100.0 + (bar % 20) - (bar % 7) for bar in range(n_bars)]
    return sma_crossover_signal(make_prices(closes), 5, 15)


class MeanHoldingBarsTests(unittest.TestCase):
    def test_holding_period_is_counted_in_rows_not_calendar_days(self):
        # The fixture's dates are business days, so a 3-row hold spans 3
        # calendar days mid-week but 5 across a weekend. Counting rows is what
        # keeps the baseline's trip length comparable to the strategy's.
        prices = make_prices([float(bar) for bar in range(10)])
        prices["Buy_Next_Open"] = [False, True] + [False] * 8
        prices["Sell_Next_Open"] = [False] * 6 + [True] + [False] * 3

        self.assertEqual(mean_holding_bars(prices, run_backtest(prices)), 5)

    def test_an_empty_trade_log_does_not_divide_by_zero(self):
        prices = make_prices([1.0, 2.0, 3.0])

        self.assertEqual(mean_holding_bars(prices, pd.DataFrame({"P&L": []})), 1)


class BaselineResultsTests(unittest.TestCase):
    def test_both_baselines_report_the_costs_they_were_run_with(self):
        # Rule 4's "identical costs" clause, checked rather than assumed: a
        # baseline run cheaper than the strategy would flatter the strategy.
        prices = sawtooth_prices()

        results = baseline_results(prices, 4, 10, seed_count=20, **COSTS)

        summaries = [results["buy_and_hold"], *results["random_summaries"]]
        self.assertEqual(len(results["random_summaries"]), 20)
        for summary in summaries:
            self.assertEqual(summary["commission_per_trade"], 1.00)
            self.assertEqual(summary["slippage_bps"], 5.0)

    def test_the_random_baseline_matches_the_strategys_trade_count(self):
        results = baseline_results(sawtooth_prices(), 4, 10, seed_count=20, **COSTS)

        for summary in results["random_summaries"]:
            self.assertEqual(summary["total_trades"], 4)

    def test_seeds_produce_a_spread_rather_than_one_repeated_number(self):
        # If every seed returned the same P&L the "± dispersion" Rule 4 asks
        # for would be zero, and the baseline would be one draw wearing a
        # distribution's clothes.
        results = baseline_results(sawtooth_prices(), 4, 10, seed_count=20, **COSTS)

        pnls = {summary["total_pnl"] for summary in results["random_summaries"]}
        self.assertGreater(len(pnls), 1)

    def test_buy_and_hold_holds_exactly_one_position(self):
        results = baseline_results(sawtooth_prices(), 4, 10, seed_count=5, **COSTS)

        self.assertEqual(results["buy_and_hold"]["total_trades"], 1)

    def test_an_infeasible_random_baseline_is_reported_not_swallowed(self):
        # Too few bars for 4 trips of 10 bars each. The report must say so
        # rather than quietly compare against a shorter baseline.
        prices = sawtooth_prices(30)

        results = baseline_results(prices, 4, 10, seed_count=20, **COSTS)

        self.assertEqual(results["random_summaries"], [])
        self.assertIsNotNone(results["random_error"])


class FormatComparisonTests(unittest.TestCase):
    def report(self, prices: pd.DataFrame, seed_count: int = 20) -> str:
        trade_log = run_backtest(prices, **COSTS)
        summary = summarize_trades(trade_log, **COSTS)
        baselines = baseline_results(
            prices,
            n_trades=summary["total_trades"],
            holding_bars=mean_holding_bars(prices, trade_log),
            seed_count=seed_count,
            **COSTS,
        )
        return format_comparison(summary, baselines, seed_count=seed_count)

    def test_three_rows_are_reported_side_by_side(self):
        # SC-004: the strategy and both baselines, in one block.
        report = self.report(sawtooth_prices())

        self.assertIn("SMA crossover", report)
        self.assertIn("Buy and hold", report)
        self.assertIn("Random baseline (20 seeds)", report)

    def test_cost_parameters_are_stated_once_not_per_row(self):
        # Stated once above the table is what makes "identical costs"
        # structural rather than something the reader has to verify.
        report = self.report(sawtooth_prices())

        self.assertEqual(report.count("$1.00 per fill"), 1)
        self.assertEqual(report.count("5.0 bps"), 1)

    def test_the_random_row_reports_dispersion_beside_the_mean(self):
        report = self.report(sawtooth_prices())

        self.assertIn("±", report)
        self.assertIn("sample standard deviation", report)

    def test_a_strategy_with_no_trades_still_produces_a_report(self):
        # Flat prices never cross, so the strategy takes no trades. The
        # frequency-matched baseline for "traded zero times" is zero trades,
        # not an error — and buy-and-hold still has something to say.
        flat = sma_crossover_signal(make_prices([100.0] * 60), 5, 15)

        report = self.report(flat)

        self.assertIn("Buy and hold", report)
        self.assertIn("Random baseline (20 seeds)", report)
        self.assertIn("$0.00 ± $0.00", report)

    def test_an_infeasible_random_baseline_says_so_in_the_report(self):
        # The other zero-row case, and the one that must never be silent: the
        # baseline could not match the strategy's frequency at all.
        prices = sawtooth_prices(30)
        summary = summarize_trades(run_backtest(prices, **COSTS), **COSTS)
        baselines = baseline_results(prices, 4, 10, seed_count=20, **COSTS)

        report = format_comparison(summary, baselines, seed_count=20)

        self.assertIn("Random baseline not run", report)


if __name__ == "__main__":
    unittest.main()
