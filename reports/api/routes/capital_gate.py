"""Capital Gate status and verification cockpit API endpoints.

No verification artifact is read here yet, so every gate reports `unknown`
with no evidence and the test run is not computed (spec 018, finding 47).
`CapitalGateItem` rejects any other state without an evidence reference;
evidence-backed states arrive with the experiment run store (audit work
order 3).
"""

from __future__ import annotations

from fastapi import APIRouter
from reports.api.schemas import CapitalGateItem, CapitalGateStatusResponse, NotComputed

router = APIRouter(prefix="/api/capital_gate", tags=["capital_gate"])

NO_EVIDENCE = "No verification artifact is recorded for this gate, so its state is unknown."


@router.get("/status", response_model=CapitalGateStatusResponse)
def get_capital_gate_status() -> CapitalGateStatusResponse:
    """Return the evidence status of the 5 Capital Gates (Project Instructions v2.1 §12)."""
    gates = [
        CapitalGateItem(
            gate_number=1,
            title="Layer 3 Machine Gates",
            description="Automated CI verification: lookahead shift test, null pipeline test on shuffled labels (Sharpe <= 0.3), and 2x cost stress test.",
            status="unknown",
            details=NO_EVIDENCE,
        ),
        CapitalGateItem(
            gate_number=2,
            title="Out-of-Sample Positive Expectancy",
            description="Purged & embargoed walk-forward OOS backtest shows positive expectancy net of realistic transaction costs ($1.00/trade, 5 bps slippage).",
            status="unknown",
            details=NO_EVIDENCE,
        ),
        CapitalGateItem(
            gate_number=3,
            title="Deflated Sharpe Ratio (AFML)",
            description="Deflated Sharpe ratio remains positive after adjusting for multiple testing across all hyperparameter grids and strategy variants tried.",
            status="unknown",
            details=NO_EVIDENCE,
        ),
        CapitalGateItem(
            gate_number=4,
            title="Paper Trading Verification",
            description="Minimum 1-2 months paper trading (broker paper account or live-data simulation) matching backtest performance within tolerance.",
            status="unknown",
            details="Awaits Phase 4 order execution and broker paper account integration.",
        ),
        CapitalGateItem(
            gate_number=5,
            title="Capped Real Capital Allocation",
            description="Starts with small, explicitly-capped real capital with automated stop-loss circuit breakers and strict risk limits.",
            status="unknown",
            details="Subject to human approval and execution gate (Constitution Rule 7).",
        ),
    ]

    return CapitalGateStatusResponse(
        overall_readiness="Phase 3: Quantitative Model Calibration & Feature Refinement",
        test_run=NotComputed(
            reason="The API reads no CI result, so the terminal reports no test count or pass state."
        ),
        gates=gates,
    )
