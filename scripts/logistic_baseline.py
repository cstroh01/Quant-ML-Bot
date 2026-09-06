"""Phase 2 logistic-regression baseline with walk-forward validation."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from data import cache_path, download_market_data
from ma_crossover_backtest import baseline_results, mean_holding_bars
from signals import sma_crossover_signal
from backtest_harness import run_backtest, summarize_trades
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

# Same illustrative retail-broker cost model ma_crossover_backtest.py uses,
# restated here rather than imported — the two scripts should report
# directly comparable numbers, but a shared *value* isn't a real coupling
# worth adding for that alone (see spec 005 plan).
COMMISSION_PER_TRADE = 1.00
SLIPPAGE_BPS = 5.0
RANDOM_BASELINE_SEEDS = 20
CURRENCY_COLUMNS = ["Entry Price", "Exit Price", "P&L", "Cumulative P&L"]


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
        walk_forward_splits(features, label_horizon=1, embargo_bars=1), start=1
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


def walk_forward_predictions(features: pd.DataFrame) -> pd.Series:
    """Return each row's out-of-sample next-day-direction prediction.

    Every prediction here is made by a model fit only on data strictly
    before it, via the exact same purged & embargoed folds
    `evaluate_walk_forward` uses (`label_horizon=1, embargo_bars=1`) — this
    function trains and predicts fold-by-fold rather than fitting once on
    the whole frame, which is what keeps a resulting trading signal free of
    the lookahead Rule 2 exists to prevent.

    Rows before the first fold's test window (the initial training period)
    have no out-of-sample prediction and come back as `pd.NA` — there is no
    model yet at that point, so there is no signal. That is a real
    "not trading yet" state, not a gap to fill in.

    Deliberately duplicates the fit/predict loop in `evaluate_walk_forward`
    rather than sharing it (spec 005 plan): refactoring both to share one
    generator would touch a function spec 003's tests already cover and
    pass against. A handful of extra `LogisticRegression` fits on a few
    years of daily bars costs milliseconds.
    """
    predictions = pd.Series(pd.NA, index=features.index, dtype="Int64")

    for fold, (train_indices, test_indices) in enumerate(
        walk_forward_splits(features, label_horizon=1, embargo_bars=1), start=1
    ):
        train_dates = pd.to_datetime(features.iloc[train_indices]["Date"])
        test_dates = pd.to_datetime(features.iloc[test_indices]["Date"])
        assert (
            train_dates.max() < test_dates.min()
        ), f"Fold {fold} has test data at or before training data."

        model = LogisticRegression(max_iter=1000, random_state=42)
        train_labels = features.iloc[train_indices]["Label"].astype(int)
        model.fit(features.iloc[train_indices][FEATURE_COLUMNS], train_labels)
        fold_predictions = model.predict(features.iloc[test_indices][FEATURE_COLUMNS])
        predictions.iloc[test_indices] = fold_predictions

    return predictions


def _signal_from_predictions(predictions: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Turn a per-row prediction series into next-open Buy/Sell series.

    Pulled out of `build_ml_signal` so the transition/shift logic can be
    tested directly against a hand-built `predictions` series, without
    needing a real model fit for every test case.

    A prediction of "up", known at that row's close, becomes tradeable at
    the *next* row's open — the same next-open discipline every other
    signal in this repo uses (Rule 1). `<NA>` (no prediction yet) reads as
    flat: no position is desired, so no trade fires.
    """
    # Desired position: long when the model expects the next close to be
    # higher; flat wherever there is no out-of-sample prediction yet.
    desired_long = (predictions == 1).fillna(False).astype(bool)

    # Same shape as sma_crossover_signal's Crosses_Above/Crosses_Below: a
    # same-bar transition detector, computed before any shifting.
    enters_long = desired_long & ~desired_long.shift(1, fill_value=False)
    exits_long = ~desired_long & desired_long.shift(1, fill_value=False)

    buy_next_open = enters_long.shift(1, fill_value=False)
    sell_next_open = exits_long.shift(1, fill_value=False)
    return buy_next_open, sell_next_open


def build_ml_signal(features: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Attach next-open Buy/Sell signals derived from out-of-sample predictions.

    Returns the frame with `Buy_Next_Open`/`Sell_Next_Open` attached, and
    the positional index of the first row with an out-of-sample
    prediction — the point at which "live" trading, and therefore any
    honest backtest of it, can actually start.

    That position is derived positionally, from a boolean mask, and never
    from the predictions' pandas index. `Series.first_valid_index()` returns
    an index *label*; the caller feeds the result to `.iloc`, which takes a
    *position*. The two agree only on a 0-based `RangeIndex` — which every
    caller happens to pass today, because `build_features` ends with
    `reset_index(drop=True)`. On an offset index the live window would be
    silently truncated and the reported P&L would change; on a
    `DatetimeIndex` it would raise (spec 007).
    """
    predictions = walk_forward_predictions(features)

    # Positions, not labels. `notna()` is exactly "has an out-of-sample
    # prediction": walk_forward_predictions writes only into fold test
    # windows and leaves every other row <NA>.
    covered_positions = np.flatnonzero(predictions.notna().to_numpy())
    if covered_positions.size == 0:
        raise RuntimeError("walk_forward_predictions produced no predictions.")
    # Emptiness, not falsiness — position 0 is a legitimate answer meaning
    # the very first row is covered.
    first_covered_pos = int(covered_positions[0])

    buy_next_open, sell_next_open = _signal_from_predictions(predictions)

    features = features.copy()
    features["Buy_Next_Open"] = buy_next_open
    features["Sell_Next_Open"] = sell_next_open
    return features, first_covered_pos


def _format_ml_comparison(ml_summary: dict, baselines: dict, *, seed_count: int) -> str:
    """Render the ML strategy and both baselines as one cost-adjusted block.

    Deliberately not a call into `ma_crossover_backtest.format_comparison`:
    that function hardcodes the SMA strategy's own window sizes into its
    row label, so reusing it here would print "SMA crossover" beside a
    logistic-regression result (FR-005). Layout and precision otherwise
    match it exactly, so the two scripts' reports read as one system.
    """
    commission = ml_summary["commission_per_trade"]
    slippage = ml_summary["slippage_bps"]
    hold = baselines["buy_and_hold"]

    def row(label: str, trades: str, pnl: str, win_rate: str) -> str:
        return f"{label:<30}{trades:>7}{pnl:>24}{win_rate:>10}"

    lines = [
        "Cost model (applied identically to all three rows below):",
        f"  Commission: ${commission:,.2f} per fill, charged on entry and again"
        " on exit",
        f"  Slippage:   {slippage:.1f} bps of notional, always against the fill",
        "",
        row("Strategy", "Trades", "Total P&L", "Win rate"),
        "-" * 71,
        row(
            "Logistic (walk-forward)",
            str(ml_summary["total_trades"]),
            f"${ml_summary['total_pnl']:,.2f}",
            f"{ml_summary['win_rate']:.1f}%",
        ),
        row(
            "Buy and hold",
            str(hold["total_trades"]),
            f"${hold['total_pnl']:,.2f}",
            f"{hold['win_rate']:.1f}%",
        ),
    ]

    random_summaries = baselines["random_summaries"]
    label = f"Random baseline ({seed_count} seeds)"
    if not random_summaries:
        reason = baselines["random_error"] or "the strategy took no trades"
        lines.append(row(label, "-", "not run", "-"))
        lines.append(f"  Random baseline not run: {reason}")
        return "\n".join(lines)

    import statistics

    pnls = [summary["total_pnl"] for summary in random_summaries]
    win_rates = [summary["win_rate"] for summary in random_summaries]
    spread = statistics.stdev(pnls) if len(pnls) > 1 else 0.0
    lines.append(
        row(
            label,
            str(random_summaries[0]["total_trades"]),
            f"${statistics.fmean(pnls):,.2f} ± ${spread:,.2f}",
            f"{statistics.fmean(win_rates):.1f}%",
        )
    )
    lines.append("")
    lines.append(
        f"Random figures are the mean ± sample standard deviation over "
        f"{seed_count} seeds, matched to"
    )
    lines.append("the strategy's own trade count and mean holding period.")
    return "\n".join(lines)


def main() -> None:
    market_data = download_market_data([TICKER], period="2y")
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    prices = prices.sort_values("Date").reset_index(drop=True)
    features = build_features(prices)
    results = evaluate_walk_forward(features)
    output_path = cache_path(RESULTS_FILENAME)
    results.to_csv(output_path, index=False)
    print(f"Saved fold results to {output_path}")

    signalled, first_covered_pos = build_ml_signal(features)
    live = signalled.iloc[first_covered_pos:].reset_index(drop=True)

    costs = {
        "commission_per_trade": COMMISSION_PER_TRADE,
        "slippage_bps": SLIPPAGE_BPS,
    }
    trade_log = run_backtest(live, **costs)
    trade_log.to_csv(cache_path("phase2_logistic_baseline_trades.csv"), index=False)

    print(f"\n{TICKER} logistic-regression walk-forward backtest")
    print(f"Live window: {live['Date'].min()} to {live['Date'].max()}")
    print("Position: long one share or flat; prices below are net of costs")
    print("\nTrade log:")
    if trade_log.empty:
        print("No completed trades.")
    else:
        print(
            trade_log.to_string(
                index=False,
                formatters={
                    column: "${:,.2f}".format for column in CURRENCY_COLUMNS
                },
            )
        )

    summary = summarize_trades(trade_log, **costs)
    baselines = baseline_results(
        live,
        n_trades=summary["total_trades"],
        holding_bars=mean_holding_bars(live, trade_log),
        seed_count=RANDOM_BASELINE_SEEDS,
        **costs,
    )

    print("\nSummary, against both required baselines:\n")
    print(_format_ml_comparison(summary, baselines, seed_count=RANDOM_BASELINE_SEEDS))


if __name__ == "__main__":
    main()
