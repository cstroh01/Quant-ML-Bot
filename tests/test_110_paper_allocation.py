"""Spec 059 FR-004 / D-9 (queue Q100, Q110): the PAPER loop trades the preregistered allocation.

EXAMPLE — NOT A RESULT. ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED. Offline only: fakes, no
network, no keys, synthetic prices.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401 -- makes scripts importable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

import alpaca_paper  # noqa: E402
import paper_loop  # noqa: E402
from live_safety_gate import LiveSafetyGate, SafetyConfig  # noqa: E402
from paper_targets import ALLOCATION_CASH_BUFFER, plan_allocation  # noqa: E402
from portfolio_risk import allocation_weights  # noqa: E402
from signals import ALLOCATION_SLEEVES, allocation_selection, decision_sessions  # noqa: E402

VOLS = dict(zip(ALLOCATION_SLEEVES, (0.010, 0.011, 0.014, 0.004, 0.009, 0.003, 0.009, 0.012)))
NOW = lambda: datetime(2026, 10, 5, 12, 30, 1, tzinfo=timezone.utc)  # Monday 08:30 New York
# Test-only limits wide enough to let the allocation through; production values are Camden's (Q131).
OPEN_CONFIG = SafetyConfig(version="test-only", max_position_pct=0.9, max_gross_pct=1.0, daily_loss_pct=0.5,
                           rolling_drawdown_pct=0.9, rolling_window_sessions=63, max_snapshot_age_seconds=60,
                           max_clock_skew_seconds=5)


def sleeve_closes(end="2026-10-02", n=300, seed=11):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(end=end, periods=n)
    steps = rng.normal(0.0002, [VOLS[t] for t in ALLOCATION_SLEEVES], size=(n, len(ALLOCATION_SLEEVES)))
    start = np.array([600.0, 90.0, 50.0, 95.0, 90.0, 110.0, 380.0, 23.0])
    return pd.DataFrame(start * np.exp(np.cumsum(steps, axis=0)), index=index, columns=list(ALLOCATION_SLEEVES))


SESSION = pd.Timestamp("2026-10-02")
ALL_FRACTIONAL = {t: True for t in ALLOCATION_SLEEVES}


def plan(closes=None, **kwargs):
    args = dict(equity=100_000.0, positions={}, fractionable=ALL_FRACTIONAL, executed_decision=None)
    args.update(kwargs)
    return plan_allocation(sleeve_closes() if closes is None else closes, SESSION, **args)


def test_targets_are_the_latest_decision_row_scaled_by_the_cash_buffer():
    closes = sleeve_closes()
    frame, orders, decision = plan(closes)
    assert decision == "2026-10-01", f"Q110 DECISION latest monthly decision {decision}"
    history = closes.loc[:SESSION]
    mask = decision_sessions(history.index, cadence="monthly")
    expected = allocation_weights(allocation_selection(history), history, mask).loc["2026-10-01"]
    np.testing.assert_allclose(frame["Target"].to_numpy(), expected.to_numpy() * (1 - ALLOCATION_CASH_BUFFER),
                               err_msg="Q110 DECISION target is not the spec 059 row times (1 - buffer)")
    assert frame["Target"].sum() <= 1 - ALLOCATION_CASH_BUFFER + 1e-12, "Q110 GROSS above 1 - buffer"
    notional = sum(o.delta_quantity * closes.at[SESSION, o.ticker] for o in orders)
    assert notional <= 100_000.0 * (1 - ALLOCATION_CASH_BUFFER) + 1e-6, "Q110 GROSS orders exceed the budget"
    assert all(o.delta_quantity > 0 for o in orders) and len(orders) == 8, "Q110 DECISION first deployment buys 8 sleeves"


def test_rows_after_the_session_change_nothing():
    closes = sleeve_closes()
    extra = pd.bdate_range(SESSION + pd.Timedelta(days=1), periods=40)
    future = pd.concat([closes, pd.DataFrame(3.0 * closes.iloc[-1].to_numpy() * np.ones((40, 8)),
                                             index=extra, columns=closes.columns)])
    a = plan(closes)[1]
    try:
        b = plan(future)[1]
    except ValueError as error:
        raise AssertionError(f"Q110 LOOKAHEAD rows after the session broke the plan: {error}") from error
    assert a == b, "Q110 LOOKAHEAD orders depend on rows after the session"


def test_book_is_held_between_decisions():
    _, orders, decision = plan(executed_decision="2026-10-01")
    assert (orders, decision) == ([], "2026-10-01"), "Q110 HOLD re-targeted an executed decision"


def test_fractional_where_allowed_whole_shares_otherwise():
    fractional = plan()[1]
    whole = plan(fractionable={t: False for t in ALLOCATION_SLEEVES})[1]
    assert any(o.delta_quantity != int(o.delta_quantity) for o in fractional), "Q110 FRACTION no fractional buy"
    assert all(round(o.delta_quantity, 6) == o.delta_quantity for o in fractional), "Q110 FRACTION beyond 6 places"
    assert all(o.delta_quantity == int(o.delta_quantity) for o in whole), "Q110 FRACTION whole-share profile"


def test_sells_first_and_never_below_zero():
    held = {t: 10.0 for t in ALLOCATION_SLEEVES}
    held["SPY"] = 500.0
    orders = plan(positions=held)[1]
    sides = [o.delta_quantity < 0 for o in orders]
    assert sides == sorted(sides, reverse=True), "Q110 ORDER buys before sells"
    assert all(held[o.ticker] + o.delta_quantity >= 0 for o in orders), "Q110 ORDER sold below zero"


def test_foreign_positions_are_refused():
    try:
        plan(positions={"AAPL": 23.0})
    except ValueError as error:
        assert "outside the allocation sleeves" in str(error), f"Q110 FOREIGN wrong refusal {error}"
    else:
        raise AssertionError("Q110 FOREIGN an account holding AAPL was traded as an allocation account")


class Client:
    """Broker double for one allocation account."""

    def __init__(self, positions=None, timestamp="2026-10-05T08:30:00-04:00"):
        self.timestamp, self._positions, self.submitted = timestamp, dict(positions or {}), []

    def clock(self):
        return {"timestamp": self.timestamp, "is_open": False}

    def account(self):
        return {"equity": "100000", "cash": "100000", "status": "ACTIVE"}

    def positions(self):
        return dict(self._positions)

    def order_status(self, cid):
        return "filled"

    def snapshot(self, prices, *, parse_time):
        return alpaca_paper.BrokerSnapshot(as_of=parse_time(self.timestamp), status="OK", equity=100000.0,
                                           external_cash_flow=0.0, positions=dict(self._positions), prices=dict(prices))

    def submit_market_on_open(self, intent):
        self.submitted.append(intent)
        return {"id": intent.client_order_id}


def run(tmp_path, client, *, submit=True, config=OPEN_CONFIG, now=NOW, closes=None):
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", config)
    planner = paper_loop.AllocationPlanner(tmp_path / paper_loop.ALLOCATION_STATE, ALL_FRACTIONAL)
    try:
        return paper_loop.run_once(client=client, gate=gate, closes=sleeve_closes() if closes is None else closes,
                                   submit=submit,
                                   now_fn=now, planner=planner), planner
    finally:
        gate.close()


def test_a_fully_sent_decision_is_recorded_and_not_traded_again(tmp_path):
    client = Client()
    record, planner = run(tmp_path, client)
    assert len(client.submitted) == 8 and all(a["outcome"] == "SUBMITTED" for a in record["actions"]), \
        f"Q110 SUBMIT {[a.get('outcome') for a in record['actions']]}"
    assert record["decision_executed"] == "2026-10-01" == planner.executed_decision(), "Q110 STATE not recorded"
    assert any(i.delta_quantity != int(i.delta_quantity) for i in client.submitted), "Q110 FRACTION run_once floored"
    again = Client(positions={i.instrument: i.delta_quantity for i in client.submitted},
                   timestamp="2026-10-06T08:30:00-04:00")
    record2, _ = run(tmp_path, again, now=lambda: datetime(2026, 10, 6, 12, 30, 1, tzinfo=timezone.utc),
                     closes=sleeve_closes(end="2026-10-05", n=301))
    assert again.submitted == [] and record2["actions"] == [], "Q110 HOLD traded an executed decision again"


def test_a_denied_order_leaves_the_decision_pending(tmp_path):
    record, planner = run(tmp_path, Client(), config=paper_loop.PAPER_SAFETY_CONFIG)
    outcomes = {a["outcome"] for a in record["actions"]}
    assert "DENIED" in outcomes, f"Q110 PENDING 2026-09-29 limits let the whole allocation through: {outcomes}"
    assert record["decision_executed"] is None and planner.executed_decision() is None, \
        "Q110 PENDING a partly denied decision was marked executed"


def test_dry_run_records_nothing(tmp_path):
    client = Client()
    record, planner = run(tmp_path, client, submit=False)
    assert client.submitted == [] and planner.executed_decision() is None, "Q110 DRY wrote state or sent"
    assert {a["outcome"] for a in record["actions"]} == {"DRY_RUN"}, "Q110 DRY outcomes"


def test_unreadable_state_refuses_the_run(tmp_path):
    (tmp_path / paper_loop.ALLOCATION_STATE).write_text("{not json", encoding="utf-8")
    with pytest.raises(paper_loop.RunAborted, match="unreadable"):
        run(tmp_path, Client())


def small_profile():
    from mode_config import load_profiles
    from mode_fixtures import raw
    return load_profiles([raw(bot_budget_usd=5000.0, daily_deploy_fraction=0.2)])["paper_small"]


class SmallAccount(Client):
    def account(self):
        return {"equity": "5000", "cash": "5000", "status": "ACTIVE", "account_number": "PA-1"}  # raw()'s account


def test_profile_deploys_fractionally_inside_the_daily_cap_and_finishes_later(tmp_path):
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", OPEN_CONFIG)
    planner = paper_loop.AllocationPlanner(tmp_path / paper_loop.ALLOCATION_STATE, ALL_FRACTIONAL)
    client = SmallAccount()
    try:
        record = paper_loop.run_once(client=client, gate=gate, closes=sleeve_closes(), submit=True, now_fn=NOW,
                                     profile=small_profile(), planner=planner)
    finally:
        gate.close()
    closes = sleeve_closes()
    spent = sum(i.delta_quantity * closes.at[SESSION, i.instrument] for i in client.submitted)
    assert client.submitted and spent <= 1000.0 + 1e-6, f"Q110 CAP spent {spent} over the 20% daily cap"
    assert any(i.delta_quantity != int(i.delta_quantity) for i in client.submitted), "Q110 FRACTION profile floored"
    assert planner.executed_decision() is None and record["decision_executed"] is None, \
        "Q110 PENDING a cap-shrunk first deployment was marked executed"


def test_a_buy_the_cap_only_shrank_leaves_the_decision_pending(tmp_path):
    from mode_config import load_profiles
    from mode_fixtures import raw
    closes = sleeve_closes()
    _, orders, _ = plan(closes, equity=5000.0)
    notional = {o.ticker: o.delta_quantity * closes.at[SESSION, o.ticker] for o in orders}
    last = sorted(notional)[-1]  # buys are sized in ticker order; only the last one is shrunk
    fraction = (sum(notional.values()) - notional[last] / 2) / 5000.0
    profile = load_profiles([raw(bot_budget_usd=5000.0, daily_deploy_fraction=fraction)])["paper_small"]
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", OPEN_CONFIG)
    planner = paper_loop.AllocationPlanner(tmp_path / paper_loop.ALLOCATION_STATE, ALL_FRACTIONAL)
    try:
        record = paper_loop.run_once(client=SmallAccount(), gate=gate, closes=closes, submit=True, now_fn=NOW,
                                     profile=profile, planner=planner)
    finally:
        gate.close()
    assert {a["outcome"] for a in record["actions"]} == {"SUBMITTED"}, f"Q110 PENDING setup {record['actions']}"
    assert planner.executed_decision() is None, "Q110 PENDING a cap-shrunk buy was marked executed"


def test_the_loop_still_refuses_any_url_but_paper():
    assert alpaca_paper.PAPER_BASE_URL == "https://paper-api.alpaca.markets", "Q110 LIVE paper URL changed"
    source = (ROOT / "exec" / "paper_loop.py").read_text(encoding="utf-8")
    assert "fidelity" not in source.lower() and "api.alpaca.markets\"" not in source, "Q110 LIVE a live path leaked in"
    assert json.dumps(paper_loop.PAPER_SAFETY_CONFIG.version) == '"2026-09-29-v1"', "Q110 LIVE SafetyConfig changed"
