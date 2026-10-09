"""Spec 051 F01: non-finite inputs and aliased paths fail closed. EXAMPLE — NOT A RESULT."""

import pytest

import context  # noqa: F401
from mode_config import (BuyRequest, Holding, ProfileError, bot_sell_quantities, bound_buys,
                         concentration_refusals, load_profiles, sizing_equity)
from mode_fixtures import raw

NAN, INF = float("nan"), float("inf")


def two(**second):
    return [raw(), raw("paper_large", account="PA-2", **second)]


@pytest.mark.parametrize("state_dir", ["state/other/../paper_small", "STATE/Paper_Small", "state\\paper_small",
                                       "./state/paper_small/", "state/paper_small/sub", "state"])
def test_aliased_or_nested_state_dirs_are_refused(state_dir):
    with pytest.raises(ProfileError, match="state_dir"):
        load_profiles(two(state_dir=state_dir))


def test_log_namespace_differing_only_by_case_is_refused():
    with pytest.raises(ProfileError, match="log_namespace"):
        load_profiles(two(log_namespace="Paper_Small"))


def test_distinct_sibling_state_dirs_load():
    assert set(load_profiles(two(state_dir="state/paper_smaller"))) == {"paper_small", "paper_large"}


@pytest.mark.parametrize("budget", [INF, NAN])
def test_non_finite_budget_is_refused(budget):
    with pytest.raises(ProfileError, match="bot_budget_usd"):
        load_profiles([raw(bot_budget_usd=budget)])


def profile():
    return load_profiles([raw(bot_budget_usd=5000.0, daily_deploy_fraction=0.2)])["paper_small"]


@pytest.mark.parametrize("kwargs", [dict(deployed_today_usd=-1000.0), dict(deployed_today_usd=NAN),
                                    dict(settled_cash=NAN), dict(settled_cash=INF), dict(min_notional_usd=NAN)])
def test_bound_buys_refuses_negative_or_non_finite_day_state(kwargs):
    args = dict(settled_cash=10_000.0, deployed_today_usd=0.0, min_notional_usd=1.0) | kwargs
    with pytest.raises(ValueError):
        bound_buys(profile(), [BuyRequest("AAA", 100, 10.0, False)], **args)


def test_negative_deployed_never_lifts_spend_above_the_daily_cap():
    try:
        accepted, _ = bound_buys(profile(), [BuyRequest("AAA", 1000, 10.0, False)], settled_cash=1e6,
                                 deployed_today_usd=-1000.0, min_notional_usd=1.0)
    except ValueError:
        return
    assert sum(b.notional for b in accepted) <= 1000.0


@pytest.mark.parametrize("bot_owned_value,bot_cash", [(NAN, 0.0), (0.0, NAN), (INF, 0.0)])
def test_sizing_equity_refuses_non_finite_inputs(bot_owned_value, bot_cash):
    with pytest.raises(ValueError):
        sizing_equity(profile(), bot_owned_value=bot_owned_value, bot_cash=bot_cash)


@pytest.mark.parametrize("target", [NAN, INF, -INF])
def test_non_finite_target_never_liquidates(target):
    with pytest.raises(ValueError, match="AAA"):
        bot_sell_quantities({"AAA": target}, [Holding("AAA", 10, "bot")])


BOOK = [Holding("AAA", 10, "bot"), Holding("BBB", 1, "external")]
PRICES = {"AAA": 10.0, "BBB": 5.0}


@pytest.mark.parametrize("prices,qty,kwargs,refused", [
    ({"AAA": NAN, "BBB": 5.0}, {"AAA": 1.0, "BBB": 1.0}, {}, ["AAA"]),
    (PRICES, {"AAA": NAN, "BBB": 1.0}, {}, ["AAA"]),
    (PRICES, {"AAA": 1.0, "BBB": 1.0}, dict(portfolio_value=NAN), ["AAA", "BBB"]),
    (PRICES, {"AAA": 1.0, "BBB": 1.0}, dict(portfolio_value=0.0), ["AAA", "BBB"]),
    (PRICES, {"AAA": 1.0, "BBB": 1.0}, dict(max_position_pct=NAN), ["AAA", "BBB"]),
    ({"BBB": 5.0}, {"AAA": 1.0, "BBB": 1.0}, {}, ["AAA"]),
])
def test_concentration_gate_fails_closed(prices, qty, kwargs, refused):
    args = dict(portfolio_value=1e6, max_position_pct=0.10) | kwargs
    assert concentration_refusals(BOOK, prices, qty, **args) == refused
