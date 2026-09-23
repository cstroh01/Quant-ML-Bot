"""REQ-034-001: one fail-closed seam before any future broker adapter."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import context  # noqa: F401 -- makes scripts importable
from live_safety_gate import ACTION_BLOCK_NEW, ALLOW, DENY, GateDecision
from order_gateway import OrderDeniedError, submit_order

REPO_ROOT = Path(__file__).resolve().parents[1]


BROKER_CLIENT_ROOTS = {
    "alpaca",
    "alpaca_trade_api",
    "binance",
    "ccxt",
    "coinbase",
    "ib_insync",
    "ibapi",
    "oandapyV20",
    "robin_stocks",
    "schwab",
    "tastytrade",
    "tradier",
}


def _imports(path: Path) -> tuple[set[str], bool]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    roots: set[str] = set()
    imports_live_gate = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
            if node.module in {"live_safety_gate", "scripts.live_safety_gate"}:
                imports_live_gate |= any(alias.name == "LiveSafetyGate" for alias in node.names)
    return roots, imports_live_gate


def broker_import_without_gate(path: Path) -> bool:
    roots, imports_live_gate = _imports(path)
    return bool(roots & BROKER_CLIENT_ROOTS) and not imports_live_gate


def decision(outcome: str, reason: str = "OK") -> GateDecision:
    return GateDecision(
        outcome=outcome,
        reason=reason,
        config_version="test-v1",
        action=ACTION_BLOCK_NEW,
        checks={},
    )


class FakeGate:
    def __init__(self, result: GateDecision, events: list[str]) -> None:
        self.result = result
        self.events = events

    def evaluate_order(self, snapshot, intent, *, now):
        self.events.append("evaluate")
        return self.result


class OrderGatewayTests(unittest.TestCase):
    def test_allow_evaluates_before_calling_submitter(self):
        events: list[str] = []
        gate = FakeGate(decision(ALLOW), events)

        result = submit_order(
            gate,
            snapshot=object(),
            intent=object(),
            now=object(),
            submit=lambda intent: events.append("submit") or "broker-ack",
        )

        self.assertEqual(result, "broker-ack")
        self.assertEqual(events, ["evaluate", "submit"])

    def test_deny_is_a_hard_stop_and_preserves_the_decision(self):
        events: list[str] = []
        blocked = decision(DENY, "KILL_LATCHED")
        gate = FakeGate(blocked, events)

        with self.assertRaises(OrderDeniedError) as caught:
            submit_order(
                gate,
                snapshot=object(),
                intent=object(),
                now=object(),
                submit=lambda intent: events.append("submit"),
            )

        self.assertIs(caught.exception.decision, blocked)
        self.assertEqual(events, ["evaluate"])

    def test_any_non_allow_outcome_is_a_hard_stop(self):
        events: list[str] = []
        gate = FakeGate(decision("WARNING", "UNKNOWN_OUTCOME"), events)
        with self.assertRaises(OrderDeniedError):
            submit_order(
                gate,
                snapshot=object(),
                intent=object(),
                now=object(),
                submit=lambda intent: events.append("submit"),
            )
        self.assertEqual(events, ["evaluate"])


class BrokerImportGuardTests(unittest.TestCase):
    def test_planted_broker_import_without_live_gate_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adapter.py"
            path.write_text("import alpaca\n", encoding="utf-8")
            self.assertTrue(broker_import_without_gate(path))

    def test_control_broker_import_with_live_gate_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adapter.py"
            path.write_text(
                "import alpaca\nfrom live_safety_gate import LiveSafetyGate\n",
                encoding="utf-8",
            )
            self.assertFalse(broker_import_without_gate(path))

    def test_production_broker_imports_always_import_live_gate(self):
        roots = [REPO_ROOT / "scripts", REPO_ROOT / "reports"]
        exec_dir = REPO_ROOT / "exec"
        if exec_dir.exists():
            roots.append(exec_dir)
        offenders = [
            path.relative_to(REPO_ROOT).as_posix()
            for root in roots
            for path in root.rglob("*.py")
            if broker_import_without_gate(path)
        ]
        self.assertEqual(offenders, [], f"broker modules missing LiveSafetyGate: {offenders}")


if __name__ == "__main__":
    unittest.main()
