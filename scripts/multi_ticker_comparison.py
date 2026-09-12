"""Run the full per-ticker pipeline over a named universe and compare.

Every existing runnable script hardcodes `TICKER = "AAPL"`. This is the
composition spec 008's Background pointed at: one ticker's tuned estimator
(spec 010/011), cost-aware signal (spec 012), and risk-adjusted
`performance_summary` (spec 008), run independently over a five-ticker
universe and assembled into one comparison table.

**Composition only (Rule 8/FR-007).** This module adds no feature, target,
estimator, signal, or metrics logic of its own. It calls, in order:
`data.download_market_data` -> `features.build_features` ->
`model_cv.nested_walk_forward` -> `ml_signal.{log_hurdle,
positions_from_predicted_return, signal_from_positions}` ->
`backtest_harness.run_backtest` -> `metrics.performance_summary`, plus
`signals.{buy_and_hold_signal, random_signal}` and
`ma_crossover_backtest.mean_holding_bars` for the two Rule 4 baselines.

**Why the baselines are not built from `ma_crossover_backtest.baseline_results`.**
That function summarizes each baseline's trade log with
`backtest_harness.summarize_trades` -- total P&L and win rate, no Sharpe or
drawdown. User Story 2 requires every row, baselines included, to carry
`performance_summary`'s risk-adjusted fields so a cross-ticker ranking
compares Sharpe, not raw P&L. `_baseline_rows` below therefore calls the same
two signal functions `baseline_results` calls (`buy_and_hold_signal`,
`random_signal`) directly and summarizes each resulting trade log with
`performance_summary` instead -- `mean_holding_bars` is reused verbatim, since
its holding-period arithmetic is unrelated to which summarizer runs after it.

**Failure isolation (FR-002).** `run_one_ticker` is the one place in this
module allowed to catch a bare `Exception`, and it catches exactly one span:
everything from downloading that ticker's data through building its three
rows. A `ComparisonFailure` is returned instead of raised -- a distinct type
from the list of row-dicts a success returns, so `run_comparison` cannot
mistake one for the other by checking a sentinel value. Every exception
*inside* the modules this composes is left to propagate normally; the
isolation boundary is this function's body, not a try/except sprinkled
through the pipeline.

Prerequisite: the ten-year download for `TICKER_UNIVERSE`, which this lane
cannot make itself (specs 002, 006). `main()` fails fast with the exact
command to run, rather than letting a network error surface from inside the
loop for whichever ticker happens to be first.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from data import cache_path, download_market_data
from estimators import REGRESSION
from features import build_features, feature_columns
from ma_crossover_backtest import mean_holding_bars
from backtest_harness import run_backtest
from metrics import performance_summary
from ml_signal import log_hurdle, positions_from_predicted_return, signal_from_positions
from model_cv import nested_walk_forward
from signals import buy_and_hold_signal, random_signal

# Settled in spec 013's Background: two more mega-cap names alongside the
# three `return_stats.py` already used for an unrelated purpose. Every one is
# high-priced, which keeps the per-share commission hurdle (spec 012) as small
# as this cost model allows. Not reopened here -- see spec.md Assumptions.
TICKER_UNIVERSE = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]

PERIOD = "10y"

# The estimator/target this module runs. Spec 012's cost-aware entry rule
# needs a continuous prediction, and `ridge`/regression is the regression
# entry spec 014's screening comparison found real improvement on (p =
# 0.0313) -- picked, not searched, per spec 013's own Assumptions ("this spec
# does not add model selection logic of its own").
ESTIMATOR_NAME = "ridge"
TARGET_KIND = "return"
LABEL_HORIZON = 1
EMBARGO_BARS = 1
RANDOM_STATE = 42

# A retail-broker cost model, restated from `ma_crossover_backtest.py` rather
# than imported -- Rule 8 puts this runner beside that script, not beneath it,
# and the two already agree because both trace to the same real broker
# assumption. Applied identically to every ticker and every strategy (Rule 3,
# SC-003): never a per-ticker override.
COMMISSION_PER_TRADE = 1.00
SLIPPAGE_BPS = 5.0

# The hurdle prices a round trip; once cleared, hold until the model no longer
# predicts a gain. See `ml_signal.positions_from_predicted_return`.
EXIT_THRESHOLD = 0.0

RANDOM_BASELINE_SEEDS = 20

STRATEGY_ML = "ml_cost_aware"
STRATEGY_BUY_AND_HOLD = "buy_and_hold"
STRATEGY_RANDOM = "random_baseline"


@dataclasses.dataclass(frozen=True)
class ComparisonFailure:
    """One ticker's pipeline could not complete. Reported, never swallowed."""

    ticker: str
    reason: str


def _bps(value: float) -> float:
    return float(value) * 10_000.0


def _baseline_rows(
    ticker: str,
    ml_prices: pd.DataFrame,
    ml_trade_log: pd.DataFrame,
    *,
    commission_per_trade: float,
    slippage_bps: float,
    seed_count: int,
) -> tuple[list[dict], dict]:
    """Buy-and-hold and random-baseline rows, run over the identical bars.

    `ml_prices` -- the features frame with the ML strategy's own
    `Buy_Next_Open`/`Sell_Next_Open` columns attached -- is what both
    baselines overwrite their own copy of, so all three strategies see an
    identical `Close` series and an identical row count. That identity is
    what makes "run over the same bars and costs" true rather than merely
    intended (Rule 4, User Story 2).
    """
    costs = {"commission_per_trade": commission_per_trade, "slippage_bps": slippage_bps}
    n_trades = len(ml_trade_log)
    holding_bars = mean_holding_bars(ml_prices, ml_trade_log)

    hold_log = run_backtest(buy_and_hold_signal(ml_prices), **costs)
    hold_summary = performance_summary(ml_prices, hold_log, **costs)

    random_summaries: list[dict] = []
    random_error: str | None = None
    try:
        for seed in range(seed_count):
            signalled = random_signal(ml_prices, n_trades, holding_bars, seed)
            trade_log = run_backtest(signalled, **costs)
            random_summaries.append(performance_summary(ml_prices, trade_log, **costs))
    except ValueError as error:
        # Reported, never swallowed: a random baseline that could not match
        # the strategy's trade frequency is not a baseline, and the honest
        # reading is a named reason, not a silently different comparison.
        random_summaries = []
        random_error = str(error)

    if random_summaries:
        pnls = np.array([row["total_pnl"] for row in random_summaries], dtype=float)
        random_row = dict(random_summaries[0])
        random_row["total_pnl"] = float(pnls.mean())
        random_row["total_return"] = float(
            np.mean([row["total_return"] for row in random_summaries])
        )
        sharpe_values = [
            row["sharpe_ratio"] for row in random_summaries if not np.isnan(row["sharpe_ratio"])
        ]
        # Every seed can legitimately produce an empty trade log (the cost
        # hurdle declines nearly every trade -- spec 012's own finding), which
        # makes every Sharpe `nan`. `np.nanmean` on an all-`nan` array warns
        # and still returns `nan`; filtering first reaches the same `nan`
        # without the warning.
        random_row["sharpe_ratio"] = float(np.mean(sharpe_values)) if sharpe_values else float("nan")
        random_row["max_drawdown"] = float(
            np.mean([row["max_drawdown"] for row in random_summaries])
        )
        random_pnl_dispersion = float(pnls.std(ddof=0))
    else:
        random_row = {
            "total_trades": 0,
            "total_pnl": float("nan"),
            "total_return": float("nan"),
            "sharpe_ratio": float("nan"),
            "max_drawdown": float("nan"),
            "drawdown_peak_bar": -1,
            "drawdown_trough_bar": -1,
            "bars": int(len(ml_prices)),
            "bars_in_market": 0,
            "capital_base": hold_summary["capital_base"],
            "commission_per_trade": float(commission_per_trade),
            "slippage_bps": float(slippage_bps),
        }
        random_pnl_dispersion = float("nan")

    honesty_columns = {"Median hurdle (bps)": float("nan"), "|pred| q90 (bps)": float("nan")}
    random_baseline_columns = {
        "random_baseline_seed_count": seed_count,
        "random_baseline_pnl_dispersion": random_pnl_dispersion,
        "random_baseline_error": random_error,
    }

    rows = [
        {
            "Ticker": ticker,
            "Strategy": STRATEGY_BUY_AND_HOLD,
            **hold_summary,
            **honesty_columns,
        },
        {
            "Ticker": ticker,
            "Strategy": STRATEGY_RANDOM,
            **random_row,
            **honesty_columns,
        },
    ]
    return rows, random_baseline_columns


def run_one_ticker(
    ticker: str,
    *,
    period: str = PERIOD,
    commission_per_trade: float = COMMISSION_PER_TRADE,
    slippage_bps: float = SLIPPAGE_BPS,
    random_state: int = RANDOM_STATE,
    seed_count: int = RANDOM_BASELINE_SEEDS,
) -> list[dict] | ComparisonFailure:
    """Run the full pipeline for one ticker; never raise past this function.

    Returns three row-dicts (cost-aware ML, buy-and-hold, random baseline) on
    success, or a `ComparisonFailure` naming the ticker and the reason on any
    exception raised along the way -- an empty frame from `download_market_data`
    and a frame too short for a single walk-forward fold both surface as
    ordinary exceptions here and are deliberately not special-cased apart
    (spec.md Edge Cases: "treated the same way").
    """
    try:
        prices = download_market_data([ticker], period=period)
        if prices.empty:
            raise ValueError(f"no market data returned for {ticker!r}")

        frame, task, label_horizon = build_features(
            prices, target_kind=TARGET_KIND, label_horizon=LABEL_HORIZON
        )

        predictions, covered, fold_results = nested_walk_forward(
            frame,
            feature_columns=feature_columns(),
            label_column="Label",
            task=task,
            name=ESTIMATOR_NAME,
            label_horizon=label_horizon,
            embargo_bars=EMBARGO_BARS,
            random_state=random_state,
        )
        assert task == REGRESSION, "ml_signal's hurdle comparison expects a continuous prediction"

        hurdle = log_hurdle(
            frame["Close"],
            commission_per_trade=commission_per_trade,
            slippage_bps=slippage_bps,
        )
        desired_long = positions_from_predicted_return(
            predictions, hurdle, exit_threshold=EXIT_THRESHOLD
        )
        buy_next_open, sell_next_open = signal_from_positions(desired_long)

        ml_prices = frame.copy()
        ml_prices["Buy_Next_Open"] = buy_next_open
        ml_prices["Sell_Next_Open"] = sell_next_open

        costs = {"commission_per_trade": commission_per_trade, "slippage_bps": slippage_bps}
        ml_trade_log = run_backtest(ml_prices, **costs)
        ml_summary = performance_summary(ml_prices, ml_trade_log, **costs)

        covered_predictions = predictions.iloc[np.sort(np.asarray(covered))].dropna()
        pred_q90_bps = (
            _bps(covered_predictions.abs().quantile(0.9))
            if not covered_predictions.empty
            else float("nan")
        )

        ml_row = {
            "Ticker": ticker,
            "Strategy": STRATEGY_ML,
            **ml_summary,
            "Median hurdle (bps)": _bps(hurdle.median()),
            "|pred| q90 (bps)": pred_q90_bps,
        }

        baseline_rows, random_baseline_columns = _baseline_rows(
            ticker,
            ml_prices,
            ml_trade_log,
            commission_per_trade=commission_per_trade,
            slippage_bps=slippage_bps,
            seed_count=seed_count,
        )

        # Every row -- the ML row included -- carries the same Rule 2/3/4
        # parameters behind its metrics (FR-005), so SC-003's cross-row
        # consistency check has the same columns to compare on every row.
        shared_columns = {
            "fold_count": len(fold_results),
            "purge_bars": label_horizon,
            "embargo_bars": EMBARGO_BARS,
            "random_state": random_state,
            **random_baseline_columns,
        }
        rows = [ml_row, *baseline_rows]
        for row in rows:
            row.update(shared_columns)
        return rows
    except Exception as error:  # noqa: BLE001 -- the deliberate isolation boundary (FR-002)
        return ComparisonFailure(ticker=ticker, reason=str(error))


def run_comparison(
    tickers: list[str] = TICKER_UNIVERSE,
    *,
    period: str = PERIOD,
    commission_per_trade: float = COMMISSION_PER_TRADE,
    slippage_bps: float = SLIPPAGE_BPS,
    random_state: int = RANDOM_STATE,
    seed_count: int = RANDOM_BASELINE_SEEDS,
) -> tuple[pd.DataFrame, list[ComparisonFailure]]:
    """Run every ticker independently; one failure never stops the rest.

    Returns `(results_frame, failures)`. `results_frame` is empty (with no
    columns) rather than absent when every ticker fails -- the loop still
    completes and the caller can see what failed for every name, never an
    unhandled exception from whichever ticker happened to be first.
    """
    all_rows: list[dict] = []
    failures: list[ComparisonFailure] = []

    for ticker in tickers:
        result = run_one_ticker(
            ticker,
            period=period,
            commission_per_trade=commission_per_trade,
            slippage_bps=slippage_bps,
            random_state=random_state,
            seed_count=seed_count,
        )
        if isinstance(result, ComparisonFailure):
            failures.append(result)
        else:
            all_rows.extend(result)

    results_frame = pd.DataFrame(all_rows)
    return results_frame, failures


def _output_filename(tickers: list[str]) -> str:
    """Ticker-namespaced, matching `data.py`'s own sorted-deduped convention.

    `phase2_logistic_baseline_results.csv` is not namespaced, so a naive loop
    over this universe would have each ticker overwrite the last (FR-006).
    """
    return f"{'-'.join(sorted(set(tickers)))}_comparison.csv"


def main() -> None:
    universe_cache = cache_path(
        f"{'-'.join(sorted(set(TICKER_UNIVERSE)))}_{PERIOD}.csv"
    )
    if not universe_cache.exists():
        raise SystemExit(
            "No cached market data for the ticker universe. This lane cannot "
            "reach Yahoo Finance (specs 002, 006) -- run this once on a "
            "machine with network access:\n\n"
            "  ./venv/Scripts/python.exe -c \"import sys; "
            "sys.path.insert(0,'scripts'); from data import "
            "download_market_data; download_market_data("
            f"{TICKER_UNIVERSE!r}, period={PERIOD!r})\""
        )

    results_frame, failures = run_comparison()

    output_path = cache_path(_output_filename(TICKER_UNIVERSE))
    results_frame.to_csv(output_path, index=False)
    print(f"Wrote {len(results_frame)} rows to {output_path}")

    if failures:
        print(f"\n{len(failures)} ticker(s) failed:")
        for failure in failures:
            print(f"  {failure.ticker}: {failure.reason}")


if __name__ == "__main__":
    main()
