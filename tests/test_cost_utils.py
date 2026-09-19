"""Shared numeric helpers retain their domains without accounting dependencies."""

import math

import numpy as np
import pytest

import context  # noqa: F401
from cost_utils import risk_free_log_return, validate_costs


@pytest.mark.parametrize("rate", [0.0, 0.0378, -0.05, 0.5, 1e-12])
def test_risk_free_rate_converts_effective_annual_to_log_units(rate):
    assert risk_free_log_return(rate) == pytest.approx(math.log1p(rate), rel=1e-14)


@pytest.mark.parametrize("rate", [-1.0, -1.1, np.nan, np.inf, -np.inf])
def test_risk_free_rate_rejects_undefined_log_hurdles(rate):
    with pytest.raises(ValueError, match="annual effective risk-free rate"):
        risk_free_log_return(rate)


@pytest.mark.parametrize("commission,slippage", [(0.0, 0.0), (1.0, 5.0), (1.0, 9999.0)])
def test_valid_costs(commission, slippage):
    assert validate_costs(commission, slippage) is None


@pytest.mark.parametrize("commission", [-1.0, np.nan, np.inf, -np.inf])
def test_invalid_commission(commission):
    with pytest.raises(ValueError, match="commission_per_trade"):
        validate_costs(commission, 5.0)


@pytest.mark.parametrize("slippage", [-1.0, 10000.0, np.nan, np.inf, -np.inf])
def test_invalid_slippage(slippage):
    with pytest.raises(ValueError, match="slippage_bps"):
        validate_costs(1.0, slippage)
