"""Spec 051 U2: budget-bounded, daily-capped, cash-settled buy sizing.

EXAMPLE — NOT A RESULT. All prices, budgets and balances are synthetic.
"""
import pytest

import context  # noqa: F401
from mode_config import BuyRequest, bound_buys, load_profiles, sizing_equity
from mode_fixtures import raw


def profile(**extra):
    return load_profiles([raw(**extra)])["paper_small"]


def test_sizing_equity_is_the_budget_not_the_broker_account():
    p = profile(bot_budget_usd=5000.0)
    assert sizing_equity(p, bot_owned_value=1000.0, bot_cash=250_000.0) == 5000.0
    assert sizing_equity(p, bot_owned_value=1000.0, bot_cash=2000.0) == 3000.0


@pytest.mark.parametrize("broker_cash", [5_000.0, 1_000_000.0])
def test_inflated_settled_cash_never_raises_spend_above_daily_cap(broker_cash):
    p = profile(bot_budget_usd=5000.0, daily_deploy_fraction=0.2)
    accepted, refused = bound_buys(p, [BuyRequest("AAA", 100, 50.0, False)],
                                   settled_cash=broker_cash, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert [(a.ticker, a.quantity) for a in accepted] == [("AAA", 20)]
    assert sum(a.notional for a in accepted) <= 1000.0
    assert refused == []


def test_daily_cap_counts_what_was_already_deployed_today():
    p = profile(bot_budget_usd=5000.0, daily_deploy_fraction=0.2)
    accepted, refused = bound_buys(p, [BuyRequest("AAA", 10, 50.0, False)],
                                   settled_cash=5000.0, deployed_today_usd=1000.0, min_notional_usd=1.0)
    assert accepted == [] and refused == [("AAA", "daily_cap")]


def test_only_settled_cash_is_spent():
    p = profile(bot_budget_usd=5000.0, daily_deploy_fraction=1.0)
    accepted, refused = bound_buys(p, [BuyRequest("AAA", 10, 50.0, False), BuyRequest("BBB", 10, 50.0, False)],
                                   settled_cash=700.0, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert [(a.ticker, a.quantity) for a in accepted] == [("AAA", 10), ("BBB", 4)]
    accepted, refused = bound_buys(p, [BuyRequest("CCC", 1, 50.0, False)],
                                   settled_cash=10.0, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert refused == [("CCC", "insufficient_settled_cash")]


def test_fractional_only_when_profile_and_instrument_allow():
    small_budget = dict(bot_budget_usd=300.0, daily_deploy_fraction=1.0)
    frac = profile(fractional=True, **small_budget)
    whole = profile(fractional=False, **small_budget)
    req = [BuyRequest("AAA", 0.75, 400.0, True)]
    accepted, _ = bound_buys(frac, req, settled_cash=300.0, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert [a.quantity for a in accepted] == [0.75]
    accepted, refused = bound_buys(whole, req, settled_cash=300.0, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert accepted == [] and refused == [("AAA", "budget_exhausted")]
    accepted, refused = bound_buys(frac, [BuyRequest("AAA", 0.75, 400.0, False)],
                                   settled_cash=300.0, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert accepted == [] and refused == [("AAA", "budget_exhausted")]


def test_fractional_quantity_is_floored_to_six_decimals_never_rounded_up():
    p = profile(fractional=True, bot_budget_usd=100.0, daily_deploy_fraction=1.0)
    accepted, _ = bound_buys(p, [BuyRequest("AAA", 9.0, 15.0, True)],
                             settled_cash=100.0, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert accepted[0].quantity == 6.666666 and accepted[0].notional <= 100.0


def test_below_broker_minimum_is_dropped_with_reason():
    p = profile(fractional=True, bot_budget_usd=5000.0, daily_deploy_fraction=1.0)
    accepted, refused = bound_buys(p, [BuyRequest("AAA", 0.001, 50.0, True)],
                                   settled_cash=5000.0, deployed_today_usd=0.0, min_notional_usd=1.0)
    assert accepted == [] and refused == [("AAA", "below_minimum")]


@pytest.mark.parametrize("bad", [dict(quantity=-1), dict(ref_price=0.0), dict(ref_price=float("nan"))])
def test_invalid_requests_raise(bad):
    values = dict(ticker="AAA", quantity=1, ref_price=10.0, fractionable=False) | bad
    with pytest.raises(ValueError):
        bound_buys(profile(), [BuyRequest(**values)], settled_cash=100.0,
                   deployed_today_usd=0.0, min_notional_usd=1.0)
