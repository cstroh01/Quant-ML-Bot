"""Spec 058 T014: purged, embargoed walk-forward runner for the preregistered 058-edge family.

One call evaluates one declared configuration on a session panel that ends inside the research
window, records it through `trial_runner.research_attempt(family="058-edge")`, and stores its
out-of-sample daily log returns with fold count, purge and embargo (Rules 2, 3).

Composition only (Rule 8): `signals` decides holdings and rebalance rows, `portfolio_risk` sizes
them, `portfolio_backtest` fills them at the next open and costs them through the injected
`fill_cost` (spec 046), and `walk_forward_cv` defines the folds. No configuration fits a parameter,
so a fold's training window is never read: the walk-forward discipline is that only test-window
sessions are recorded, every row at t computed from data at or before t, with the purge and an
embargo at least the longest lookback stated beside them.

Sizing (spec 058 §5, declaration `common`): inverse-volatility legs scaled to a 10% portfolio
volatility target for H1, H2, H4, H5 (and H9 as their blend); H10 is a fixed 60/40; B-BH is equal
weight of every name with a close. H3, H6, H7 and H8 are equal legs whose book is scaled by
`min(1, 0.10 / portfolio_vol)` and capped at gross 1 (058 D-8, declaration `common.sizing`). H8
rebalances on the first session of each ISO week; every other configuration monthly.

Never runs T015: tests inject a synthetic ledger and the real ledger is written only by a caller
that enables production recording.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data_sources import RESEARCH_END, HoldoutSealError, sealed_sessions
from portfolio_backtest import FillCost, run_portfolio_backtest
from portfolio_risk import (blend_books, equal_weight_book, equal_weight_vol_target_book, fixed_allocation_book,
                            volatility_target_book)
from signals import MONTH_SESSIONS, decision_sessions, hypothesis_selection
from trial_runner import research_attempt
from walk_forward_cv import walk_forward_splits

FAMILY = "058-edge"
RUNNER = "edge_walk_forward.run_configuration"
VOL_SPAN = 60
TARGET_VOLATILITY = 0.10
MAX_GROSS = 1.0
# H1-12 and H3 read close[t - 252] and need every close from there to t: 253 sessions.
LONGEST_LOOKBACK = 12 * MONTH_SESSIONS + 1
# A decision at close t fills at the open of t+1; its return is realized by close t+1.
LABEL_HORIZON = 1
EMBARGO = LONGEST_LOOKBACK
INITIAL_TRAIN_MONTHS = 13  # covers the longest lookback before the first test window
TEST_MONTHS = 12
COST_MODEL = "spread_plus_sqrt_impact"
INVERSE_VOL = ("H1-3", "H1-6", "H1-12", "H2-100", "H2-200", "H4", "H5")
H9_PARTS = ("H1-12", "H2-200", "H4")
H10 = {"SPY": 0.6, "IEF": 0.4}
EQUAL_LEGS = ("H3-3", "H3-5", "H6-6", "H6-12", "H7", "H8")  # 058 D-8
WEEKLY = ("H8",)
CONFIGURATIONS = (*INVERSE_VOL, *EQUAL_LEGS, "H9", "H10", "B-BH")


def require_buildable(config_id: str) -> None:
    """Raise `ValueError` for a configuration the 058 declaration does not name."""
    if config_id not in CONFIGURATIONS:
        raise ValueError(f"unknown 058 configuration {config_id!r}")


def target_book(config_id: str, closes: pd.DataFrame) -> pd.DataFrame:
    """Target weights for `config_id` on its monthly rebalance rows only. Row t reads closes at or before t."""
    require_buildable(config_id)

    def sized(part: str) -> pd.DataFrame:
        return volatility_target_book(hypothesis_selection(part, closes), closes, span=VOL_SPAN,
                                      target_volatility=TARGET_VOLATILITY, max_gross=MAX_GROSS)

    if config_id in EQUAL_LEGS:
        book = equal_weight_vol_target_book(hypothesis_selection(config_id, closes), closes, span=VOL_SPAN,
                                            target_volatility=TARGET_VOLATILITY, max_gross=MAX_GROSS)
    elif config_id == "H9":
        book = blend_books(*(sized(part) for part in H9_PARTS))
    elif config_id == "H10":
        book = fixed_allocation_book(closes, H10)
    elif config_id == "B-BH":
        book = equal_weight_book(closes.notna(), max_gross=MAX_GROSS)
    else:
        book = sized(config_id)
    return book.loc[decision_sessions(book.index, cadence="weekly" if config_id in WEEKLY else "monthly")]


def oos_sessions(sessions: pd.DatetimeIndex) -> tuple[pd.DatetimeIndex, dict]:
    """Union of the walk-forward test windows over `sessions`, and the fold/purge/embargo record."""
    folds = list(walk_forward_splits(pd.DataFrame({"Date": sessions}), INITIAL_TRAIN_MONTHS, TEST_MONTHS,
                                     label_horizon=LABEL_HORIZON, embargo_bars=EMBARGO))
    if not folds:
        raise ValueError("the panel is too short for one walk-forward test window")
    tested = np.unique(np.concatenate([test for _, test in folds]))
    cv = {"scheme": "purged_embargoed_walk_forward", "folds": len(folds), "purge": LABEL_HORIZON, "embargo": EMBARGO,
          "initial_train_months": INITIAL_TRAIN_MONTHS, "test_months": TEST_MONTHS}
    return sessions[tested], cv


def oos_returns(config_id: str, opens: pd.DataFrame, closes: pd.DataFrame, *, fill_cost: FillCost,
                commission_per_fill: float, starting_capital: float) -> tuple[list[dict], dict]:
    """Daily log returns of costed equity on test-window sessions, and the CV record.

    Refuses (`HoldoutSealError`) any panel holding a session after the research window, before
    anything is computed. The return on session s is `ln(E[s] / E[s-1])` of close-marked equity.
    """
    if sealed_sessions(closes.index).any() or sealed_sessions(opens.index).any():
        raise HoldoutSealError(f"the walk-forward panel must end by {RESEARCH_END}; the holdout is sealed")
    result = run_portfolio_backtest(opens, closes, target_book(config_id, closes), starting_capital=starting_capital,
                                    commission_per_fill=commission_per_fill, fill_cost=fill_cost)
    equity = result.equity
    if (equity <= 0).any():
        raise ValueError("equity reached zero; log returns are undefined")
    daily = np.log(equity / equity.shift(1))
    tested, cv = oos_sessions(closes.index)
    daily = daily.loc[tested].dropna()
    rows = [{"session": session.strftime("%Y-%m-%d"), "log_return": float(value)} for session, value in daily.items()]
    return rows, cv


def run_configuration(config_id: str, opens: pd.DataFrame, closes: pd.DataFrame, *, fill_cost: FillCost,
                      costs: dict, data: dict, starting_capital: float = 100_000.0) -> dict:
    """Record one 058-edge trial: started before evaluation, completed with its OOS returns.

    `costs` must carry `commission` (per fill) and a `slippage` dict whose `model` is the spec 046
    spread-plus-square-root-impact model (Rule 13); `data` identifies the panel (hash, basis).
    Baseline B-BH is recorded with role `buy_and_hold_baseline`, so it never counts toward N.
    Returns the ledger receipt of the terminal event.
    """
    slippage = costs.get("slippage") if isinstance(costs, dict) else None
    if not isinstance(slippage, dict) or slippage.get("model") != COST_MODEL or "commission" not in costs:
        raise ValueError(f"costs must state a commission and the spec 046 {COST_MODEL!r} slippage model (Rule 13)")
    if sealed_sessions(closes.index).any() or sealed_sessions(opens.index).any():
        raise HoldoutSealError(f"the walk-forward panel must end by {RESEARCH_END}; the holdout is sealed")
    require_buildable(config_id)
    _, cv = oos_sessions(closes.index)  # the started config carries the exact CV record the sidecar will (033)
    config = {"runner": RUNNER, "data": data, "universe": list(closes.columns),
              "date_range": [closes.index[0].strftime("%Y-%m-%d"), closes.index[-1].strftime("%Y-%m-%d")],
              "features": [], "transforms": [], "target": {"label": "next_open_fill_daily_log_return", "horizon": 1},
              "model": {"name": config_id, "params": {"vol_span": VOL_SPAN, "target_volatility": TARGET_VOLATILITY,
                                                      "max_gross": MAX_GROSS,
                                                      "sizing": "equal_legs_scaled_down" if config_id in EQUAL_LEGS
                                                      else "per_configuration"}},
              "cv": cv,
              "seed": None, "initial_capital": starting_capital, "commission": costs["commission"],
              "slippage": slippage, "liquidation": False, "risk_free": {"annual_rate": 0.0, "days_per_year": 252}}
    role = "buy_and_hold_baseline" if config_id == "B-BH" else "candidate"
    with research_attempt(config, role=role, family=FAMILY) as attempt:
        rows, cv = oos_returns(config_id, opens, closes, fill_cost=fill_cost,
                               commission_per_fill=costs["commission"], starting_capital=starting_capital)
        attempt.returns(rows, {"frequency": "daily", "return_convention": "funded_account_log", "net_costs": True,
                               "oos": True, "cv": cv, "costs": {"commission": costs["commission"], "slippage": slippage}})
    return attempt.receipt
