"""Single fail-closed seam between an order decision and any future adapter.

This module deliberately contains no broker client, network call, credential,
or retry policy. A reviewed adapter supplies the final submission callback; the
callback is unreachable unless the live safety gate returns exactly ``ALLOW``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, TypeVar

from live_safety_gate import (
    ALLOW,
    BrokerSnapshot,
    GateDecision,
    LiveSafetyGate,
    OrderIntent,
)


SubmissionResult = TypeVar("SubmissionResult")


class OrderDeniedError(RuntimeError):
    """Hard-stop result carrying the safety decision that blocked submission."""

    def __init__(self, decision: GateDecision) -> None:
        self.decision = decision
        super().__init__(f"order blocked by live safety gate: {decision.reason}")


def submit_order(
    gate: LiveSafetyGate,
    *,
    snapshot: BrokerSnapshot,
    intent: OrderIntent,
    now: datetime,
    submit: Callable[[OrderIntent], SubmissionResult],
) -> SubmissionResult:
    """Evaluate once, then submit only after an explicit ``ALLOW`` decision."""

    decision = gate.evaluate_order(snapshot, intent, now=now)
    if decision.outcome != ALLOW:
        raise OrderDeniedError(decision)
    return submit(intent)

