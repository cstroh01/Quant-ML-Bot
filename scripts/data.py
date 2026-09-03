"""Small reusable helpers for downloading market data."""

import pandas as pd
import yfinance as yf
from pathlib import Path


def download_market_data(
    tickers: list[str], period: str = "2y", force_refresh: bool = False
) -> pd.DataFrame:
    """Download daily adjusted OHLCV data and return it in tidy form."""
    cache_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "cache"
        / f"{'-'.join(tickers)}_{period}.csv"
    )

    if cache_path.exists() and not force_refresh:
        return pd.read_csv(cache_path, parse_dates=["Date"])

    downloaded_data = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
    )

    if downloaded_data.empty:
        raise RuntimeError(
            "yfinance returned no data. Check the symbols or connection."
        )

    # yfinance returns one nested column block per ticker. Flattening each
    # block into its own table makes filtering easier than using a MultiIndex.
    tidy_frames = []
    for ticker in tickers:
        ticker_data = downloaded_data[ticker].copy()
        ticker_data.columns.name = None
        ticker_data = ticker_data.reset_index()
        ticker_data["Ticker"] = ticker
        tidy_frames.append(ticker_data)

    market_data = (
        pd.concat(tidy_frames, ignore_index=True)
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    market_data.to_csv(cache_path, index=False)
    return market_data
