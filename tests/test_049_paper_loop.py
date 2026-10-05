"""Spec 049: paper-loop prototype. Offline only: fakes, no network, no keys."""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import context  # noqa: F401 -- makes scripts importable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

import alpaca_paper  # noqa: E402
import paper_loop  # noqa: E402
from live_safety_gate import LiveSafetyGate, SafetyConfig  # noqa: E402
from paper_targets import (  # noqa: E402
    PAPER_RISK_CONFIG,
    close_panel,
    order_deltas,
    plan_next_open,
    trend_confidence,
)

TICKERS = ["AAPL", "AMZN", "GOOGL", "MSFT", "NVDA"]


def synthetic_closes(end: str = "2026-10-02", n: int = 140, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(end=end, periods=n)
    drift = np.linspace(-0.002, 0.003, len(TICKERS))
    steps = rng.normal(drift, 0.015, size=(n, len(TICKERS)))
    return pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=index, columns=TICKERS)


class PaperTargetsTests(unittest.TestCase):
    def test_future_rows_change_nothing(self):
        closes = synthetic_closes()
        session = closes.index[-20]
        base = plan_next_open(closes.loc[:session], session, equity=1e5, positions={}, entries_halted=False)
        future = closes.copy()
        future.loc[future.index > session] *= 3.0
        moved = plan_next_open(future, session, equity=1e5, positions={}, entries_halted=False)
        pd.testing.assert_frame_equal(base[0], moved[0])
        self.assertEqual(base[1], moved[1])

    def test_confidence_is_trend_state_and_zero_in_warmup(self):
        closes = pd.DataFrame({"UP": np.arange(1.0, 41.0), "DOWN": np.arange(40.0, 0.0, -1.0)},
                              index=pd.bdate_range("2026-01-01", periods=40))
        conf = trend_confidence(closes, closes.index[-1])
        self.assertEqual(conf.to_dict(), {"UP": 1.0, "DOWN": 0.0})
        self.assertEqual(trend_confidence(closes, closes.index[10]).sum(), 0.0)

    def test_buys_floor_sells_first_and_absent_names_flatten(self):
        targets = pd.Series({"AAPL": 0.05, "MSFT": 0.0})
        orders = order_deltas(targets, equity=10_000, positions={"MSFT": 3, "XOM": 2.5},
                              prices={"AAPL": 99.0, "MSFT": 50.0})
        self.assertEqual([(o.ticker, o.delta_quantity) for o in orders],
                         [("MSFT", -3), ("XOM", -2.5), ("AAPL", 5.0)])

    def test_targets_stay_inside_gate_limits(self):
        self.assertLess(PAPER_RISK_CONFIG.max_weight * (1 + paper_loop.GAP_ALLOWANCE),
                        paper_loop.PAPER_SAFETY_CONFIG.max_position_pct)
        self.assertLess(PAPER_RISK_CONFIG.max_gross * (1 + paper_loop.GAP_ALLOWANCE),
                        paper_loop.PAPER_SAFETY_CONFIG.max_gross_pct)

    def test_close_panel_rejects_duplicates(self):
        tidy = pd.DataFrame({"Date": ["2026-01-02"] * 2, "Ticker": ["A", "A"], "Close": [1.0, 2.0]})
        with self.assertRaises(ValueError):
            close_panel(tidy)


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        status, payload = self.routes[(method, url.split("alpaca.markets", 1)[1])]
        return FakeResponse(status, payload)


ENV = {"APCA_API_KEY_ID": "k-not-real", "APCA_API_SECRET_KEY": "s-not-real"}


class AlpacaAdapterTests(unittest.TestCase):
    def test_paper_url_is_the_only_url(self):
        self.assertEqual(alpaca_paper.PAPER_BASE_URL, "https://paper-api.alpaca.markets")
        params = inspect.signature(alpaca_paper.AlpacaPaperClient.__init__).parameters
        self.assertNotIn("base_url", params)
        session = FakeSession({("GET", "/v2/account"): (200, {})})
        alpaca_paper.AlpacaPaperClient(environ=ENV, session=session).account()
        self.assertTrue(session.calls[0][1].startswith("https://paper-api.alpaca.markets/"))

    def test_missing_credentials_refuse(self):
        with self.assertRaises(alpaca_paper.BrokerError):
            alpaca_paper.AlpacaPaperClient(environ={})

    def test_secret_never_in_repr_or_errors(self):
        session = FakeSession({("GET", "/v2/account"): (401, {})})
        client = alpaca_paper.AlpacaPaperClient(environ=ENV, session=session)
        self.assertNotIn("s-not-real", repr(client))
        with self.assertRaises(alpaca_paper.BrokerError) as caught:
            client.account()
        self.assertNotIn("s-not-real", str(caught.exception))

    def test_submit_is_market_on_open_with_client_id(self):
        session = FakeSession({("POST", "/v2/orders"): (200, {"id": "x"})})
        client = alpaca_paper.AlpacaPaperClient(environ=ENV, session=session)
        client.submit_market_on_open(paper_loop.OrderIntent("cid1", "AAPL", -3.0))
        body = session.calls[0][2]["json"]
        self.assertEqual(body, {"symbol": "AAPL", "qty": "3", "side": "sell", "type": "market",
                                "time_in_force": "opg", "client_order_id": "cid1"})

    def test_server_error_is_unknown_not_refused(self):
        session = FakeSession({("POST", "/v2/orders"): (503, {})})
        client = alpaca_paper.AlpacaPaperClient(environ=ENV, session=session)
        with self.assertRaises(alpaca_paper.SubmissionUnknown):
            client.submit_market_on_open(paper_loop.OrderIntent("cid1", "AAPL", 1.0))


class FakeClient:
    """Broker double: fixed clock, account, positions; records submissions."""

    def __init__(self, timestamp="2026-10-05T08:30:00-04:00", is_open=False, positions=None):
        self.timestamp, self.is_open = timestamp, is_open
        self._positions = dict(positions or {})
        self.submitted, self.statuses = [], {}

    def clock(self):
        return {"timestamp": self.timestamp, "is_open": self.is_open}

    def account(self):
        return {"equity": "100000", "status": "ACTIVE"}

    def positions(self):
        return dict(self._positions)

    def order_status(self, cid):
        return self.statuses.get(cid)

    def snapshot(self, prices, *, parse_time):
        return alpaca_paper.BrokerSnapshot(
            as_of=parse_time(self.timestamp), status="OK", equity=100000.0,
            external_cash_flow=0.0, positions=dict(self._positions), prices=dict(prices))

    def submit_market_on_open(self, intent):
        self.submitted.append(intent)
        return {"id": intent.client_order_id}


def trending_closes():
    # Friday 2026-10-02 is the last completed session before Monday 10-05.
    index = pd.bdate_range(end="2026-10-02", periods=140)
    base = np.linspace(100, 160, len(index))
    return pd.DataFrame({t: base * (1 + 0.001 * i) + np.sin(np.arange(len(index)) * (i + 1)) for i, t in enumerate(TICKERS)},
                        index=index)


class PaperLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gate = LiveSafetyGate(Path(self.tmp.name) / "gate.sqlite", paper_loop.PAPER_SAFETY_CONFIG)
        self.now = lambda: datetime(2026, 10, 5, 12, 30, 1, tzinfo=timezone.utc)

    def tearDown(self):
        self.gate.close()
        self.tmp.cleanup()

    def test_dry_run_submits_and_reserves_nothing(self):
        client = FakeClient()
        record = paper_loop.run_once(client=client, gate=self.gate, closes=trending_closes(), submit=False, now_fn=self.now)
        self.assertTrue(record["actions"])
        self.assertTrue(all(a["outcome"] == "DRY_RUN" for a in record["actions"]))
        self.assertEqual(client.submitted, [])
        self.assertEqual(self.gate.pending_orders(), [])

    def test_submit_goes_through_gate_and_reserves(self):
        client = FakeClient()
        record = paper_loop.run_once(client=client, gate=self.gate, closes=trending_closes(), submit=True, now_fn=self.now)
        self.assertEqual({a["outcome"] for a in record["actions"]}, {"SUBMITTED"})
        self.assertEqual(len(client.submitted), len(self.gate.pending_orders()))

    def test_kill_latch_blocks_every_buy(self):
        self.gate.request_kill(operator="test", reason="planted", now=self.now())
        client = FakeClient()
        record = paper_loop.run_once(client=client, gate=self.gate, closes=trending_closes(), submit=True, now_fn=self.now)
        self.assertEqual(client.submitted, [])
        self.assertTrue(all(a["outcome"] == "DENIED" for a in record["actions"]))

    def test_stale_data_aborts(self):
        stale = trending_closes().iloc[:-1]
        with self.assertRaises(paper_loop.RunAborted):
            paper_loop.run_once(client=FakeClient(), gate=self.gate, closes=stale, submit=False, now_fn=self.now)

    def test_todays_partial_bar_is_ignored(self):
        closes = trending_closes()
        today = closes.iloc[[-1]].copy()
        today.index = pd.DatetimeIndex([pd.Timestamp("2026-10-05")])
        with_partial = pd.concat([closes, today * 10])
        a = paper_loop.run_once(client=FakeClient(), gate=self.gate, closes=closes, submit=False, now_fn=self.now)
        b = paper_loop.run_once(client=FakeClient(), gate=self.gate, closes=with_partial, submit=False, now_fn=self.now)
        self.assertEqual(a["session"], "2026-10-02")
        self.assertEqual(a["actions"], b["actions"])

    def test_open_market_refuses_submit(self):
        with self.assertRaises(paper_loop.RunAborted):
            paper_loop.run_once(client=FakeClient(is_open=True), gate=self.gate, closes=trending_closes(), submit=True, now_fn=self.now)

    def test_reconcile_releases_only_terminal(self):
        client = FakeClient()
        paper_loop.run_once(client=client, gate=self.gate, closes=trending_closes(), submit=True, now_fn=self.now)
        first, *rest = [i.client_order_id for i in client.submitted]
        client.statuses[first] = "filled"
        paper_loop.reconcile_pending(self.gate, client, self.now())
        open_ids = {r["client_order_id"] for r in self.gate.pending_orders() if not r["terminal"]}
        self.assertEqual(open_ids, set(rest))

    def test_broker_time_parsing_keeps_zone(self):
        t = paper_loop.parse_broker_time("2026-10-05T08:30:00.123456789-04:00")
        self.assertEqual(t.utcoffset().total_seconds(), -4 * 3600)


if __name__ == "__main__":
    unittest.main()
