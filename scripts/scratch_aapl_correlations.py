"""Resolve discrepancy between AAPL r(SMA_Spread, Close_To_Short) = 0.319 and '0.998 -> 0.527'.

Prints full pairwise correlation matrix for AAPL across scale-free features:
Log_Return, Rolling_Volatility, SMA_Spread, Close_To_Short, Rel_Volume.
"""

from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "cache" / "AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv"

SCALE_FREE_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "SMA_Spread",
    "Close_To_Short",
    "Rel_Volume",
]

LEVEL_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "Short_SMA",
    "Long_SMA",
    "Volume",
]

SHORT_WINDOW = 10
LONG_WINDOW = 30
VOLATILITY_WINDOW = 10
VOLUME_WINDOW = 30


def build_aapl_frame():
    df = pd.read_csv(CSV_PATH)
    aapl = df[df["Ticker"] == "AAPL"].copy().sort_values("Date").reset_index(drop=True)

    # SMAs
    aapl["Short_SMA"] = aapl["Close"].rolling(SHORT_WINDOW).mean()
    aapl["Long_SMA"] = aapl["Close"].rolling(LONG_WINDOW).mean()

    # Log Return & Rolling Volatility
    aapl["Log_Return"] = np.log(aapl["Close"] / aapl["Close"].shift(1))
    aapl["Rolling_Volatility"] = aapl["Log_Return"].rolling(VOLATILITY_WINDOW).std()

    # Scale-free features
    aapl["SMA_Spread"] = aapl["Short_SMA"] / aapl["Long_SMA"] - 1.0
    aapl["Close_To_Short"] = aapl["Close"] / aapl["Short_SMA"] - 1.0
    aapl["Close_To_Long"] = aapl["Close"] / aapl["Long_SMA"] - 1.0
    aapl["Rel_Volume"] = aapl["Volume"] / aapl["Volume"].rolling(VOLUME_WINDOW).mean()

    # Horizon=1 label to match build_features row drops
    aapl["Label"] = aapl["Close"].shift(-1) / aapl["Close"] - 1.0

    # Drop warm-up rows and final unobservable row
    cols_to_check = list(
        set(SCALE_FREE_COLUMNS + LEVEL_COLUMNS + ["Close_To_Long", "Label"])
    )
    cleaned = aapl.iloc[LONG_WINDOW:].dropna(subset=cols_to_check).reset_index(drop=True)
    return cleaned


def main():
    df = build_aapl_frame()
    print("=" * 80)
    print(f"AAPL CORRELATION AUDIT ({len(df)} sessions)")
    print("=" * 80)

    # Full 5x5 correlation matrix
    corr_matrix = df[SCALE_FREE_COLUMNS].corr()
    print("\nFULL PAIRWISE CORRELATION MATRIX (SCALE-FREE):")
    print(corr_matrix.to_string(float_format="{: .6f}".format))

    # All off-diagonal pairs ranked by |corr|
    pairs = []
    for i in range(len(SCALE_FREE_COLUMNS)):
        for j in range(i + 1, len(SCALE_FREE_COLUMNS)):
            c1, c2 = SCALE_FREE_COLUMNS[i], SCALE_FREE_COLUMNS[j]
            r = corr_matrix.loc[c1, c2]
            pairs.append((abs(r), r, c1, c2))

    pairs.sort(key=lambda x: x[0], reverse=True)

    print("\nALL 10 OFF-DIAGONAL PAIRS RANKED BY |r|:")
    for rank, (abs_r, r, c1, c2) in enumerate(pairs, 1):
        print(f"  {rank:2d}. |r| = {abs_r:.6f} (r = {r: .6f}) : {c1} vs {c2}")

    # Inspect the levels correlation matrix for comparison
    levels_corr = df[LEVEL_COLUMNS].corr()
    level_pairs = []
    for i in range(len(LEVEL_COLUMNS)):
        for j in range(i + 1, len(LEVEL_COLUMNS)):
            c1, c2 = LEVEL_COLUMNS[i], LEVEL_COLUMNS[j]
            r = levels_corr.loc[c1, c2]
            level_pairs.append((abs(r), r, c1, c2))
    level_pairs.sort(key=lambda x: x[0], reverse=True)

    print("\nLARGEST PAIR IN LEVELS:")
    top_level = level_pairs[0]
    print(f"  |r| = {top_level[0]:.6f} (r = {top_level[1]: .6f}) : {top_level[2]} vs {top_level[3]}")

    print("\nEXACT TARGET PAIRS CHECK:")
    r_spread_short = corr_matrix.loc["SMA_Spread", "Close_To_Short"]
    r_ret_short = corr_matrix.loc["Log_Return", "Close_To_Short"]
    r_spread_long = df["SMA_Spread"].corr(df["Close_To_Long"])

    print(f"  1. SMA_Spread vs Close_To_Short: r = {r_spread_short:.6f}")
    print(f"  2. Log_Return vs Close_To_Short: r = {r_ret_short:.6f}")
    print(f"  3. SMA_Spread vs Close_To_Long : r = {r_spread_long:.6f}")
    print(f"  4. Short_SMA vs Long_SMA (Levels): r = {levels_corr.loc['Short_SMA', 'Long_SMA']:.6f}")
    print("=" * 80)


if __name__ == "__main__":
    main()
