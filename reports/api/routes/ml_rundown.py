"""Indicator rule readings for the terminal's right-hand pane.

No fitted model is wired into this endpoint, so the model forecast is reported
as not computed (spec 018, finding 46). The endpoint used to return a literal
forecast probability and logit score, and described two indicator sign tests
as a model's prediction. Every item is an indicator rule reading.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from features import build_features
from reports.api.routes.data import get_cache_dir, get_cached_ticker_data
from reports.api.schemas import MLInsightItem, MLRundownResponse, NotComputed

router = APIRouter(prefix="/api/ml", tags=["ml"])

FORECAST_NOT_COMPUTED = (
    "No fitted model is wired to this endpoint, so no forecast probability or score "
    "is shown. Fitted-model inference, with its timestamp, feature version, horizon "
    "and calibration, arrives with the experiment run store (audit work order 3)."
)


@router.get("/rundown", response_model=MLRundownResponse)
def get_ml_rundown(
    ticker: str = Query("AAPL", description="Ticker symbol"),
    cache_dir: Path = Depends(get_cache_dir),
) -> MLRundownResponse:
    """Return the model-forecast status and five indicator rule readings for the selected asset."""
    raw_df = get_cached_ticker_data(ticker.upper(), cache_dir)

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

    # 1. SMA rule agreement: the signs of two trend indicators, not a forecast
    is_bullish_momentum = close_to_short > 0
    is_bullish_regime = sma_spread > 0
    direction_score = (1 if is_bullish_momentum else -1) + (1 if is_bullish_regime else -1)
    technical_forecast = (
        f"Close / Short_SMA - 1 = {close_to_short*100:+.2f}% | Short_SMA / Long_SMA - 1 = {sma_spread*100:+.2f}%"
    )

    if direction_score > 0:
        forecast_status = "bullish"
        forecast_title = "Both Trend Rules Read Up"
        plain_forecast = (
            f"{ticker.upper()} closed above its 10-day average, and the 10-day average is above the 30-day. "
            "Two rules agree; that is not an estimate of the next move."
        )
    elif direction_score < 0:
        forecast_status = "bearish"
        forecast_title = "Both Trend Rules Read Down"
        plain_forecast = (
            f"{ticker.upper()} closed below its 10-day average, and the 10-day average is below the 30-day. "
            "Two rules agree; that is not an estimate of the next move."
        )
    else:
        forecast_status = "neutral"
        forecast_title = "Trend Rules Disagree"
        plain_forecast = (
            f"For {ticker.upper()}, the close-versus-10-day rule and the 10-day-versus-30-day rule point in opposite directions."
        )
    plan_forecast = "No model has scored this bar, and this endpoint does not measure whether the rules predict returns."

    # 2. Fast Price Momentum (Close_To_Short)
    fast_status = "bullish" if close_to_short >= 0 else "bearish"
    fast_pct = close_to_short * 100
    fast_reading = f"Close / Short_SMA - 1 = {fast_pct:+.2f}% (Price: ${close:.2f} vs SMA10: ${short_sma:.2f})"
    if abs(fast_pct) > 4.0:
        fast_english = (
            f"Price has moved sharply ({fast_pct:+.1f}%) away from its 10-day average, "
            "beyond this rule's fixed 4% stretch line."
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
        "Trade with the Regime: this rule reads the broader regime as "
        f"{'Long only' if sma_spread >= 0 else 'Cash or Short'}. Its win rate is not measured here."
    )

    # 4. Volatility Clustering & Position Sizing Risk (Rolling_Volatility)
    vol_status = "caution" if annual_vol > 0.35 else "neutral" if annual_vol > 0.22 else "bullish"
    vol_reading = f"Trailing 10-bar Volatility = {rolling_vol*100:.2f}% daily | {annual_vol*100:.1f}% annualized"
    if annual_vol > 0.35:
        vol_english = (
            f"Volatility is high ({annual_vol*100:.1f}% annualized), above this rule's fixed 35% line. "
            "Recent daily ranges have been wide."
        )
        vol_plan = (
            "Size Down: To maintain constant dollar risk, reduce position size as volatility rises. "
            "Wider stop-losses are required to avoid getting stopped out by random market noise."
        )
    else:
        vol_english = (
            f"Volatility is calm and orderly ({annual_vol*100:.1f}% annualized). Daily fluctuations are within standard bounds."
        )
        vol_plan = (
            "Normal Sizing: Standard position sizing applies. The market is not currently exhibiting erratic panic behavior."
        )

    # 5. Relative Volume (Rel_Volume): a ratio to its trailing mean, nothing more
    vol_ratio = rel_volume
    flow_status = "bullish" if vol_ratio > 1.25 and close_to_short > 0 else "caution" if vol_ratio > 1.4 and close_to_short < 0 else "neutral"
    flow_reading = f"Volume / Trailing Mean = {vol_ratio:.2f}x (Current Volume: {int(last_row['Volume']):,})"
    flow_english = f"Today's volume is {vol_ratio:.2f}x its trailing average."
    flow_plan = "Relative volume describes participation only. It does not identify who traded or confirm a price move."

    insights = [
        MLInsightItem(
            rank=1,
            category="SMA Rule Agreement",
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
            category="Relative Volume",
            headline=f"Relative Volume ({vol_ratio:.2f}x Normal)",
            technical_reading=flow_reading,
            plain_english=flow_english,
            how_to_plan=flow_plan,
            status=flow_status,
            importance="Medium",
        ),
    ]

    verdict = (
        f"{ticker.upper()} — both trend rules read up."
        if direction_score > 0
        else f"{ticker.upper()} — both trend rules read down."
        if direction_score < 0
        else f"{ticker.upper()} — trend rules disagree."
    )

    return MLRundownResponse(
        ticker=ticker.upper(),
        as_of_date=last_date,
        model_forecast=NotComputed(reason=FORECAST_NOT_COMPUTED),
        summary_verdict=verdict,
        verdict_status=forecast_status,
        insights=insights,
    )
