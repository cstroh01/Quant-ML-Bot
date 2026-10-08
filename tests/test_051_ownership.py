"""Spec 051 U3: bot-owned lots vs external holdings. EXAMPLE — NOT A RESULT."""
import pytest

import context  # noqa: F401
from mode_config import Holding, aggregate_exposure, bot_sell_quantities, concentration_refusals


def book():
    return [Holding("AAA", 10, "bot"), Holding("AAA", 50, "external"),
            Holding("BBB", 30, "external"), Holding("CCC", 4, "bot")]


def test_external_holding_absent_from_targets_creates_no_sell():
    sells = bot_sell_quantities({"AAA": 10}, book())
    assert "BBB" not in sells and sells == {"CCC": 4}


def test_sells_never_reach_external_shares():
    assert bot_sell_quantities({"AAA": 0}, book())["AAA"] == 10
    assert bot_sell_quantities({}, [Holding("AAA", 50, "external")]) == {}


def test_aggregate_exposure_counts_every_owner():
    exposure = aggregate_exposure(book(), {"AAA": 10.0, "BBB": 2.0, "CCC": 5.0})
    assert exposure == {"AAA": 600.0, "BBB": 60.0, "CCC": 20.0}


def test_concentration_includes_external_holdings():
    prices = {"AAA": 10.0, "BBB": 2.0, "CCC": 5.0}
    refusals = concentration_refusals(book(), prices, {"AAA": 5.0, "CCC": 1.0},
                                      portfolio_value=1000.0, max_position_pct=0.60)
    assert refusals == ["AAA"]


@pytest.mark.parametrize("quantity,owner", [(-1, "bot"), (1, "someone"), (float("nan"), "bot")])
def test_invalid_holdings_raise(quantity, owner):
    with pytest.raises(ValueError):
        Holding("AAA", quantity, owner)
