"""Spec 059 FR-005 (queue Q117): the PAPER loop records broker fill snapshots for the evidence report.

EXAMPLE — NOT A RESULT. Offline only: fakes, no network, no keys, synthetic prices.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from test_110_paper_allocation import ALL_FRACTIONAL as _  # noqa: F401,E402 - puts exec/ on the path
import paper_loop  # noqa: E402
import alpaca_paper  # noqa: E402
from live_safety_gate import LiveSafetyGate  # noqa: E402
from test_110_paper_allocation import ALL_FRACTIONAL, NOW, OPEN_CONFIG, Client, sleeve_closes  # noqa: E402

TUESDAY = lambda: datetime(2026, 10, 6, 12, 30, 1, tzinfo=timezone.utc)


class Filled(Client):
    """Monday's orders are now terminal at the broker."""

    def __init__(self, status="filled", **kwargs):
        super().__init__(timestamp="2026-10-06T08:30:00-04:00", **kwargs)
        self.status = status

    def order_snapshot(self, cid):
        filled = self.status == "filled"
        return {"client_order_id": cid, "status": self.status, "symbol": "SPY", "filled_qty": 1.5 if filled else 0.0,
                "filled_avg_price": 101.25 if filled else None, "filled_at": None}


def durable(tmp_path, persisted, fail=False):
    def persist():
        if fail:
            raise OSError("push refused")
        persisted.append(1)
    return paper_loop.Durable(intents_dir=tmp_path, persist=persist)


def day(tmp_path, client, *, now, closes, store):
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", OPEN_CONFIG)
    planner = paper_loop.AllocationPlanner(tmp_path / paper_loop.ALLOCATION_STATE, ALL_FRACTIONAL)
    try:
        return paper_loop.run_once(client=client, gate=gate, closes=closes, submit=True, now_fn=now,
                                   planner=planner, durable=store), gate
    finally:
        gate.close()


def monday(tmp_path):
    client, persisted = Client(), []
    day(tmp_path, client, now=NOW, closes=sleeve_closes(), store=durable(tmp_path, persisted))
    assert len(client.submitted) == 8, "Q117 SETUP"
    return client


def fills(tmp_path):
    path = tmp_path / paper_loop.FILLS_LOG
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_terminal_orders_are_recorded_once_and_persisted(tmp_path):
    sent = monday(tmp_path)
    persisted = []
    tuesday = sleeve_closes(end="2026-10-05", n=301)
    record, _ = day(tmp_path, Filled(positions={i.instrument: i.delta_quantity for i in sent.submitted}),
                    now=TUESDAY, closes=tuesday, store=durable(tmp_path, persisted))
    rows = fills(tmp_path)
    assert sorted(r["client_order_id"] for r in rows) == sorted(i.client_order_id for i in sent.submitted), \
        f"Q117 RECORD {len(rows)} lines for 8 terminal orders"
    assert all({"status", "filled_qty", "filled_avg_price"} <= r.keys() for r in rows), "Q117 RECORD fields"
    assert all(r["fill_recorded"] for r in record["reconciliation"]), "Q117 RECORD report"
    assert persisted, "Q117 PERSIST recorded fills were not made durable"
    day(tmp_path, Filled(positions={}), now=TUESDAY, closes=tuesday, store=durable(tmp_path, []))
    assert len(fills(tmp_path)) == 8, "Q117 ONCE a released order was recorded again"


def test_open_orders_are_not_recorded_and_stay_reserved(tmp_path):
    monday(tmp_path)
    record, _ = day(tmp_path, Filled(status="accepted"), now=TUESDAY, closes=sleeve_closes(end="2026-10-05", n=301),
                    store=durable(tmp_path, []))
    assert fills(tmp_path) == [], "Q117 OPEN a non-terminal order was recorded"
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", OPEN_CONFIG)
    try:
        assert sum(not r["terminal"] for r in gate.pending_orders()) == 8, "Q117 OPEN reservation released"
    finally:
        gate.close()


def test_unpersisted_fills_stop_new_exposure(tmp_path):
    monday(tmp_path)
    client = Filled()
    try:
        day(tmp_path, client, now=TUESDAY, closes=sleeve_closes(end="2026-10-05", n=301),
            store=durable(tmp_path, [], fail=True))
    except paper_loop.RunAborted as error:
        assert "not persisted" in str(error), f"Q117 PERSIST wrong refusal {error}"
    else:
        raise AssertionError("Q117 PERSIST the run went on after recorded fills failed to persist")
    assert client.submitted == [], "Q117 PERSIST orders sent after a persist failure"


class Response:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


class Session:
    def __init__(self, status, payload):
        self.status, self.payload = status, payload

    def request(self, method, url, **kwargs):
        return Response(self.status, self.payload)


ENV = {"APCA_API_KEY_ID": "k-not-real", "APCA_API_SECRET_KEY": "s-not-real"}


def test_broker_snapshot_parses_alpaca_strings():
    order = {"status": "filled", "symbol": "TIP", "filled_qty": "12.345678", "filled_avg_price": "110.42",
             "filled_at": "2026-10-06T13:30:02Z"}
    client = alpaca_paper.AlpacaPaperClient(environ=ENV, session=Session(200, order))
    snap = client.order_snapshot("cid")
    assert (snap["status"], snap["filled_qty"], snap["filled_avg_price"]) == ("filled", 12.345678, 110.42), \
        f"Q117 PARSE {snap}"
    assert client.order_status("cid") == "filled", "Q117 PARSE status"
    expired = alpaca_paper.AlpacaPaperClient(environ=ENV, session=Session(200, {"status": "expired", "filled_qty": "0",
                                                                               "filled_avg_price": None}))
    assert expired.order_snapshot("cid")["filled_avg_price"] is None, "Q117 PARSE unfilled price invented"
    assert alpaca_paper.AlpacaPaperClient(environ=ENV, session=Session(404, {})).order_snapshot("cid") is None, \
        "Q117 PARSE unknown order"
