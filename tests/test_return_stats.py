"""Offline regression coverage for the Sharpe reported by return_stats.main."""

import math
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401
import metrics
import return_stats


@pytest.mark.parametrize("rate", [0.0, 0.0378, -0.05, 0.5])
def test_reported_sharpe_matches_log_hurdle_and_metrics(monkeypatch, capsys, rate):
    prices = pd.DataFrame({
        "Ticker": "SYNTHETIC",
        "Date": pd.bdate_range("2020-01-01", periods=7),
        "Close": [100.0, 101.0, 99.0, 102.0, 100.0, 103.0, 104.0],
    })
    monkeypatch.setattr(return_stats, "TICKERS", ["SYNTHETIC"])
    monkeypatch.setattr(return_stats, "RISK_FREE_RATE_ANNUAL", rate)
    monkeypatch.setattr(return_stats, "download_market_data", Mock(return_value=prices))
    monkeypatch.setattr(return_stats.plt, "subplots", Mock(return_value=(Mock(), [[Mock()]])))
    monkeypatch.setattr(return_stats, "save_figure", Mock())
    monkeypatch.setattr(return_stats, "cache_path", Mock(return_value="unused.png"))

    return_stats.main()
    output = capsys.readouterr().out
    line = next(line for line in output.splitlines() if line.startswith("SYNTHETIC:"))
    reported = float(line.split("Sharpe ratio = ")[1])

    returns = np.log(prices.Close / prices.Close.shift(1)).dropna()
    expected = (returns.mean() * 252 - math.log1p(rate)) / (returns.std() * math.sqrt(252))
    assert reported == pytest.approx(expected, abs=5e-7, rel=0)
    assert metrics.sharpe_ratio(returns, risk_free_rate_annual=rate) == pytest.approx(expected)
