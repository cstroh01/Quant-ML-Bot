"""REQ-034-005: Gate 5 operational endpoints live outside capital_gate.py."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import context  # noqa: F401 -- makes scripts importable
from live_safety_gate import BrokerSnapshot, OrderIntent, SafetyConfig, SafetyGate
from reports.api.main import create_app
from reports.api.routes.safety import get_safety_gate, router


UTC = timezone.utc


def at(day: int = 10, hour: int = 15) -> datetime:
    return datetime(2026, 6, day, hour, tzinfo=UTC)


def config() -> SafetyConfig:
    return SafetyConfig(
        version="router-test-v1",
        max_position_pct=0.25,
        max_gross_pct=1.0,
        daily_loss_pct=0.5,
        rolling_drawdown_pct=0.10,
        rolling_window_sessions=5,
        max_snapshot_age_seconds=30.0,
        max_clock_skew_seconds=5.0,
    )


def snapshot(day: int, equity: float) -> BrokerSnapshot:
    return BrokerSnapshot(
        as_of=at(day, 14),
        status="OK",
        equity=equity,
        external_cash_flow=0.0,
        positions={},
        prices={"AAPL": 10.0},
    )


class SafetyRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "safety.db"
        self.safety_config = config()
        self.gate = SafetyGate(self.db_path, self.safety_config)
        self.addCleanup(self.gate.close)
        app = FastAPI()
        app.include_router(router)

        async def request_gate():
            gate = SafetyGate(self.db_path, self.safety_config)
            try:
                yield gate
            finally:
                gate.close()

        app.dependency_overrides[get_safety_gate] = request_gate
        self.client = TestClient(app)

    def test_status_delegates_to_gate(self):
        response = self.client.get("/api/safety/status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["state"]["kill_latched"])
        self.assertEqual(response.json()["state"]["config_json"]["version"], "router-test-v1")

    def test_kill_confirm_and_reset_delegate_in_order(self):
        kill = self.client.post(
            "/api/safety/kill",
            json={"operator": "camden", "reason": "operator stop", "now": at().isoformat()},
        )
        self.assertEqual(kill.status_code, 200)
        self.assertEqual(kill.json(), {"status": "LOCAL_BLOCKED"})

        confirm = self.client.post(
            "/api/safety/kill/confirm",
            json={
                "query": {"working_orders_terminal": True, "disable_status": True},
                "now": at().isoformat(),
            },
        )
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(confirm.json(), {"status": "KILL_CONFIRMED"})

        reset = self.client.post(
            "/api/safety/kill/reset",
            json={
                "operator": "camden",
                "reason": "review complete",
                "broker_disable_independently_verified": False,
                "now": at().isoformat(),
            },
        )
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json(), {"status": "RESET"})
        self.assertFalse(self.gate.status()["kill_latched"])

    def test_rolling_halt_reset_delegates_with_snapshot(self):
        self.gate.evaluate_order(
            snapshot(8, 100_000.0),
            OrderIntent("router-seed-1", "AAPL", 0.0001),
            now=at(8, 14),
        )
        self.gate.evaluate_order(
            snapshot(9, 88_000.0),
            OrderIntent("router-seed-2", "AAPL", 0.0001),
            now=at(9, 14),
        )
        self.assertTrue(self.gate.status()["rolling_halt_active"])

        recovered = snapshot(10, 100_000.0)
        response = self.client.post(
            "/api/safety/halt/rolling/reset",
            json={
                "snapshot": {
                    "as_of": recovered.as_of.isoformat(),
                    "status": recovered.status,
                    "equity": recovered.equity,
                    "external_cash_flow": recovered.external_cash_flow,
                    "positions": recovered.positions,
                    "prices": recovered.prices,
                },
                "operator": "camden",
                "reason": "drawdown reviewed",
                "now": at(10, 14).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "RESET"})
        self.assertFalse(self.gate.status()["rolling_halt_active"])

    def test_domain_reset_refusal_maps_to_conflict(self):
        response = self.client.post(
            "/api/safety/kill/reset",
            json={
                "operator": "camden",
                "reason": "nothing active",
                "broker_disable_independently_verified": True,
                "now": at().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("no active kill", response.json()["detail"])

    def test_naive_control_timestamp_is_rejected(self):
        response = self.client.post(
            "/api/safety/kill",
            json={"operator": "camden", "reason": "x", "now": "2026-06-10T15:00:00"},
        )
        self.assertEqual(response.status_code, 422)

    def test_missing_gate_dependency_fails_closed(self):
        response = TestClient(create_app(dist_dir=None)).get("/api/safety/status")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
