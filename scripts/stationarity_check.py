"""Augmented Dickey-Fuller stationarity checks for cached market data."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.stattools import acf

from data import download_market_data

TICKERS = ["AAPL", "MSFT", "GOOGL"]
ADF_SIGNIFICANCE_LEVEL = 0.05
ACF_LAGS = 30
PLOTS_DIRECTORY = Path(__file__).resolve().parent.parent / "plots"


def adf_summary(series: pd.Series, ticker: str, series_type: str) -> dict:
    """Return the ADF statistic, p-value, and verdict for one series."""
    adf_statistic, p_value, *_ = adfuller(series, result_object=False)
    verdict = "Stationary" if p_value < ADF_SIGNIFICANCE_LEVEL else "Non-stationary"
    return {
        "Ticker": ticker,
        "Series": series_type,
        "ADF Statistic": adf_statistic,
        "p-value": p_value,
        "Verdict": verdict,
    }


def save_acf_plot(log_returns: pd.Series, ticker: str):
    """Save an ACF plot for one ticker's log returns."""
    PLOTS_DIRECTORY.mkdir(exist_ok=True)
    figure = plot_acf(log_returns, lags=ACF_LAGS)
    axis = figure.axes[0]
    axis.set_title(f"{ticker} Log-Return Autocorrelation")
    figure.tight_layout()
    figure.savefig(PLOTS_DIRECTORY / f"{ticker.lower()}_log_returns_acf.png")
    plt.close(figure)


def main():
    market_data = download_market_data(TICKERS)
    summary_rows = []

    for ticker in TICKERS:
        prices = market_data[market_data["Ticker"] == ticker].sort_values("Date")
        closing_prices = prices["Close"].dropna()
        log_returns = np.log(closing_prices).diff().dropna()

        summary_rows.append(adf_summary(closing_prices, ticker, "Price"))
        summary_rows.append(adf_summary(log_returns, ticker, "Log return"))
        save_acf_plot(log_returns, ticker)

        autocorrelations = acf(log_returns, nlags=5)
        print(f"{ticker} log-return ACF (lags 1-5):")
        print(
            ", ".join(
                f"lag {lag} = {value:.6f}"
                for lag, value in enumerate(autocorrelations[1:], 1)
            )
        )

    summary = pd.DataFrame(summary_rows)
    print("Augmented Dickey-Fuller stationarity test (5% threshold):")
    print(
        summary.to_string(
            index=False,
            formatters={
                "ADF Statistic": lambda value: f"{value:.6f}",
                "p-value": lambda value: f"{value:.6f}",
            },
        )
    )


if __name__ == "__main__":
    main()
