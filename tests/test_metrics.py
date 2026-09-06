"""Tests for scripts/metrics.py (spec 008: reporting from a trade log).

Every test here drives the **real** `run_backtest` rather than a hand-built
trade log wherever a trade log is needed. That is deliberate: the module's
whole correctness claim is that its per-bar attribution telescopes to the
harness's own P&L expression, and a hand-written log could drift from what
the harness actually produces without any test noticing.
"""

import math
import unittest

import numpy as np
import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
from backtest_harness import run_backtest
from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
from metrics import (
    equity_curve,
    equity_log_returns,
    max_drawdown,
    performance_summary,
    sharpe_ratio,
)
from test_backtest_harness import make_signalled_prices
from test_ma_crossover_backtest import COSTS, sawtooth_prices


class TestReconciliation(unittest.TestCase):
    """SC-001 — the load-bearing invariant.

    The four-part attribution (entry bar, held bars, exit bar, flat bars)
    telescopes to `X - E - 2c`, which is `run_backtest`'s own `P&L`
    expression term for term. If the sums agree, the derivation cannot
    contain an off-by-one; if it contains one, the sums cannot agree.
    """

    def test_bar_pnl_sums_to_trade_log_pnl(self):
        prices = sawtooth_prices(200)
        trade_log = run_backtest(prices, **COSTS)
        self.assertGreater(len(trade_log), 1, "fixture should produce real trades")

        curve = equity_curve(prices, trade_log, **COSTS)

        self.assertAlmostEqual(
            float(curve["Bar P&L"].sum()),
            float(trade_log["P&L"].sum()),
            places=9,
        )

    def test_reconciliation_holds_without_costs_too(self):
        prices = sawtooth_prices(200)
        trade_log = run_backtest(prices)
        curve = equity_curve(prices, trade_log, commission_per_trade=0.0, slippage_bps=0.0)

        self.assertAlmostEqual(
            float(curve["Bar P&L"].sum()),
            float(trade_log["P&L"].sum()),
            places=9,
        )

    def test_curve_has_one_row_per_bar(self):
        prices = sawtooth_prices(200)
        trade_log = run_backtest(prices, **COSTS)
        curve = equity_curve(prices, trade_log, **COSTS)

        self.assertEqual(len(curve), len(prices))
        pd.testing.assert_series_equal(
            curve["Date"], prices["Date"], check_names=False
        )


class TestAttributionOffByOne(unittest.TestCase):
    """SC-002 — where the P&L actually lands, bar by bar."""

    def test_one_bar_hold_puts_pnl_on_exactly_two_bars(self):
        # Buy fires on bar 1 (fill at bar 1's open), sell on bar 2 (fill at
        # bar 2's open). Opens and closes differ on every bar so a fill taken
        # from the wrong column changes the answer rather than passing.
        prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 22.0, True, False),
                (2, 30.0, 33.0, False, True),
                (3, 40.0, 44.0, False, False),
            ]
        )
        trade_log = run_backtest(prices)
        curve = equity_curve(prices, trade_log, commission_per_trade=0.0, slippage_bps=0.0)

        bar_pnl = curve["Bar P&L"].to_numpy()
        # Entry bar: Close[1] - Open[1] = 22 - 20.
        self.assertAlmostEqual(bar_pnl[1], 2.0)
        # Exit bar: Open[2] - Close[1] = 30 - 22.
        self.assertAlmostEqual(bar_pnl[2], 8.0)
        # Nothing anywhere else.
        self.assertAlmostEqual(bar_pnl[0], 0.0)
        self.assertAlmostEqual(bar_pnl[3], 0.0)
        # And it still telescopes: 30 - 20 = 10.
        self.assertAlmostEqual(bar_pnl.sum(), 10.0)

    def test_position_is_one_from_entry_up_to_but_not_including_exit(self):
        prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 22.0, True, False),
                (2, 30.0, 33.0, False, False),
                (3, 40.0, 44.0, False, True),
                (4, 50.0, 55.0, False, False),
            ]
        )
        trade_log = run_backtest(prices)
        curve = equity_curve(prices, trade_log, commission_per_trade=0.0, slippage_bps=0.0)

        # Shares held at each bar's close: on at bars 1 and 2, off at bar 3
        # because the position was sold at bar 3's open.
        np.testing.assert_array_equal(
            curve["Position"].to_numpy(), np.array([0, 1, 1, 0, 0])
        )

    def test_commission_is_charged_on_the_entry_and_exit_bars(self):
        prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 22.0, True, False),
                (2, 30.0, 33.0, False, True),
            ]
        )
        trade_log = run_backtest(prices, commission_per_trade=1.0, slippage_bps=0.0)
        curve = equity_curve(
            prices, trade_log, commission_per_trade=1.0, slippage_bps=0.0
        )

        bar_pnl = curve["Bar P&L"].to_numpy()
        self.assertAlmostEqual(bar_pnl[1], 2.0 - 1.0)
        self.assertAlmostEqual(bar_pnl[2], 8.0 - 1.0)


class TestBoundaries(unittest.TestCase):
    """SC-002/SC-005 — first bar, last bar, and the same-bar round trip."""

    def test_entry_on_bar_zero(self):
        prices = make_signalled_prices(
            [
                (0, 10.0, 12.0, True, False),
                (1, 20.0, 22.0, False, True),
            ]
        )
        trade_log = run_backtest(prices)
        curve = equity_curve(prices, trade_log, commission_per_trade=0.0, slippage_bps=0.0)

        self.assertAlmostEqual(curve["Bar P&L"].iloc[0], 2.0)   # 12 - 10
        self.assertAlmostEqual(curve["Bar P&L"].iloc[1], 8.0)   # 20 - 12
        self.assertAlmostEqual(curve["Bar P&L"].sum(), 10.0)

    def test_position_still_open_on_the_final_bar_marks_to_its_close(self):
        # The harness closes any open position at the final Close, so the
        # exit bar's recorded price is a close, not an open. The attribution
        # uses the log's recorded price and so does not care which it was.
        prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 22.0, True, False),
                (2, 30.0, 33.0, False, False),
            ]
        )
        trade_log = run_backtest(prices)
        self.assertEqual(len(trade_log), 1)
        curve = equity_curve(prices, trade_log, commission_per_trade=0.0, slippage_bps=0.0)

        self.assertAlmostEqual(curve["Bar P&L"].iloc[1], 2.0)    # 22 - 20
        self.assertAlmostEqual(curve["Bar P&L"].iloc[2], 11.0)   # 33 - 22
        self.assertAlmostEqual(
            curve["Bar P&L"].sum(), float(trade_log["P&L"].sum())
        )

    def test_same_bar_round_trip(self):
        # Buy_Next_Open on the final row: the harness enters at that bar's
        # open and its end-of-data block exits at that same bar's close, so
        # entry and exit land on one bar.
        prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 26.0, True, False),
            ]
        )
        trade_log = run_backtest(prices, commission_per_trade=1.0, slippage_bps=0.0)
        self.assertEqual(len(trade_log), 1)
        self.assertEqual(
            trade_log.iloc[0]["Entry Date"], trade_log.iloc[0]["Exit Date"]
        )

        curve = equity_curve(
            prices, trade_log, commission_per_trade=1.0, slippage_bps=0.0
        )
        # 26 - 20 - 2*1, all on bar 1.
        self.assertAlmostEqual(curve["Bar P&L"].iloc[1], 4.0)
        self.assertAlmostEqual(curve["Bar P&L"].iloc[0], 0.0)
        self.assertAlmostEqual(
            curve["Bar P&L"].sum(), float(trade_log["P&L"].sum())
        )

    def test_equity_is_anchored_so_a_bar_zero_drawdown_is_captured(self):
        """SC-005 — a decline beginning on the very first bar must show up.

        The curve is anchored at the capital base *before* bar 0's P&L is
        added. Anchoring at bar 0's equity instead would make bar 0 its own
        high-water mark and silently hide the first bar's loss.
        """
        prices = make_signalled_prices(
            [
                (0, 100.0, 90.0, True, False),
                (1, 80.0, 80.0, False, True),
            ]
        )
        trade_log = run_backtest(prices)
        curve = equity_curve(
            prices,
            trade_log,
            commission_per_trade=0.0,
            slippage_bps=0.0,
            starting_capital=100.0,
        )

        # Bar 0 loses 10 immediately (bought at 100, closed at 90).
        self.assertAlmostEqual(curve["Equity"].iloc[0], 90.0)
        worst, peak_pos, trough_pos = max_drawdown(curve["Equity"])
        self.assertLess(worst, 0.0)
        self.assertEqual(peak_pos, 0)
        self.assertGreater(trough_pos, 0)


class TestEmptyTradeLog(unittest.TestCase):
    """SC-004 — no trades is an expected outcome, not an error.

    Phase 3's cost-aware entry rule is expected to decline nearly every
    trade, so this is the path the phase's headline result travels through.
    """

    def setUp(self):
        self.prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 22.0, False, False),
                (2, 30.0, 33.0, False, False),
            ]
        )
        self.trade_log = run_backtest(self.prices, **COSTS)
        self.assertTrue(self.trade_log.empty)

    def test_curve_is_flat_at_the_capital_base(self):
        curve = equity_curve(self.prices, self.trade_log, **COSTS)

        self.assertEqual(len(curve), 3)
        self.assertTrue((curve["Bar P&L"] == 0.0).all())
        self.assertTrue((curve["Equity"] == 11.0).all())  # first bar's Close
        self.assertTrue((curve["Position"] == 0).all())

    def test_sharpe_is_nan_not_zero(self):
        curve = equity_curve(self.prices, self.trade_log, **COSTS)
        result = sharpe_ratio(equity_log_returns(curve["Equity"]))

        self.assertTrue(math.isnan(result))
        self.assertNotEqual(result, 0.0)

    def test_drawdown_is_a_genuine_zero(self):
        curve = equity_curve(self.prices, self.trade_log, **COSTS)
        worst, _, _ = max_drawdown(curve["Equity"])

        self.assertEqual(worst, 0.0)

    def test_performance_summary_has_every_key(self):
        summary = performance_summary(self.prices, self.trade_log, **COSTS)

        expected = {
            "total_trades",
            "total_pnl",
            "total_return",
            "sharpe_ratio",
            "max_drawdown",
            "drawdown_peak_bar",
            "drawdown_trough_bar",
            "bars",
            "bars_in_market",
            "capital_base",
            "commission_per_trade",
            "slippage_bps",
        }
        self.assertEqual(set(summary), expected)
        self.assertEqual(summary["total_trades"], 0)
        self.assertEqual(summary["total_pnl"], 0.0)
        self.assertTrue(math.isnan(summary["sharpe_ratio"]))
        # Printable without branching on the empty case.
        self.assertIsInstance(f"{summary['sharpe_ratio']:.2f}", str)


class TestSharpeConventions(unittest.TestCase):
    """SC-003 and the annualization contract."""

    def test_costs_reach_the_metric(self):
        """SC-003 — Rule 3's whole point: a costed run must not report the
        same risk-adjusted number as an uncosted one."""
        prices = sawtooth_prices(200)

        costed = performance_summary(prices, run_backtest(prices, **COSTS), **COSTS)
        free = performance_summary(
            prices,
            run_backtest(prices),
            commission_per_trade=0.0,
            slippage_bps=0.0,
        )

        self.assertNotAlmostEqual(costed["sharpe_ratio"], free["sharpe_ratio"])
        self.assertLess(costed["total_pnl"], free["total_pnl"])

    def test_matches_return_stats_annualization_arithmetic(self):
        """The Sharpe here must be the same formula `return_stats.annualize`
        and `return_stats.main` use, or two Sharpe ratios in this repository
        would not be comparable."""
        returns = pd.Series([0.01, -0.005, 0.02, 0.0, -0.01, 0.015])

        annualized_return = returns.mean() * TRADING_DAYS_PER_YEAR
        annualized_volatility = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        expected = (annualized_return - RISK_FREE_RATE_ANNUAL) / annualized_volatility

        self.assertAlmostEqual(sharpe_ratio(returns), float(expected), places=12)

    def test_undefined_cases_are_nan_never_inf_or_zero(self):
        # Fewer than two observations.
        self.assertTrue(math.isnan(sharpe_ratio(pd.Series([0.01]))))
        self.assertTrue(math.isnan(sharpe_ratio(pd.Series([], dtype=float))))
        # Zero variance with a non-zero mean would be inf, not a huge Sharpe.
        result = sharpe_ratio(pd.Series([0.01, 0.01, 0.01]))
        self.assertTrue(math.isnan(result))
        self.assertFalse(math.isinf(result))

    def test_equity_reaching_zero_yields_nan_not_negative_infinity(self):
        equity = pd.Series([100.0, 50.0, 0.0, 10.0])
        returns = equity_log_returns(equity)

        self.assertTrue(returns.isna().any())
        self.assertFalse(np.isinf(returns.to_numpy()).any())
        self.assertTrue(math.isnan(sharpe_ratio(returns)))


class TestMaxDrawdown(unittest.TestCase):
    def test_peak_is_the_last_high_water_mark_strictly_before_the_trough(self):
        # Two separate declines; the deeper one is the second.
        equity = pd.Series([100.0, 95.0, 120.0, 118.0, 60.0, 80.0])
        worst, peak_pos, trough_pos = max_drawdown(equity)

        self.assertEqual(trough_pos, 4)
        self.assertEqual(peak_pos, 2)  # the 120, not the opening 100
        self.assertAlmostEqual(worst, 60.0 / 120.0 - 1.0)

    def test_a_monotonically_rising_curve_has_no_drawdown(self):
        worst, peak_pos, trough_pos = max_drawdown(pd.Series([1.0, 2.0, 3.0]))

        self.assertEqual(worst, 0.0)
        self.assertEqual((peak_pos, trough_pos), (0, 0))


class TestValidation(unittest.TestCase):
    """SC-006 — the guards that stop a silently wrong curve.

    `.loc` against a duplicated label returns every match rather than
    raising, which would produce a longer array than the trade log and a
    wrong curve with no error anywhere.
    """

    def setUp(self):
        self.prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 22.0, True, False),
                (2, 30.0, 33.0, False, True),
            ]
        )
        self.trade_log = run_backtest(self.prices, **COSTS)

    def _expect_value_error(self, prices, trade_log=None):
        with self.assertRaises(ValueError):
            equity_curve(
                prices,
                self.trade_log if trade_log is None else trade_log,
                **COSTS,
            )

    def test_duplicate_dates_raise(self):
        prices = self.prices.copy()
        prices.loc[2, "Date"] = prices.loc[1, "Date"]
        self._expect_value_error(prices)

    def test_unsorted_dates_raise(self):
        prices = self.prices.iloc[::-1].reset_index(drop=True)
        self._expect_value_error(prices)

    def test_non_range_index_raises(self):
        prices = self.prices.copy()
        prices.index = pd.RangeIndex(start=5, stop=5 + len(prices))
        self._expect_value_error(prices)

    def test_a_trade_date_absent_from_prices_raises(self):
        trade_log = self.trade_log.copy()
        trade_log.loc[0, "Exit Date"] = pd.Timestamp("2099-01-01")
        self._expect_value_error(self.prices, trade_log)

    def test_empty_price_frame_raises(self):
        self._expect_value_error(self.prices.iloc[:0].reset_index(drop=True))

    def test_negative_costs_raise(self):
        with self.assertRaises(ValueError):
            equity_curve(
                self.prices,
                self.trade_log,
                commission_per_trade=-1.0,
                slippage_bps=0.0,
            )


class TestGapCase(unittest.TestCase):
    """Rule 5's gap case — the curve is per *bar*, not per calendar day."""

    def test_a_missing_session_does_not_change_the_bar_count(self):
        # Bars 0, 1, 4: a three-day hole between bar 1 and bar 2, as a
        # holiday or halt would produce.
        prices = make_signalled_prices(
            [
                (0, 10.0, 11.0, False, False),
                (1, 20.0, 22.0, True, False),
                (4, 30.0, 33.0, False, True),
            ]
        )
        trade_log = run_backtest(prices, **COSTS)
        curve = equity_curve(prices, trade_log, **COSTS)

        # Three bars, not five calendar days. The 252 annualization is
        # bars-per-year, so a gapped frame is treated as though its bars
        # were consecutive trading days.
        self.assertEqual(len(curve), 3)
        self.assertAlmostEqual(
            float(curve["Bar P&L"].sum()), float(trade_log["P&L"].sum()), places=9
        )


class TestConstantsAreShared(unittest.TestCase):
    """FR-010/FR-011 — one definition, imported everywhere."""

    def test_return_stats_uses_the_shared_constants(self):
        import constants
        import return_stats

        self.assertIs(
            return_stats.TRADING_DAYS_PER_YEAR, constants.TRADING_DAYS_PER_YEAR
        )
        self.assertIs(
            return_stats.RISK_FREE_RATE_ANNUAL, constants.RISK_FREE_RATE_ANNUAL
        )

    def test_the_values_are_unchanged_by_the_extraction(self):
        import constants

        self.assertEqual(constants.TRADING_DAYS_PER_YEAR, 252)
        self.assertEqual(constants.RISK_FREE_RATE_ANNUAL, 0.0378)


if __name__ == "__main__":
    unittest.main()
