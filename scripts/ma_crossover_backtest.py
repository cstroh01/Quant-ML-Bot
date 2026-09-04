"""Phase 0 moving-average crossover backtest for AAPL.

This is intentionally a simple plumbing baseline. It is not meant to be a
production trading strategy or investment recommendation.
"""

from backtest_harness import run_backtest, summarize_trades
from data import cache_path, download_market_data
from plotting import plt, save_figure
from signals import sma_crossover_signal

TICKER = "AAPL"
SHORT_WINDOW = 10
LONG_WINDOW = 30

# Every dollar column in the trade log is printed the same way, so the format
# is declared once rather than repeated per column.
CURRENCY_COLUMNS = ["Entry Price", "Exit Price", "P&L", "Cumulative P&L"]


def main():
    market_data = download_market_data([TICKER])
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    prices = prices.sort_values("Date").reset_index(drop=True)

    # A 10-day average reacts fairly quickly, while a 30-day average gives a
    # little more trend context. These are illustrative defaults, not tuned
    # parameters; tuning them here would make this baseline less useful.
    prices = sma_crossover_signal(prices, SHORT_WINDOW, LONG_WINDOW)
    trade_log = run_backtest(prices)
    trade_log.to_csv(cache_path("phase0_aapl_ma_crossover_trades.csv"), index=False)

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
                    column: "${:,.2f}".format for column in CURRENCY_COLUMNS
                },
            )
        )

    summary = summarize_trades(trade_log)
    print("\nSummary:")
    print(f"Total trades: {summary['total_trades']}")
    print(f"Total P&L: ${summary['total_pnl']:,.2f}")
    print(f"Win rate: {summary['win_rate']:.1f}%")

    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(prices["Date"], prices["Close"], label="Adjusted close", color="black")
    axis.plot(prices["Date"], prices["Short_SMA"], label=f"SMA {SHORT_WINDOW}")
    axis.plot(prices["Date"], prices["Long_SMA"], label=f"SMA {LONG_WINDOW}")

    # Markers sit at the Open, because that is the bar the shifted signal
    # actually trades at — plotting them on the Close would draw a fill the
    # backtest never took.
    buys = prices.loc[prices["Buy_Next_Open"]]
    sells = prices.loc[prices["Sell_Next_Open"]]
    axis.scatter(buys["Date"], buys["Open"], marker="^", color="green", label="Buy")
    axis.scatter(sells["Date"], sells["Open"], marker="v", color="red", label="Sell")
    axis.set_title(f"{TICKER} SMA Crossover Backtest")
    axis.set_xlabel("Date")
    axis.set_ylabel("Adjusted price (USD)")
    axis.grid(True, alpha=0.3)
    axis.legend()

    save_figure(figure, cache_path("phase0_aapl_ma_crossover.png"))


if __name__ == "__main__":
    main()
