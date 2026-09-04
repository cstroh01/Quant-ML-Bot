"""Phase 2 logistic-regression baseline with walk-forward validation."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from data import cache_path, download_market_data
from signals import sma_crossover_signal
from walk_forward_cv import walk_forward_splits

TICKER = "AAPL"
SHORT_WINDOW = 10
LONG_WINDOW = 30
VOLATILITY_WINDOW = 10
RESULTS_FILENAME = "phase2_logistic_baseline_results.csv"
FEATURE_COLUMNS = [
    "Log_Return",
    "Rolling_Volatility",
    "Short_SMA",
    "Long_SMA",
    "Volume",
]


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Build causal features and the next-day direction label."""
    features = sma_crossover_signal(prices, SHORT_WINDOW, LONG_WINDOW)
    features["Log_Return"] = np.log(features["Close"] / features["Close"].shift(1))
    features["Rolling_Volatility"] = (
        features["Log_Return"].rolling(VOLATILITY_WINDOW).std()
    )

    # The label uses Close[t+1] by design. It is the prediction target only;
    # never include this column in FEATURE_COLUMNS.
    next_close = features["Close"].shift(-1)
    features["Label"] = (next_close > features["Close"]).astype("Int64")
    features.loc[next_close.isna(), "Label"] = pd.NA

    # Remove the SMA/volatility warm-up rows and the final row without a label.
    return (
        features.iloc[LONG_WINDOW:]
        .dropna(subset=FEATURE_COLUMNS + ["Label"])
        .reset_index(drop=True)
    )


def evaluate_walk_forward(features: pd.DataFrame) -> pd.DataFrame:
    """Fit and score one logistic model per chronological walk-forward fold."""
    fold_results = []
    all_predictions = []
    all_actuals = []

    for fold, (train_indices, test_indices) in enumerate(
        walk_forward_splits(features), start=1
    ):
        train_dates = pd.to_datetime(features.iloc[train_indices]["Date"])
        test_dates = pd.to_datetime(features.iloc[test_indices]["Date"])
        assert (
            train_dates.max() < test_dates.min()
        ), f"Fold {fold} has test data at or before training data."

        model = LogisticRegression(max_iter=1000, random_state=42)
        train_labels = features.iloc[train_indices]["Label"].astype(int)
        test_labels = features.iloc[test_indices]["Label"].astype(int)
        model.fit(features.iloc[train_indices][FEATURE_COLUMNS], train_labels)
        predictions = model.predict(features.iloc[test_indices][FEATURE_COLUMNS])

        accuracy = float(np.mean(predictions == test_labels.to_numpy()))
        predicted_counts = np.bincount(predictions, minlength=2)
        actual_counts = np.bincount(test_labels.to_numpy(), minlength=2)
        print(
            f"Fold {fold}: accuracy = {accuracy:.3f}; "
            f"predicted [down={predicted_counts[0]}, up={predicted_counts[1]}]; "
            f"actual [down={actual_counts[0]}, up={actual_counts[1]}]"
        )

        fold_results.append(
            {
                "Fold": fold,
                "Train_Rows": len(train_indices),
                "Test_Rows": len(test_indices),
                "Train_End": train_dates.max(),
                "Test_Start": test_dates.min(),
                "Accuracy": accuracy,
                "Predicted_Down": predicted_counts[0],
                "Predicted_Up": predicted_counts[1],
                "Actual_Down": actual_counts[0],
                "Actual_Up": actual_counts[1],
            }
        )
        all_predictions.extend(predictions)
        all_actuals.extend(test_labels.to_numpy())

    if not fold_results:
        raise RuntimeError("Walk-forward validation produced no test folds.")

    result_frame = pd.DataFrame(fold_results)
    overall_accuracy = float(
        np.mean(np.array(all_predictions) == np.array(all_actuals))
    )
    actual_counts = np.bincount(np.array(all_actuals), minlength=2)
    majority_accuracy = float(actual_counts.max() / actual_counts.sum())

    print(f"Overall accuracy: {overall_accuracy:.3f}")
    print(f"Aggregate actual labels: down={actual_counts[0]}, up={actual_counts[1]}")
    print(
        f"Class-balance note: always predicting the majority class would score "
        f"{majority_accuracy:.3f}; model accuracy should be compared with that "
        "baseline because a mostly-up market can make naive predictions look good."
    )
    return result_frame


def main() -> None:
    market_data = download_market_data([TICKER], period="2y")
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    prices = prices.sort_values("Date").reset_index(drop=True)
    features = build_features(prices)
    results = evaluate_walk_forward(features)
    output_path = cache_path(RESULTS_FILENAME)
    results.to_csv(output_path, index=False)
    print(f"Saved fold results to {output_path}")


if __name__ == "__main__":
    main()
