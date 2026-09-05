"""Reusable trading signal generators."""

import numpy as np
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


def buy_and_hold_signal(prices: pd.DataFrame) -> pd.DataFrame:
    """Add next-open signals for buying once at the start and never selling.

    The entry decision is taken on the first row and, like every other signal
    here, shifted forward one bar — so the fill lands on row 1's open rather
    than on a bar whose price the decision would have had to see. No exit
    signal is ever produced: the backtest harness already marks a still-open
    position to the final close, and duplicating that as an explicit sell would
    put end-of-data bookkeeping into the signal layer, where it does not
    belong.

    A frame with fewer than two rows has no bar to shift the entry onto, so it
    yields no signals rather than an error — "not enough history to trade yet"
    is a normal outcome, the same one the SMA warm-up period produces.
    """
    prices = prices.copy()

    decision = pd.Series(False, index=prices.index, dtype=bool)
    if not prices.empty:
        decision.iloc[0] = True

    prices["Buy_Next_Open"] = decision.shift(1, fill_value=False)
    prices["Sell_Next_Open"] = pd.Series(False, index=prices.index, dtype=bool)
    return prices


def random_signal(
    prices: pd.DataFrame,
    n_trades: int,
    avg_holding_days: int,
    seed: int,
) -> pd.DataFrame:
    """Add next-open signals for `n_trades` randomly timed round trips.

    Each round trip is held for exactly `avg_holding_days` bars, and the trips
    never overlap — a new entry is never signalled while an earlier position is
    still open. Timing is the only random thing here: the function reads the
    frame's length and nothing else, so it cannot see a price and therefore
    cannot leak one.

    `seed` is required, not optional. Every draw goes through
    `numpy.random.default_rng(seed)`, so the same arguments always produce the
    same trade log and no call disturbs global random state.

    Raises `ValueError` if the frame is too short to hold `n_trades`
    non-overlapping trips of that length. Silently returning fewer trades than
    asked for would quietly break the trade-frequency match that makes this a
    baseline rather than a different strategy.
    """
    if n_trades < 0:
        raise ValueError(f"n_trades must be >= 0; got {n_trades}")
    if avg_holding_days < 1:
        raise ValueError(f"avg_holding_days must be >= 1; got {avg_holding_days}")

    prices = prices.copy()
    n_bars = len(prices)

    buys = np.zeros(n_bars, dtype=bool)
    sells = np.zeros(n_bars, dtype=bool)

    # A strategy that never traded gets a baseline that never trades. Returning
    # early here is what keeps the capacity arithmetic below out of the
    # n_trades == 0 case, where it would divide the frame up for no trips.
    if n_trades == 0:
        prices["Buy_Next_Open"] = buys
        prices["Sell_Next_Open"] = sells
        return prices

    # Entries start at row 1 for the same reason the shifted signals above do:
    # row 0 is the first bar anyone could have looked at, so nothing is filled
    # on it. An entry at row i exits at row i + avg_holding_days, which must
    # still be inside the frame.
    first_entry_row = 1
    last_entry_row = n_bars - 1 - avg_holding_days
    n_candidate_rows = last_entry_row - first_entry_row + 1

    # Non-overlap is imposed by construction rather than checked afterwards.
    # Draw n_trades distinct offsets from a range shortened by the room every
    # trip needs, sort them, then push the i-th one forward by i * (holding -
    # 1). That spreads consecutive entries at least avg_holding_days apart,
    # which is exactly the gap one trip occupies — so the earlier trip has
    # always exited by the time the next one enters.
    spread = avg_holding_days - 1
    n_offsets = n_candidate_rows - (n_trades - 1) * spread
    if n_candidate_rows < 1 or n_offsets < n_trades:
        raise ValueError(
            f"{n_bars} bars cannot hold {n_trades} non-overlapping trades of "
            f"{avg_holding_days} bars each; at least "
            f"{n_trades * avg_holding_days + 2} bars are needed."
        )

    rng = np.random.default_rng(seed)
    offsets = np.sort(rng.choice(n_offsets, size=n_trades, replace=False))
    entries = first_entry_row + offsets + np.arange(n_trades) * spread
    exits = entries + avg_holding_days

    buys[entries] = True
    sells[exits] = True

    prices["Buy_Next_Open"] = buys
    prices["Sell_Next_Open"] = sells
    return prices
