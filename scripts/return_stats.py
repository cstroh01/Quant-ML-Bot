"""Phase 0 return statistics and distribution plots for cached market data."""

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
from data import cache_path, download_market_data
from plotting import plt, save_figure

TICKERS = ["AAPL", "MSFT", "GOOGL"]


def daily_log_returns(prices: pd.DataFrame) -> pd.Series:
    """Return the daily log returns of one ticker's closing prices.

    Log returns are used because they add across time: the two-day return is
    the sum of the two daily returns, which simple percentage returns are not.
    """
    return np.log(prices["Close"] / prices["Close"].shift(1)).dropna()


def cumulative_price_index(prices: pd.DataFrame, returns: pd.Series) -> pd.Series:
    """Rebuild a growth-of-one price index from a series of log returns.

    The index is anchored at 1.0 on the first close, not on the first return.
    That first close is itself a candidate peak, and anchoring later would
    silently ignore a drawdown that began on day one.
    """
    return pd.concat(
        [pd.Series([1.0], index=[prices.index[0]]), np.exp(returns.cumsum())]
    )


def annualize(returns: pd.Series) -> tuple[float, float]:
    """Return the annualized mean return and volatility of a daily series."""
    # Mean scales with time, standard deviation with its square root — the
    # standard independent-increments assumption behind this convention.
    annualized_return = returns.mean() * TRADING_DAYS_PER_YEAR
    annualized_volatility = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return annualized_return, annualized_volatility


def main():
    market_data = download_market_data(TICKERS)

    return_series = {}
    summary_rows = []

    for ticker in TICKERS:
        prices = market_data[market_data["Ticker"] == ticker].sort_values("Date")
        returns = daily_log_returns(prices)
        return_series[ticker] = returns
        dates = prices["Date"]

        price_index = cumulative_price_index(prices, returns)
        running_max = price_index.cummax()
        drawdown = price_index / running_max - 1
        trough_index = drawdown.idxmin()

        # The peak is the most recent high water mark strictly before the
        # trough, which is what makes the pair a real peak-to-trough decline
        # rather than two unrelated dates.
        peak_candidates = price_index[
            (price_index.index < trough_index) & (price_index == running_max)
        ]
        peak_index = peak_candidates.index[-1] if not peak_candidates.empty else None

        annualized_return, annualized_volatility = annualize(returns)
        summary_rows.append(
            {
                "Ticker": ticker,
                "Mean Daily Log Return": returns.mean(),
                "Daily Std Dev": returns.std(),
                "Annualized Volatility": annualized_volatility,
                # Skew measures lopsidedness; excess kurtosis measures how much
                # more weight the tails carry than a normal distribution would.
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
        f"\nAnnualized return and Sharpe ratio "
        f"(risk-free rate: {RISK_FREE_RATE_ANNUAL:.2%}):"
    )
    for ticker, returns in return_series.items():
        annualized_return, annualized_volatility = annualize(returns)
        # Sharpe is excess return per unit of volatility. Subtracting the
        # risk-free rate is what makes it a measure of skill rather than a
        # measure of simply having been invested.
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
        # Overlaying a normal curve fitted to the same mean and standard
        # deviation is what makes the fat tails visible: the histogram has
        # more weight far from centre than this reference curve allows.
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
    save_figure(figure, cache_path("phase0_return_distributions.png"))


if __name__ == "__main__":
    main()
