"""Spec 046 T007/T008 (U2): the harness charges the Rule 13 model per fill and metrics reconcile it.

Synthetic frames only (EXAMPLE — NOT A RESULT). Expected fills come from the real estimator called
here with the cutoff and quantity the spec fixes: bars through the session before the fill, Q = shares
bought or shares held at exit. Witness strings ("046 U2 ...") let the mutation driver count a kill.
"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401
from backtest_harness import FLAT_LABEL, run_backtest
from cost_model import MODEL, CostConfig, estimate_fill_cost
from data import trading_days
from metrics import equity_curve

SESSIONS = pd.DatetimeIndex(trading_days(date(2024, 1, 2), date(2024, 6, 28)))
CAPITAL, SHARES, FEE = 100_000.0, 100, 1.0
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def frame(n=70, buys=(), sells=(), split=None, basis="provider_nominal", seed=20261012):
    """Alternating bid/ask trades around a random walk; `split=(row, ratio)` rescales later bars."""
    rng = np.random.default_rng(seed)
    mid = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n * 50)))
    px = (mid * (1 + rng.choice([-1, 1], n * 50) * 0.005)).reshape(n, 50)
    out = pd.DataFrame({"Date": SESSIONS[:n], "Open": px[:, 0], "High": px.max(1), "Low": px.min(1),
                        "Close": px[:, -1], "Volume": rng.integers(20_000, 60_000, n).astype(float),
                        "Split": 1.0, "Buy_Next_Open": False, "Sell_Next_Open": False})
    if split:
        row, ratio = split
        out.loc[row:, ["Open", "High", "Low", "Close"]] /= ratio
        out.loc[row:, "Volume"] *= ratio
        out.loc[row, "Split"] = ratio
    out.loc[list(buys), "Buy_Next_Open"] = True
    out.loc[list(sells), "Sell_Next_Open"] = True
    out.attrs.update(price_basis="unadjusted_dollars", volume_basis=basis)
    return out


def expected(prices, row, quantity):
    """The estimate a fill at `row`'s open must use: bars through row - 1, Q as given."""
    history = prices.set_index("Date")[OHLCV]
    history.attrs["volume_basis"] = prices.attrs["volume_basis"]
    splits = prices.loc[prices.Split != 1, "Date"]
    return estimate_fill_cost(history, as_of=prices.Date[row - 1], quantity=quantity,
                              config=CostConfig(), split_sessions=splits)


def run(prices, capital=CAPITAL, **kw):
    return run_backtest(prices, commission_per_trade=FEE, starting_capital=capital, shares=SHARES,
                        cost_config=CostConfig(), **kw)


def fills(log):
    ledger = log.attrs["ledger"]
    return ledger[ledger.Event.isin(["buy", "sell", "liquidation"])].reset_index(drop=True)


def test_buy_and_sell_charge_the_model_on_the_right_cutoff_and_quantity():
    prices = frame(buys=[30], sells=[45])
    log = run(prices)
    buy, sell = fills(log).itertuples()
    b, s = expected(prices, 30, SHARES).total, expected(prices, 45, SHARES).total
    assert buy.Cost_Fraction == pytest.approx(b, abs=1e-15), "046 U2 buy fraction"
    assert sell.Cost_Fraction == pytest.approx(s, abs=1e-15), "046 U2 sell fraction"
    entry, exit_ = prices.Open[30] * (1 + b), prices.Open[45] * (1 - s)
    assert buy.Cash == pytest.approx(CAPITAL - SHARES * entry - FEE, abs=1e-9), "046 U2 buy cash"
    assert sell.Cash == pytest.approx(buy.Cash + SHARES * exit_ - FEE, abs=1e-9), "046 U2 sell cash"
    assert [buy.Slippage, sell.Slippage] == pytest.approx(
        [SHARES * prices.Open[30] * b, SHARES * prices.Open[45] * s], abs=1e-9), "046 U2 slippage dollars"
    assert log["Exit Price"][0] == pytest.approx(exit_, abs=1e-12), "046 U2 sell fraction"


def test_exit_quantity_is_the_held_post_split_quantity():
    prices = frame(buys=[24], sells=[60], split=(32, 2.0))
    _, sell = fills(run(prices)).itertuples()
    held = expected(prices, 60, 2 * SHARES).total
    assert expected(prices, 60, SHARES).total != pytest.approx(held, abs=1e-12), "fixture must separate Q"
    assert sell.Cost_Fraction == pytest.approx(held, abs=1e-15), "046 U2 held exit quantity"


def test_terminal_liquidation_uses_the_preceding_session_estimate():
    prices = frame(buys=[40])
    *_, last = fills(run(prices, liquidate=True)).itertuples()
    est = expected(prices, len(prices) - 1, SHARES).total
    assert last.Event == "liquidation" and last.Cost_Fraction == pytest.approx(est, abs=1e-15), "046 U2 liquidation"


def test_future_bars_do_not_move_a_fill_fraction():
    # Rule 1: perturb High/Low/Volume of the fill session and after; the quote (Open) is held fixed.
    prices = frame(buys=[30])
    later = prices.copy()
    later.loc[30:, "High"] *= 1.05
    later.loc[30:, "Low"] *= 0.95
    later.loc[30:, "Volume"] *= 7
    later.attrs.update(prices.attrs)
    a, b = fills(run(prices)).Cost_Fraction[0], fills(run(later)).Cost_Fraction[0]
    assert a == b, "046 U2 future bars"


def test_warmup_and_split_window_refuse_the_order_without_a_flat_fallback():
    prices = frame(buys=[5, 24], sells=[34, 60], split=(32, 2.0))
    ledger = run(prices).attrs["ledger"]
    refused = ledger[ledger.Event == "cost_refused"]
    assert list(refused.Date) == [prices.Date[5], prices.Date[34]], "046 U2 refusal"
    assert list(refused.Cost_Status) == ["warmup", "split_in_window"], "046 U2 refusal"
    assert (refused.Fee == 0).all() and (refused.Slippage == 0).all(), "046 U2 refusal"
    filled = ledger[ledger.Event.isin(["buy", "sell"])]
    assert list(zip(filled.Event, filled.Date)) == [("buy", prices.Date[24]), ("sell", prices.Date[60])], \
        "046 U2 refusal: a refused order must not fill"
    assert ledger.loc[ledger.Date == prices.Date[34], "Quantity"].iloc[-1] == 2 * SHARES, "046 U2 refusal"


def test_affordability_includes_the_modeled_cost():
    prices = frame(buys=[30])
    est = expected(prices, 30, SHARES).total
    flat_need = SHARES * prices.Open[30] + FEE
    capital = flat_need + SHARES * prices.Open[30] * est / 2  # covers the quote, not the modeled cost
    ledger = run(prices, capital=capital).attrs["ledger"]
    assert "buy" not in set(ledger.Event) and "rejected" in set(ledger.Event), "046 U2 affordability"


def test_unverified_volume_refuses_the_run():
    with pytest.raises(ValueError, match="volume_basis"):
        run(frame(buys=[30], basis="provider_unverified"))


def test_model_and_flat_runs_are_labelled_and_never_mixed():
    prices = frame(buys=[30], sells=[45])
    model = run(prices).attrs
    assert (model["cost_model"], model["slippage_bps"], model["cost_config"]) == (
        MODEL, 0.0, CostConfig().as_mapping()), "046 U2 labels"
    flat = run_backtest(prices, commission_per_trade=FEE, slippage_bps=5.0, starting_capital=CAPITAL,
                        shares=SHARES).attrs
    assert (flat["cost_model"], flat["cost_label"], flat["cost_config"]) == (
        "flat_bps", FLAT_LABEL, None), "046 U2 labels"
    assert FLAT_LABEL == "not reportable (Rule 13)"
    with pytest.raises(ValueError, match="one cost model"):
        run(prices, slippage_bps=5.0)


def test_strategy_and_baseline_share_the_executed_config():
    strategy = run(frame(buys=[30], sells=[45])).attrs["cost_config"]
    hold = run(frame(buys=[22])).attrs["cost_config"]
    assert strategy == hold == CostConfig().as_mapping(), "046 U2 baseline parity"


def test_metrics_reconcile_recorded_model_costs_and_refuse_a_forged_fraction():
    prices = frame(buys=[30], sells=[45, 60], split=None)
    log = run(prices, liquidate=True)
    try:
        curve = equity_curve(prices, log, commission_per_trade=FEE, slippage_bps=0.0)
    except ValueError as error:
        pytest.fail(f"046 U2 reconcile: {error}")
    assert curve.Equity.iloc[-1] == pytest.approx(fills(log).Cash.iloc[-1], abs=1e-9), "046 U2 reconcile"
    forged = log.copy()
    ledger = log.attrs["ledger"].copy()
    ledger.loc[ledger.Event == "buy", "Cost_Fraction"] = 5.0 / 10_000  # flat 5 bps stamped on a model fill
    forged.attrs.update(log.attrs, ledger=ledger)
    with pytest.raises(ValueError, match="cost"):
        equity_curve(prices, forged, commission_per_trade=FEE, slippage_bps=0.0)


def test_metrics_hold_flat_runs_to_their_declared_rate():
    prices = frame(buys=[30], sells=[45])
    log = run_backtest(prices, commission_per_trade=FEE, slippage_bps=5.0, starting_capital=CAPITAL, shares=SHARES)
    equity_curve(prices, log, commission_per_trade=FEE, slippage_bps=5.0)
    # A self-consistent 10 bps run relabelled as 5 bps: cash, fills and slippage dollars all agree
    # with each other, so only the declared-rate check can refuse it.
    other = run_backtest(prices, commission_per_trade=FEE, slippage_bps=10.0, starting_capital=CAPITAL, shares=SHARES)
    other.attrs["slippage_bps"] = 5.0
    with pytest.raises(ValueError, match="declared cost model"):
        equity_curve(prices, other, commission_per_trade=FEE, slippage_bps=5.0)


def test_a_split_on_the_fill_session_refuses():
    # Review P1-a: the split is applied at the open before the fill, so Q is post-split while every
    # window bar is pre-split. The estimator's window ends at t, so the harness must refuse here.
    prices = frame(buys=[24], sells=[32], split=(32, 2.0))
    ledger = run(prices).attrs["ledger"]
    refused = ledger[ledger.Event == "cost_refused"]
    assert list(zip(refused.Date, refused.Cost_Status)) == [(prices.Date[32], "split_in_window")], \
        "046 U2 fill-session split"
    assert "sell" not in set(ledger.Event), "046 U2 fill-session split"


def test_a_refused_liquidation_is_flagged_and_still_reconciles():
    # Review P1-b: a split in the last 21 sessions refuses terminal liquidation; the position stays marked.
    prices = frame(buys=[24], split=(60, 2.0))
    log = run(prices, liquidate=True)
    last = log.attrs["ledger"].iloc[-1]
    assert (last.Phase, last.Event, last.Cost_Status) == ("close", "cost_refused", "split_in_window"), \
        "046 U2 refused liquidation"
    assert log.attrs["liquidation_refused"] is True and last.Quantity == 2 * SHARES, "046 U2 refused liquidation"
    try:
        equity_curve(prices, log, commission_per_trade=FEE, slippage_bps=0.0)
    except ValueError as error:
        pytest.fail(f"046 U2 refused liquidation: {error}")


@pytest.mark.parametrize("cost", ["flat", "model"])
def test_large_notional_fills_still_reconcile(cost):
    # Review P2: slippage dollars must be compared at a tolerance that scales with notional.
    prices = frame(buys=[30], sells=[45])
    kw = dict(slippage_bps=5.0) if cost == "flat" else dict(cost_config=CostConfig())
    log = run_backtest(prices, commission_per_trade=FEE, starting_capital=1e9, shares=1_000_000, **kw)
    try:
        equity_curve(prices, log, commission_per_trade=FEE, slippage_bps=kw.get("slippage_bps", 0.0))
    except ValueError as error:
        pytest.fail(f"046 U2 large notional: {error}")


def test_model_mode_needs_full_ohlcv():
    with pytest.raises(ValueError, match="High"):
        run(frame(buys=[30]).drop(columns="High"))
