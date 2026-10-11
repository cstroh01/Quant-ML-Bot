"""Multi-asset weights -> next-open fills -> portfolio P&L (spec 058 T010, D-6).

A `weights` row labelled session t is a decision made at the close of t. Its
share targets are fixed at that close, from equity and closes through t only,
and fill at the open of the next panel session t+1 (Rule 1). A ticker with no
row on a session (NaN open, or NaN close at the decision) is not tradable
then: its order is skipped and recorded, and its holding is left unchanged.

Costs come from an injected `fill_cost(ticker, as_of, quantity)` returning the
adverse fraction, read as of the decision session t (spec 046's
`estimate_fill_cost(...).total` plugs in). A `CostUnavailable` skips that order;
it never fills free. Commission per fill is required (Rule 3). Long-only with
no borrowing: buys the cash after sells cannot fund are scaled down together,
priced at the unscaled quantity's cost (conservative). Panels must share one
share basis; splits and dividends are not applied here. This module knows
nothing of how weights or signals were produced (Rule 8).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from cost_model import CostUnavailable

FillCost = Callable[[str, pd.Timestamp, float], float]
GROSS_TOLERANCE = 1e-9
FILL_COLUMNS = ["Decision", "Session", "Ticker", "Quantity", "Quote", "Price",
                "Cost_Fraction", "Slippage", "Commission"]
SKIP_COLUMNS = ["Decision", "Session", "Ticker", "Reason"]


@dataclass(frozen=True)
class PortfolioResult:
    """Close-marked equity and holdings per session, plus every fill and skipped order."""

    equity: pd.Series
    holdings: pd.DataFrame
    fills: pd.DataFrame
    skipped: pd.DataFrame
    commission_per_fill: float


def _require_amount(name: str, value: object, *, positive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not np.isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'non-negative'}")
    return number


def _validate(opens: pd.DataFrame, closes: pd.DataFrame, weights: pd.DataFrame) -> None:
    for name, frame in (("opens", opens), ("closes", closes), ("weights", weights)):
        index = frame.index
        if not isinstance(index, pd.DatetimeIndex) or index.tz is not None \
                or not (index == index.normalize()).all() or index.has_duplicates \
                or not index.is_monotonic_increasing or frame.columns.has_duplicates:
            raise ValueError(f"{name} needs naive, midnight, unique, ascending sessions and unique tickers")
    if not (opens.index.equals(closes.index) and opens.columns.equals(closes.columns)):
        raise ValueError("opens and closes must share sessions and tickers")
    if not (weights.index.isin(opens.index).all() and weights.columns.isin(opens.columns).all()):
        raise ValueError("weights must use panel sessions and tickers")
    prices = np.concatenate([opens.to_numpy(float).ravel(), closes.to_numpy(float).ravel()])
    present = prices[~np.isnan(prices)]
    if not (np.isfinite(present) & (present > 0)).all():
        raise ValueError("prices must be positive and finite where a row exists")
    w = weights.to_numpy(float)
    if not np.isfinite(w).all() or (w < 0).any() or (w.sum(axis=1) > 1 + GROSS_TOLERANCE).any():
        raise ValueError("weights must be finite, long-only and gross <= 1")


def run_portfolio_backtest(opens: pd.DataFrame, closes: pd.DataFrame, weights: pd.DataFrame, *,
                           starting_capital: float, commission_per_fill: float,
                           fill_cost: FillCost) -> PortfolioResult:
    """Fund each decision at the next open; every value at session t uses data through t only."""
    _validate(opens, closes, weights)
    cash = _require_amount("starting_capital", starting_capital, positive=True)
    commission = _require_amount("commission_per_fill", commission_per_fill, positive=False)
    tickers, sessions = opens.columns, opens.index
    weights = weights.reindex(columns=tickers, fill_value=0.0)
    marks = closes.ffill()  # last observed close at or before each session; never a later one
    shares = pd.Series(0.0, index=tickers)
    pending = None
    equity, held, fills, skipped = [], [], [], []
    for i, session in enumerate(sessions):
        if pending is not None:
            decision, target = pending
            quotes = opens.iloc[i]
            orders = []
            for ticker, delta in (target - shares).items():
                if delta == 0:
                    continue
                if np.isnan(quotes[ticker]):
                    skipped.append((decision, session, ticker, "no_row"))
                    continue
                try:
                    fraction = float(fill_cost(ticker, decision, abs(delta)))
                except CostUnavailable as error:
                    skipped.append((decision, session, ticker, f"cost_unavailable:{error.reason}"))
                    continue
                if not 0 <= fraction < 1:
                    raise ValueError(f"fill_cost for {ticker} must be in [0, 1); got {fraction}")
                orders.append((ticker, delta, quotes[ticker], fraction))
            buys = [o for o in orders if o[1] > 0]
            for ticker, delta, quote, fraction in [o for o in orders if o[1] < 0]:
                cash += -delta * quote * (1 - fraction) - commission
                shares[ticker] += delta
                fills.append((decision, session, ticker, delta, quote, quote * (1 - fraction),
                              fraction, -delta * quote * fraction, commission))
            notional = sum(delta * quote * (1 + fraction) for _, delta, quote, fraction in buys)
            scale = min(1.0, max(cash - commission * len(buys), 0.0) / notional) if buys else 0.0
            for ticker, delta, quote, fraction in buys:
                if scale == 0:
                    skipped.append((decision, session, ticker, "insufficient_cash"))
                    continue
                quantity = delta * scale
                cash -= quantity * quote * (1 + fraction) + commission
                shares[ticker] += quantity
                fills.append((decision, session, ticker, quantity, quote, quote * (1 + fraction),
                              fraction, quantity * quote * fraction, commission))
            pending = None
        value = cash + float((shares * marks.iloc[i].fillna(0.0)).sum())
        equity.append(value)
        held.append(shares.copy())
        if session not in weights.index:
            continue
        if i + 1 == len(sessions):
            skipped.append((session, pd.NaT, None, "no_next_session"))
            continue
        row, close, target = weights.loc[session], closes.iloc[i], shares.copy()
        for ticker in tickers:
            if row[ticker] > 0 and np.isnan(close[ticker]):
                skipped.append((session, sessions[i + 1], ticker, "no_close_at_decision"))
            else:
                target[ticker] = row[ticker] * value / close[ticker] if row[ticker] > 0 else 0.0
        pending = (session, target)
    return PortfolioResult(pd.Series(equity, index=sessions, name="Equity"),
                           pd.DataFrame(held, index=sessions),
                           pd.DataFrame(fills, columns=FILL_COLUMNS),
                           pd.DataFrame(skipped, columns=SKIP_COLUMNS), commission)
