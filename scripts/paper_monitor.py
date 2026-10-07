"""049 T012: retrospective trend-direction diagnostics, never P&L or features.

The state for t is causal. Its next-session outcome and rolling hit rate are
observable only at t+1's completed close, explicitly recorded in each row.
Ties/missing closes are unknown and invalidate their rolling window. This
monitors the deployed SMA rule, not an ML model or statistically validated edge.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import paper_targets
from data import trading_days


def monitor(closes: pd.DataFrame, *, source: str, window: int = 63) -> pd.DataFrame:
    """Return per-decision-session/ticker matured direction diagnostic rows.

    Input rows must include every NYSE session in their range; per-ticker NaN
    closes remain unknown. No resampling, filling, fetching, writing, fitting,
    trading, costed return evaluation or trial recording occurs here.
    ``source`` identifies the caller's artifact; attrs also hash input bytes and
    this implementation. No output is eligible as a performance result.
    """
    if not isinstance(window, int) or isinstance(window, bool) or window < 1:
        raise ValueError("window must be a positive session count")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source artifact identity is required")
    index = closes.index
    if (not isinstance(index, pd.DatetimeIndex) or index.tz is not None
            or index.hasnans or not index.equals(index.normalize())
            or not index.is_unique or not index.is_monotonic_increasing):
        raise ValueError("sessions must be unique increasing naive midnight labels")
    if closes.empty or not closes.columns.is_unique:
        raise ValueError("a nonempty panel with unique ticker columns is required")
    expected = pd.DatetimeIndex(trading_days(index[0].date(), index[-1].date()))
    if not index.equals(expected):
        raise ValueError("panel must contain every NYSE session; missing sessions are not a longer horizon")
    values = closes.to_numpy(dtype=float)
    if np.isinf(values).any() or (values[np.isfinite(values)] <= 0).any():
        raise ValueError("recorded closes must be positive finite values or missing")
    next_returns = closes.shift(-1).div(closes).sub(1.0)
    rows = []
    for i, session in enumerate(index):
        next_session = index[min(i + 1, len(index) - 1)]
        state = paper_targets.trend_confidence(closes, session)
        for ticker in closes.columns:
            outcome = float(next_returns.loc[session, ticker])
            known = np.isfinite(outcome) and outcome != 0.0
            hit = float((outcome > 0) == (state[ticker] > 0)) if known else np.nan
            rows.append(dict(Decision_Session=session, Ticker=ticker,
                             Outcome_Session=next_session if i + 1 < len(index) else pd.NaT,
                             Confidence=float(state[ticker]), Next_Return=outcome, Hit=hit,
                             Coin_Flip_Baseline=0.5))
    result = pd.DataFrame(rows).set_index(["Decision_Session", "Ticker"])
    result["Rolling_Hit_Rate"] = result.groupby(level="Ticker", sort=False).Hit.transform(
        lambda hits: hits.rolling(window, min_periods=window).mean())
    result.attrs.update(source=source,
        input_sha256=hashlib.sha256(closes.to_csv(date_format="%Y-%m-%d").encode()).hexdigest(),
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        observed_through_session=index[-1].strftime("%Y-%m-%d"), window_sessions=window,
        availability="Confidence uses <=t; Next_Return, Hit and Rolling_Hit_Rate mature at t+1 close (Outcome_Session).",
        disclosure="diagnostic, not a result; retrospective direction only, no P&L/cost/DSR or edge claim; static survivor panel and modeled-cost limitations remain.")
    return result
