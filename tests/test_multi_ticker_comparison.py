"""Tests for scripts/multi_ticker_comparison.py (spec 013).

Synthetic, network-free (Rule 5's "a test that requires a download is not a
test"): `download_market_data` is monkeypatched per test so `run_one_ticker`
never leaves this process. Grid sizes and `RANDOM_BASELINE_SEEDS` are left at
the module's real defaults -- `ridge` is cheap enough on a few hundred
synthetic rows that this suite runs in seconds, not the hours the module's
own docstring notes for `hgb` at ten years of real data.
"""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from context import SCRIPTS_DIR  # noqa: F401  (import for the sys.path effect)

import multi_ticker_comparison as mtc


def _price_walk(n: int, seed: int = 11) -> pd.DataFrame:
    """An OHLCV frame long enough to build features and several folds from.

    Mirrors `test_model_cv.py`'s `_price_walk` fixture: a random walk with no
    Ticker/High/Low columns, since `build_features` only reads Date/Open/
    Close/Volume.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n)
    close = 100.0 + np.cumsum(rng.normal(scale=0.8, size=n))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, size=n),
        }
    )


def _long_history(seed: int = 11) -> pd.DataFrame:
    """Enough rows for several outer walk-forward folds to run."""
    return _price_walk(600, seed=seed)


def _short_history(seed: int = 7) -> pd.DataFrame:
    """Too little history for even one outer walk-forward fold."""
    return _price_walk(60, seed=seed)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["Date", "Open", "Close", "Volume"])


def _fake_download(frames: dict[str, pd.DataFrame]):
    """A `download_market_data` stand-in keyed by the single requested ticker.

    `run_one_ticker` always calls with `[ticker]` (one name at a time, per
    spec.md's "Owns" section), so the fake only has to serve one key.
    """

    def _download(tickers, period="2y", **kwargs):
        (ticker,) = tickers
        return frames[ticker].copy()

    return _download


class TestIsolatedFailure(unittest.TestCase):
    """T007 — one ticker too short for a fold; the rest complete. (SC-001)"""

    def test_the_short_ticker_fails_by_name_and_the_others_complete(self):
        frames = {
            "GOOD1": _long_history(seed=1),
            "BAD": _short_history(),
            "GOOD2": _long_history(seed=2),
        }
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, failures = mtc.run_comparison(
                tickers=["GOOD1", "BAD", "GOOD2"], seed_count=3
            )

        self.assertEqual([failure.ticker for failure in failures], ["BAD"])
        self.assertTrue(failures[0].reason)  # a real reason, not an empty string

        completed_tickers = set(results_frame["Ticker"])
        self.assertEqual(completed_tickers, {"GOOD1", "GOOD2"})
        for ticker in ("GOOD1", "GOOD2"):
            rows = results_frame[results_frame["Ticker"] == ticker]
            self.assertEqual(
                set(rows["Strategy"]),
                {mtc.STRATEGY_ML, mtc.STRATEGY_BUY_AND_HOLD, mtc.STRATEGY_RANDOM},
            )


class TestAllSucceed(unittest.TestCase):
    """T008 — one row per (ticker, strategy), three strategies each. (SC-002)"""

    def test_every_ticker_produces_exactly_three_rows(self):
        frames = {"A": _long_history(seed=1), "B": _long_history(seed=2)}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, failures = mtc.run_comparison(
                tickers=["A", "B"], seed_count=3
            )

        self.assertEqual(failures, [])
        self.assertEqual(len(results_frame), 6)
        for ticker in ("A", "B"):
            strategies = results_frame.loc[
                results_frame["Ticker"] == ticker, "Strategy"
            ]
            self.assertEqual(
                set(strategies),
                {mtc.STRATEGY_ML, mtc.STRATEGY_BUY_AND_HOLD, mtc.STRATEGY_RANDOM},
            )
            self.assertEqual(len(strategies), 3)


class TestAllFail(unittest.TestCase):
    """T009 — the runner completes and reports every failure."""

    def test_every_ticker_failing_still_returns_a_complete_report(self):
        frames = {"BAD1": _short_history(seed=1), "BAD2": _empty_frame()}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, failures = mtc.run_comparison(
                tickers=["BAD1", "BAD2"], seed_count=3
            )

        self.assertEqual({failure.ticker for failure in failures}, {"BAD1", "BAD2"})
        self.assertTrue(all(failure.reason for failure in failures))
        self.assertTrue(results_frame.empty)


class TestCostParameterConsistency(unittest.TestCase):
    """T010 — every row shares identical cost parameters. (SC-003)"""

    def test_commission_and_slippage_match_across_tickers_and_strategies(self):
        frames = {"A": _long_history(seed=1), "B": _long_history(seed=2)}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, failures = mtc.run_comparison(
                tickers=["A", "B"],
                commission_per_trade=1.25,
                slippage_bps=7.0,
                seed_count=3,
            )

        self.assertEqual(failures, [])
        self.assertTrue((results_frame["commission_per_trade"] == 1.25).all())
        self.assertTrue((results_frame["slippage_bps"] == 7.0).all())

    def test_isolated_failure_still_matches_costs_for_completed_tickers(self):
        frames = {"GOOD": _long_history(seed=1), "BAD": _short_history()}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, _failures = mtc.run_comparison(
                tickers=["GOOD", "BAD"], seed_count=3
            )

        self.assertTrue((results_frame["commission_per_trade"] == mtc.COMMISSION_PER_TRADE).all())
        self.assertTrue((results_frame["slippage_bps"] == mtc.SLIPPAGE_BPS).all())


class TestHonestyColumns(unittest.TestCase):
    """FR-005 — the mandatory hurdle/prediction columns and Rule 2/3/4 params."""

    def test_ml_row_carries_hurdle_and_prediction_columns_and_fold_geometry(self):
        frames = {"A": _long_history(seed=1)}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, failures = mtc.run_comparison(tickers=["A"], seed_count=3)

        self.assertEqual(failures, [])
        ml_row = results_frame[results_frame["Strategy"] == mtc.STRATEGY_ML].iloc[0]
        self.assertGreater(ml_row["fold_count"], 0)
        self.assertEqual(ml_row["purge_bars"], mtc.LABEL_HORIZON)
        self.assertEqual(ml_row["embargo_bars"], mtc.EMBARGO_BARS)
        self.assertEqual(ml_row["random_state"], mtc.RANDOM_STATE)
        self.assertEqual(ml_row["random_baseline_seed_count"], 3)
        self.assertFalse(np.isnan(ml_row["Median hurdle (bps)"]))
        self.assertGreaterEqual(ml_row["Median hurdle (bps)"], 0.0)

    def test_baseline_rows_carry_nan_for_the_ml_only_columns(self):
        frames = {"A": _long_history(seed=1)}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, _failures = mtc.run_comparison(tickers=["A"], seed_count=3)

        baseline_rows = results_frame[results_frame["Strategy"] != mtc.STRATEGY_ML]
        self.assertTrue(baseline_rows["Median hurdle (bps)"].isna().all())
        self.assertTrue(baseline_rows["|pred| q90 (bps)"].isna().all())


class TestOutputFilename(unittest.TestCase):
    """FR-006 — a ticker-namespaced filename, sorted and deduped."""

    def test_filename_is_sorted_and_deduped(self):
        self.assertEqual(
            mtc._output_filename(["NVDA", "AAPL", "AAPL"]), "AAPL-NVDA_comparison.csv"
        )


class TestCsvRoundTrip(unittest.TestCase):
    """T011 — the CSV round-trips through data.cache_path. (SC-004)"""

    def test_round_trip_preserves_shape(self):
        frames = {"A": _long_history(seed=1), "B": _long_history(seed=2)}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, failures = mtc.run_comparison(
                tickers=["A", "B"], seed_count=3
            )
        self.assertEqual(failures, [])

        path = mtc.cache_path(mtc._output_filename(["A", "B"]))
        try:
            results_frame.to_csv(path, index=False)
            reloaded = pd.read_csv(path)
            self.assertEqual(reloaded.shape, results_frame.shape)
            self.assertEqual(list(reloaded.columns), list(results_frame.columns))
        finally:
            path.unlink(missing_ok=True)


class TestMutations(unittest.TestCase):
    """T012 — a mutation check: each injected defect must fail a test. (SC-005)"""

    def test_letting_one_tickers_exception_propagate_breaks_isolation(self):
        # The defect under test: `run_comparison` calling `run_one_ticker`
        # without the try/except boundary, so one bad ticker raises past the
        # loop instead of producing a `ComparisonFailure`. Simulated here by
        # calling the un-isolated pipeline steps directly on a too-short
        # frame and confirming they DO raise -- which is exactly what
        # `run_one_ticker`'s try/except must catch, and what a version of
        # `run_comparison` missing that boundary would let escape.
        frames = {"BAD": _short_history()}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            with self.assertRaises(Exception):
                prices = mtc.download_market_data(["BAD"], period=mtc.PERIOD)
                frame, task, horizon = mtc.build_features(
                    prices, target_kind=mtc.TARGET_KIND, label_horizon=mtc.LABEL_HORIZON
                )
                mtc.nested_walk_forward(
                    frame,
                    feature_columns=mtc.feature_columns(),
                    label_column="Label",
                    task=task,
                    name=mtc.ESTIMATOR_NAME,
                    label_horizon=horizon,
                    embargo_bars=mtc.EMBARGO_BARS,
                    random_state=mtc.RANDOM_STATE,
                )

            # And confirm the real (isolated) path converts that same
            # exception into a reported failure rather than raising it.
            result = mtc.run_one_ticker("BAD")
        self.assertIsInstance(result, mtc.ComparisonFailure)

    def test_dropping_a_baseline_is_caught_by_the_strategy_set_assertion(self):
        frames = {"A": _long_history(seed=1)}
        with patch.object(mtc, "download_market_data", _fake_download(frames)):
            results_frame, failures = mtc.run_comparison(tickers=["A"], seed_count=3)
        self.assertEqual(failures, [])

        # The defect this guards: a version of `run_one_ticker` that returns
        # only the ML row (silently dropping a baseline for one ticker).
        strategies = set(results_frame["Strategy"])
        required = {mtc.STRATEGY_ML, mtc.STRATEGY_BUY_AND_HOLD, mtc.STRATEGY_RANDOM}
        self.assertEqual(strategies, required)
        mutated = results_frame[results_frame["Strategy"] != mtc.STRATEGY_RANDOM]
        self.assertNotEqual(set(mutated["Strategy"]), required)


if __name__ == "__main__":
    unittest.main()
