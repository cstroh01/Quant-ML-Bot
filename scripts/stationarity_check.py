"""Augmented Dickey-Fuller stationarity checks for cached market data."""

from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.tsa.stattools import adfuller
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


def main(*, clock=lambda: datetime.now(timezone.utc), root: Path = REPO_ROOT):
    """Print the ADF and ACF panel; the Rule 11 stamp and register reference come before any figure."""
    market_data = download_market_data(TICKERS, period=PERIOD)
    for line in provenance_stamp(cache_path(_cache_key(TICKERS, PERIOD)), root=root, clock=clock,
                                 data_end=market_data["Date"].max()):
        print(line)
    print(LIMITATIONS_REFERENCE)
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
