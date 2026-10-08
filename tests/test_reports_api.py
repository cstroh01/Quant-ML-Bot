"""Unit tests for reports API bridge.

Validates that API responses conform to quantitative contracts, preserve
reconciliation tolerances, and match repository calculations without leaking future data.

Every request is served from a generated panel (tests/api_fixtures.py), so the
module needs no data/cache/, no built frontend and no network (spec 018,
finding 57).
"""

from __future__ import annotations

from datetime import date
import hashlib
import math
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_fixtures import FIXTURE_A, fixture_client, synthetic_panel
from unadjusted_fixtures import publish_bundle, session_prices
import data
import reports.api.routes.data as data_routes

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestReportsApi(unittest.TestCase):
    def setUp(self):
        self.panel = synthetic_panel(**FIXTURE_A)
        self.client = fixture_client(self, self.panel)

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_list_tickers(self):
        # The fixture's tickers, not the fallback list an empty cache returns (finding 18).
        response = self.client.get("/api/data/tickers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["AAPL", "NVDA"])

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
        expected = self.panel[self.panel["Ticker"] == "AAPL"].iloc[0]
        self.assertAlmostEqual(first_bar["open"], expected["Open"], places=9)

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
        # Spec 018, finding 45: this test asserted the four literal p-values.
        # No saved run is wired in, so every ticker reports "not computed".
        for ticker in ("AAPL", "NVDA"):
            response = self.client.get(f"/api/diagnostics/significance?ticker={ticker}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["ticker"], ticker)
            self.assertEqual(data["status"], "not_computed")
            self.assertTrue(data["reason"])
            self.assertEqual(set(data), {"ticker", "status", "reason"})

    def test_backtest_tearsheet(self):
        sessions = data.trading_days(date(2024, 1, 2), date(2024, 9, 30))[:160]
        closes = [100.0 + 8.0 * math.sin(i / 4.0) for i in range(len(sessions))]
        prices = session_prices("AAPL", sessions[0], sessions[-1], closes)
        manifest = publish_bundle(self.client.fixture_cache_dir / "unadjusted", "AAPL", prices)
        from trial_registry import TrialLedger
        from trial_runner import injected_ledger
        from ledger_copy_support import manifest as ledger_manifest
        import ma_crossover_backtest as crossover
        ledger = TrialLedger(self.client.fixture_cache_dir / "recorded", synthetic=True)
        with injected_ledger(ledger), patch.object(crossover, "cache_path", side_effect=lambda name: self.client.fixture_cache_dir / name):
            crossover.main(["--record-trial"], cache_dir=self.client.fixture_cache_dir / "unadjusted")
            before = ledger_manifest(ledger.root)
            response = self.client.get(
                "/api/backtest/tearsheet?ticker=AAPL&short_window=10&long_window=30&commission=1.0&slippage_bps=5.0"
            )
            self.assertEqual(ledger_manifest(ledger.root), before, "GET wrote ledger bytes")
            mismatch = self.client.get("/api/backtest/tearsheet?commission=2.0")
            self.assertEqual(mismatch.status_code, 409)
            self.assertIn("--commission 2.0", mismatch.json()["detail"]["recording_command"])
            self.assertEqual(ledger_manifest(ledger.root), before, "mismatched GET wrote ledger bytes")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["trial_id"])
        self.assertTrue(payload["recorded_at_utc"])
        self.assertEqual(len(payload["recorded_source_tree_hash"]), 64)
        self.assertEqual(payload["ticker"], "AAPL")
        self.assertTrue(payload["reconciliation_passed"])
        self.assertGreater(len(payload["equity_curve"]), 50)
        self.assertGreater(len(payload["trade_log"]), 0)
        for field in ("starting_capital", "liquidate_at_end", "source_name",
                      "downloaded_at_utc", "capital_gate_eligible",
                      "source_limitations", "source_manifest_sha256"):
            self.assertIn(field, payload)
        self.assertEqual(payload["starting_capital"], 10000.0)
        self.assertTrue(payload["liquidate_at_end"])
        self.assertFalse(payload["capital_gate_eligible"])
        self.assertEqual(payload["source_manifest_sha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())

        # Verify 3-way baseline table (Rule 4)
        comparison = {row["strategy_name"]: row for row in payload["comparison_table"]}
        self.assertTrue(any("SMA Crossover" in k for k in comparison))
        self.assertIn("Buy & Hold (Baseline 1)", comparison)
        self.assertTrue(any("Random Signal" in k for k in comparison))

    def assert_unavailable(self, response, reason: str):
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertEqual(set(detail), {"error", "ticker", "reason", "check"})
        self.assertEqual(detail["error"], "unadjusted_price_data_unavailable")
        self.assertEqual(detail["ticker"], "AAPL" if reason != "ticker" else "../x")
        self.assertEqual(detail["reason"], "invalid" if reason == "ticker" else reason)
        self.assertTrue(detail["check"])

    def test_tearsheet_503_missing(self):
        self.assert_unavailable(self.client.get("/api/backtest/tearsheet?ticker=AAPL"), "missing")

    def test_tearsheet_503_ambiguous(self):
        root = self.client.fixture_cache_dir / "unadjusted"
        for start, end, count in ((date(2024, 1, 2), date(2024, 1, 5), 4),
                                  (date(2024, 1, 8), date(2024, 1, 12), 5)):
            publish_bundle(root, "AAPL", session_prices("AAPL", start, end, [100.0] * count))
        self.assert_unavailable(self.client.get("/api/backtest/tearsheet?ticker=AAPL"), "ambiguous")

    def test_tearsheet_503_invalid(self):
        root = self.client.fixture_cache_dir / "unadjusted"
        prices = session_prices("AAPL", date(2024, 1, 2), date(2024, 1, 5), [100.0] * 4)
        manifest = publish_bundle(root, "AAPL", prices)
        data_file = manifest.with_name(manifest.name.replace(".manifest.json", ".ohlcv.csv"))
        data_file.write_bytes(data_file.read_bytes() + b"x")
        response = self.client.get("/api/backtest/tearsheet?ticker=AAPL")
        self.assert_unavailable(response, "invalid")
        self.assertIn("data file hash check failed", response.json()["detail"]["check"])

    def test_tearsheet_503_invalid_ticker(self):
        self.assert_unavailable(self.client.get("/api/backtest/tearsheet?ticker=../x"), "ticker")

    def test_capital_gate_status(self):
        response = self.client.get("/api/capital_gate/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["gates"]), 5)
        # Spec 018, finding 47: this test asserted Gate 1's literal pass. No
        # verification artifact is read, so every gate is unknown, without evidence.
        for gate in data["gates"]:
            self.assertEqual(gate["status"], "unknown")
            self.assertIsNone(gate["evidence"])
            self.assertTrue(gate["details"])
        self.assertEqual(data["test_run"]["status"], "not_computed")
        self.assertTrue(data["test_run"]["reason"])

    def test_ml_rundown(self):
        response = self.client.get("/api/ml/rundown?ticker=AAPL")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "AAPL")
        # Spec 021 FR-018 (finding 23): 019 keeps every session, so the rundown
        # reads the final one. FIXTURE_A is 320 weekdays from Tue 2023-01-03:
        # 64 weeks of 5, each ending on a Monday, so the last is Mon 2023-01-09
        # + 63 weeks = 2024-03-25.
        aapl_dates = self.panel.loc[self.panel["Ticker"] == "AAPL", "Date"]
        self.assertEqual(aapl_dates.max().strftime("%Y-%m-%d"), "2024-03-25")
        self.assertEqual(data["as_of_date"], "2024-03-25")
        # Spec 018, finding 46: no fitted model is wired in, so the forecast is
        # not computed and the five items are indicator rule readings.
        self.assertEqual(data["model_forecast"]["status"], "not_computed")
        self.assertTrue(data["model_forecast"]["reason"])
        self.assertEqual(len(data["insights"]), 5)
        first = data["insights"][0]
        self.assertEqual(first["rank"], 1)
        self.assertIn("technical_reading", first)
        self.assertIn("plain_english", first)
        self.assertIn("how_to_plan", first)

    def test_static_frontend_root(self):
        with tempfile.TemporaryDirectory() as dist:
            Path(dist, "index.html").write_text(
                '<html><script src="/assets/index.js"></script><body>Quant-ML-Bot</body></html>',
                encoding="utf-8",
            )
            response = fixture_client(self, None, dist_dir=Path(dist)).get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("<html", response.text.lower())
            self.assertIn("/assets/", response.text.lower())
            self.assertIn("quant-ml-bot", response.text.lower())
        self.assertEqual(fixture_client(self, None).get("/").status_code, 404)


class TestCleanCheckoutSeams(unittest.TestCase):
    """The seams that keep this module independent of machine state (finding 57)."""

    def test_routes_read_only_the_injected_cache(self):
        # A route that ignored `get_cache_dir` would find the sentinel ticker and return 200.
        client = fixture_client(self, None)
        with tempfile.TemporaryDirectory() as other:
            panel = synthetic_panel(seed=9, sessions=60, drift=0.0, tickers=("SENTINEL",))
            panel.attrs["price_basis"] = "unadjusted_dollars"
            panel.to_csv(Path(other) / "panel.csv", index=False)
            with patch.object(data_routes, "CACHE_DIR", Path(other)):
                response = client.get("/api/data/ohlcv?ticker=SENTINEL")
        self.assertEqual(response.status_code, 404)

    def test_dev_requirements_match_declared_ui_pins(self):
        def pins(name: str) -> dict[str, str]:
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            return dict(re.findall(r"^([A-Za-z0-9_.-]+)==(\S+)$", text, flags=re.MULTILINE))

        dev, ui = pins("requirements-dev.txt"), pins("reports/requirements-ui.txt")
        self.assertTrue(dev)
        api_dependencies = ("fastapi", "httpx")
        self.assertTrue(all(name in dev for name in api_dependencies))
        self.assertEqual(
            {name: dev[name] for name in api_dependencies},
            {name: ui.get(name) for name in api_dependencies},
        )


if __name__ == "__main__":
    unittest.main()
