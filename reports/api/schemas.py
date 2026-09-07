"""Pydantic schemas for Quant-ML-Bot Terminal API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class BarData(BaseModel):
    """OHLCV candlestick representation for TradingView Lightweight Charts."""
    time: str = Field(description="Session date YYYY-MM-DD")
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketStatsResponse(BaseModel):
    ticker: str
    bars_count: int
    start_date: str
    end_date: str
    annual_volatility: float
    skewness: float
    excess_kurtosis: float
    max_drawdown: float
    peak_date: str | None = None
    trough_date: str | None = None


class GapsResponse(BaseModel):
    ticker: str
    total_missing_bars: int
    sample_dates: list[str]


class CollinearityEntry(BaseModel):
    feature_set: str
    condition_number: float
    max_vif: float
    max_vif_feature: str
    max_correlation_pair: list[str]
    max_correlation_value: float


class FeatureDiagnosticsResponse(BaseModel):
    ticker: str
    features_levels: list[str]
    features_scale_free: list[str]
    diagnostics: list[CollinearityEntry]
    correlation_matrix: dict[str, dict[str, float]]


class SignificanceEntry(BaseModel):
    estimator: str
    task: str
    test_name: str
    p_value: float
    alpha: float
    passed_screening: bool


class SignificanceResponse(BaseModel):
    ticker: str
    screening_alpha: float
    entries: list[SignificanceEntry]


class TradeRecord(BaseModel):
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    pnl: float
    cumulative_pnl: float
    holding_bars: int = 1


class BaselineComparisonRow(BaseModel):
    strategy_name: str
    total_trades: int
    net_pnl: float
    win_rate: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    std_pnl: float | None = None


class EquityPoint(BaseModel):
    time: str
    equity: float
    drawdown: float
    position: int
    bar_pnl: float


class BacktestTearsheetResponse(BaseModel):
    ticker: str
    strategy_name: str
    commission_per_trade: float
    slippage_bps: float
    capital_base: float
    total_return: float
    total_pnl: float
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    reconciliation_passed: bool
    equity_curve: list[EquityPoint]
    trade_log: list[TradeRecord]
    comparison_table: list[BaselineComparisonRow]


class CapitalGateItem(BaseModel):
    gate_number: int
    title: str
    description: str
    status: str  # "passed" | "in_progress" | "pending"
    details: str
    evidence: str | None = None


class CapitalGateStatusResponse(BaseModel):
    overall_readiness: str
    gates: list[CapitalGateItem]
