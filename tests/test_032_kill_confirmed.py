"""Spec 032 audit defect: a stored kill confirmation must not outlive later contrary broker evidence.

Before this fix, `confirm_kill` set `kill_confirmed=True` once and never cleared it. A later
confirmation that reported working orders, a broker not yet disabled, or no evidence left the
stale True in place, and `reset_kill` accepted it without a fresh query (cleanup audit
2026-09-18; HANDOFF-2026-09-25 item 4). EXAMPLE — NOT A RESULT: synthetic gate state only.
"""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from context import SCRIPTS_DIR  # noqa: F401  (puts scripts/ on sys.path)
import live_safety_gate as lsg
import mutation_support_032
from live_safety_gate import (KILL_BROKER_CANCEL_PENDING, KILL_BROKER_DISABLE_UNVERIFIED, KILL_CONFIRMED,
                              KILL_RECONCILING)

AT = datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc)


def query(terminal, disabled):
    """Built from the live module each call, so an in-memory mutant uses its own classes."""
    return lsg.BrokerKillQuery(working_orders_terminal=terminal, disable_status=disabled)


def later():
    return {
        "working orders reopened": (query(False, None), KILL_RECONCILING),
        "broker not disabled": (query(True, False), KILL_BROKER_CANCEL_PENDING),
        "disable status unknown": (query(True, None), KILL_BROKER_DISABLE_UNVERIFIED),
        "no evidence": (None, KILL_BROKER_DISABLE_UNVERIFIED),
    }


def config():
    return lsg.SafetyConfig(version="test-v1", max_position_pct=0.25, max_gross_pct=1.0, daily_loss_pct=0.02,
                        rolling_drawdown_pct=0.05, rolling_window_sessions=5, max_snapshot_age_seconds=30.0,
                        max_clock_skew_seconds=5.0)


class StickyKillConfirmationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._gates = []

    def tearDown(self):
        for gate in self._gates:
            gate.close()
        self._tmp.cleanup()

    def gate(self):
        gate = lsg.SafetyGate(Path(self._tmp.name) / f"g{len(self._gates)}.sqlite", config())
        self._gates.append(gate)
        return gate

    def confirmed_then(self, contrary):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="halt", now=AT)
        self.assertEqual(gate.confirm_kill(query=query(True, True), now=AT), KILL_CONFIRMED)
        return gate, gate.confirm_kill(query=contrary, now=AT)

    def test_control_fresh_confirmation_still_permits_reset(self):
        gate = self.gate()
        gate.request_kill(operator="camden", reason="halt", now=AT)
        self.assertEqual(gate.confirm_kill(query=query(True, True), now=AT), KILL_CONFIRMED)
        gate.reset_kill(operator="camden", reason="broker confirmed clear", now=AT)

    def test_later_contrary_evidence_revokes_the_stored_confirmation(self):
        for name, (contrary, status) in later().items():
            gate, observed = self.confirmed_then(contrary)
            self.assertEqual(observed, status, f"032 STATUS {name}")
            try:
                gate.reset_kill(operator="camden", reason="stale", now=AT)
            except ValueError:
                continue
            raise AssertionError(f"032 STICKY reset accepted a stale confirmation after {name}")

    def test_reconfirming_after_revocation_permits_reset_again(self):
        gate, _ = self.confirmed_then(later()["working orders reopened"][0])
        self.assertEqual(gate.confirm_kill(query=query(True, True), now=AT), KILL_CONFIRMED)
        gate.reset_kill(operator="camden", reason="re-confirmed", now=AT)

    def test_planted_defect_never_clearing_the_flag_is_caught(self):
        """Rule 12: restore the pre-fix behavior (no revocation) and the sticky oracle must fail."""
        mutation_support_032.killed(
            lsg,
            'if status_result != KILL_CONFIRMED and state["kill_confirmed"]:',
            "if False:",
            lambda: self.test_later_contrary_evidence_revokes_the_stored_confirmation(),
        )


if __name__ == "__main__":
    unittest.main()
