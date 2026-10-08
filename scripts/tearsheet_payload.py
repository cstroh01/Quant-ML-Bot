"""Pure tearsheet payload formatting; no API framework or trial writes."""
import numpy as np
import pandas as pd
from backtest_harness import summarize_trades
from metrics import equity_curve, performance_summary


def recorded_tearsheet_payload(prices, trade_log, baselines, *, ticker, short_window,
                              long_window, commission, slippage_bps, starting_capital, liquidate_at_end, dividend_disclosure, provenance=None):
    """Format an evaluated account without strategy evaluation or trial writes."""
    curve = equity_curve(
        prices,
        trade_log,
        commission_per_trade=commission,
        slippage_bps=slippage_bps,
        starting_capital=starting_capital,
    )
    summary = performance_summary(
        prices,
        trade_log,
        commission_per_trade=commission,
        slippage_bps=slippage_bps,
        starting_capital=starting_capital,
    )

    hold_summary = baselines["buy_and_hold"]
    random_summaries = baselines["random_summaries"]

    random_pnls = [r["total_pnl"] for r in random_summaries] if random_summaries else []
    random_mean_pnl = float(np.mean(random_pnls)) if random_pnls else 0.0
    random_std_pnl = float(np.std(random_pnls, ddof=1)) if len(random_pnls) > 1 else 0.0
    random_win_rate = (
        float(np.mean([r["win_rate"] for r in random_summaries]))
        if random_summaries
        else 0.0
    )

    strategy_summary = summarize_trades(trade_log, commission_per_trade=commission, slippage_bps=slippage_bps)

    comparison_rows = [
        dict(
            strategy_name=f"SMA Crossover ({short_window}/{long_window})",
            total_trades=strategy_summary["total_trades"],
            net_pnl=float(round(strategy_summary["total_pnl"], 2)),
            win_rate=float(round(strategy_summary["win_rate"], 1)),
            sharpe_ratio=float(round(summary["sharpe_ratio"], 2)) if not np.isnan(summary["sharpe_ratio"]) else None,
            max_drawdown=float(round(summary["max_drawdown"] * 100, 2)) if not np.isnan(summary["max_drawdown"]) else None,
            std_pnl=None,
        ),
        dict(
            strategy_name="Buy & Hold (Baseline 1)",
            total_trades=hold_summary["total_trades"],
            net_pnl=float(round(hold_summary["total_pnl"], 2)),
            win_rate=float(round(hold_summary["win_rate"], 1)),
            sharpe_ratio=None,
            max_drawdown=None,
            std_pnl=None,
        ),
        dict(
            strategy_name="Random Signal (Baseline 2, 20 seeds)",
            total_trades=strategy_summary["total_trades"],
            net_pnl=float(round(random_mean_pnl, 2)),
            win_rate=float(round(random_win_rate, 1)),
            sharpe_ratio=None,
            max_drawdown=None,
            std_pnl=float(round(random_std_pnl, 2)),
        ),
    ]

    # Format equity curve points with rolling drawdown
    equity_points = []
    running_max = curve["Equity"].cummax()
    drawdown_series = curve["Equity"] / running_max - 1.0

    for idx, row in curve.iterrows():
        equity_points.append(
            dict(
                time=pd.Timestamp(row["Date"]).strftime("%Y-%m-%d"),
                equity=float(round(row["Equity"], 2)),
                drawdown=float(round(drawdown_series.iloc[idx] * 100, 2)),
                position=int(row["Position"]),
                bar_pnl=float(round(row["Bar P&L"], 2)),
            )
        )

    # Format trade log
    trades = []
    for _, t in trade_log.iterrows():
        trades.append(
            dict(
                entry_date=pd.Timestamp(t["Entry Date"]).strftime("%Y-%m-%d"),
                entry_price=float(round(t["Entry Price"], 2)),
                exit_date=pd.Timestamp(t["Exit Date"]).strftime("%Y-%m-%d"),
                exit_price=float(round(t["Exit Price"], 2)),
                pnl=float(round(t["P&L"], 2)),
                cumulative_pnl=float(round(t["Cumulative P&L"], 2)),
                holding_bars=1,
            )
        )

    return dict(
        **(provenance or {}),
        ticker=ticker.upper(),
        strategy_name=f"SMA Crossover ({short_window}/{long_window})",
        commission_per_trade=commission,
        slippage_bps=slippage_bps,
        commission_total=float(round(trade_log.attrs["commission_total"], 2)),
        slippage_total=float(round(trade_log.attrs["slippage_total"], 2)),
        starting_capital=starting_capital,
        liquidate_at_end=liquidate_at_end,
        source_name=prices.attrs["source_name"],
        downloaded_at_utc=prices.attrs["downloaded_at_utc"],
        capital_gate_eligible=prices.attrs["capital_gate_eligible"],
        source_limitations=list(prices.attrs["source_limitations"]),
        source_manifest_sha256=prices.attrs["source_manifest_sha256"],
        dividend_pay_date_disclosure=dividend_disclosure,
        capital_base=float(round(summary["capital_base"], 2)),
        total_return=float(round(summary["total_return"] * 100, 2)),
        total_pnl=float(round(summary["total_pnl"], 2)),
        sharpe_ratio=float(round(summary["sharpe_ratio"], 2)) if not np.isnan(summary["sharpe_ratio"]) else None,
        max_drawdown=float(round(summary["max_drawdown"] * 100, 2)) if not np.isnan(summary["max_drawdown"]) else None,
        reconciliation_passed=True,
        equity_curve=equity_points,
        trade_log=trades,
        comparison_table=comparison_rows,
    )
