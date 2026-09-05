"""Tests for signal generation, with lookahead bias as the headline concern."""

import unittest

import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
from backtest_harness import run_backtest
from signals import buy_and_hold_signal, random_signal, sma_crossover_signal


def make_prices(closes: list[float]) -> pd.DataFrame:
    """Build a minimal one-ticker price frame with distinguishable columns.

    Open is deliberately offset from Close so a test can tell which of the two
    a fill actually used.
    """
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": [close + 100 for close in closes],
            "Close": closes,
        }
    )


class SmaCrossoverSignalTests(unittest.TestCase):
    def test_trade_signal_never_fires_on_the_bar_that_created_it(self):
        # The core lookahead check: a crossover is only knowable at that bar's
        # close, so the tradeable signal must land on the *following* bar. If
        # this ever fails, the backtest is filling on information it could not
        # have had at the time.
        prices = make_prices([1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1, 2, 3, 4, 5, 6, 7, 8])
        signals = sma_crossover_signal(prices, short_window=2, long_window=4)

        pd.testing.assert_series_equal(
            signals["Buy_Next_Open"],
            signals["Crosses_Above"].shift(1, fill_value=False),
            check_names=False,
        )
        pd.testing.assert_series_equal(
            signals["Sell_Next_Open"],
            signals["Crosses_Below"].shift(1, fill_value=False),
            check_names=False,
        )

    def test_no_signal_fires_before_the_long_window_is_full(self):
        # The long average does not exist until enough bars have accumulated,
        # so nothing tradeable may appear inside that warm-up period.
        prices = make_prices([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        signals = sma_crossover_signal(prices, short_window=2, long_window=5)

        warmup = signals.iloc[:5]
        self.assertFalse(warmup["Buy_Next_Open"].any())
        self.assertFalse(warmup["Sell_Next_Open"].any())

    def test_caller_frame_is_not_modified(self):
        # The function returns a frame; it must not also rewrite its argument.
        prices = make_prices([1, 2, 3, 4, 5, 6, 7, 8])
        original_columns = list(prices.columns)

        sma_crossover_signal(prices, short_window=2, long_window=4)

        self.assertEqual(list(prices.columns), original_columns)

    def test_crossover_is_detected_at_the_expected_bar(self):
        # A falling then rising series crosses exactly once upward. Pinning the
        # bar keeps the shift from being silently off by one in either
        # direction, which a same-shape check alone would not catch.
        closes = [10, 9, 8, 7, 6, 5, 6, 7, 8, 9, 10, 11]
        signals = sma_crossover_signal(make_prices(closes), 2, 4)

        crossings = list(signals.index[signals["Crosses_Above"]])
        self.assertEqual(len(crossings), 1)
        self.assertEqual(
            list(signals.index[signals["Buy_Next_Open"]]), [crossings[0] + 1]
        )

    def test_short_window_must_be_shorter_than_long_window(self):
        with self.assertRaises(ValueError):
            sma_crossover_signal(make_prices([1, 2, 3, 4]), 10, 10)


class BuyAndHoldSignalTests(unittest.TestCase):
    def test_one_entry_on_the_second_bar_and_never_an_exit(self):
        # The decision is taken on row 0 and shifted like every other signal
        # here, so the fill lands on row 1's open. An entry left on row 0 would
        # be filled at a price the decision itself had to see.
        signals = buy_and_hold_signal(make_prices([1, 2, 3, 4, 5]))

        self.assertEqual(list(signals.index[signals["Buy_Next_Open"]]), [1])
        self.assertFalse(signals["Sell_Next_Open"].any())

    def test_the_harness_closes_the_position_at_the_final_close(self):
        # No exit logic is added anywhere for this baseline; it relies on the
        # harness's existing end-of-data mark. This is the test that says so.
        closes = [10.0, 20.0, 30.0, 40.0]
        trade_log = run_backtest(buy_and_hold_signal(make_prices(closes)))

        self.assertEqual(len(trade_log), 1)
        # Open is Close + 100 in this fixture, so the entry is row 1's open.
        self.assertEqual(trade_log.iloc[0]["Entry Price"], 120.0)
        self.assertEqual(trade_log.iloc[0]["Exit Price"], 40.0)

    def test_a_single_row_frame_produces_no_trade_rather_than_crashing(self):
        # Boundary case: there is no next bar to shift the entry onto, which is
        # the same "not enough history yet" outcome as an SMA warm-up.
        signals = buy_and_hold_signal(make_prices([10.0]))

        self.assertFalse(signals["Buy_Next_Open"].any())
        self.assertTrue(run_backtest(signals).empty)

    def test_an_empty_frame_produces_no_trade_rather_than_crashing(self):
        signals = buy_and_hold_signal(make_prices([]))

        self.assertFalse(signals["Buy_Next_Open"].any())
        self.assertTrue(run_backtest(signals).empty)

    def test_caller_frame_is_not_modified(self):
        prices = make_prices([1, 2, 3, 4])
        original_columns = list(prices.columns)

        buy_and_hold_signal(prices)

        self.assertEqual(list(prices.columns), original_columns)


class RandomSignalTests(unittest.TestCase):
    def price_frame(self, n_bars: int = 120):
        return make_prices([float(bar) for bar in range(n_bars)])

    def test_the_same_seed_twice_gives_an_identical_trade_log(self):
        # SC-003, and the project's determinism convention: a result that
        # cannot be reproduced is not a result.
        first = random_signal(self.price_frame(), 8, 12, seed=0)
        second = random_signal(self.price_frame(), 8, 12, seed=0)

        pd.testing.assert_frame_equal(first, second)

    def test_different_seeds_give_different_trade_logs(self):
        # If the seed were ignored, every "random" baseline would be the same
        # single draw and its standard deviation would be zero.
        patterns = set()
        for seed in range(20):
            signals = random_signal(self.price_frame(), 8, 12, seed)
            patterns.add(tuple(signals.index[signals["Buy_Next_Open"]]))

        self.assertGreater(len(patterns), 1)

    def test_every_seed_yields_the_requested_count_and_no_overlap(self):
        # The two properties that make this a matched-frequency baseline
        # rather than a different strategy, checked across all 20 seeds the
        # report uses.
        for seed in range(20):
            with self.subTest(seed=seed):
                signals = random_signal(self.price_frame(), 8, 12, seed)
                entries = list(signals.index[signals["Buy_Next_Open"]])
                exits = list(signals.index[signals["Sell_Next_Open"]])

                self.assertEqual(len(entries), 8)
                self.assertEqual(len(exits), 8)
                # Each trip is exactly the requested length, and the next entry
                # never precedes the previous exit.
                for entry, exit_ in zip(entries, exits):
                    self.assertEqual(exit_ - entry, 12)
                for previous_exit, next_entry in zip(exits, entries[1:]):
                    self.assertGreaterEqual(next_entry, previous_exit)

    def test_the_harness_records_exactly_the_requested_number_of_trades(self):
        # Non-overlap stated as the harness sees it: a trip that opened while
        # another was still open would be swallowed by the one-share state
        # machine and the count would come back short.
        trade_log = run_backtest(random_signal(self.price_frame(), 8, 12, seed=3))

        self.assertEqual(len(trade_log), 8)

    def test_no_signal_lands_where_its_exit_would_fall_off_the_end(self):
        # Boundary case: the last entry must leave room for its own exit, or
        # the harness would close it at the final close and the trip would be
        # shorter than the baseline claims.
        for seed in range(20):
            with self.subTest(seed=seed):
                signals = random_signal(self.price_frame(40), 2, 12, seed)
                last_entry = max(signals.index[signals["Buy_Next_Open"]])
                self.assertLessEqual(last_entry + 12, len(signals) - 1)

    def test_zero_trades_is_a_valid_request_not_a_division_by_zero(self):
        # A strategy with no crossovers in the window gets a baseline with no
        # trades, which has to run rather than raise.
        signals = random_signal(self.price_frame(), 0, 12, seed=0)

        self.assertFalse(signals["Buy_Next_Open"].any())
        self.assertFalse(signals["Sell_Next_Open"].any())
        self.assertTrue(run_backtest(signals).empty)

    def test_too_few_bars_raises_rather_than_quietly_shortening_the_baseline(self):
        # Returning 3 trades when 8 were asked for would silently break the
        # frequency match, and the comparison would no longer mean anything.
        with self.assertRaises(ValueError):
            random_signal(self.price_frame(20), 8, 12, seed=0)
        with self.assertRaises(ValueError):
            random_signal(self.price_frame(5), 1, 12, seed=0)

    def test_a_frame_sized_to_the_exact_minimum_still_works(self):
        # n trips of length h need n * h bars plus one unused row at each end:
        # row 0, which carries no fill, and the row the last exit fills on.
        signals = random_signal(self.price_frame(2 * 12 + 2), 2, 12, seed=0)

        self.assertEqual(int(signals["Buy_Next_Open"].sum()), 2)
        with self.assertRaises(ValueError):
            random_signal(self.price_frame(2 * 12 + 1), 2, 12, seed=0)

    def test_invalid_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            random_signal(self.price_frame(), -1, 12, seed=0)
        with self.assertRaises(ValueError):
            random_signal(self.price_frame(), 8, 0, seed=0)

    def test_caller_frame_is_not_modified(self):
        prices = self.price_frame()
        original_columns = list(prices.columns)

        random_signal(prices, 8, 12, seed=0)

        self.assertEqual(list(prices.columns), original_columns)


if __name__ == "__main__":
    unittest.main()
