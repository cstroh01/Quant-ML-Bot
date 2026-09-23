"""Gate 5 operational controls, separate from Gate 3's status cockpit."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from live_safety_gate import BrokerKillQuery, BrokerSnapshot, LiveSafetyGate
from reports.api.schemas import (
    SafetyActionResponse,
    SafetyKillConfirmRequest,
    SafetyKillRequest,
    SafetyKillResetRequest,
    SafetyRollingHaltResetRequest,
    SafetyStatusResponse,
)


router = APIRouter(prefix="/api/safety", tags=["safety"])


async def get_safety_gate() -> LiveSafetyGate:
    """Fail closed until reviewed process bootstrap injects the durable gate."""

    raise HTTPException(status_code=503, detail="live safety gate is not configured")


def _snapshot(request: SafetyRollingHaltResetRequest) -> BrokerSnapshot:
    value = request.snapshot
    return BrokerSnapshot(
        as_of=value.as_of,
        status=value.status,
        equity=value.equity,
        external_cash_flow=value.external_cash_flow,
        positions=value.positions,
        prices=value.prices,
    )


def _conflict(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/kill", response_model=SafetyActionResponse)
async def request_kill(
    request: SafetyKillRequest,
    gate: LiveSafetyGate = Depends(get_safety_gate),
) -> SafetyActionResponse:
    try:
        status = gate.request_kill(
            operator=request.operator, reason=request.reason, now=request.now
        )
    except ValueError as exc:
        raise _conflict(exc) from exc
    return SafetyActionResponse(status=status)


@router.post("/kill/confirm", response_model=SafetyActionResponse)
async def confirm_kill(
    request: SafetyKillConfirmRequest,
    gate: LiveSafetyGate = Depends(get_safety_gate),
) -> SafetyActionResponse:
    query = None
    if request.query is not None:
        query = BrokerKillQuery(
            working_orders_terminal=request.query.working_orders_terminal,
            disable_status=request.query.disable_status,
        )
    try:
        status = gate.confirm_kill(query=query, now=request.now)
    except ValueError as exc:
        raise _conflict(exc) from exc
    return SafetyActionResponse(status=status)


@router.post("/kill/reset", response_model=SafetyActionResponse)
async def reset_kill(
    request: SafetyKillResetRequest,
    gate: LiveSafetyGate = Depends(get_safety_gate),
) -> SafetyActionResponse:
    try:
        gate.reset_kill(
            operator=request.operator,
            reason=request.reason,
            broker_disable_independently_verified=(
                request.broker_disable_independently_verified
            ),
            now=request.now,
        )
    except ValueError as exc:
        raise _conflict(exc) from exc
    return SafetyActionResponse(status="RESET")


@router.post("/halt/rolling/reset", response_model=SafetyActionResponse)
async def reset_rolling_halt(
    request: SafetyRollingHaltResetRequest,
    gate: LiveSafetyGate = Depends(get_safety_gate),
) -> SafetyActionResponse:
    try:
        gate.reset_rolling_halt(
            _snapshot(request),
            operator=request.operator,
            reason=request.reason,
            now=request.now,
        )
    except ValueError as exc:
        raise _conflict(exc) from exc
    return SafetyActionResponse(status="RESET")


@router.get("/status", response_model=SafetyStatusResponse)
async def get_status(
    gate: LiveSafetyGate = Depends(get_safety_gate),
) -> SafetyStatusResponse:
    return SafetyStatusResponse(state=gate.status())
