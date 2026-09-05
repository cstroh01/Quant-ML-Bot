"""Phase 0 moving-average crossover backtest for AAPL.

This is intentionally a simple plumbing baseline. It is not meant to be a
production trading strategy or investment recommendation.
"""

import statistics

import pandas as pd

from backtest_harness import run_backtest, summarize_trades
from data import cache_path, download_market_data
from plotting import plt, save_figure
from signals import buy_and_hold_signal, random_signal, sma_crossover_signal

TICKER = "AAPL"
SHORT_WINDOW = 10
LONG_WINDOW = 30

# A retail-broker cost model, stated once and applied identically to the
# strategy and to both baselines. Comparing a costed strategy against an
# uncosted baseline would flatter whichever of the two trades more.
COMMISSION_PER_TRADE = 1.00
SLIPPAGE_BPS = 5.0

# Enough seeds for a mean and a spread to mean something. The spread is
# reported alongside the mean because a single random run says nothing: the
# question is whether the strategy beats the *distribution* of luck, not one
# draw from it.
RANDOM_BASELINE_SEEDS = 20

# Every dollar column in the trade log is printed the same way, so the format
# is declared once rather than repeated per column.
CURRENCY_COLUMNS = ["Entry Price", "Exit Price", "P&L", "Cumulative P&L"]


def mean_holding_bars(prices: pd.DataFrame, trade_log: pd.DataFrame) -> int:
    """Return a trade log's mean holding period, measured in trading bars.

    Measured in bars rather than calendar days because a random baseline is
    built by index: two trades held "10 days" across a holiday weekend occupy
    different numbers of tradeable rows, and it is the rows the baseline needs
    to match. Returns 1 for an empty log, which no caller uses — a strategy
    with no trades gets a baseline with no trades.
    """
    if trade_log.empty:
        return 1

    # The trade log records dates, not row positions, because the harness has
    # no reason to expose its own indexing. Mapping them back is the caller's
    # job — which is this script, the only layer that legitimately sees both
    # the price frame and the resulting trades.
    row_of_date = pd.Series(range(len(prices)), index=prices["Date"])
    entry_rows = row_of_date.loc[trade_log["Entry Date"]].to_numpy()
    exit_rows = row_of_date.loc[trade_log["Exit Date"]].to_numpy()
    return max(1, int(round(float((exit_rows - entry_rows).mean()))))


def baseline_results(
    prices: pd.DataFrame,
    n_trades: int,
    holding_bars: int,
    *,
    commission_per_trade: float,
    slippage_bps: float,
    seed_count: int,
) -> dict:
    """Run both Rule 4 baselines over the same bars, with the same costs.

    `prices` is the already-signalled strategy frame; each baseline overwrites
    the signal columns on its own copy, so all three runs see an identical
    price history and an identical cost model. That identity is the whole point
    of a baseline — any difference in the numbers then has to come from the
    signal.
    """
    costs = {
        "commission_per_trade": commission_per_trade,
        "slippage_bps": slippage_bps,
    }

    hold_log = run_backtest(buy_and_hold_signal(prices), **costs)
    results = {
        "buy_and_hold": summarize_trades(hold_log, **costs),
        "random_summaries": [],
        "random_error": None,
    }

    try:
        for seed in range(seed_count):
            signalled = random_signal(prices, n_trades, holding_bars, seed)
            results["random_summaries"].append(
                summarize_trades(run_backtest(signalled, **costs), **costs)
            )
    except ValueError as error:
        # Reported, never swallowed: a random baseline that could not match the
        # strategy's trade frequency is not a baseline, and printing why beats
        # printing a comparison against a quietly different one.
        results["random_summaries"] = []
        results["random_error"] = str(error)

    return results


def _comparison_row(label: str, trades: str, pnl: str, win_rate: str) -> str:
    """Lay out one row of the comparison table."""
    return f"{label:<30}{trades:>7}{pnl:>24}{win_rate:>10}"


def format_comparison(sma_summary: dict, baselines: dict, *, seed_count: int) -> str:
    """Render the strategy and both baselines as one cost-adjusted block.

    The cost parameters are printed once, above the table, rather than repeated
    per row. Repeating them would invite the reader to check whether they
    match; printing them once makes it structurally impossible for them not to.
    """
    commission = sma_summary["commission_per_trade"]
    slippage = sma_summary["slippage_bps"]
    hold = baselines["buy_and_hold"]

    lines = [
        "Cost model (applied identically to all three rows below):",
        f"  Commission: ${commission:,.2f} per fill, charged on entry and again"
        " on exit",
        f"  Slippage:   {slippage:.1f} bps of notional, always against the fill",
        "",
        _comparison_row("Strategy", "Trades", "Total P&L", "Win rate"),
        "-" * 71,
        _comparison_row(
            f"SMA crossover ({SHORT_WINDOW}/{LONG_WINDOW})",
            str(sma_summary["total_trades"]),
            f"${sma_summary['total_pnl']:,.2f}",
            f"{sma_summary['win_rate']:.1f}%",
        ),
        _comparison_row(
            "Buy and hold",
            str(hold["total_trades"]),
            f"${hold['total_pnl']:,.2f}",
            f"{hold['win_rate']:.1f}%",
        ),
    ]

    random_summaries = baselines["random_summaries"]
    label = f"Random baseline ({seed_count} seeds)"
    if not random_summaries:
        reason = baselines["random_error"] or "the strategy took no trades"
        lines.append(_comparison_row(label, "-", "not run", "-"))
        lines.append(f"  Random baseline not run: {reason}")
        return "\n".join(lines)

    pnls = [summary["total_pnl"] for summary in random_summaries]
    win_rates = [summary["win_rate"] for summary in random_summaries]
    # Sample standard deviation across seeds, so the dispersion Rule 4 asks for
    # is reported next to the mean rather than instead of it. One seed has no
    # dispersion to report, and stdev would raise rather than say so.
    spread = statistics.stdev(pnls) if len(pnls) > 1 else 0.0
    lines.append(
        _comparison_row(
            label,
            str(random_summaries[0]["total_trades"]),
            f"${statistics.fmean(pnls):,.2f} ± ${spread:,.2f}",
            f"{statistics.fmean(win_rates):.1f}%",
        )
    )
    lines.append("")
    lines.append(
        f"Random figures are the mean ± sample standard deviation over "
        f"{seed_count} seeds, matched to"
    )
    lines.append("the strategy's own trade count and mean holding period.")
    return "\n".join(lines)


def main():
    market_data = download_market_data([TICKER])
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    prices = prices.sort_values("Date").reset_index(drop=True)

    # A 10-day average reacts fairly quickly, while a 30-day average gives a
    # little more trend context. These are illustrative defaults, not tuned
    # parameters; tuning them here would make this baseline less useful.
    prices = sma_crossover_signal(prices, SHORT_WINDOW, LONG_WINDOW)
    costs = {
        "commission_per_trade": COMMISSION_PER_TRADE,
        "slippage_bps": SLIPPAGE_BPS,
    }
    trade_log = run_backtest(prices, **costs)
    trade_log.to_csv(cache_path("phase0_aapl_ma_crossover_trades.csv"), index=False)

    print(f"{TICKER} SMA crossover backtest")
    print(f"SMA windows: {SHORT_WINDOW} and {LONG_WINDOW} trading days")
    print("Position: long one share or flat; prices below are net of costs")
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

    summary = summarize_trades(trade_log, **costs)
    baselines = baseline_results(
        prices,
        n_trades=summary["total_trades"],
        holding_bars=mean_holding_bars(prices, trade_log),
        seed_count=RANDOM_BASELINE_SEEDS,
        **costs,
    )

    print("\nSummary, against both required baselines:\n")
    print(format_comparison(summary, baselines, seed_count=RANDOM_BASELINE_SEEDS))

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
