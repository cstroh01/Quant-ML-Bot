"""Small reusable helpers for downloading market data."""

from pathlib import Path

import pandas as pd
import yfinance as yf

# Single source of truth for where generated artifacts live. Every script
# writes here rather than rebuilding the same relative path by hand, so the
# layout can change in one place. data/cache/ is already gitignored: it holds
# regenerable output, never repository content.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"


def cache_path(name: str) -> Path:
    """Return a path inside data/cache/, creating the directory if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def download_market_data(
    tickers: list[str], period: str = "2y", force_refresh: bool = False
) -> pd.DataFrame:
    """Download daily adjusted OHLCV data and return it in tidy form."""
    if not tickers:
        raise ValueError("At least one ticker is required.")

    path = cache_path(f"{'-'.join(tickers)}_{period}.csv")

    if path.exists() and not force_refresh:
        cached = pd.read_csv(path, parse_dates=["Date"])
        # A cache file is only usable if it actually holds every ticker asked
        # for. A truncated or interrupted write would otherwise be read back
        # as if it were complete, and the error would surface much later as a
        # confusing empty-slice bug in whichever script consumed it.
        if set(tickers).issubset(cached["Ticker"].unique()):
            return cached

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
        try:
            ticker_data = downloaded_data[ticker].copy()
        except KeyError as error:
            # yfinance drops unknown symbols silently rather than raising, so
            # naming the bad ticker here turns a bare KeyError into a message
            # that says which symbol was actually the problem.
            raise RuntimeError(
                f"yfinance returned no data for ticker {ticker!r}."
            ) from error
        ticker_data.columns.name = None
        ticker_data = ticker_data.reset_index()
        ticker_data["Ticker"] = ticker
        tidy_frames.append(ticker_data)

    market_data = (
        pd.concat(tidy_frames, ignore_index=True)
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )

    # Write to a temporary file and rename it into place. A rename is atomic,
    # so an interrupted run leaves the previous good cache intact instead of a
    # half-written file that later runs would happily read as valid.
    temporary_path = path.with_suffix(".csv.tmp")
    market_data.to_csv(temporary_path, index=False)
    temporary_path.replace(path)
    return market_data
