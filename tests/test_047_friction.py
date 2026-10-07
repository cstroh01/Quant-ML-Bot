"""047 T006/T007 U1a: synthetic fill costs, EXAMPLE -- NOT A RESULT."""
from datetime import date
import hashlib
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
import pytest

import context  # noqa: F401
import backtest_harness as harness
import reports.api.routes.backtest as route
from api_fixtures import fixture_client
from unadjusted_fixtures import publish_bundle, session_prices
from mutation_support_019 import killed


def frame(*, split=False, reopen=False):
    # Perturbed inputs are actual Buy/Sell, Split and slippage_bps consumers.
    prices = pd.DataFrame({"Date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        "Open": [100., 25., 30.] if split else [100., 120., 140.],
        "Close": [100., 25., 30.] if split else [100., 120., 140.],
        "Buy_Next_Open": [True, False, reopen],
        "Sell_Next_Open": [False, not split, split],
        "Split": [1., 4. if split else 1., 1.]})
    prices.attrs["price_basis"] = "unadjusted_dollars"
    return prices


def run(*, split=False, reopen=False, liquidate=False, bps=5., capital=10000.):
    return harness.run_backtest(frame(split=split, reopen=reopen), commission_per_trade=1.5,
        slippage_bps=bps, starting_capital=capital, shares=2, liquidate=liquidate)


def check_total(field, expected, mutant, **kwargs):
    assert math.isclose(run(**kwargs).attrs[field], expected, abs_tol=1e-9), mutant


def survives(old, new, oracle):
    """The specified mutant must still pass its non-defective control fixture."""
    source_path = Path(harness.__file__)
    source = source_path.read_text()
    before = hashlib.sha256(source_path.read_bytes()).digest()
    assert source.count(old) == 1
    oracle()
    with patch.dict(harness.__dict__):
        exec(compile(source.replace(old, new), str(source_path), "exec"), harness.__dict__)
        oracle()
    assert hashlib.sha256(source_path.read_bytes()).digest() == before
    oracle()  # restored control


def test_closed_trade_friction_comes_from_each_fill():
    log = run()
    check_total("slippage_total", 2*100*.0005 + 2*120*.0005, "two fill concessions")
    check_total("commission_total", 3., "two fill commissions")
    ledger = log.attrs["ledger"]
    assert ledger.Slippage.ge(0).all()
    assert ledger.loc[~ledger.Event.isin(["buy", "sell", "liquidation"]), "Slippage"].eq(0).all()
    assert ledger.Event.tolist() == ["initial", "buy", "mark", "sell", "mark", "mark"]
    assert ledger.Fee.tolist() == [0., 1.5, 0., 1.5, 0., 0.]
    assert ledger.Quantity.tolist() == [0., 2., 2., 0., 0., 0.]
    assert ledger.Cash.tolist() == pytest.approx([10000., 9798.4, 9798.4, 10036.78, 10036.78, 10036.78])


@pytest.mark.parametrize("liquidate,fees,slip", [(False, 4.5, .36), (True, 6., .50)])
def test_open_entry_is_counted_without_fabricating_exit(liquidate, fees, slip):
    check_total("commission_total", fees, "open entry commission", reopen=True, liquidate=liquidate)
    check_total("slippage_total", slip, "open entry slippage", reopen=True, liquidate=liquidate)


def test_split_exit_uses_post_split_quantity_and_boundary_fills():
    log = run(split=True)
    check_total("slippage_total", .22, "post-split exit quantity", split=True)
    assert log.iloc[0]["Quantity"] == 8.
    assert log.attrs["ledger"].query("Event == 'buy'").Date.iloc[0] == frame().Date.iloc[0]
    assert log.attrs["ledger"].query("Event == 'sell'").Date.iloc[0] == frame().Date.iloc[-1]


@pytest.mark.parametrize("rejected", [False, True])
def test_empty_and_rejected_orders_charge_nothing(rejected):
    prices = frame()
    if not rejected:
        prices.Buy_Next_Open = False
    log = harness.run_backtest(prices, commission_per_trade=1.5, slippage_bps=5.,
                               shares=2, starting_capital=1. if rejected else 10000.)
    assert log.attrs["commission_total"] == log.attrs["slippage_total"] == 0.
    assert log.attrs["ledger"].Slippage.eq(0).all()
    if rejected:
        assert "rejected" in log.attrs["ledger"].Event.values


@pytest.mark.parametrize("old", ["slippage=shares * (fill - row.Open)", "slippage=exit_slippage"])
def test_m1_slippage_mutants_with_zero_cost_controls(old):
    killed(harness, old, "slippage=0.", lambda: check_total("slippage_total", .22, "M1"))
    survives(old, "slippage=0.", lambda: check_total("slippage_total", 0., "M1-zero", bps=0.))


def test_m1b_commission_mutant_with_liquidated_control():
    old = 'commission_total=float(fills["Fee"].sum())'
    new = 'commission_total=float(2 * commission_per_trade * len(trades))'
    killed(harness, old, new, lambda: check_total("commission_total", 4.5, "M1b", reopen=True))
    survives(old, new, lambda: check_total("commission_total", 6., "M1b-control", reopen=True, liquidate=True))


def test_m2_open_entry_mutant_with_liquidated_control():
    old = 'slippage_total=float(fills["Slippage"].sum())'
    new = 'slippage_total=float(fills.loc[(fills.Event != "buy") | fills.Date.isin(log["Entry Date"]), "Slippage"].sum())'
    killed(harness, old, new, lambda: check_total("slippage_total", .36, "M2", reopen=True))
    survives(old, new, lambda: check_total("slippage_total", .50, "M2-control", reopen=True, liquidate=True))


def test_m3_split_mutant_with_no_split_control():
    old, new = "exit_slippage = quantity * (quote - fill)", "exit_slippage = entry[4] * (quote - fill)"
    killed(harness, old, new, lambda: check_total("slippage_total", .22, "M3", split=True))
    survives(old, new, lambda: check_total("slippage_total", .22, "M3-no-split"))


class RouteFrictionTests(unittest.TestCase):
    def test_route_copies_harness_totals_rounded_once(self):
        client = fixture_client(self, None)
        import data
        sessions = data.trading_days(date(2024, 1, 2), date(2024, 3, 28))
        prices = session_prices("AAPL", sessions[0], sessions[-1],
                                [100 + 8 * math.sin(i/4) for i in range(len(sessions))])
        publish_bundle(client.fixture_cache_dir / "unadjusted", "AAPL", prices)
        observed = []
        def capture(*args, **kwargs):
            log = harness.run_backtest(*args, **kwargs)
            observed.append(log.attrs.copy())
            return log
        with patch.object(route, "run_backtest", side_effect=capture):
            response = client.get("/api/backtest/tearsheet?ticker=AAPL&short_window=3&long_window=7&commission=1.337&slippage_bps=5")
        self.assertEqual(response.status_code, 200)
        for field in ("commission_total", "slippage_total"):
            self.assertEqual(response.json()[field], round(observed[0][field], 2))
        self.assertGreater(response.json()["slippage_total"], 0.)
