"""Phase 0 return statistics and distribution plots for cached market data."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

TICKERS = ["AAPL", "MSFT", "GOOGL"]
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE_ANNUAL = 0.0378  # 3-month T-bill, ~Sept 2026 snapshot — not live-fetched, revisit periodically


def main():
    project_root = Path(__file__).resolve().parents[1]
    input_path = project_root / "data" / "cache" / "AAPL-MSFT-GOOGL_2y.csv"
    output_path = project_root / "data" / "cache" / "phase0_return_distributions.png"

    market_data = pd.read_csv(input_path, parse_dates=["Date"])
    return_series = {}
    summary_rows = []

    for ticker in TICKERS:
        prices = market_data[market_data["Ticker"] == ticker].sort_values("Date")
        returns = np.log(prices["Close"] / prices["Close"].shift(1)).dropna()
        return_series[ticker] = returns
        dates = prices.loc[returns.index, "Date"]

        cumulative_index = np.exp(returns.cumsum())
        running_max = cumulative_index.cummax()
        drawdown = cumulative_index / running_max - 1
        trough_index = drawdown.idxmin()
        peak_candidates = cumulative_index[
            (cumulative_index.index < trough_index) & (cumulative_index == running_max)
        ]
        peak_index = peak_candidates.index[-1] if not peak_candidates.empty else None

        daily_mean = returns.mean()
        daily_std = returns.std()
        annualized_volatility = daily_std * np.sqrt(TRADING_DAYS_PER_YEAR)
        summary_rows.append(
            {
                "Ticker": ticker,
                "Mean Daily Log Return": daily_mean,
                "Daily Std Dev": daily_std,
                "Annualized Volatility": annualized_volatility,
                "Skew": skew(returns),
                "Excess Kurtosis": kurtosis(returns),
                "Max Drawdown": drawdown.min(),
                "Peak Date": (
                    dates.loc[peak_index] if peak_index is not None else pd.NaT
                ),
                "Trough Date": dates.loc[trough_index],
            }
        )

    summary = pd.DataFrame(summary_rows).set_index("Ticker")
    print("Daily log-return summary:")
    print(
        summary.to_string(
            float_format=lambda value: f"{value:.6f}",
            formatters={"Max Drawdown": lambda value: f"{value:.2%}"},
        )
    )

    print(
        "\nAnnualized return and Sharpe ratio (risk-free rate: RISK_FREE_RATE_ANNUAL):"
    )
    for ticker, returns in return_series.items():
        annualized_return = returns.mean() * TRADING_DAYS_PER_YEAR
        annualized_volatility = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        sharpe_ratio = (
            annualized_return - RISK_FREE_RATE_ANNUAL
        ) / annualized_volatility
        print(
            f"{ticker}: annualized return = {annualized_return:.6f}, "
            f"Sharpe ratio = {sharpe_ratio:.6f}"
        )

    figure, axes = plt.subplots(1, len(TICKERS), figsize=(15, 5), squeeze=False)
    for axis, ticker in zip(axes[0], TICKERS):
        returns = return_series[ticker]
        daily_mean = returns.mean()
        daily_std = returns.std()
        axis.hist(
            returns,
            bins=35,
            density=True,
            alpha=0.7,
            color="steelblue",
            edgecolor="white",
            label="Daily log returns",
        )
        x_values = np.linspace(
            daily_mean - 4 * daily_std, daily_mean + 4 * daily_std, 300
        )
        axis.plot(
            x_values,
            norm.pdf(x_values, loc=daily_mean, scale=daily_std),
            color="darkred",
            linewidth=2,
            label="Normal reference",
        )
        axis.set_title(ticker)
        axis.set_xlabel("Daily log return")
        axis.set_ylabel("Density")
        axis.grid(True, alpha=0.3)
        axis.legend()

    figure.suptitle("Daily Log-Return Distributions")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    print(f"\nSaved plot to: {output_path}")


if __name__ == "__main__":
    main()
