"""Augmented Dickey-Fuller stationarity checks for cached market data."""

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

from data import download_market_data

TICKERS = ["AAPL", "MSFT", "GOOGL"]
ADF_SIGNIFICANCE_LEVEL = 0.05


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


def main():
    market_data = download_market_data(TICKERS)
    summary_rows = []

    for ticker in TICKERS:
        prices = market_data[market_data["Ticker"] == ticker].sort_values("Date")
        closing_prices = prices["Close"].dropna()
        log_returns = np.log(closing_prices).diff().dropna()

        summary_rows.append(adf_summary(closing_prices, ticker, "Price"))
        summary_rows.append(adf_summary(log_returns, ticker, "Log return"))

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
