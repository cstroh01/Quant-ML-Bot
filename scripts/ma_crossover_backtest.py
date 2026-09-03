"""Phase 0 moving-average crossover backtest for AAPL.

This is intentionally a simple plumbing baseline. It is not meant to be a
production trading strategy or investment recommendation.
"""

from pathlib import Path

# Select a non-interactive backend before importing pyplot so this also works
# on a server or in another environment without a desktop window.
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from data import download_market_data

TICKER = "AAPL"
SHORT_WINDOW = 10
LONG_WINDOW = 30


def main():
    market_data = download_market_data([TICKER])
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    prices = prices.sort_values("Date").reset_index(drop=True)

    # A 10-day average reacts fairly quickly, while a 30-day average gives a
    # little more trend context. These are illustrative defaults, not tuned
    # parameters; tuning them here would make this baseline less useful.
    prices["Short_SMA"] = prices["Close"].rolling(SHORT_WINDOW).mean()
    prices["Long_SMA"] = prices["Close"].rolling(LONG_WINDOW).mean()

    # The comparison uses today's completed closing price and yesterday's
    # completed averages. It therefore identifies a crossover only after the
    # close that caused it is known. The first valid long average cannot exist
    # until LONG_WINDOW observations have accumulated.
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
    trade_log_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "cache"
        / "phase0_aapl_ma_crossover_trades.csv"
    )
    trade_log_path.parent.mkdir(parents=True, exist_ok=True)
    trade_log.to_csv(trade_log_path, index=False)

    print(f"{TICKER} SMA crossover backtest")
    print(f"SMA windows: {SHORT_WINDOW} and {LONG_WINDOW} trading days")
    print("Position: long one share or flat; fees and slippage: none")
    print("\nTrade log:")
    if trade_log.empty:
        print("No completed trades.")
    else:
        print(
            trade_log.to_string(
                index=False,
                formatters={
                    "Entry Price": "${:,.2f}".format,
                    "Exit Price": "${:,.2f}".format,
                    "P&L": "${:,.2f}".format,
                    "Cumulative P&L": "${:,.2f}".format,
                },
            )
        )

    total_pnl = float(trade_log["P&L"].sum()) if not trade_log.empty else 0.0
    wins = int((trade_log["P&L"] > 0).sum()) if not trade_log.empty else 0
    total_trades = len(trade_log)
    win_rate = (wins / total_trades * 100) if total_trades else 0.0

    print("\nSummary:")
    print(f"Total trades: {total_trades}")
    print(f"Total P&L: ${total_pnl:,.2f}")
    print(f"Win rate: {win_rate:.1f}%")

    output_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "cache"
        / "phase0_aapl_ma_crossover.png"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(prices["Date"], prices["Close"], label="Adjusted close", color="black")
    axis.plot(prices["Date"], prices["Short_SMA"], label=f"SMA {SHORT_WINDOW}")
    axis.plot(prices["Date"], prices["Long_SMA"], label=f"SMA {LONG_WINDOW}")

    buy_dates = prices.loc[prices["Buy_Next_Open"], "Date"]
    buy_prices = prices.loc[prices["Buy_Next_Open"], "Open"]
    sell_dates = prices.loc[prices["Sell_Next_Open"], "Date"]
    sell_prices = prices.loc[prices["Sell_Next_Open"], "Open"]
    axis.scatter(buy_dates, buy_prices, marker="^", color="green", label="Buy")
    axis.scatter(sell_dates, sell_prices, marker="v", color="red", label="Sell")
    axis.set_title(f"{TICKER} SMA Crossover Backtest")
    axis.set_xlabel("Date")
    axis.set_ylabel("Adjusted price (USD)")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    print(f"\nSaved plot to: {output_path}")


if __name__ == "__main__":
    main()
