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
from portfolio_backtest import FillCost, run_portfolio_backtest
from portfolio_risk import allocation_weights, equal_weight_book
from selection_bias import deflated_sharpe
from signals import ALLOCATION_SLEEVES, allocation_selection, decision_sessions, random_selections

LABEL = "ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED"
COST_MODEL = "spread_plus_sqrt_impact"
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


def allocation_report(opens: pd.DataFrame, closes: pd.DataFrame, *, fill_cost: FillCost, costs: dict,
                      seeds: list[int], starting_capital: float = 100_000.0) -> dict:
    """The FR-003 research-window report: allocation, buy-and-hold and seeded random baselines.

    `costs` must state a per-fill `commission` and a `slippage` dict whose `model` is spec 046's
    (Rule 13); `fill_cost` is that model's per-fill estimate. Raises `HoldoutSealError` for a panel
    past 2023-09-29 and `ValueError` for other costs or fewer than two seeds.
    """
    slippage = costs.get("slippage") if isinstance(costs, dict) else None
    if not isinstance(slippage, dict) or slippage.get("model") != COST_MODEL or "commission" not in costs:
        raise ValueError(f"costs must state a commission and the spec 046 {COST_MODEL!r} slippage model (Rule 13)")
    if sealed_sessions(closes.index).any() or sealed_sessions(opens.index).any():
        raise HoldoutSealError(f"the allocation report reads the research window only (<= {RESEARCH_END})")
    columns = [ticker for ticker in closes.columns if ticker in ALLOCATION_SLEEVES]
    opens, closes = opens[columns], closes[columns]  # only the eight sleeves exist for every series
    decisions = decision_sessions(closes.index, cadence="monthly")
    selection = allocation_selection(closes)

    def run(weights: pd.DataFrame) -> pd.Series:
        return run_portfolio_backtest(opens, closes, weights, starting_capital=starting_capital,
                                      commission_per_fill=costs["commission"], fill_cost=fill_cost).equity

    allocation = series_stats(run(allocation_weights(selection, closes, decisions)))
    buy_and_hold = series_stats(run(equal_weight_book(closes.notna(), max_gross=1.0).loc[decisions]))
    # `matched_activity` of an always-invested allocation is degenerate (enter 1, exit 0): the draws
    # would reproduce the allocation and the baseline would show no dispersion. Each sleeve is instead
    # long or flat with probability 1/2 on every decision row: same cadence, sizing and costs.
    activity = dict(RANDOM_ACTIVITY)
    draws = random_selections(closes, decision_mask=decisions, seeds=seeds, **activity)
    random = {seed: series_stats(run(allocation_weights(draw, closes, decisions))) for seed, draw in draws.items()}
    sharpes = [s["sharpe"] for s in random.values() if s["sharpe"] is not None]
    dispersion = {"seeds": list(draws), "mean_sharpe": float(np.mean(sharpes)) if sharpes else None,
                  "std_sharpe": float(np.std(sharpes, ddof=1)) if len(sharpes) > 1 else None,
                  "min_sharpe": min(sharpes) if sharpes else None, "max_sharpe": max(sharpes) if sharpes else None}
    return {"label": LABEL, "window": [closes.index[0].strftime("%Y-%m-%d"), closes.index[-1].strftime("%Y-%m-%d")],
            "costs": {"commission": costs["commission"], "slippage": slippage}, "allocation": allocation,
            "buy_and_hold": buy_and_hold, "random": random, "random_dispersion": dispersion, "activity": activity}


def _number(value: float | None, digits: int = 3) -> str:
    return "undefined" if value is None else f"{value:.{digits}f}"


def render(report: dict, stamp: list[str]) -> list[str]:
    """Report lines: the Rule 11 `stamp` first, the label on every Sharpe line, the full register last."""
    a, b, d = report["allocation"], report["buy_and_hold"], report["random_dispersion"]
    lines = [*stamp, LABEL,
             f"window: {report['window'][0]} to {report['window'][1]} (research window; holdout sealed)",
             f"costs: commission {report['costs']['commission']} per fill; slippage model "
             f"{report['costs']['slippage']['model']} (spec 046), identical for every series",
             f"allocation: Sharpe {_number(a['sharpe'])}, PSR(N=1) {_number(a['psr'])} [{LABEL}]",
             f"buy-and-hold (equal-weight sleeves): Sharpe {_number(b['sharpe'])} [{LABEL}]",
             f"random baseline ({len(d['seeds'])} seeds): mean Sharpe {_number(d['mean_sharpe'])}, "
             f"std {_number(d['std_sharpe'])}, range {_number(d['min_sharpe'])} to {_number(d['max_sharpe'])} [{LABEL}]",
             "Limitations (Rule 16), docs/SCOPE-V1.md §6:"]
    return lines + [f"- {item}" for item in LIMITATIONS]
