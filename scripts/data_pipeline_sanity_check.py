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
import yfinance as yf


# Keeping scripts in scripts/ makes small, runnable development utilities
# separate from reusable application code. It also gives us a natural place
# for this one-off Phase 0 check without adding project structure too early.
TICKERS = ["AAPL", "MSFT", "GOOGL"]


def main():
    # period="2y" asks yfinance for approximately two years of data. Using
    # interval="1d" requests one row per trading day instead of intraday bars.
    # auto_adjust=False keeps both the raw Close and yfinance's adjusted close
    # available, which is useful to inspect before deciding which one to model.
    # progress=False keeps the script's diagnostic output easy to read.
    downloaded_data = yf.download(
        TICKERS,
        period="2y",
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
    )

    if downloaded_data.empty:
        raise RuntimeError("yfinance returned no data. Check the symbols or connection.")

    # With several tickers, yfinance returns a DataFrame whose columns have
    # two levels, conceptually like ("AAPL", "Open") and ("AAPL", "Close").
    # We convert that wide MultiIndex shape into a tidy/long shape: each row is
    # one ticker on one date, and Ticker is an ordinary column.
    #
    # Tidy data is a good choice here because filtering one ticker is simple,
    # combining symbols for later ML work is straightforward, and the schema
    # remains understandable when more columns are added. A wide MultiIndex
    # can be convenient for comparing tickers side-by-side, but its column
    # indexing is less beginner-friendly and less convenient for grouping.
    tidy_frames = []
    for ticker in TICKERS:
        # group_by="ticker" means downloaded_data[ticker] selects the OHLCV
        # block belonging to that symbol.
        ticker_data = downloaded_data[ticker].copy()
        ticker_data.columns.name = None

        # reset_index turns the Date index into a normal column. Keeping Date
        # and Ticker as columns makes the row's identity explicit when we print
        # or later pass the data to other pandas operations.
        ticker_data = ticker_data.reset_index()
        ticker_data["Ticker"] = ticker
        tidy_frames.append(ticker_data)

    # concat stacks the three per-ticker tables vertically into one DataFrame.
    # ignore_index gives the combined table a fresh simple row index.
    market_data = pd.concat(tidy_frames, ignore_index=True)
    market_data = market_data.sort_values(["Ticker", "Date"]).reset_index(drop=True)

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
        Path(__file__).resolve().parents[1]
        / "data"
        / "cache"
        / "phase0_aapl_close.png"
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