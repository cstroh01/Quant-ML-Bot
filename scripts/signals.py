"""Reusable trading signal generators."""

import pandas as pd


def sma_crossover_signal(
    prices: pd.DataFrame, short_window: int = 10, long_window: int = 30
) -> pd.DataFrame:
    """Add tradeable next-open SMA crossover signals to one ticker's prices."""
    if short_window >= long_window:
        raise ValueError(
            "short_window must be smaller than long_window; "
            f"got {short_window} and {long_window}."
        )

    # Work on a copy so the caller's frame is never modified as a side effect.
    # A function that both returns a frame and rewrites its argument is easy to
    # misuse once more than one signal is generated from the same prices.
    prices = prices.copy()

    prices["Short_SMA"] = prices["Close"].rolling(short_window).mean()
    prices["Long_SMA"] = prices["Close"].rolling(long_window).mean()

    # The comparison uses today's completed closing price and yesterday's
    # completed averages. It therefore identifies a crossover only after the
    # close that caused it is known. The first valid long average cannot exist
    # until long_window observations have accumulated.
    prices["Crosses_Above"] = (prices["Short_SMA"] > prices["Long_SMA"]) & (
        prices["Short_SMA"].shift(1) <= prices["Long_SMA"].shift(1)
    )
    prices["Crosses_Below"] = (prices["Short_SMA"] < prices["Long_SMA"]) & (
        prices["Short_SMA"].shift(1) >= prices["Long_SMA"].shift(1)
    )

    # A close-based signal cannot be filled at that same close without using
    # information that was only known at the end of the bar. Shifting the
    # signals by one row means we trade at the next day's Open instead.
    prices["Buy_Next_Open"] = prices["Crosses_Above"].shift(1, fill_value=False)
    prices["Sell_Next_Open"] = prices["Crosses_Below"].shift(1, fill_value=False)
    return prices
