"""Reusable execution, accounting, and reporting helpers."""

import pandas as pd


def run_backtest(prices: pd.DataFrame) -> pd.DataFrame:
    """Run a long-only, one-share backtest on already-shifted signals."""
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

    trade_log = pd.DataFrame(
        trades,
        columns=["Entry Date", "Entry Price", "Exit Date", "Exit Price", "P&L"],
    )
    trade_log["Cumulative P&L"] = trade_log["P&L"].cumsum()
    return trade_log


def summarize_trades(trade_log: pd.DataFrame) -> dict[str, float]:
    """Return the summary values used by the backtest report."""
    total_pnl = float(trade_log["P&L"].sum()) if not trade_log.empty else 0.0
    wins = int((trade_log["P&L"] > 0).sum()) if not trade_log.empty else 0
    total_trades = len(trade_log)
    win_rate = (wins / total_trades * 100) if total_trades else 0.0
    return {
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
    }
