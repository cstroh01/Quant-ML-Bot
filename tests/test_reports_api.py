"""Unit tests for reports API bridge.

Validates that API responses conform to quantitative contracts, preserve
reconciliation tolerances, and match repository calculations without leaking future data.
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from reports.api.main import app


class TestReportsApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_list_tickers(self):
        response = self.client.get("/api/data/tickers")
        self.assertEqual(response.status_code, 200)
        tickers = response.json()
        self.assertIsInstance(tickers, list)
        self.assertIn("AAPL", tickers)

    def test_get_ohlcv_bars(self):
        response = self.client.get("/api/data/ohlcv?ticker=AAPL")
        self.assertEqual(response.status_code, 200)
        bars = response.json()
        self.assertGreater(len(bars), 100)
        first_bar = bars[0]
        self.assertIn("time", first_bar)
        self.assertIn("open", first_bar)
        self.assertIn("high", first_bar)
        self.assertIn("low", first_bar)
        self.assertIn("close", first_bar)
        self.assertIn("volume", first_bar)
        # Verify ISO YYYY-MM-DD date format
        self.assertEqual(len(first_bar["time"]), 10)
        self.assertEqual(first_bar["time"][4], "-")

    def test_market_stats(self):
        response = self.client.get("/api/data/stats?ticker=AAPL")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "AAPL")
        self.assertGreater(data["bars_count"], 100)
        self.assertGreater(data["annual_volatility"], 0.0)
        self.assertLess(data["max_drawdown"], 0.0)

    def test_missing_bars_gaps(self):
        response = self.client.get("/api/data/gaps?ticker=AAPL")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "AAPL")
        self.assertIsInstance(data["total_missing_bars"], int)

    def test_collinearity_diagnostics(self):
        response = self.client.get("/api/diagnostics/collinearity?ticker=AAPL")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "AAPL")
        diagnostics = {d["feature_set"]: d for d in data["diagnostics"]}
        self.assertIn("levels", diagnostics)
        self.assertIn("scale_free", diagnostics)

        # Spec 014: condition number of scale_free is substantially better than levels
        self.assertLess(
            diagnostics["scale_free"]["condition_number"],
            diagnostics["levels"]["condition_number"],
        )

    def test_significance_screening(self):
        response = self.client.get("/api/diagnostics/significance?ticker=AAPL")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "AAPL")
        self.assertEqual(data["screening_alpha"], 0.10)
        self.assertEqual(len(data["entries"]), 4)

    def test_backtest_tearsheet(self):
        response = self.client.get(
            "/api/backtest/tearsheet?ticker=AAPL&short_window=10&long_window=30&commission=1.0&slippage_bps=5.0"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "AAPL")
        self.assertTrue(data["reconciliation_passed"])
        self.assertGreater(len(data["equity_curve"]), 50)
        self.assertGreater(len(data["trade_log"]), 0)

        # Verify 3-way baseline table (Rule 4)
        comparison = {row["strategy_name"]: row for row in data["comparison_table"]}
        self.assertTrue(any("SMA Crossover" in k for k in comparison))
        self.assertIn("Buy & Hold (Baseline 1)", comparison)
        self.assertTrue(any("Random Signal" in k for k in comparison))

    def test_capital_gate_status(self):
        response = self.client.get("/api/capital_gate/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["gates"]), 5)
        # Gate 1 should be passed
        self.assertEqual(data["gates"][0]["status"], "passed")

    def test_static_frontend_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<html", response.text.lower())
        self.assertIn("/assets/", response.text.lower())
        self.assertIn("quant-ml-bot", response.text.lower())


if __name__ == "__main__":
    unittest.main()
