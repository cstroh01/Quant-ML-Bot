"""Tests for signal generation, with lookahead bias as the headline concern."""

import unittest

import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)
from signals import sma_crossover_signal


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


if __name__ == "__main__":
    unittest.main()
