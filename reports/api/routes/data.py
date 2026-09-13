"""Data and market session inspector API endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from scipy.stats import kurtosis, skew

# Ensure repo root and scripts are in path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from constants import TRADING_DAYS_PER_YEAR
from data import CACHE_DIR, find_missing_bars
from reports.api.schemas import BarData, GapsResponse, MarketStatsResponse

router = APIRouter(prefix="/api/data", tags=["data"])


def get_cache_dir() -> Path:
    """The directory every route reads market-data CSVs from.

    A FastAPI dependency, so tests can inject a directory of generated
    fixtures through `app.dependency_overrides` instead of reading the
    developer's gitignored cache (spec 018, finding 57).
    """
    return CACHE_DIR


def get_cached_ticker_data(ticker: str, cache_dir: Path) -> pd.DataFrame:
    """Load cached OHLCV data for a ticker from `cache_dir`, without network access."""
    # Priority: 10y file, then 2y files
    preferred_files = [
        "AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv",
        "AAPL-MSFT-GOOGL_2y.csv",
        f"{ticker}_2y.csv",
    ]

    for filename in preferred_files:
        path = cache_dir / filename
        if path.exists():
            df = pd.read_csv(path, parse_dates=["Date"])
            if "Ticker" in df.columns:
                ticker_df = df[df["Ticker"] == ticker].copy()
                if not ticker_df.empty:
                    return ticker_df.sort_values("Date").reset_index(drop=True)
            elif filename.startswith(ticker):
                return df.sort_values("Date").reset_index(drop=True)

    # Search all csv files in cache
    for path in cache_dir.glob("*.csv"):
        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            if "Ticker" in df.columns:
                ticker_df = df[df["Ticker"] == ticker].copy()
                if not ticker_df.empty:
                    return ticker_df.sort_values("Date").reset_index(drop=True)
        except Exception:
            continue

    raise HTTPException(status_code=404, detail=f"No cached data found for ticker {ticker}")


@router.get("/tickers", response_model=list[str])
def list_available_tickers(cache_dir: Path = Depends(get_cache_dir)) -> list[str]:
    """List tickers present in local cache."""
    tickers = set()
    for path in cache_dir.glob("*.csv"):
        try:
            df = pd.read_csv(path, nrows=50)
            if "Ticker" in df.columns:
                full_df = pd.read_csv(path, usecols=["Ticker"])
                tickers.update(full_df["Ticker"].dropna().unique())
        except Exception:
            continue
    if not tickers:
        # Fallback to known cached universe
        return ["AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"]
    return sorted(tickers)


@router.get("/ohlcv", response_model=list[BarData])
def get_ohlcv(
    ticker: str = Query("AAPL", description="Ticker symbol"),
    cache_dir: Path = Depends(get_cache_dir),
) -> list[BarData]:
    """Return OHLCV candlestick bars formatted for Lightweight Charts."""
    df = get_cached_ticker_data(ticker.upper(), cache_dir)
    bars = []
    for _, row in df.iterrows():
        # Ensure session date format YYYY-MM-DD
        date_str = pd.Timestamp(row["Date"]).strftime("%Y-%m-%d")
        bars.append(
            BarData(
                time=date_str,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        )
    return bars


@router.get("/stats", response_model=MarketStatsResponse)
def get_market_stats(
    ticker: str = Query("AAPL", description="Ticker symbol"),
    cache_dir: Path = Depends(get_cache_dir),
) -> MarketStatsResponse:
    """Return statistical distribution and drawdown metrics matching return_stats.py."""
    df = get_cached_ticker_data(ticker.upper(), cache_dir)
    closes = df["Close"]
    log_returns = np.log(closes / closes.shift(1)).dropna()

    if len(log_returns) < 2:
        raise HTTPException(status_code=400, detail="Insufficient bars for statistical calculation")

    ann_vol = float(log_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    sk = float(skew(log_returns))
    kurt = float(kurtosis(log_returns))

    # Reconstruct cumulative price index
    cum_idx = np.exp(log_returns.cumsum())
    cum_idx = pd.concat([pd.Series([1.0], index=[df.index[0]]), cum_idx])
    running_max = cum_idx.cummax()
    drawdown = cum_idx / running_max - 1.0

    trough_idx = drawdown.idxmin()
    max_dd = float(drawdown.min())

    peak_candidates = cum_idx[(cum_idx.index < trough_idx) & (cum_idx == running_max)]
    peak_idx = peak_candidates.index[-1] if not peak_candidates.empty else df.index[0]

    peak_date = pd.Timestamp(df.loc[peak_idx, "Date"]).strftime("%Y-%m-%d") if peak_idx in df.index else None
    trough_date = pd.Timestamp(df.loc[trough_idx, "Date"]).strftime("%Y-%m-%d") if trough_idx in df.index else None

    return MarketStatsResponse(
        ticker=ticker.upper(),
        bars_count=len(df),
        start_date=pd.Timestamp(df["Date"].iloc[0]).strftime("%Y-%m-%d"),
        end_date=pd.Timestamp(df["Date"].iloc[-1]).strftime("%Y-%m-%d"),
        annual_volatility=ann_vol,
        skewness=sk,
        excess_kurtosis=kurt,
        max_drawdown=max_dd,
        peak_date=peak_date,
        trough_date=trough_date,
    )


@router.get("/gaps", response_model=GapsResponse)
def get_missing_bars(
    ticker: str = Query("AAPL", description="Ticker symbol"),
    cache_dir: Path = Depends(get_cache_dir),
) -> GapsResponse:
    """Report NYSE calendar sessions missing a bar (FR-009)."""
    df = get_cached_ticker_data(ticker.upper(), cache_dir)
    if "Ticker" not in df.columns:
        df["Ticker"] = ticker.upper()

    missing_df = find_missing_bars(df)
    missing_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in missing_df["Date"]]

    return GapsResponse(
        ticker=ticker.upper(),
        total_missing_bars=len(missing_dates),
        sample_dates=missing_dates[:15],
    )
