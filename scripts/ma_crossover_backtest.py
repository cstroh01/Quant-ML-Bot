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
from signals import sma_crossover_signal
from backtest_harness import run_backtest, summarize_trades

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
    prices = sma_crossover_signal(prices, SHORT_WINDOW, LONG_WINDOW)
    trade_log = run_backtest(prices)
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

    summary = summarize_trades(trade_log)
    total_trades = summary["total_trades"]
    total_pnl = summary["total_pnl"]
    win_rate = summary["win_rate"]

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
