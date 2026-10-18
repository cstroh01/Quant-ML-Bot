"""Spec 059 FR-006 / SCOPE §11.3 item 5 (queue Q111): replay the PAPER pipeline with a simulated broker.

EXAMPLE — NOT A RESULT. Synthetic prices only; offline; temporary state.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

import context  # noqa: F401
import replay_runner  # noqa: E402
from data import trading_days  # noqa: E402
from signals import ALLOCATION_SLEEVES  # noqa: E402
from test_110_paper_allocation import OPEN_CONFIG, VOLS  # noqa: E402

START, END = date(2020, 2, 3), date(2020, 3, 13)


def panels(seed=5, end=date(2020, 4, 30)):
    index = pd.DatetimeIndex(trading_days(date(2018, 10, 1), end))
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0002, [VOLS[t] for t in ALLOCATION_SLEEVES], size=(len(index), 8))
    closes = pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=index, columns=list(ALLOCATION_SLEEVES))
    opens = closes.shift(1).bfill() * (1 + rng.normal(0, 0.002, size=closes.shape))
    return opens, closes


def profile():
    return replay_runner.replay_profile(5000.0, 1.0)


def test_window_replays_every_session_and_trades_each_monthly_decision():
    opens, closes = panels()
    # The 061 equal-weight rule needs an actual weight drift beyond the no-trade
    # band to require eight more orders; do not depend on A1's vol re-sizing.
    factors = pd.DataFrame(1.0, index=closes.index, columns=closes.columns)
    factors.loc["2020-02-18":, list(ALLOCATION_SLEEVES[:4])] = 1.12
    factors.loc["2020-02-18":, list(ALLOCATION_SLEEVES[4:])] = 0.88
    closes *= factors
    opens *= factors.shift(1).fillna(1.0)
    report = replay_runner.replay_window(opens, closes, START, END, profile=profile(), config=OPEN_CONFIG)
    assert report["sessions"] == len(trading_days(START, END)), f"Q111 SESSIONS {report['sessions']}"
    assert not report["errors"] and not report["aborted"] and not report["denied"], f"Q111 CLEAN {report}"
    assert report["decisions_executed"] == ["2020-01-02", "2020-02-03", "2020-03-02"], \
        f"Q111 DECISIONS {report['decisions_executed']}"
    assert report["orders"] >= 16 and replay_runner.verdict([report]), "Q111 CLEAN verdict"


def test_fills_happen_at_the_session_open():
    opens, closes = panels()
    broker = replay_runner.SimulatedBroker(opens=opens, closes=closes, cash=5000.0)
    broker.at(date(2020, 2, 4))

    class Intent:
        client_order_id, instrument, delta_quantity = "c1", "TIP", 2.0

    broker.submit_market_on_open(Intent())
    broker.open_market()
    snap = broker.order_snapshot("c1")
    assert snap["filled_avg_price"] == float(opens.at[pd.Timestamp("2020-02-04"), "TIP"]), "Q111 FILL not at the open"
    assert broker.cash == 5000.0 - 2.0 * snap["filled_avg_price"], "Q111 FILL cash"


def test_denials_under_the_live_limits_fail_the_replay():
    opens, closes = panels()
    report = replay_runner.replay_window(opens, closes, START, END, profile=profile(),
                                         config=replay_runner.paper_loop.PAPER_SAFETY_CONFIG)
    assert report["denied"], "Q111 DENIED 2026-09-29 limits let the allocation through"
    assert not replay_runner.verdict([report]), "Q111 DENIED verdict passed with denials"


def test_missing_bar_aborts_and_missing_open_is_an_unhandled_error():
    opens, closes = panels()
    holed = closes.copy()
    holed.loc[pd.Timestamp("2020-02-20"), "GLD"] = np.nan
    report = replay_runner.replay_window(opens, holed, START, END, profile=profile(), config=OPEN_CONFIG)
    assert [a["session"] for a in report["aborted"]] == ["2020-02-21"], f"Q111 ABORT {report['aborted']}"
    assert not replay_runner.verdict([report]), "Q111 ABORT verdict passed"
    gaps = opens.drop(index=pd.Timestamp("2020-02-04"))
    report = replay_runner.replay_window(gaps, closes, START, END, profile=profile(), config=OPEN_CONFIG)
    assert report["errors"] and report["errors"][0]["session"] == "2020-02-04", f"Q111 ERROR {report['errors']}"
    assert not replay_runner.verdict([report]), "Q111 ERROR verdict passed"


def test_an_exception_inside_the_loop_is_reported_and_ends_the_window(monkeypatch):
    opens, closes = panels()
    real = replay_runner.paper_loop.run_once

    def crashing(**kwargs):
        if kwargs["closes"].index[-1] >= pd.Timestamp("2020-02-10"):
            raise KeyError("planted")
        return real(**kwargs)

    monkeypatch.setattr(replay_runner.paper_loop, "run_once", crashing)
    report = replay_runner.replay_window(opens, closes, START, END, profile=profile(), config=OPEN_CONFIG)
    assert [e["session"] for e in report["errors"]] == ["2020-02-11"], f"Q111 ERROR {report['errors']}"
    assert report["sessions"] == 6 and not replay_runner.verdict([report]), "Q111 ERROR window did not stop"


def test_a_rebalance_sends_its_sells_before_its_buys():
    from paper_targets import plan_allocation
    from test_110_paper_allocation import ALL_FRACTIONAL, SESSION, sleeve_closes
    closes = sleeve_closes()
    held = {t: 10.0 for t in ALLOCATION_SLEEVES}
    held["SPY"] = 500.0  # far above target: must sell, while the other sleeves must buy
    frame, orders, _ = plan_allocation(closes, SESSION, equity=100_000.0, positions=held,
                                       fractionable=ALL_FRACTIONAL, executed_decision=None)
    assert orders and all(o.delta_quantity < 0 for o in orders), "Q111 DEFER buys sent with unfilled sells"
    assert frame.attrs["deferred_buys"] > 0, "Q111 DEFER deferred buys not reported"
    after = {**held, **{o.ticker: held[o.ticker] + o.delta_quantity for o in orders}}
    frame, orders, _ = plan_allocation(closes, SESSION, equity=100_000.0, positions=after,
                                       fractionable=ALL_FRACTIONAL, executed_decision=None)
    assert orders and all(o.delta_quantity > 0 for o in orders), "Q111 DEFER buys never followed the sells"
    assert frame.attrs["deferred_buys"] == 0, "Q111 DEFER still deferring with nothing to sell"


def test_rows_after_the_window_change_nothing():
    opens, closes = panels()
    later_opens, later_closes = opens.copy(), closes.copy()
    after = later_closes.index > pd.Timestamp(END)
    later_closes.loc[after] *= 5.0
    later_opens.loc[after] *= 5.0
    a = replay_runner.replay_window(opens, closes, START, END, profile=profile(), config=OPEN_CONFIG)
    b = replay_runner.replay_window(later_opens, later_closes, START, END, profile=profile(), config=OPEN_CONFIG)
    assert a == b, "Q111 LOOKAHEAD the replay read rows after its window"
