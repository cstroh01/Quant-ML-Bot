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
from tearsheet_payload import recorded_tearsheet_payload
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

    return BacktestTearsheetResponse(**recorded_tearsheet_payload(
        prices, trade_log, baselines, ticker=ticker, short_window=short_window,
        long_window=long_window, commission=commission, slippage_bps=slippage_bps,
        starting_capital=STARTING_CAPITAL, liquidate_at_end=LIQUIDATE_AT_END,
        dividend_disclosure=pay_date_disclosure(prices.attrs),
    ))
