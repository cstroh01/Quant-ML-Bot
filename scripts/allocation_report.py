"""Spec 059 T003 / FR-003: offline costed backtest report for the preregistered allocation.

ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED. The allocation is a portfolio-construction choice,
not a forecast (constitution Rule 15 carve-out). This module composes, read-only: `signals` (sleeves,
monthly rows, the seeded random baseline), `portfolio_risk` (weights), `portfolio_backtest` (next-open
fills with the injected spec 046 `fill_cost`), `selection_bias.deflated_sharpe` (PSR at N = 1) and
`disclosure` (register, provenance). It downloads nothing.

Every series runs over the identical panel with the identical costs (Rule 4): the allocation, an
equal-weight buy-and-hold of the sleeves with a close (rebalanced on the same monthly rows), and the
random baseline over at least two seeds, each sleeve long or flat with probability 1/2 on every
decision row and sized exactly as the allocation, reported as mean, dispersion and range. A panel holding any session after 2023-09-29 is
refused, so spec 058's sealed holdout is never read; the full-history variant FR-003 also names is
not built here (it would read those sessions).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
from cost_utils import risk_free_log_return
from data_sources import RESEARCH_END, HoldoutSealError, sealed_sessions
from disclosure import LIMITATIONS
from cost_model import CostConfig, estimate_fill_cost
from portfolio_backtest import run_portfolio_backtest
from portfolio_risk import allocation_weights, equal_weight_book
from selection_bias import deflated_sharpe
from signals import ALLOCATION_SLEEVES, allocation_selection, decision_sessions, random_selections

LABEL = "ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED"
RANDOM_ACTIVITY = {"enter_probability": 0.5, "exit_probability": 0.5, "initial_probability": 0.5}


def series_stats(equity: pd.Series) -> dict:
    """Daily log-return statistics of close-marked equity, with PSR against zero at N = 1.

    Excess returns subtract `log1p(RISK_FREE_RATE_ANNUAL) / 252` per session. The annualized Sharpe
    and the PSR are undefined (None) for fewer than two returns or zero variance.
    """
    returns = np.log(equity / equity.shift(1)).iloc[1:]
    excess = returns - risk_free_log_return(RISK_FREE_RATE_ANNUAL) / TRADING_DAYS_PER_YEAR
    n, std = len(excess), float(excess.std(ddof=1)) if len(excess) > 1 else float("nan")
    stats = {"sessions": n, "total_log_return": float(returns.sum()), "sharpe": None, "psr": None}
    if n < 2 or not math.isfinite(std) or std == 0:
        return stats
    daily = float(excess.mean()) / std
    centered = excess - excess.mean()
    variance = float((centered ** 2).mean())
    psr = deflated_sharpe(observed_sharpe=daily, observations=n,
                          skewness=float((centered ** 3).mean()) / variance ** 1.5,
                          pearson_kurtosis=float((centered ** 4).mean()) / variance ** 2,
                          trial_sharpe_std=1.0, n_current=1)
    stats.update(sharpe=daily * math.sqrt(TRADING_DAYS_PER_YEAR), psr=psr["value"])
    return stats


def cash_months(weights: pd.DataFrame, required: pd.DataFrame) -> dict:
    """Spec 059 D-6: decision rows of `weights` that hold nothing although `required` marks a sleeve.

    A row whose sleeves need an EWMA variance or covariance that is undefined is sized all cash; such
    a row counts. A row where no sleeve is eligible yet (warm-up) is not a data hole and is not counted.
    Missing weights count as cash. Returns the count and the ISO dates, in row order.
    """
    invested = weights.fillna(0.0).ne(0.0).any(axis=1)
    needed = required.loc[weights.index].any(axis=1)
    dates = weights.index[needed & ~invested]
    return {"count": int(len(dates)), "dates": [d.strftime("%Y-%m-%d") for d in dates]}


def allocation_report(bars: dict[str, pd.DataFrame], *, commission_per_fill: float, cost_config: CostConfig,
                      split_sessions: dict[str, tuple], seeds: list[int], starting_capital: float = 100_000.0) -> dict:
    """The FR-003 research-window report: allocation, buy-and-hold and seeded random baselines.

    `bars` maps tickers to OHLCV frames on NYSE session labels (with `attrs["volume_basis"]`); only the
    eight sleeves are read. Every fill's slippage is `cost_model.estimate_fill_cost(...).total` under
    `cost_config` (spec 046, Rule 13), computed here, so the recorded cost model is the one applied; a
    fill with no valid estimate is skipped, never filled free. Raises `HoldoutSealError` for bars past
    2023-09-29 and `ValueError` for a non-finite or negative commission or fewer than two seeds.
    """
    if not isinstance(cost_config, CostConfig):
        raise ValueError("cost_config must be a validated spec 046 CostConfig (Rule 13)")
    if isinstance(commission_per_fill, bool) or not (isinstance(commission_per_fill, (int, float))
                                                     and math.isfinite(commission_per_fill) and commission_per_fill >= 0):
        raise ValueError("commission_per_fill must be a finite, non-negative number (Rule 3)")
    sleeves = [ticker for ticker in ALLOCATION_SLEEVES if ticker in bars]
    if not sleeves:
        raise ValueError("bars hold none of the allocation's sleeves")
    opens = pd.DataFrame({t: bars[t]["Open"] for t in sleeves}).sort_index()
    closes = pd.DataFrame({t: bars[t]["Close"] for t in sleeves}).sort_index()
    if sealed_sessions(closes.index).any():
        raise HoldoutSealError(f"the allocation report reads the research window only (<= {RESEARCH_END})")
    decisions = decision_sessions(closes.index, cadence="monthly")
    selection = allocation_selection(closes)

    def fill_cost(ticker: str, as_of: pd.Timestamp, quantity: float) -> float:
        return estimate_fill_cost(bars[ticker], as_of=as_of, quantity=quantity, config=cost_config,
                                  split_sessions=split_sessions.get(ticker, ())).total

    def run(weights: pd.DataFrame) -> pd.Series:
        return run_portfolio_backtest(opens, closes, weights, starting_capital=starting_capital,
                                      commission_per_fill=commission_per_fill, fill_cost=fill_cost).equity

    allocation_book = allocation_weights(selection, closes, decisions)
    allocation = series_stats(run(allocation_book))
    held = closes.notna()
    buy_and_hold_book = equal_weight_book(held, max_gross=1.0).loc[decisions]
    buy_and_hold = series_stats(run(buy_and_hold_book))
    # `matched_activity` of an always-invested allocation is degenerate (enter 1, exit 0): the draws
    # would reproduce the allocation and the baseline would show no dispersion. Each sleeve is instead
    # long or flat with probability 1/2 on every decision row: same cadence, sizing and costs.
    draws = random_selections(closes, decision_mask=decisions, seeds=seeds, **RANDOM_ACTIVITY)
    random_books = {seed: allocation_weights(draw, closes, decisions) for seed, draw in draws.items()}
    random = {seed: series_stats(run(book)) for seed, book in random_books.items()}
    cash = {"allocation": cash_months(allocation_book, selection),
            "buy_and_hold": cash_months(buy_and_hold_book, held),
            # a draw may hold a sleeve before it is eligible (warm-up); only eligible draws are required
            "random": {seed: cash_months(book, draws[seed] & selection) for seed, book in random_books.items()},
            "warmup_rows": int((~selection.loc[allocation_book.index].any(axis=1)).sum())}
    sharpes = [s["sharpe"] for s in random.values() if s["sharpe"] is not None]
    dispersion = {"seeds": list(draws), "mean_sharpe": float(np.mean(sharpes)) if sharpes else None,
                  "std_sharpe": float(np.std(sharpes, ddof=1)) if len(sharpes) > 1 else None,
                  "min_sharpe": min(sharpes) if sharpes else None, "max_sharpe": max(sharpes) if sharpes else None}
    return {"label": LABEL, "window": [closes.index[0].strftime("%Y-%m-%d"), closes.index[-1].strftime("%Y-%m-%d")],
            "costs": {"commission": commission_per_fill, "slippage": cost_config.as_mapping()},
            "allocation": allocation, "buy_and_hold": buy_and_hold, "random": random,
            "random_dispersion": dispersion, "random_activity": dict(RANDOM_ACTIVITY), "cash_months": cash}


def _number(value: float | None, digits: int = 3) -> str:
    return "undefined" if value is None else f"{value:.{digits}f}"


def _cash_line(cash: dict) -> str:
    def one(name: str, entry: dict) -> str:
        return f"{name} {entry['count']} [{', '.join(entry['dates'])}]"
    random = "; ".join(one(f"seed {seed}", entry) for seed, entry in cash["random"].items())
    return (f"cash months (D-6: a required EWMA variance or covariance undefined, whole book cash): "
            f"{one('allocation', cash['allocation'])}; {one('buy-and-hold', cash['buy_and_hold'])}; random {random}; "
            f"{cash['warmup_rows']} warm-up decision rows with no sleeve eligible are cash and not counted")


def render(report: dict, stamp: list[str]) -> list[str]:
    """Report lines: the Rule 11 `stamp` first, the label on every Sharpe line, the full register last."""
    a, b, d = report["allocation"], report["buy_and_hold"], report["random_dispersion"]
    lines = [*stamp, LABEL,
             f"window: {report['window'][0]} to {report['window'][1]} (research window; holdout sealed); one pass, "
             "no fitted parameters, so folds, purge and embargo do not apply",
             f"costs: commission {report['costs']['commission']} per fill; slippage model "
             f"{report['costs']['slippage']['model']} (spec 046), identical for every series",
             f"allocation: Sharpe {_number(a['sharpe'])}, PSR(N=1) {_number(a['psr'])} [{LABEL}]",
             f"buy-and-hold (equal-weight sleeves, rebalanced monthly): Sharpe {_number(b['sharpe'])} [{LABEL}]",
             f"random baseline ({len(d['seeds'])} seeds, each sleeve long/flat at 1/2 per decision): mean Sharpe {_number(d['mean_sharpe'])}, "
             f"std {_number(d['std_sharpe'])}, range {_number(d['min_sharpe'])} to {_number(d['max_sharpe'])} [{LABEL}]",
             _cash_line(report["cash_months"]),
             "Limitations (Rule 16), docs/SCOPE-V1.md §6:"]
    return lines + [f"- {item}" for item in LIMITATIONS]
