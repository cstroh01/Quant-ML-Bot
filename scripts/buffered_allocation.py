"""Spec 061 T002: buffered equal-weight targets; no execution or accounting."""
from __future__ import annotations

import pandas as pd

from portfolio_risk import equal_weight_book
from signals import ALLOCATION_SLEEVES, decision_sessions

CASH_RESERVE = 0.07


def buffered_weights(closes: pd.DataFrame) -> pd.DataFrame:
    """Monthly targets on the eight declared sleeves, using only closes through t."""
    closes = closes.loc[:, list(ALLOCATION_SLEEVES)]
    decisions = decision_sessions(closes.index, cadence="monthly")
    return equal_weight_book(closes.notna(), max_gross=1.0 - CASH_RESERVE).loc[decisions]
