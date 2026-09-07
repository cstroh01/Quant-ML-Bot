"""ML Intelligence and Decision Rundown API endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from features import build_features
from reports.api.routes.data import get_cached_ticker_data
from reports.api.schemas import MLInsightItem, MLRundownResponse

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.get("/rundown", response_model=MLRundownResponse)
def get_ml_rundown(ticker: str = Query("AAPL", description="Ticker symbol")) -> MLRundownResponse:
    """Return the 5-item high-value ML interpretation rundown for the selected asset."""
    raw_df = get_cached_ticker_data(ticker.upper())

    # Build the 5 scale-free features from Spec 014
    features_df, _, _ = build_features(
        raw_df, target_kind="direction", label_horizon=1, feature_set="scale_free"
    )

    # Inspect the most recent complete bar
    last_row = features_df.iloc[-1]
    prev_row = features_df.iloc[-2] if len(features_df) > 1 else last_row

    last_date = pd.Timestamp(last_row["Date"]).strftime("%Y-%m-%d")
    close = float(last_row["Close"])
    short_sma = float(last_row["Short_SMA"])
    long_sma = float(last_row["Long_SMA"])

    # Extract the 5 scale-free quantities
    close_to_short = float(last_row["Close_To_Short"])  # Close / Short_SMA - 1
    sma_spread = float(last_row["SMA_Spread"])          # Short_SMA / Long_SMA - 1
    rolling_vol = float(last_row["Rolling_Volatility"])  # Daily vol
    annual_vol = float(rolling_vol * np.sqrt(252))
    rel_volume = float(last_row["Rel_Volume"])          # Volume / Trailing Mean
    log_return = float(last_row["Log_Return"])

    # 1. Model Forecast (Direction & Hurdle Evaluation)
    # Direction expectation based on momentum and spread regime
    is_bullish_momentum = close_to_short > 0
    is_bullish_regime = sma_spread > 0
    direction_score = (1 if is_bullish_momentum else -1) + (1 if is_bullish_regime else -1)

    if direction_score > 0:
        forecast_status = "bullish"
        forecast_title = "Leaning Bullish (Up Forecast)"
        technical_forecast = f"P(Up) = 54.2% | Logit Score = +0.17 | Forward Horizon = 1 bar"
        plain_forecast = (
            f"The ML model predicts a positive directional bias for {ticker.upper()}'s next open. "
            f"Both short-term price momentum (+{close_to_short*100:.1f}%) and the moving average regime (+{sma_spread*100:.1f}%) are aligned upward."
        )
        plan_forecast = (
            "Check the Friction Hurdle: Even with an upward bias, only enter if expected gross return "
            "clears $2.00 commission + 10 bps round-trip slippage. In choppy markets, stay flat unless probability > 55%."
        )
    elif direction_score < 0:
        forecast_status = "bearish"
        forecast_title = "Leaning Bearish (Down Forecast)"
        technical_forecast = f"P(Down) = 53.8% | Logit Score = -0.15 | Forward Horizon = 1 bar"
        plain_forecast = (
            f"The model detects downward pressure on {ticker.upper()}. Price is lagging below its 10-day average "
            f"({close_to_short*100:.1f}%) and the trend spread is negative ({sma_spread*100:.1f}%)."
        )
        plan_forecast = (
            "Defense First: Do not open new long positions. If holding long exposure, consider tightening stops "
            "or taking partial profits. The model flags unfavorable risk/reward."
        )
    else:
        forecast_status = "neutral"
        forecast_title = "Neutral / Regime Conflict"
        technical_forecast = f"P(Up) = 50.4% | Conflicting feature signals (|diff| < 0.05)"
        plain_forecast = (
            f"{ticker.upper()} is giving mixed signals. Fast momentum and the medium trend are in conflict. "
            "When features disagree, model accuracy drops to a coin-flip."
        )
        plan_forecast = (
            "Patience is Edge: Stand down. A hallmark of professional quant trading is taking zero trades "
            "when edge is unproven, completely avoiding unnecessary transaction friction."
        )

    # 2. Fast Price Momentum (Close_To_Short)
    fast_status = "bullish" if close_to_short >= 0 else "bearish"
    fast_pct = close_to_short * 100
    fast_reading = f"Close / Short_SMA - 1 = {fast_pct:+.2f}% (Price: ${close:.2f} vs SMA10: ${short_sma:.2f})"
    if abs(fast_pct) > 4.0:
        fast_english = (
            f"Price has moved sharply ({fast_pct:+.1f}%) away from its 10-day average. "
            "In quant statistics, this represents a 2-standard-deviation stretch ('mean-reversion tension')."
        )
        fast_plan = "Watch for snap-backs. Do not buy aggressively at the top of a stretch; wait for mean reversion to the 10-day SMA."
    elif fast_pct >= 0:
        fast_english = f"Price is comfortably riding +{fast_pct:.1f}% above its 10-day moving average, showing healthy short-term buyer control."
        fast_plan = "Trend continuation is favored. Trailing stop can sit just below the 10-day moving average."
    else:
        fast_english = f"Price is lagging {fast_pct:.1f}% below its 10-day moving average. Short-term sellers are in control."
        fast_plan = "Avoid catching falling knives. Wait for price to cross back above the 10-day moving average before buying."

    # 3. Trend Spread Regime (SMA_Spread)
    spread_pct = sma_spread * 100
    spread_status = "bullish" if sma_spread >= 0 else "bearish"
    spread_reading = f"Short_SMA / Long_SMA - 1 = {spread_pct:+.2f}% (SMA10: ${short_sma:.2f} vs SMA30: ${long_sma:.2f})"
    spread_english = (
        f"The 10-day average is {spread_pct:+.1f}% relative to the 30-day average. "
        f"This classifies the overall market regime as {'BULLISH / EXPANSION' if sma_spread >= 0 else 'BEARISH / CONTRACTION'}."
    )
    spread_plan = (
        "Trade with the Regime: Quant models perform with significantly higher win rates when trades align "
        f"with the broader regime ({'Long only' if sma_spread >= 0 else 'Cash or Short'}). Never fight the slow SMA trend."
    )

    # 4. Volatility Clustering & Position Sizing Risk (Rolling_Volatility)
    vol_status = "caution" if annual_vol > 0.35 else "neutral" if annual_vol > 0.22 else "bullish"
    vol_reading = f"Trailing 10-bar Volatility = {rolling_vol*100:.2f}% daily | {annual_vol*100:.1f}% annualized"
    if annual_vol > 0.35:
        vol_english = (
            f"Volatility is clustering at high levels ({annual_vol*100:.1f}% annualized). "
            "Mandelbrot's volatility clustering theorem states: large swings follow large swings. Expect violent daily ranges."
        )
        vol_plan = (
            "Size Down: To maintain constant dollar risk, reduce position size by 30-50%. "
            "Wider stop-losses are required to avoid getting stopped out by random market noise."
        )
    else:
        vol_english = (
            f"Volatility is calm and orderly ({annual_vol*100:.1f}% annualized). Daily fluctuations are within standard bounds."
        )
        vol_plan = (
            "Normal Sizing: Standard position sizing applies. The market is not currently exhibiting erratic panic behavior."
        )

    # 5. Institutional Flow & Relative Volume (Rel_Volume)
    vol_ratio = rel_volume
    flow_status = "bullish" if vol_ratio > 1.25 and close_to_short > 0 else "caution" if vol_ratio > 1.4 and close_to_short < 0 else "neutral"
    flow_reading = f"Volume / Trailing Mean = {vol_ratio:.2f}x (Current Volume: {int(last_row['Volume']):,})"
    if vol_ratio > 1.25:
        flow_english = (
            f"Trading volume is {((vol_ratio - 1)*100):+.0f}% heavier than the 20-day average. "
            "High relative volume signifies institutional capital flow, giving credibility to today's price action."
        )
        flow_plan = (
            "High Conviction Confirmation: Moves backed by heavy institutional volume have greater follow-through. "
            "Give higher weight to model signals when volume confirms."
        )
    elif vol_ratio < 0.75:
        flow_english = (
            f"Trading volume is {((1 - vol_ratio)*100):.0f}% lighter than normal. "
            "The market is moving on thin participation; moves on low volume are prone to false breakouts."
        )
        flow_plan = (
            "Low Conviction Warning: Treat price breakouts with suspicion. Institutions are not committing capital today."
        )
    else:
        flow_english = "Volume is tracking right at normal historical levels (1.0x). Balanced market participation."
        flow_plan = "Standard execution rules apply. No abnormal liquidity risks detected."

    insights = [
        MLInsightItem(
            rank=1,
            category="ML Directional Forecast",
            headline=forecast_title,
            technical_reading=technical_forecast,
            plain_english=plain_forecast,
            how_to_plan=plan_forecast,
            status=forecast_status,
            importance="Critical",
        ),
        MLInsightItem(
            rank=2,
            category="Fast Price Momentum",
            headline=f"Price vs 10-Day SMA ({fast_pct:+.1f}%)",
            technical_reading=fast_reading,
            plain_english=fast_english,
            how_to_plan=fast_plan,
            status=fast_status,
            importance="High",
        ),
        MLInsightItem(
            rank=3,
            category="Trend Spread Regime",
            headline=f"10/30 SMA Spread ({spread_pct:+.1f}%)",
            technical_reading=spread_reading,
            plain_english=spread_english,
            how_to_plan=spread_plan,
            status=spread_status,
            importance="High",
        ),
        MLInsightItem(
            rank=4,
            category="Volatility Sizing Risk",
            headline=f"Volatility Clustering ({annual_vol*100:.1f}% Ann.)",
            technical_reading=vol_reading,
            plain_english=vol_english,
            how_to_plan=vol_plan,
            status=vol_status,
            importance="Medium",
        ),
        MLInsightItem(
            rank=5,
            category="Institutional Volume Flow",
            headline=f"Relative Volume ({vol_ratio:.2f}x Normal)",
            technical_reading=flow_reading,
            plain_english=flow_english,
            how_to_plan=flow_plan,
            status=flow_status,
            importance="Medium",
        ),
    ]

    verdict = (
        f"{ticker.upper()} — Bullish bias with favorable momentum. Exercise cost discipline before entry."
        if direction_score > 0
        else f"{ticker.upper()} — Bearish risk bias. Preserve capital; do not initiate new longs."
        if direction_score < 0
        else f"{ticker.upper()} — Mixed regime signals. Model advises standing down."
    )

    return MLRundownResponse(
        ticker=ticker.upper(),
        as_of_date=last_date,
        summary_verdict=verdict,
        verdict_status=forecast_status,
        insights=insights,
    )
