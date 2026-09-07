"""Independent verification of the Close_To_Short collinearity fix across all 5 tickers.

Spec 014 replaces the collinear feature Close_To_Long with Close_To_Short to break
the algebraic identity Close/Long == (Close/Short) * (Short/Long).

This script independently evaluates all 5 tickers (AAPL, AMZN, GOOGL, MSFT, NVDA)
from data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv.

For each ticker, it computes:
1. Correlation between SMA_Spread and Close_To_Short (and compares to Close_To_Long).
2. Standardized condition number across the full scale-free feature set
   (and compares to levels and the collinear Close_To_Long set).
3. Max VIF across the full scale-free feature set (and all individual VIFs).
"""

from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "cache" / "AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv"

# Feature set definitions per scripts/features.py
SCALE_FREE_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "SMA_Spread",
    "Close_To_Short",
    "Rel_Volume",
]

COLLINEAR_RATIO_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "SMA_Spread",
    "Close_To_Long",
    "Rel_Volume",
]

LEVEL_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "Short_SMA",
    "Long_SMA",
    "Volume",
]

# Windows confirmed from scripts/features.py
SHORT_WINDOW = 10
LONG_WINDOW = 30
VOLATILITY_WINDOW = 10
VOLUME_WINDOW = 30  # defaults to long_window


def compute_ticker_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute all feature candidates independently from OHLCV prices."""
    df = prices.copy().sort_values("Date").reset_index(drop=True)

    # SMAs
    df["Short_SMA"] = df["Close"].rolling(SHORT_WINDOW).mean()
    df["Long_SMA"] = df["Close"].rolling(LONG_WINDOW).mean()

    # Log Return & Rolling Volatility
    df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1))
    df["Rolling_Volatility"] = df["Log_Return"].rolling(VOLATILITY_WINDOW).std()

    # Scale-free features
    df["SMA_Spread"] = df["Short_SMA"] / df["Long_SMA"] - 1.0
    df["Close_To_Short"] = df["Close"] / df["Short_SMA"] - 1.0
    df["Close_To_Long"] = df["Close"] / df["Long_SMA"] - 1.0  # Old / collinear feature
    df["Rel_Volume"] = df["Volume"] / df["Volume"].rolling(VOLUME_WINDOW).mean()

    # Forward return label (horizon=1) to match row drop behavior of build_features
    df["Label"] = df["Close"].shift(-1) / df["Close"] - 1.0

    # Replace infinities if any
    cols_to_check = [
        "SMA_Spread",
        "Close_To_Short",
        "Close_To_Long",
        "Rel_Volume",
        "Short_SMA",
        "Long_SMA",
        "Log_Return",
        "Rolling_Volatility",
    ]
    df[cols_to_check] = df[cols_to_check].replace([np.inf, -np.inf], np.nan)

    # Drop warm-up rows (first long_window rows) and rows with NaNs in required columns
    all_needed = list(
        set(SCALE_FREE_COLUMNS + COLLINEAR_RATIO_COLUMNS + LEVEL_COLUMNS + ["Label"])
    )
    cleaned = df.iloc[LONG_WINDOW:].dropna(subset=all_needed).reset_index(drop=True)
    return cleaned


def standardized_matrix(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    """Z-score standardize columns."""
    matrix = frame[columns].to_numpy(dtype=float)
    centered = matrix - matrix.mean(axis=0)
    deviations = matrix.std(axis=0, ddof=0)
    safe = np.where(deviations == 0.0, 1.0, deviations)
    return centered / safe


def condition_number(frame: pd.DataFrame, columns: list[str]) -> float:
    """Standardized 2-norm condition number."""
    z = standardized_matrix(frame, columns)
    return float(np.linalg.cond(z))


def variance_inflation_factors(
    frame: pd.DataFrame, columns: list[str]
) -> pd.Series:
    """VIF computed from inverse correlation matrix."""
    z = standardized_matrix(frame, columns)
    corr = np.corrcoef(z, rowvar=False)
    corr = np.atleast_2d(corr)
    inv = np.linalg.pinv(corr)
    return pd.Series(np.diag(inv), index=columns, name="VIF")


def run_analysis():
    print("=" * 80)
    print("SPEC 014 MULTI-TICKER COLLINEARITY INDEPENDENT VERIFICATION")
    print(f"Data source: {CSV_PATH}")
    print("=" * 80)

    raw_data = pd.read_csv(CSV_PATH)
    tickers = sorted(raw_data["Ticker"].unique())
    print(f"Tickers found: {tickers}")
    print(f"Total rows in cache: {len(raw_data)}\n")

    summary_rows = []

    for ticker in tickers:
        prices = raw_data[raw_data["Ticker"] == ticker].copy()
        feat_df = compute_ticker_features(prices)
        n_rows = len(feat_df)

        # 1. Correlations
        corr_short = float(feat_df["SMA_Spread"].corr(feat_df["Close_To_Short"]))
        corr_long = float(feat_df["SMA_Spread"].corr(feat_df["Close_To_Long"]))
        corr_sma = float(feat_df["Short_SMA"].corr(feat_df["Long_SMA"]))

        # 2. Condition Numbers
        cond_scale_free = condition_number(feat_df, SCALE_FREE_COLUMNS)
        cond_collinear = condition_number(feat_df, COLLINEAR_RATIO_COLUMNS)
        cond_levels = condition_number(feat_df, LEVEL_COLUMNS)

        # 3. VIFs
        vif_scale_free = variance_inflation_factors(feat_df, SCALE_FREE_COLUMNS)
        max_vif_scale_free = float(vif_scale_free.max())
        max_vif_col = vif_scale_free.idxmax()

        vif_collinear = variance_inflation_factors(feat_df, COLLINEAR_RATIO_COLUMNS)
        max_vif_collinear = float(vif_collinear.max())

        vif_levels = variance_inflation_factors(feat_df, LEVEL_COLUMNS)
        max_vif_levels = float(vif_levels.max())

        # Full correlation matrix for scale-free
        corr_matrix = feat_df[SCALE_FREE_COLUMNS].corr()

        summary_rows.append(
            {
                "Ticker": ticker,
                "Rows": n_rows,
                "corr(Spread, Close_To_Short)": corr_short,
                "corr(Spread, Close_To_Long)": corr_long,
                "corr(Short_SMA, Long_SMA)": corr_sma,
                "Cond(Scale_Free)": cond_scale_free,
                "Cond(Collinear_Ratios)": cond_collinear,
                "Cond(Levels)": cond_levels,
                "Max_VIF(Scale_Free)": max_vif_scale_free,
                "Worst_VIF_Feature": max_vif_col,
                "Max_VIF(Collinear)": max_vif_collinear,
                "Max_VIF(Levels)": max_vif_levels,
            }
        )

        print(f"--------------------------------------------------")
        print(f"TICKER: {ticker} ({n_rows} rows)")
        print(f"--------------------------------------------------")
        print(f"Pairwise Correlations:")
        print(f"  SMA_Spread vs Close_To_Short (Spec 014 fix) : {corr_short: .4f}")
        print(f"  SMA_Spread vs Close_To_Long  (Collinear trap): {corr_long: .4f}")
        print(f"  Short_SMA  vs Long_SMA       (Level baseline): {corr_sma: .4f}")
        print(f"\nCondition Numbers (standardized):")
        print(f"  Scale-free (Close_To_Short) : {cond_scale_free: .2f}")
        print(f"  Collinear (Close_To_Long)   : {cond_collinear: .2f}")
        print(f"  Levels baseline             : {cond_levels: .2f}")
        print(f"\nVIFs for Scale-Free Feature Set:")
        for col, val in vif_scale_free.items():
            print(f"  {col:<20}: {val: .3f}")
        print(f"  Max VIF (Scale-Free)        : {max_vif_scale_free: .3f} ({max_vif_col})")
        print(f"  Max VIF (Collinear trap)    : {max_vif_collinear: .3f}")
        print(f"  Max VIF (Levels baseline)   : {max_vif_levels: .3f}")
        print(f"\nScale-Free Correlation Matrix:")
        print(corr_matrix.to_string(float_format="{: .3f}".format))
        print("\n")

    summary_df = pd.DataFrame(summary_rows)
    print("=" * 80)
    print("CROSS-TICKER COMPARISON SUMMARY TABLE")
    print("=" * 80)
    print(
        summary_df[
            [
                "Ticker",
                "corr(Spread, Close_To_Short)",
                "Cond(Scale_Free)",
                "Max_VIF(Scale_Free)",
                "Worst_VIF_Feature",
            ]
        ].to_string(index=False, float_format="{: .3f}".format)
    )
    print("\n" + "=" * 80)
    print("BEFORE vs AFTER FIX BY TICKER")
    print("=" * 80)
    print(
        summary_df[
            [
                "Ticker",
                "corr(Spread, Close_To_Long)",
                "corr(Spread, Close_To_Short)",
                "Cond(Collinear_Ratios)",
                "Cond(Scale_Free)",
                "Max_VIF(Collinear)",
                "Max_VIF(Scale_Free)",
            ]
        ].to_string(index=False, float_format="{: .3f}".format)
    )
    print("=" * 80)


if __name__ == "__main__":
    run_analysis()
