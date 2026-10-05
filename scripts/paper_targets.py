"""Paper-loop decision layer: completed closes in, signed share deltas out.

Pure and offline. This module owns *what the book should hold after the next
open*, computed from data that existed at the close of ``session``. It knows
nothing about brokers, credentials, the safety gate, fills, or P&L (Rule 8).
``exec/paper_loop.py`` feeds it a price panel and a broker snapshot and sends
whatever it returns through ``order_gateway.submit_order``.

Guarantees:

- **Point-in-time (Rule 1).** Every output for ``session`` is bit-identical
  under any change to rows after ``session``. Orders computed from the close
  of ``session`` are for the *next* open, which is the same next-open fill
  convention ``signals.sma_crossover_signal`` uses in the backtest.
- **Long-only, whole shares, cash account.** A buy rounds *down* toward the
  target, a sell never takes a position below zero, so rounding can only
  leave the book smaller than the target, never larger.
- **Sells first.** Reduce-only orders are returned before any buy, so the
  safety gate sees exposure fall before it is asked to add any.

This is the spec 049 mechanics prototype. The trend rule is a
reference implementation, not a validated strategy, and nothing it produces is
a result (Rules 11, 15, 16).
"""

from __future__ import annotations

import dataclasses
import math
from typing import Mapping

import pandas as pd

from portfolio_risk import RiskConfig, target_weights

# Sizing for the paper prototype. Chosen to sit strictly inside the safety
# gate's provisional limits (ADR 0002 item 5, SafetyConfig 2026-09-29-v1:
# max_position_pct 0.10, max_gross_pct 0.60). The gate denies at *reaching*
# a limit, and its worst-case price is above the last close, so the per-name
# cap is 0.08, not 0.10, and five names at 0.08 is 0.40 gross, under 0.60.
# Every other field is spec 017's RECOMMENDED_CONFIG. Camden-owned values:
# changing them is a sizing decision recorded in spec 049.
PAPER_RISK_CONFIG = RiskConfig(
    target_volatility=0.10,
    max_weight=0.08,
    max_gross=0.40,
    volatility_window=63,
    correlation_window=63,
    daily_loss_limit=0.02,
    weekly_loss_limit=0.04,
    weekly_drawdown_limit=0.05,
)

SHORT_WINDOW = 10
LONG_WINDOW = 30


@dataclasses.dataclass(frozen=True)
class OrderDelta:
    """One signed whole-share change for the next open."""

    ticker: str
    delta_quantity: float
    target_weight: float
    reference_price: float


def close_panel(tidy: pd.DataFrame) -> pd.DataFrame:
    """Wide Close panel (session label index x ticker) from tidy OHLCV.

    Session labels stay timezone-naive and midnight-normalized (CLAUDE.md,
    Timestamps). Raises if a (Date, Ticker) pair repeats.
    """
    required = {"Date", "Ticker", "Close"}
    missing = required - set(tidy.columns)
    if missing:
        raise ValueError(f"tidy frame is missing columns: {sorted(missing)}")
    if tidy.duplicated(["Date", "Ticker"]).any():
        raise ValueError("tidy frame repeats a (Date, Ticker) pair.")
    panel = tidy.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    panel.index = pd.DatetimeIndex(panel.index)
    if panel.index.tz is not None:
        raise ValueError("session labels must be timezone-naive.")
    panel.columns.name = None
    return panel


def trend_confidence(
    closes: pd.DataFrame,
    session: pd.Timestamp,
    *,
    short_window: int = SHORT_WINDOW,
    long_window: int = LONG_WINDOW,
) -> pd.Series:
    """1.0 where the short SMA is above the long SMA at ``session``'s close.

    This is the *state* of ``signals.sma_crossover_signal``'s rule (long while
    the short average is above the long one), read at one session. A name
    without ``long_window`` completed closes up to ``session`` gets 0.0.
    Reads only ``closes.loc[:session]``.
    """
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window.")
    label = pd.Timestamp(session)
    if label not in closes.index:
        raise ValueError(f"session {label.date()} is not in the price panel.")
    history = closes.loc[:label]
    out = {}
    for ticker in closes.columns:
        series = history[ticker].dropna()
        if len(series) < long_window or series.index[-1] != label:
            out[ticker] = 0.0
            continue
        short = series.iloc[-short_window:].mean()
        long = series.iloc[-long_window:].mean()
        out[ticker] = 1.0 if short > long else 0.0
    return pd.Series(out, name="Confidence", dtype="float64")


def order_deltas(
    targets: pd.Series,
    *,
    equity: float,
    positions: Mapping[str, float],
    prices: Mapping[str, float],
) -> list[OrderDelta]:
    """Whole-share orders that move ``positions`` toward ``targets``.

    ``targets`` are equity fractions; ``prices`` are per-share reference
    prices (the last completed close). A buy's target quantity is floored;
    a sell never goes below zero; a held name absent from ``targets`` is
    sold to zero. Sells are returned first, each group sorted by ticker.
    """
    if not (isinstance(equity, (int, float)) and math.isfinite(equity) and equity > 0):
        raise ValueError("equity must be a positive finite number.")
    sells: list[OrderDelta] = []
    buys: list[OrderDelta] = []
    names = sorted(set(targets.index) | {k for k, v in positions.items() if v})
    for ticker in names:
        weight = float(targets.get(ticker, 0.0))
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"target weight for {ticker} must be finite and >= 0.")
        held = float(positions.get(ticker, 0.0))
        if held < 0:
            raise ValueError(f"{ticker}: short positions are out of scope (long-only).")
        price = prices.get(ticker)
        if weight > 0:
            if price is None or not math.isfinite(price) or price <= 0:
                raise ValueError(f"{ticker}: no valid reference price to size a target.")
            wanted = math.floor(weight * equity / price)
        else:
            wanted = 0
        if wanted == 0:
            delta = -held  # flatten fully, fractional remainder included
        else:
            delta = float(wanted - math.floor(held))
        if delta == 0:
            continue
        ref = float(price) if price is not None else float("nan")
        item = OrderDelta(ticker, delta, weight, ref)
        (sells if delta < 0 else buys).append(item)
    return sells + buys


def plan_next_open(
    closes: pd.DataFrame,
    session: pd.Timestamp,
    *,
    equity: float,
    positions: Mapping[str, float],
    entries_halted: bool,
    config: RiskConfig = PAPER_RISK_CONFIG,
) -> tuple[pd.DataFrame, list[OrderDelta]]:
    """The decision frame and the orders for the open after ``session``.

    Current weights are marked at ``session``'s close. The decision frame is
    ``portfolio_risk.target_weights``'s full record, so every step of the
    sizing is inspectable in the run log.
    """
    label = pd.Timestamp(session)
    confidence = trend_confidence(closes, label)
    last = closes.loc[label]
    current = pd.Series(
        {t: float(positions.get(t, 0.0)) * float(last[t]) / equity for t in closes.columns},
        dtype="float64",
    ).fillna(0.0)
    decision = target_weights(
        closes,
        confidence,
        current,
        session=label,
        config=config,
        entries_halted=entries_halted,
    )
    prices = {t: float(last[t]) for t in closes.columns if pd.notna(last[t])}
    orders = order_deltas(decision["Target"], equity=equity, positions=positions, prices=prices)
    return decision, orders
