"""Reusable execution, accounting, and reporting helpers."""

import pandas as pd

# The trade log's shape is fixed here so an empty result still has the same
# columns as a populated one. Downstream code can then treat "no trades" as a
# normal outcome instead of a special case.
TRADE_LOG_COLUMNS = ["Entry Date", "Entry Price", "Exit Date", "Exit Price", "P&L"]

REQUIRED_PRICE_COLUMNS = ("Date", "Open", "Close", "Buy_Next_Open", "Sell_Next_Open")


def run_backtest(prices: pd.DataFrame) -> pd.DataFrame:
    """Run a long-only, one-share backtest on already-shifted signals."""
    # This layer deliberately knows nothing about how the signals were made.
    # Checking for the columns it does depend on keeps the contract explicit,
    # so a future ML signal that forgets to shift fails loudly and early
    # rather than producing a plausible-looking but wrong trade log.
    missing = [name for name in REQUIRED_PRICE_COLUMNS if name not in prices.columns]
    if missing:
        raise ValueError(f"prices is missing required columns: {missing}")

    # We go flat below the long average rather than shorting. That keeps this
    # first test focused on long-entry/exit accounting and avoids borrowing and
    # short-sale assumptions before the plumbing is trusted.
    trades = []
    entry_date = None
    entry_price = None

    # This small state machine represents one share: either we hold it or we
    # do not. Checking exits before entries makes the intended order explicit
    # if the signal rules are expanded later.
    for row in prices.itertuples(index=False):
        if entry_price is not None and row.Sell_Next_Open:
            exit_price = float(row.Open)
            trades.append(
                {
                    "Entry Date": entry_date,
                    "Entry Price": entry_price,
                    "Exit Date": row.Date,
                    "Exit Price": exit_price,
                    "P&L": exit_price - entry_price,
                }
            )
            entry_date = None
            entry_price = None

        if entry_price is None and row.Buy_Next_Open:
            entry_date = row.Date
            entry_price = float(row.Open)

    # If the final position is still open, mark it to the final known close.
    # This is an end-of-data bookkeeping exit, not a future prediction.
    if entry_price is not None:
        final_row = prices.iloc[-1]
        exit_price = float(final_row["Close"])
        trades.append(
            {
                "Entry Date": entry_date,
                "Entry Price": entry_price,
                "Exit Date": final_row["Date"],
                "Exit Price": exit_price,
                "P&L": exit_price - entry_price,
            }
        )

    trade_log = pd.DataFrame(trades, columns=TRADE_LOG_COLUMNS)
    # An empty frame's P&L column has no dtype of its own, so cast before the
    # cumulative sum to keep "Cumulative P&L" numeric in both cases.
    trade_log["P&L"] = trade_log["P&L"].astype(float)
    trade_log["Cumulative P&L"] = trade_log["P&L"].cumsum()
    return trade_log


def summarize_trades(trade_log: pd.DataFrame) -> dict[str, float | int]:
    """Return the summary values used by the backtest report."""
    total_trades = len(trade_log)
    # Summing an empty column already yields 0.0, so no empty-case branch is
    # needed here. A trade that breaks exactly even counts as a loss, which is
    # the conservative reading of a win rate.
    total_pnl = float(trade_log["P&L"].sum())
    wins = int((trade_log["P&L"] > 0).sum())
    win_rate = (wins / total_trades * 100) if total_trades else 0.0
    return {
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
    }
