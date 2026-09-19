"""Pure cost-domain validation and rate conversion, independent of accounting."""

import numpy as np


def validate_costs(commission_per_trade: float, slippage_bps: float) -> None:
    """Validate the cash execution cost domain before any event."""
    if not np.isfinite(commission_per_trade) or commission_per_trade < 0:
        raise ValueError("commission_per_trade must be finite and >= 0")
    if not np.isfinite(slippage_bps) or not 0 <= slippage_bps < 10000:
        raise ValueError("slippage_bps must be finite and in [0, 10000)")


def risk_free_log_return(risk_free_rate_annual: float) -> float:
    """Convert a finite effective annual risk-free rate > -1 to log units."""
    if not np.isfinite(risk_free_rate_annual) or risk_free_rate_annual <= -1:
        raise ValueError("annual effective risk-free rate must be finite and > -1")
    return float(np.log1p(risk_free_rate_annual))
