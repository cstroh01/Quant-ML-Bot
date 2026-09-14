"""Offline acceptance tests for spec 020's manifest-backed price store."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import data


def split_prices() -> pd.DataFrame:
    """Four contiguous sessions with an exact nominal four-for-one step."""
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
            "Ticker": ["TEST"] * 4,
            "Open": [98.0, 100.0, 25.0, 26.0],
            "High": [101.0, 101.0, 27.0, 28.0],
            "Low": [97.0, 99.0, 24.0, 25.0],
            "Close": [100.0, 100.0, 26.0, 27.0],
            "Volume": [1000.0, 1100.0, 4400.0, 4200.0],
        }
    )


def split_actions(*, on_first_session: bool = False) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02" if on_first_session else "2024-01-04"]),
            "Ticker": ["TEST"],
            "Action_Type": ["split"],
            "Value": [4.0],
            "Dividend_Pay_Date": [pd.NaT],
        }
    )


class SyntheticSource:
    def __init__(self, prices: pd.DataFrame | None = None, actions: pd.DataFrame | None = None):
        self.prices = split_prices() if prices is None else prices
        self.actions = split_actions() if actions is None else actions

    def fetch(self, ticker: str, start: date, end: date) -> data.UnadjustedSourceSnapshot:
        del start, end
        prices = self.prices.copy()
        prices["Ticker"] = ticker
        actions = self.actions.copy()
        if not actions.empty:
            actions["Ticker"] = ticker
        return data.UnadjustedSourceSnapshot(
            prices=prices,
            corporate_actions=actions,
            source_name="synthetic-test-source",
            source_method="SyntheticSource.fetch(in-memory fixture)",
            downloaded_at_utc=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc),
            capital_gate_eligible=False,
            limitations=("Synthetic fixture; not market evidence.",),
        )


class ManifestBackedStoreTests(unittest.TestCase):
    def publish(self, root: Path, source: SyntheticSource | None = None) -> Path:
        return data.cache_unadjusted_market_data(
            source or SyntheticSource(),
            "TEST",
            date(2024, 1, 2),
            date(2024, 1, 5),
            created_by_revision="spec-020-synthetic-test",
            cache_dir=root,
        )

    def test_known_four_for_one_split_reconciles_and_store_remains_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.publish(Path(tmp))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertNotEqual(manifest["data_file"], manifest["corporate_actions_file"])
            self.assertTrue((Path(tmp) / manifest["data_file"]).is_file())
            self.assertTrue((Path(tmp) / manifest["corporate_actions_file"]).is_file())

            loaded = data.load_unadjusted_market_data(manifest_path)
            self.assertEqual(loaded.attrs["price_basis"], "unadjusted_dollars")
            self.assertEqual(loaded.attrs["source_name"], "synthetic-test-source")
            self.assertEqual(loaded.attrs["created_by_revision"], "spec-020-synthetic-test")
            self.assertFalse(loaded.attrs["capital_gate_eligible"])
            self.assertEqual(loaded["Split"].tolist(), [1.0, 1.0, 4.0, 1.0])
            self.assertEqual(float(loaded.iloc[1]["Close"] / loaded.iloc[2]["Open"]), 4.0)
            self.assertIn("Research_Close", data.execution_price_frame(loaded))

            from backtest_harness import run_backtest

            execution = loaded.copy()
            execution["Buy_Next_Open"] = [True, False, False, False]
            execution["Sell_Next_Open"] = [False, False, False, True]
            trades = run_backtest(execution, starting_capital=1000.0)
            self.assertEqual(len(trades), 1)
            self.assertEqual(trades.iloc[0]["Entry Quantity"], 1)
            self.assertEqual(trades.iloc[0]["Quantity"], 4.0)

    def test_tampered_price_file_fails_hash_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.publish(Path(tmp))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            data_path = Path(tmp) / manifest["data_file"]
            data_path.write_bytes(data_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "data file hash check failed"):
                data.load_unadjusted_market_data(manifest_path)

    def test_missing_actions_pair_fails_named_existence_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.publish(Path(tmp))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            (Path(tmp) / manifest["corporate_actions_file"]).unlink()
            with self.assertRaisesRegex(FileNotFoundError, "corporate-actions file existence check failed"):
                data.load_unadjusted_market_data(manifest_path)

    def test_tampered_actions_file_fails_hash_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.publish(Path(tmp))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            actions_path = Path(tmp) / manifest["corporate_actions_file"]
            actions_path.write_bytes(actions_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "corporate-actions file hash check failed"):
                data.load_unadjusted_market_data(manifest_path)

    def test_csv_without_manifest_never_receives_unadjusted_stamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "orphan.csv"
            split_prices().to_csv(data_path, index=False)
            ordinary = pd.read_csv(data_path)
            self.assertNotIn("price_basis", ordinary.attrs)
            with self.assertRaisesRegex(ValueError, "manifest JSON check failed"):
                data.load_unadjusted_market_data(data_path)
            self.assertNotIn("price_basis", ordinary.attrs)

    def test_manifest_row_count_is_verified_against_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.publish(Path(tmp))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["row_count"] += 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest row-count check failed"):
                data.load_unadjusted_market_data(manifest_path)

    def test_manifest_download_timestamp_must_be_utc_aware(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.publish(Path(tmp))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["downloaded_at_utc"] = "2026-09-14T12:00:00"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "UTC-aware"):
                data.load_unadjusted_market_data(manifest_path)

    def test_manifest_cannot_declare_an_adjusted_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.publish(Path(tmp))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["price_basis"] = "research_adjusted"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "price-basis check failed"):
                data.load_unadjusted_market_data(manifest_path)


class CalendarAndActionBoundaryTests(unittest.TestCase):
    def publish(self, root: Path, source: SyntheticSource) -> Path:
        return data.cache_unadjusted_market_data(
            source,
            "TEST",
            date(2024, 1, 2),
            date(2024, 1, 5),
            created_by_revision="spec-020-boundary-test",
            cache_dir=root,
        )

    def test_missing_interior_session_fails_contiguity_check(self):
        prices = split_prices().drop(index=1).reset_index(drop=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "session-contiguity check failed"):
                self.publish(Path(tmp), SyntheticSource(prices=prices))

    def test_holiday_is_not_required_as_a_session(self):
        prices = split_prices().iloc[:3].copy()
        prices["Date"] = pd.to_datetime(["2023-12-29", "2024-01-02", "2024-01-03"])
        prices.loc[0:1, ["Open", "High", "Low", "Close"]] = [98.0, 101.0, 97.0, 100.0]
        prices.loc[2, ["Open", "High", "Low", "Close"]] = [25.0, 27.0, 24.0, 26.0]
        actions = split_actions()
        actions["Date"] = pd.to_datetime(["2024-01-03"])
        with tempfile.TemporaryDirectory() as tmp:
            path = self.publish(Path(tmp), SyntheticSource(prices=prices, actions=actions))
            loaded = data.load_unadjusted_market_data(path)
            self.assertEqual(loaded["Date"].dt.strftime("%Y-%m-%d").tolist(), ["2023-12-29", "2024-01-02", "2024-01-03"])

    def test_split_on_first_observed_session_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "no preceding price session"):
                self.publish(Path(tmp), SyntheticSource(actions=split_actions(on_first_session=True)))

    def test_future_price_change_does_not_change_earlier_loaded_rows(self):
        future_changed = split_prices()
        future_changed.loc[3, ["Open", "High", "Low", "Close", "Volume"]] = [40.0, 42.0, 39.0, 41.0, 9000.0]
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_loaded = data.load_unadjusted_market_data(
                self.publish(Path(first), SyntheticSource())
            )
            second_loaded = data.load_unadjusted_market_data(
                self.publish(Path(second), SyntheticSource(prices=future_changed))
            )
            pd.testing.assert_frame_equal(
                first_loaded.iloc[:3].reset_index(drop=True),
                second_loaded.iloc[:3].reset_index(drop=True),
            )

    def test_dividend_without_verified_payment_date_fails_closed(self):
        actions = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-04"]),
                "Ticker": ["TEST"],
                "Action_Type": ["dividend"],
                "Value": [0.25],
                "Dividend_Pay_Date": [pd.NaT],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "dividend payment date missing"):
                self.publish(Path(tmp), SyntheticSource(actions=actions))


class YFinanceAdapterTests(unittest.TestCase):
    def test_adapter_requests_unadjusted_actions_and_is_not_gate_eligible(self):
        calls: list[dict[str, object]] = []
        history = split_prices().drop(columns="Ticker").set_index("Date")
        history["Dividends"] = 0.0
        history["Stock Splits"] = [0.0, 0.0, 4.0, 0.0]

        class FakeTicker:
            def history(self, **kwargs):
                calls.append(kwargs)
                return history.copy()

        adapter = data.YFinanceUnadjustedAdapter(lambda ticker: FakeTicker())
        snapshot = adapter.fetch("TEST", date(2024, 1, 2), date(2024, 1, 5))
        self.assertEqual(calls[0]["auto_adjust"], False)
        self.assertEqual(calls[0]["actions"], True)
        self.assertEqual(calls[0]["interval"], "1d")
        self.assertFalse(snapshot.capital_gate_eligible)
        self.assertTrue(any("delisted" in item for item in snapshot.limitations))
        self.assertTrue(any("spinoff" in item for item in snapshot.limitations))
        self.assertTrue(any("symbol changes" in item for item in snapshot.limitations))

    def test_provisional_adapter_does_not_invent_dividend_payment_date(self):
        history = split_prices().drop(columns="Ticker").set_index("Date")
        history["Dividends"] = [0.0, 0.0, 0.25, 0.0]
        history["Stock Splits"] = 0.0

        class FakeTicker:
            def history(self, **kwargs):
                del kwargs
                return history.copy()

        adapter = data.YFinanceUnadjustedAdapter(lambda ticker: FakeTicker())
        snapshot = adapter.fetch("TEST", date(2024, 1, 2), date(2024, 1, 5))
        dividend = snapshot.corporate_actions.query("Action_Type == 'dividend'").iloc[0]
        self.assertTrue(pd.isna(dividend["Dividend_Pay_Date"]))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "dividend payment date missing"):
                data.cache_unadjusted_market_data(
                    adapter,
                    "TEST",
                    date(2024, 1, 2),
                    date(2024, 1, 5),
                    created_by_revision="spec-020-yfinance-test",
                    cache_dir=Path(tmp),
                )


if __name__ == "__main__":
    unittest.main()
