"""Pydantic schemas for Quant-ML-Bot Terminal API."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class NotComputed(BaseModel):
    """A quantity no computation produced, and why (spec 018).

    Distinct from missing data, which keeps its 404: the input exists, but
    nothing is wired to compute this value from it. Never rendered as zero.
    """

    status: Literal["not_computed"] = "not_computed"
    reason: str = Field(min_length=1)


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


class SignificanceResponse(NotComputed):
    """Paired significance screening: not computed for any ticker until saved runs exist (finding 45)."""

    ticker: str


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


GateEvidenceStatus = Literal["passed", "failed", "stale", "unknown"]


class CapitalGateItem(BaseModel):
    gate_number: int
    title: str
    description: str
    status: GateEvidenceStatus
    details: str
    evidence: str | None = None

    @model_validator(mode="after")
    def _evidence_backs_every_known_state(self) -> CapitalGateItem:
        """Only `unknown` may stand without an evidence reference (finding 47)."""
        if self.status != "unknown" and not self.evidence:
            raise ValueError(f"gate status {self.status!r} requires an evidence reference")
        return self


class CapitalGateStatusResponse(BaseModel):
    overall_readiness: str
    test_run: NotComputed
    gates: list[CapitalGateItem]


class MLInsightItem(BaseModel):
    rank: int
    category: str
    headline: str
    technical_reading: str
    plain_english: str
    how_to_plan: str
    status: str  # "bullish" | "bearish" | "neutral" | "caution"
    importance: str  # "Critical" | "High" | "Medium"


class MLRundownResponse(BaseModel):
    """Indicator rule readings; the model forecast is not computed (finding 46)."""
    ticker: str
    as_of_date: str
    model_forecast: NotComputed
    summary_verdict: str
    verdict_status: str
    insights: list[MLInsightItem]
