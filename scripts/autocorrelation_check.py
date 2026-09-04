"""Autocorrelation checks for daily log returns."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.tsa.stattools import acf

from data import download_market_data

TICKERS = ["AAPL", "MSFT", "GOOGL"]
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


def main() -> None:
    """Download data, print ACF values, and save ACF plots."""
    market_data = download_market_data(TICKERS)
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
