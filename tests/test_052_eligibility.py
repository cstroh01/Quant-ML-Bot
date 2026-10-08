"""Spec 052 U2/U3: research and executable eligibility with reasons. EXAMPLE — NOT A RESULT."""
from datetime import date

import pandas as pd
import pytest

import context  # noqa: F401
from asset_registry import ExecutableQuote, EligibilityLimits, executable_eligibility, research_eligibility

LIM = EligibilityLimits(min_sessions=5, min_price=5.0, min_median_dollar_volume=1_000_000.0,
                        max_spread_bps=50.0, max_participation=0.01)


def bars(close=20.0, volume=100_000, n=8, end="2026-10-07"):
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame({"Close": [close] * n, "Volume": [volume] * n}, index=idx)


def test_eligible_name_has_no_reasons():
    assert research_eligibility(bars(), as_of=date(2026, 10, 7), limits=LIM, actions_reconciled=True,
                                basis_known=True) == []


@pytest.mark.parametrize("frame,kw,reason", [
    (bars(n=3), {}, "insufficient_history"),
    (bars(close=4.0, volume=1_000_000), {}, "price_below_floor"),
    (bars(volume=1_000), {}, "illiquid"),
    (bars(), {"actions_reconciled": False}, "corporate_actions_unreconciled"),
    (bars(), {"basis_known": False}, "price_basis_unknown"),
])
def test_each_failure_names_its_reason(frame, kw, reason):
    args = dict(actions_reconciled=True, basis_known=True) | kw
    assert reason in research_eligibility(frame, as_of=date(2026, 10, 7), limits=LIM, **args)


def test_rows_after_as_of_are_ignored():
    future_spike = bars(volume=1_000, n=8, end="2026-10-07")
    future_spike.loc[pd.Timestamp("2026-10-08")] = [20.0, 10_000_000]
    assert "illiquid" in research_eligibility(future_spike, as_of=date(2026, 10, 7), limits=LIM,
                                              actions_reconciled=True, basis_known=True)


def quote(**extra):
    values = dict(tradable=True, halted=False, last_bar_session=date(2026, 10, 7), instrument_class="us_equity",
                  spread_bps=10.0, adv_shares=100_000.0, min_notional_usd=1.0)
    values.update(extra)
    return ExecutableQuote(**values)


def test_executable_ok_and_each_refusal():
    kw = dict(previous_session=date(2026, 10, 7), allowed_classes=("us_equity", "etf"), order_qty=500, order_notional=10_000.0, limits=LIM)
    assert executable_eligibility(quote(), **kw) == []
    assert executable_eligibility(quote(tradable=False), **kw) == ["not_tradable"]
    assert executable_eligibility(quote(halted=True), **kw) == ["halted"]
    assert executable_eligibility(quote(last_bar_session=date(2026, 10, 6)), **kw) == ["stale_bar"]
    assert executable_eligibility(quote(instrument_class="option"), **kw) == ["class_not_permitted"]
    assert executable_eligibility(quote(spread_bps=80.0), **kw) == ["spread_too_wide"]
    assert executable_eligibility(quote(adv_shares=10_000.0), **kw) == ["participation_too_high"]
    assert executable_eligibility(quote(min_notional_usd=50_000.0), **kw) == ["below_broker_minimum"]


def test_a_future_price_cannot_lift_a_name_over_the_floor():
    frame = bars(close=4.0, volume=1_000_000)
    frame.loc[pd.Timestamp("2026-10-08")] = [50.0, 1_000_000]
    assert "price_below_floor" in research_eligibility(frame, as_of=date(2026, 10, 7), limits=LIM,
                                                       actions_reconciled=True, basis_known=True)
