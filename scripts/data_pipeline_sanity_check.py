"""Phase 0 sanity check for downloading and inspecting daily market data.

This is deliberately a script rather than a reusable module. The goal in
Phase 0 is to make the data pipeline visible and easy to inspect before
adding classes, configuration files, or command-line options.
"""

from data import cache_path, download_market_data
from plotting import plt, save_figure

# Keeping scripts in scripts/ makes small, runnable development utilities
# separate from reusable application code. It also gives us a natural place
# for this one-off Phase 0 check without adding project structure too early.
TICKERS = ["AAPL", "MSFT", "GOOGL"]
PLOT_TICKER = "AAPL"


def main():
    # Adjusted prices account for splits and dividends, so a split does not
    # look like a huge artificial loss in a backtest.
    market_data = download_market_data(TICKERS)

    print("Shape:")
    print(market_data.shape)

    print("\nData types:")
    print(market_data.dtypes)

    print("\nFirst five rows:")
    print(market_data.head())

    # isna() creates a True/False table identifying missing values. Summing it
    # counts missing values in each column, which is more informative than a
    # single True/False result when diagnosing a new data source.
    missing_values = market_data.isna().sum()
    print("\nMissing values by column:")
    print(missing_values)
    print("\nAny missing values:")
    print(market_data.isna().any().any())

    # Select one symbol for a visual smoke test. A line chart is enough for
    # Phase 0: we are checking that dates, prices, and plotting all connect.
    ticker_data = market_data[market_data["Ticker"] == PLOT_TICKER]
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(ticker_data["Date"], ticker_data["Close"])
    axis.set_title(f"{PLOT_TICKER} Daily Closing Price")
    axis.set_xlabel("Date")
    axis.set_ylabel("Closing price (USD)")
    axis.grid(True, alpha=0.3)

    # Output goes under data/cache/, which is already gitignored: it is
    # regenerable by rerunning this script, so it does not belong in the repo.
    save_figure(figure, cache_path("phase0_aapl_close.png"))


if __name__ == "__main__":
    main()
