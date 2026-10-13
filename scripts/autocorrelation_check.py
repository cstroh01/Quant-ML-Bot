"""Autocorrelation checks for daily log returns."""

from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.tsa.stattools import acf

from data import _cache_key, cache_path, download_market_data
from disclosure import LIMITATIONS, provenance_stamp

TICKERS = ["AAPL", "MSFT", "GOOGL"]
PERIOD = "2y"
REPO_ROOT = Path(__file__).resolve().parents[1]
# Spec 038 D-4: script panels carry a one-line, same-surface reference to the register.
LIMITATIONS_REFERENCE = (
    f"Limitations (Rule 16): docs/SCOPE-V1.md §6 lists {len(LIMITATIONS)} limitations that "
    "bound every figure below.")
PLOTS_DIRECTORY = Path(__file__).resolve().parent.parent / "plots"
TABLE_LAGS = 5
PLOT_LAGS = 30


def compute_log_returns(market_data: pd.DataFrame, ticker: str) -> pd.Series:
    """Compute daily log returns for one ticker."""
    prices = market_data[market_data["Ticker"] == ticker].sort_values("Date")
    return np.log(prices["Close"].dropna()).diff().dropna()


def calculate_acf_values(log_returns: pd.Series) -> np.ndarray:
    """Calculate autocorrelation values for lags one through five."""
    return acf(log_returns, nlags=TABLE_LAGS)[1:]


def print_acf_table(acf_rows: list[dict[str, object]]) -> None:
    """Print the numeric ACF table."""
    table = pd.DataFrame(acf_rows, columns=["Ticker", "Lag", "ACF value"])
    print(table.to_string(index=False, formatters={"ACF value": "{:.6f}".format}))


def save_acf_plot(log_returns: pd.Series, ticker: str) -> None:
    """Save a 30-lag ACF plot for one ticker."""
    PLOTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    figure = plot_acf(log_returns, lags=PLOT_LAGS)
    figure.axes[0].set_title(f"{ticker} Log-Return Autocorrelation")
    figure.tight_layout()
    figure.savefig(PLOTS_DIRECTORY / f"{ticker}_acf.png")
    plt.close(figure)


def main(*, clock=lambda: datetime.now(timezone.utc), root: Path = REPO_ROOT) -> None:
    """Download data, print ACF values, and save ACF plots.

    The Rule 11 stamp (the cache file read, with its SHA-256) and the register reference print
    before any figure or plot (spec 038 T031).
    """
    market_data = download_market_data(TICKERS, period=PERIOD)
    for line in provenance_stamp(cache_path(_cache_key(TICKERS, PERIOD)), root=root, clock=clock,
                                 data_end=market_data["Date"].max()):
        print(line)
    print(LIMITATIONS_REFERENCE)
    acf_rows = []

    for ticker in TICKERS:
        log_returns = compute_log_returns(market_data, ticker)
        acf_values = calculate_acf_values(log_returns)
        acf_rows.extend(
            {"Ticker": ticker, "Lag": lag, "ACF value": value}
            for lag, value in enumerate(acf_values, start=1)
        )
        save_acf_plot(log_returns, ticker)

    print_acf_table(acf_rows)


if __name__ == "__main__":
    main()
