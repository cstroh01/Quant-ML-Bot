"""Phase 0 sanity check for downloading and inspecting daily market data.

This is deliberately a script rather than a reusable module. The goal in
Phase 0 is to make the data pipeline visible and easy to inspect before
adding classes, configuration files, or command-line options.
"""

from pathlib import Path

# Select a non-interactive matplotlib backend before importing pyplot. This
# matters when the script runs on a server or in another headless environment
# where there is no desktop window in which to display a chart.
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from data import download_market_data

# Keeping scripts in scripts/ makes small, runnable development utilities
# separate from reusable application code. It also gives us a natural place
# for this one-off Phase 0 check without adding project structure too early.
TICKERS = ["AAPL", "MSFT", "GOOGL"]


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

    # Save generated output under data/cache/, which is already ignored by the
    # repository's .gitignore. mkdir(..., parents=True) makes this script work
    # in a fresh clone where the output directory does not exist yet.
    output_path = (
        Path(__file__).resolve().parents[1] / "data" / "cache" / "phase0_aapl_close.png"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Select one symbol for a visual smoke test. A line chart is enough for
    # Phase 0: we are checking that dates, prices, and plotting all connect.
    aapl_data = market_data[market_data["Ticker"] == "AAPL"]
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(aapl_data["Date"], aapl_data["Close"])
    axis.set_title("AAPL Daily Closing Price")
    axis.set_xlabel("Date")
    axis.set_ylabel("Closing price (USD)")
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)

    print(f"\nSaved plot to: {output_path}")


if __name__ == "__main__":
    main()
