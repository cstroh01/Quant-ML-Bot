"""Phase 0 moving-average crossover backtest for an AAPL spec 020 bundle.

This is intentionally a simple plumbing baseline. It is not meant to be a
production trading strategy or investment recommendation.
"""

from trial_runner import research_attempt, research_config, cli_recording
import argparse
from pathlib import Path
import statistics

import pandas as pd

from backtest_harness import run_backtest, summarize_trades
from data import (
    UNADJUSTED_CACHE_DIR, UnadjustedDataUnavailable, cache_path,
    execution_price_frame, load_unadjusted_for_ticker,
)
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

# Starting capital funds all three rows identically (spec 019 C1: the harness
# never derives capital from a price). This is a report ASSUMPTION whose value
# Camden set per spec 021 D-4, printed like commission; it is not a result and
# not a capital-gate number. At one share it changes no closed-trade P&L.
STARTING_CAPITAL = 10_000.0

# End-of-data policy (spec 021 D-3): every row sells a still-open position at
# the final close, costed, as an explicit ledger `liquidation` event. Without
# it the harness only marks the position (019 C5) and buy-and-hold would
# report 0 closed trades. Rule 4 needs the identical policy on all three rows.
LIQUIDATE_AT_END = True

# Enough seeds for a mean and a spread to mean something. The spread is
# reported alongside the mean because a single random run says nothing: the
# question is whether the strategy beats the *distribution* of luck, not one
# draw from it.
RANDOM_BASELINE_SEEDS = 20

# Every dollar column in the trade log is printed the same way, so the format
# is declared once rather than repeated per column.
CURRENCY_COLUMNS = ["Entry Price", "Exit Price", "P&L", "Cumulative P&L"]


def research_close_signal(
    nominal: pd.DataFrame, short_window: int, long_window: int,
) -> pd.DataFrame:
    """Signal on causal total-return units while preserving nominal funded bars."""
    research = execution_price_frame(nominal)
    signal_input = research.copy()
    signal_input["Close"] = research["Research_Close"]
    signal = sma_crossover_signal(signal_input, short_window, long_window)
    result = nominal.copy()
    result["Research_Close"] = research["Research_Close"]
    result["Buy_Next_Open"] = signal["Buy_Next_Open"]
    result["Sell_Next_Open"] = signal["Sell_Next_Open"]
    result["Short_SMA_Research"] = signal["Short_SMA"]
    result["Long_SMA_Research"] = signal["Long_SMA"]
    return result


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
    starting_capital: float,
    liquidate: bool,
) -> dict:
    """Run both Rule 4 baselines over the same bars, with the same costs.

    `prices` is the already-signalled strategy frame; each baseline overwrites
    the signal columns on its own copy, so all three runs see an identical
    price history and an identical cost model. That identity is the whole point
    of a baseline — any difference in the numbers then has to come from the
    signal.

    `starting_capital` and `liquidate` are required, with no default: a default
    would be the implicit funding or implicit end-of-data policy spec 019
    forbids. Both go unchanged to every `run_backtest` call here.
    """
    costs = {
        "commission_per_trade": commission_per_trade,
        "slippage_bps": slippage_bps,
    }
    account = {"starting_capital": starting_capital, "liquidate": liquidate}

    with research_attempt(research_config("scripts/ma_crossover_backtest.py:run_backtest", locals()), role="buy_and_hold_baseline") as attempt:
        hold_log = run_backtest(buy_and_hold_signal(prices), **costs, **account)
        attempt.account(hold_log)
    results = {
        "buy_and_hold": summarize_trades(hold_log, **costs),
        "random_summaries": [],
        "random_error": None,
    }

    try:
        for seed in range(seed_count):
            signalled = random_signal(prices, n_trades, holding_bars, seed)
            with research_attempt(research_config("scripts/ma_crossover_backtest.py:run_backtest", locals()), role="random_signal_baseline") as attempt:
                recorded_trades = run_backtest(signalled, **costs, **account)
                results["random_summaries"].append(
                    summarize_trades(
                        recorded_trades, **costs
                    )
                )
                attempt.account(recorded_trades)
    except ValueError as error:
        # Reported, never swallowed: a random baseline that could not match the
        # strategy's trade frequency is not a baseline, and printing why beats
        # printing a comparison against a quietly different one.
        results["random_summaries"] = []
        results["random_error"] = str(error)

    return results


def pay_date_disclosure(attrs: dict) -> str | None:
    """State that dividend cash timing is a declared bound (spec 041 FR-007).

    Returns None only when no dividend in the bundle is bound. This is the one
    renderer for the line; the CLI and the tearsheet API both print its output.
    """
    bound = attrs.get("dividends_bound") or 0
    if not bound:
        return None
    policy = attrs["dividend_pay_date_policy"]
    total = bound + (attrs.get("dividends_sourced") or 0)
    line = (f"Dividend pay dates: declared bound (policy={policy}), "
            f"{bound} of {total} dividends; NOT vendor data.")
    if policy == "unbounded":
        line += " dividend cash never becomes buying power within this run."
    return line


def _comparison_row(label: str, trades: str, pnl: str, win_rate: str) -> str:
    """Lay out one row of the comparison table."""
    return f"{label:<30}{trades:>7}{pnl:>24}{win_rate:>10}"


def _end_of_data_policy(liquidate: bool) -> str:
    """Describe the end-of-data policy in one report line."""
    if liquidate:
        return "open positions are sold at the final close, with costs"
    return "open positions are marked at the final close, not sold"


def format_comparison(sma_summary: dict, baselines: dict, *, seed_count: int) -> str:
    """Render the strategy and both baselines as one cost-adjusted block.

    The cost parameters are printed once, above the table, rather than repeated
    per row. Repeating them would invite the reader to check whether they
    match; printing them once makes it structurally impossible for them not to.
    Starting capital and the end-of-data policy are stated once in the same
    block. Summaries do not carry them, so both are read from the module
    constants `main()` also passes to the harness, which keeps the printed
    value and the used value from differing.
    """
    commission = sma_summary["commission_per_trade"]
    slippage = sma_summary["slippage_bps"]
    hold = baselines["buy_and_hold"]

    lines = [
        "Cost model (applied identically to all three rows below):",
        f"  Commission: ${commission:,.2f} per fill, charged on entry and again"
        " on exit",
        f"  Slippage:   {slippage:.1f} bps of notional, always against the fill",
        f"  Capital:    ${STARTING_CAPITAL:,.2f} starting cash per row (assumption)",
        f"  End of data: {_end_of_data_policy(LIQUIDATE_AT_END)}",
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


def tearsheet_config(prices, ticker, short_window, long_window, commission, slippage_bps):
    """One recording/lookup identity: source bytes, code and all report parameters."""
    from trial_registry import CONFIG_FIELDS, source_identity
    config = {field: None for field in CONFIG_FIELDS}
    config.update(runner="scripts/ma_crossover_backtest.py:run_backtest",
                  data={"manifest_sha256": prices.attrs["source_manifest_sha256"]},
                  universe=[ticker.upper()], features={"short": short_window, "long": long_window},
                  model={"kind": "sma_crossover", "source_tree_hash": source_identity()["source_tree_hash"]},
                  initial_capital=STARTING_CAPITAL, commission=commission,
                  slippage={"model": "flat_bps", "bps": slippage_bps},
                  liquidation=LIQUIDATE_AT_END, seed={"baseline_count": RANDOM_BASELINE_SEEDS})
    return config


def main(argv=None, *, cache_dir=UNADJUSTED_CACHE_DIR):
    parser = argparse.ArgumentParser(description="Run the AAPL crossover on a verified unadjusted bundle")
    parser.add_argument("--manifest", type=Path, help="explicit unadjusted manifest path")
    parser.add_argument("--record-trial", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--ticker", default=TICKER)
    parser.add_argument("--short-window", type=int, default=SHORT_WINDOW)
    parser.add_argument("--long-window", type=int, default=LONG_WINDOW)
    parser.add_argument("--commission", type=float, default=COMMISSION_PER_TRADE)
    parser.add_argument("--slippage-bps", type=float, default=SLIPPAGE_BPS)
    args = parser.parse_args(argv)
    with cli_recording(args.record_trial, "ma_crossover_backtest"):
        return _run_main(args, args.cache_dir or cache_dir)


def _run_main(args, cache_dir):
    ticker, short_window, long_window = args.ticker.upper(), args.short_window, args.long_window
    commission, slippage_bps = args.commission, args.slippage_bps
    nominal = load_unadjusted_for_ticker(ticker, cache_dir, manifest_path=args.manifest)

    # A 10-day average reacts fairly quickly, while a 30-day average gives a
    # little more trend context. These are illustrative defaults, not tuned
    # parameters; tuning them here would make this baseline less useful.
    prices = research_close_signal(nominal, short_window, long_window)
    costs = {
        "commission_per_trade": commission,
        "slippage_bps": slippage_bps,
    }
    account = {"starting_capital": STARTING_CAPITAL, "liquidate": LIQUIDATE_AT_END}
    with research_attempt(tearsheet_config(nominal, ticker, short_window, long_window, commission, slippage_bps), role="candidate") as attempt:
        trade_log = run_backtest(prices, **costs, **account)
        summary = summarize_trades(trade_log, **costs)
        baselines = baseline_results(
            prices,
            n_trades=summary["total_trades"],
            holding_bars=mean_holding_bars(prices, trade_log),
            seed_count=RANDOM_BASELINE_SEEDS,
            **costs,
            **account,
        )
        from tearsheet_payload import recorded_tearsheet_payload
        started = next(e for e in attempt.ledger.verify()["events"] if e["trial_id"] == attempt.trial)
        provenance = dict(trial_id=attempt.trial, recorded_at_utc=started["timestamp_utc"],
                          recorded_source_tree_hash=started["source"]["source_tree_hash"])
        payload = recorded_tearsheet_payload(prices, trade_log, baselines, ticker=ticker,
            short_window=short_window, long_window=long_window, commission=commission,
            slippage_bps=slippage_bps, starting_capital=STARTING_CAPITAL,
            liquidate_at_end=LIQUIDATE_AT_END, dividend_disclosure=pay_date_disclosure(prices.attrs), provenance=provenance)
        attempt.account(trade_log, reports={"tearsheet": payload})
    trade_log.to_csv(cache_path("phase0_aapl_ma_crossover_trades.csv"), index=False)

    print(f"{ticker} SMA crossover backtest")
    for key in ("source_name", "source_method", "downloaded_at_utc",
                "capital_gate_eligible", "source_limitations", "source_manifest_sha256"):
        print(f"{key}: {prices.attrs[key]}")
    if (disclosure := pay_date_disclosure(prices.attrs)) is not None:
        print(disclosure)
    print(f"SMA windows: {short_window} and {long_window} trading days")
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

    print("\nSummary, against both required baselines:\n")
    print(format_comparison(summary, baselines, seed_count=RANDOM_BASELINE_SEEDS))

    figure, (research_axis, nominal_axis) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    research_axis.plot(prices["Date"], prices["Research_Close"], label="Research Close", color="black")
    research_axis.plot(prices["Date"], prices["Short_SMA_Research"], label=f"SMA {short_window}")
    research_axis.plot(prices["Date"], prices["Long_SMA_Research"], label=f"SMA {long_window}")
    research_axis.set_ylabel("Causal total-return index (research units)")
    research_axis.grid(True, alpha=0.3)
    research_axis.legend()
    nominal_axis.plot(prices["Date"], prices["Open"], label="Nominal Open", color="black")

    # Markers sit at the Open, because that is the bar the shifted signal
    # actually trades at — plotting them on the Close would draw a fill the
    # backtest never took.
    buys = prices.loc[prices["Buy_Next_Open"]]
    sells = prices.loc[prices["Sell_Next_Open"]]
    nominal_axis.scatter(buys["Date"], buys["Open"], marker="^", color="green", label="Buy")
    nominal_axis.scatter(sells["Date"], sells["Open"], marker="v", color="red", label="Sell")
    research_axis.set_title(f"{ticker} SMA Crossover Backtest")
    nominal_axis.set_xlabel("Date")
    nominal_axis.set_ylabel("Nominal price (USD)")
    nominal_axis.grid(True, alpha=0.3)
    nominal_axis.legend()

    save_figure(figure, cache_path("phase0_aapl_ma_crossover.png"))


if __name__ == "__main__":
    try:
        main()
    except UnadjustedDataUnavailable as error:
        raise SystemExit(str(error)) from error
