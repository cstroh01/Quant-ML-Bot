"""Capital Gate status and verification cockpit API endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from reports.api.schemas import CapitalGateItem, CapitalGateStatusResponse

router = APIRouter(prefix="/api/capital_gate", tags=["capital_gate"])


@router.get("/status", response_model=CapitalGateStatusResponse)
def get_capital_gate_status() -> CapitalGateStatusResponse:
    """Return the audit status of the 5 Capital Gates (Project Instructions v2.1 §12)."""
    gates = [
        CapitalGateItem(
            gate_number=1,
            title="Layer 3 Machine Gates",
            description="Automated CI verification: lookahead shift test, null pipeline test on shuffled labels (Sharpe <= 0.3), and 2x cost stress test.",
            status="passed",
            details="All 301 unit tests passing. Anti-lookahead assertions active across scripts/walk_forward_cv.py, scripts/features.py, and scripts/targets.py.",
            evidence="301 passed in pytest suite; purged and embargoed walk-forward test passing.",
        ),
        CapitalGateItem(
            gate_number=2,
            title="Out-of-Sample Positive Expectancy",
            description="Purged & embargoed walk-forward OOS backtest shows positive expectancy net of realistic transaction costs ($1.00/trade, 5 bps slippage).",
            status="in_progress",
            details="Spec 014 proved scale-free feature matrix is well-conditioned (cond # dropped from 36.17 to 2.15, VIF from 268 to 1.60). Spec 012 cost-hurdle entry rule and Spec 013 multi-ticker evaluation currently in flight.",
            evidence="Spec 014 feature_diagnostics.py verified on 10y AAPL.",
        ),
        CapitalGateItem(
            gate_number=3,
            title="Deflated Sharpe Ratio (AFML)",
            description="Deflated Sharpe ratio remains positive after adjusting for multiple testing across all hyperparameter grids and strategy variants tried.",
            status="pending",
            details="Scheduled for Phase 3 completion following Spec 013 multi-ticker run.",
            evidence=None,
        ),
        CapitalGateItem(
            gate_number=4,
            title="Paper Trading Verification",
            description="Minimum 1-2 months paper trading (broker paper account or live-data simulation) matching backtest performance within tolerance.",
            status="pending",
            details="Awaits Phase 4 order execution and broker paper account integration.",
            evidence=None,
        ),
        CapitalGateItem(
            gate_number=5,
            title="Capped Real Capital Allocation",
            description="Starts with small, explicitly-capped real capital with automated stop-loss circuit breakers and strict risk limits.",
            status="pending",
            details="Subject to human approval and execution gate (Constitution Rule 7).",
            evidence=None,
        ),
    ]

    return CapitalGateStatusResponse(
        overall_readiness="Phase 3: Quantitative Model Calibration & Feature Refinement",
        gates=gates,
    )
