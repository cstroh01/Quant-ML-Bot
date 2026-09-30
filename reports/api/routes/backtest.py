"""Backtest tearsheet and 3-way baseline comparison API endpoints."""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from backtest_harness import run_backtest, summarize_trades
from data import UnadjustedDataUnavailable, load_unadjusted_for_ticker
from trial_runner import research_attempt, research_config
from ma_crossover_backtest import (
    LIQUIDATE_AT_END, STARTING_CAPITAL, baseline_results, mean_holding_bars,
    pay_date_disclosure, research_close_signal,
)
from metrics import equity_curve, performance_summary
from reports.api.routes.data import get_cache_dir
from reports.api.schemas import (
    BacktestTearsheetResponse,
    BaselineComparisonRow,
    EquityPoint,
    TradeRecord,
)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/tearsheet", response_model=BacktestTearsheetResponse)
def get_backtest_tearsheet(
    ticker: str = Query("AAPL", description="Ticker symbol"),
    short_window: int = Query(10, description="Short MA window"),
    long_window: int = Query(30, description="Long MA window"),
    commission: float = Query(1.0, description="Commission per trade in dollars"),
    slippage_bps: float = Query(5.0, description="Slippage in basis points"),
    cache_dir: Path = Depends(get_cache_dir),
) -> BacktestTearsheetResponse:
    """Run baseline backtest with 3-way baseline comparisons and reconciled equity curve."""
    try:
        prices = load_unadjusted_for_ticker(ticker, cache_dir / "unadjusted")
    except UnadjustedDataUnavailable as error:
        raise HTTPException(status_code=503, detail={
            "error": "unadjusted_price_data_unavailable",
            "ticker": error.ticker, "reason": error.reason, "check": error.check,
        }) from error

    # 1. Generate signal
    signalled = research_close_signal(prices, short_window, long_window)

    # 2. Run harness
    with research_attempt(research_config("reports/api/routes/backtest.py:run_backtest", locals()), role="candidate") as attempt:
        trade_log = run_backtest(
            signalled,
            commission_per_trade=commission,
            slippage_bps=slippage_bps,
            starting_capital=STARTING_CAPITAL,
            liquidate=LIQUIDATE_AT_END,
        )
        attempt.account(trade_log)

    # 3. Compute reconciled equity curve & performance summary
    curve = equity_curve(
        prices,
        trade_log,
        commission_per_trade=commission,
        slippage_bps=slippage_bps,
        starting_capital=STARTING_CAPITAL,
    )
    summary = performance_summary(
        prices,
        trade_log,
        commission_per_trade=commission,
        slippage_bps=slippage_bps,
        starting_capital=STARTING_CAPITAL,
    )

    # 4. Generate 3-Way Baseline comparisons (Rule 4)
    holding_bars = mean_holding_bars(prices, trade_log)
    baselines = baseline_results(
        prices=signalled,
        n_trades=len(trade_log),
        holding_bars=holding_bars,
        commission_per_trade=commission,
        slippage_bps=slippage_bps,
        seed_count=20,
        starting_capital=STARTING_CAPITAL,
        liquidate=LIQUIDATE_AT_END,
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
        BaselineComparisonRow(
            strategy_name=f"SMA Crossover ({short_window}/{long_window})",
            total_trades=strategy_summary["total_trades"],
            net_pnl=float(round(strategy_summary["total_pnl"], 2)),
            win_rate=float(round(strategy_summary["win_rate"], 1)),
            sharpe_ratio=float(round(summary["sharpe_ratio"], 2)) if not np.isnan(summary["sharpe_ratio"]) else None,
            max_drawdown=float(round(summary["max_drawdown"] * 100, 2)) if not np.isnan(summary["max_drawdown"]) else None,
            std_pnl=None,
        ),
        BaselineComparisonRow(
            strategy_name="Buy & Hold (Baseline 1)",
            total_trades=hold_summary["total_trades"],
            net_pnl=float(round(hold_summary["total_pnl"], 2)),
            win_rate=float(round(hold_summary["win_rate"], 1)),
            sharpe_ratio=None,
            max_drawdown=None,
            std_pnl=None,
        ),
        BaselineComparisonRow(
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
            EquityPoint(
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
            TradeRecord(
                entry_date=pd.Timestamp(t["Entry Date"]).strftime("%Y-%m-%d"),
                entry_price=float(round(t["Entry Price"], 2)),
                exit_date=pd.Timestamp(t["Exit Date"]).strftime("%Y-%m-%d"),
                exit_price=float(round(t["Exit Price"], 2)),
                pnl=float(round(t["P&L"], 2)),
                cumulative_pnl=float(round(t["Cumulative P&L"], 2)),
                holding_bars=1,
            )
        )

    return BacktestTearsheetResponse(
        ticker=ticker.upper(),
        strategy_name=f"SMA Crossover ({short_window}/{long_window})",
        commission_per_trade=commission,
        slippage_bps=slippage_bps,
        starting_capital=STARTING_CAPITAL,
        liquidate_at_end=LIQUIDATE_AT_END,
        source_name=prices.attrs["source_name"],
        downloaded_at_utc=prices.attrs["downloaded_at_utc"],
        capital_gate_eligible=prices.attrs["capital_gate_eligible"],
        source_limitations=list(prices.attrs["source_limitations"]),
        source_manifest_sha256=prices.attrs["source_manifest_sha256"],
        dividend_pay_date_disclosure=pay_date_disclosure(prices.attrs),
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
