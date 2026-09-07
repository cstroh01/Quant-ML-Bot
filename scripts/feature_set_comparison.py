"""Does the scale-free feature set actually predict better? A paired test.

`feature_diagnostics.py` shows the design matrix is better conditioned. That
is a property of the *matrix*. It is not evidence that any prediction
improved, and spec 014 does not get to claim one from the other — a
well-conditioned matrix of useless features is still useless.

So this script runs the real nested walk-forward for every registry entry
under both feature sets and tests the two prediction series against each
other. Spec 014 FR-012 makes running it a merge requirement, not an option.

**Why paired tests.** The two feature sets are evaluated on the same bars,
under the same splits, with the same seed. The only thing that differs is
the feature matrix. A paired test removes the period effect — which
dominates any comparison of two walk-forward runs, because both are mostly
measuring what the market did — and asks only about the within-bar
difference. An unpaired comparison of two accuracy numbers throws that away
and is why "0.519 vs 0.524" reads as noise.

- **Classification** (`logistic`, `hgb`) — McNemar's test on the paired
  correct/incorrect outcomes. The bars both sets get right and the bars both
  get wrong carry no information about which set is better; McNemar
  correctly conditions on the discordant pairs alone.
- **Regression** (`ridge`, `hgb`) — Wilcoxon signed-rank on the paired
  per-bar squared-error differences. Signed-rank rather than a paired
  t-test because squared-error differences on daily returns are heavily
  right-skewed, and a t-test on them is a test about a handful of large
  days.

**The bar, and what it is not.** `p < 0.10` one-sided on at least one of the
four entries is what spec 014 means by "shows real improvement, not just
better conditioning". That is a *screening* threshold: cheap evidence,
sized for four comparisons on a single ticker, chosen to catch a real effect
rather than to certify one. It is emphatically **not** the project's
capital-readiness bar, which is the deflated Sharpe ratio and comes later.
Nothing this script prints justifies allocating capital.

All four p-values are reported whatever they say. A null result merges: the
conditioning fix stands on its own, and "well-conditioned features did not
move the prediction" is a finding worth recording rather than burying.

Rule 8: a diagnostic entry point over the signal and model layers. It
imports `data`, `features`, `estimators` and `model_cv`, and knows nothing
of fills, positions, or P&L — no metric here is a return.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from statsmodels.stats.contingency_tables import mcnemar

from data import download_market_data
from estimators import CLASSIFICATION, ESTIMATOR_REGISTRY, REGRESSION
from features import build_features, feature_columns
from model_cv import nested_walk_forward

TICKER = "AAPL"
PERIOD = "10y"

# The cached download is the five-ticker universe (spec 013's
# `TICKER_UNIVERSE`), so the whole list is requested and `TICKER` selected out
# of it. Asking for `[TICKER]` alone would miss that cache file — the key is
# the sorted ticker list — and trigger a network call this lane cannot make.
CACHE_TICKERS = ["AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"]

LABEL_HORIZON = 1
EMBARGO_BARS = 1
RANDOM_STATE = 42

# The project's walk-forward defaults, restated here so the printed report
# carries them. A metric without its fold geometry is not reportable
# (CLAUDE.md, *Pull request requirements* item 3).
INITIAL_TRAIN_MONTHS = 6
TEST_MONTHS = 1
INNER_INITIAL_TRAIN_MONTHS = 6
INNER_TEST_MONTHS = 1

# The screening threshold. See the module docstring for what it is not.
ALPHA = 0.10

# Which target each task is compared on. `direction` is the up/down label the
# Phase 2 control used; `return` is the forward log return spec 009 added.
TARGET_KIND = {CLASSIFICATION: "direction", REGRESSION: "return"}

FEATURE_SET_A = "levels"
FEATURE_SET_B = "scale_free"


def _predictions_by_date(
    prices: pd.DataFrame, *, name: str, task: str, feature_set: str
) -> tuple[pd.Series, pd.Series, int]:
    """Run the nested walk-forward once and index its output by date.

    Returns `(predictions, labels, outer_folds)`, both series indexed by
    `Date` and restricted to the rows the walk-forward actually covered.

    Indexing by date rather than by position is what makes the two feature
    sets comparable at all: they have different warm-up lengths, so row 40 of
    one is not row 40 of the other. Aligning on the timestamp compares the
    same trading day to itself, which is the whole premise of a paired test.
    """
    frame, task_out, horizon = build_features(
        prices,
        target_kind=TARGET_KIND[task],
        label_horizon=LABEL_HORIZON,
        feature_set=feature_set,
    )
    assert task_out == task, f"expected task {task!r}, got {task_out!r}"

    predictions, covered, fold_results = nested_walk_forward(
        frame,
        feature_columns=feature_columns(feature_set),
        label_column="Label",
        task=task,
        name=name,
        label_horizon=horizon,
        embargo_bars=EMBARGO_BARS,
        random_state=RANDOM_STATE,
        initial_train_months=INITIAL_TRAIN_MONTHS,
        test_months=TEST_MONTHS,
        inner_initial_train_months=INNER_INITIAL_TRAIN_MONTHS,
        inner_test_months=INNER_TEST_MONTHS,
    )

    dates = pd.to_datetime(frame["Date"])
    covered_index = np.sort(np.asarray(covered))
    predicted = pd.Series(
        predictions.iloc[covered_index].to_numpy(),
        index=pd.Index(dates.iloc[covered_index], name="Date"),
    )
    labels = pd.Series(
        frame["Label"].iloc[covered_index].to_numpy(),
        index=pd.Index(dates.iloc[covered_index], name="Date"),
    )
    return predicted, labels, len(fold_results)


def compare_classification(
    labels: pd.Series, predicted_a: pd.Series, predicted_b: pd.Series
) -> dict:
    """McNemar's test on paired correct/incorrect outcomes.

    `exact=True` uses the binomial test rather than the chi-square
    approximation. That is the right default here because the discordant
    count can be small, and the approximation is unreliable exactly there.

    statsmodels reports a two-sided p-value. Under the exact symmetric
    binomial the one-sided p is half of it in the favoured direction, so the
    one-sided figure is derived rather than re-implemented — and reported
    beside the two-sided one so a reader can see both.
    """
    truth = labels.astype(int).to_numpy()
    correct_a = predicted_a.astype(int).to_numpy() == truth
    correct_b = predicted_b.astype(int).to_numpy() == truth

    # b_wins: A wrong, B right. a_wins: A right, B wrong. These two cells are
    # the entire evidence; the concordant cells cancel.
    b_wins = int(np.sum(~correct_a & correct_b))
    a_wins = int(np.sum(correct_a & ~correct_b))
    table = [
        [int(np.sum(correct_a & correct_b)), a_wins],
        [b_wins, int(np.sum(~correct_a & ~correct_b))],
    ]

    if a_wins + b_wins == 0:
        # Identical predictions everywhere. No test is possible and none is
        # needed: the answer is "no difference", stated rather than computed.
        return {
            "test": "mcnemar (exact)",
            "n": len(truth),
            "discordant": 0,
            "statistic": float("nan"),
            "p_two_sided": 1.0,
            "p_one_sided": 1.0,
            "accuracy_a": float(np.mean(correct_a)),
            "accuracy_b": float(np.mean(correct_b)),
            "favours_b": False,
            "note": "identical predictions; no discordant pairs",
        }

    result = mcnemar(table, exact=True)
    two_sided = float(result.pvalue)
    favours_b = b_wins > a_wins
    one_sided = two_sided / 2.0 if favours_b else 1.0 - two_sided / 2.0

    return {
        "test": "mcnemar (exact)",
        "n": len(truth),
        "discordant": a_wins + b_wins,
        "statistic": float(result.statistic),
        "p_two_sided": two_sided,
        "p_one_sided": float(min(1.0, one_sided)),
        "accuracy_a": float(np.mean(correct_a)),
        "accuracy_b": float(np.mean(correct_b)),
        "favours_b": bool(favours_b),
        "note": "",
    }


def compare_regression(
    labels: pd.Series, predicted_a: pd.Series, predicted_b: pd.Series
) -> dict:
    """Wilcoxon signed-rank on paired per-bar squared-error differences.

    The paired quantity is `se_b - se_a`, so `alternative="less"` is the
    one-sided test that B has the smaller error — stated directly to scipy
    rather than derived from a two-sided p-value.

    `zero_method="wilcox"` discards exactly-tied pairs, which is the
    standard treatment and the conservative one: a bar where both feature
    sets erred identically is evidence for neither.
    """
    truth = labels.to_numpy(dtype=float)
    error_a = (predicted_a.to_numpy(dtype=float) - truth) ** 2
    error_b = (predicted_b.to_numpy(dtype=float) - truth) ** 2
    difference = error_b - error_a

    if not np.any(difference != 0.0):
        return {
            "test": "wilcoxon signed-rank",
            "n": len(truth),
            "discordant": 0,
            "statistic": float("nan"),
            "p_two_sided": 1.0,
            "p_one_sided": 1.0,
            "mse_a": float(np.mean(error_a)),
            "mse_b": float(np.mean(error_b)),
            "favours_b": False,
            "note": "identical squared errors; nothing to rank",
        }

    one_sided = wilcoxon(difference, alternative="less", zero_method="wilcox")
    two_sided = wilcoxon(difference, alternative="two-sided", zero_method="wilcox")

    return {
        "test": "wilcoxon signed-rank",
        "n": len(truth),
        "discordant": int(np.sum(difference != 0.0)),
        "statistic": float(one_sided.statistic),
        "p_two_sided": float(two_sided.pvalue),
        "p_one_sided": float(one_sided.pvalue),
        "mse_a": float(np.mean(error_a)),
        "mse_b": float(np.mean(error_b)),
        "favours_b": bool(np.mean(error_b) < np.mean(error_a)),
        "note": "",
    }


def compare_entry(prices: pd.DataFrame, *, name: str, task: str) -> dict:
    """Run one registry entry under both feature sets and test the pair."""
    predicted_a, labels_a, folds_a = _predictions_by_date(
        prices, name=name, task=task, feature_set=FEATURE_SET_A
    )
    predicted_b, labels_b, folds_b = _predictions_by_date(
        prices, name=name, task=task, feature_set=FEATURE_SET_B
    )

    # Restrict to the dates both runs covered. The warm-up lengths differ, so
    # the two coverage sets are not identical and pairing requires the
    # intersection — taking either run's own index would silently compare a
    # bar to nothing.
    shared = predicted_a.index.intersection(predicted_b.index)
    shared = shared.sort_values()

    labels = labels_a.loc[shared]
    pd.testing.assert_series_equal(
        labels, labels_b.loc[shared], check_names=False, check_dtype=False
    )

    if task == CLASSIFICATION:
        result = compare_classification(
            labels, predicted_a.loc[shared], predicted_b.loc[shared]
        )
    else:
        result = compare_regression(
            labels, predicted_a.loc[shared], predicted_b.loc[shared]
        )

    result.update(
        {
            "name": name,
            "task": task,
            "shared_bars": len(shared),
            "outer_folds_a": folds_a,
            "outer_folds_b": folds_b,
        }
    )
    return result


def format_report(results: list[dict]) -> str:
    """A printable report: the fold geometry, the four rows, and the verdict."""
    lines: list[str] = []
    lines.append(f"{TICKER} feature-set comparison over {PERIOD}")
    lines.append(f"  {FEATURE_SET_A!r} (control) vs {FEATURE_SET_B!r} (spec 014)")
    lines.append("")
    lines.append("Fold geometry — required beside any reported metric:")
    lines.append(
        f"  outer: initial_train_months={INITIAL_TRAIN_MONTHS}, "
        f"test_months={TEST_MONTHS}"
    )
    lines.append(
        f"  inner: initial_train_months={INNER_INITIAL_TRAIN_MONTHS}, "
        f"test_months={INNER_TEST_MONTHS}"
    )
    lines.append(
        f"  purge = label_horizon = {LABEL_HORIZON} bar(s); "
        f"embargo = {EMBARGO_BARS} bar(s)"
    )
    lines.append(
        "  commission and slippage: not applicable — nothing here is a "
        "backtest; these are prediction-quality tests only."
    )
    lines.append(f"  seed: {RANDOM_STATE}")
    lines.append("")

    for result in results:
        lines.append(f"--- {result['name']} / {result['task']} ---")
        lines.append(
            f"  outer folds: {result['outer_folds_a']} ({FEATURE_SET_A}) / "
            f"{result['outer_folds_b']} ({FEATURE_SET_B}); "
            f"paired bars: {result['shared_bars']}"
        )
        if result["task"] == CLASSIFICATION:
            lines.append(
                f"  accuracy: {result['accuracy_a']:.4f} -> "
                f"{result['accuracy_b']:.4f}"
            )
            lines.append(f"  discordant pairs: {result['discordant']}")
        else:
            lines.append(
                f"  MSE: {result['mse_a']:.8f} -> {result['mse_b']:.8f}"
            )
            lines.append(f"  non-tied pairs: {result['discordant']}")
        lines.append(f"  test: {result['test']}")
        lines.append(
            f"  p (two-sided): {result['p_two_sided']:.4f}"
            f"   p (one-sided, {FEATURE_SET_B} better): "
            f"{result['p_one_sided']:.4f}"
        )
        if result["note"]:
            lines.append(f"  note: {result['note']}")
        lines.append("")

    passing = [r for r in results if r["p_one_sided"] < ALPHA]
    lines.append("=== verdict ===")
    lines.append(
        f"Screening bar: p < {ALPHA:.2f} one-sided on at least one entry."
    )
    if passing:
        which = ", ".join(f"{r['name']}/{r['task']}" for r in passing)
        lines.append(f"MET, on: {which}")
    else:
        lines.append(
            "NOT MET. The conditioning fix stands on its own and spec 014 "
            "still merges, but nothing here is evidence about the model."
        )
    lines.append("")
    lines.append(
        "This is a screening threshold on one ticker, not a capital-readiness "
        "bar. That is the deflated Sharpe step, and it is not this."
    )
    return "\n".join(lines)


CHECKPOINT_PATH = Path(__file__).resolve().parents[1] / "data" / "cache" / "feature_set_comparison.json"


def _checkpoint(results: list[dict]) -> None:
    """Write completed entries to `data/cache/` after each one.

    This run is hours long and prints only at the end. An exception in the
    fourth entry used to discard the first three, which is a bad trade for
    two lines of code. The file is regenerable output under `data/cache/`,
    so it is gitignored like everything else there.
    """
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")


def main():
    """Print the paired comparison for every registry entry.

    Runs outside the agent lane: it reads `data/cache/` and downloads if the
    cache is cold. Expect this to take a while — it is eight nested
    walk-forward runs, each tuning a grid on inner folds inside every outer
    fold.
    """
    market_data = download_market_data(CACHE_TICKERS, period=PERIOD)
    prices = market_data[market_data["Ticker"] == TICKER].copy()
    prices = prices.sort_values("Date").reset_index(drop=True)

    results = []
    for name, task in sorted(ESTIMATOR_REGISTRY):
        print(f"running {name}/{task} ...", flush=True)
        result = compare_entry(prices, name=name, task=task)
        results.append(result)
        _checkpoint(results)
        print(
            f"  done: p(one-sided)={result['p_one_sided']:.4f}",
            flush=True,
        )

    print()
    print(format_report(results))


if __name__ == "__main__":
    main()
