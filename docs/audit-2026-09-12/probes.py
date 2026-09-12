"""Read-only, offline reproductions for the September 2026 project audit.

Writes only audit evidence beside this script. Does not download data or trade.
"""
from pathlib import Path
import json
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from scipy.stats import binomtest
import data
import features
import feature_diagnostics as fd
import feature_set_comparison as fc
import metrics
import multi_ticker_comparison as mt
import model_cv
from sklearn.ensemble import HistGradientBoostingClassifier
from walk_forward_cv import walk_forward_splits
import portfolio_risk as risk
from backtest_harness import run_backtest, summarize_trades
from targets import direction_label
from reports.api.main import app
from reports.api.routes import data as api_data


def main():
    out = {}
    duplicate = pd.DataFrame({"a": [1., 2., 3., 4.], "b": [1., 2., 3., 4.]})
    out["duplicate_column_vif"] = fd.variance_inflation_factors(duplicate, ["a", "b"]).to_dict()
    try:
        fd.variance_inflation_factors(duplicate.assign(b=1.), ["a", "b"])
    except Exception as exc:
        out["constant_column_vif_error"] = type(exc).__name__ + ": " + str(exc)

    p = pd.DataFrame({"Date": pd.bdate_range("2024-01-02", periods=3),
                      "Open": [100., 200., 200.], "Close": [100., 200., 200.],
                      "Buy_Next_Open": [False, True, False],
                      "Sell_Next_Open": [False, False, True]})
    log = run_backtest(p, commission_per_trade=1., slippage_bps=5.)
    curve = metrics.equity_curve(p, log, commission_per_trade=1., slippage_bps=5.)
    out["unfunded_entry"] = {"capital": curve.attrs["capital_base"],
                              "entry_fill_plus_commission": float(log.iloc[0]["Entry Price"] + 1)}
    nan_log = run_backtest(p.assign(Open=[100., np.nan, 200.]), commission_per_trade=1., slippage_bps=5.)
    out["nan_fill_summary"] = summarize_trades(nan_log, commission_per_trade=1., slippage_bps=5.)
    out["nan_trade_pnl"] = bool(nan_log["P&L"].isna().all())
    out["direction_missing_current"] = str(direction_label(pd.DataFrame({"Close": [np.nan, 101., 102.]}), horizon=1).iloc[0])
    first = p.assign(Open=100., Close=100., Buy_Next_Open=[True, False, False], Sell_Next_Open=[False, False, True])
    first_log = run_backtest(first, commission_per_trade=5., slippage_bps=0.)
    first_curve = metrics.equity_curve(first, first_log, commission_per_trade=5., slippage_bps=0., starting_capital=100.)
    out["first_bar_loss_drawdown"] = {"equity": first_curve["Equity"].tolist(), "reported": metrics.max_drawdown(first_curve["Equity"])[0], "correct_with_initial_capital": -.1}
    hx = pd.DataFrame({"x": np.arange(30.)})
    hm = HistGradientBoostingClassifier(random_state=0).fit(hx, np.ones(30))
    out["hgb_single_positive_class"] = {"classes": hm.classes_.tolist(), "reported_positive_probability": model_cv._predict_for_scoring(hm, hx.iloc[:1], task="classification").tolist(), "expected": [1.]}

    weights = pd.Series({"A": .25, "B": 1e-12})
    corr = pd.DataFrame([[1., 1.], [1., 1.]], index=weights.index, columns=weights.index)
    out["tiny_correlated_position"] = {"before": weights.to_dict(), "after": risk.correlation_adjusted_weights(weights, corr).to_dict()}
    g1 = risk.LossCapGuard.from_config(risk.RECOMMENDED_CONFIG)
    g1.observe(pd.Timestamp("2024-01-08"), 100.)
    old = g1.observe(pd.Timestamp("2024-01-09"), 94.)
    g2 = risk.LossCapGuard.from_config(risk.RECOMMENDED_CONFIG)
    new = g2.observe(pd.Timestamp("2024-01-10"), 94.)
    out["restart_resets_loss_latch"] = {"before": old.entries_halted, "after": new.entries_halted}

    labels = pd.Series([1, 1, 1, 1])
    result = fc.compare_classification(labels, pd.Series([1, 1, 1, 0]), pd.Series([1, 0, 0, 0]))
    out["mcnemar_unfavoured_tail"] = {"reported": result["p_one_sided"], "correct_binomial": binomtest(0, 2, .5, alternative="greater").pvalue}

    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
        empty_cache = Path(temp)
        with patch.object(data, "CACHE_DIR", empty_cache):
            invalid = pd.concat({"BAD": pd.DataFrame({c: [np.nan] for c in data.OHLCV_COLUMNS}, index=pd.DatetimeIndex(["2024-01-02"], name="Date"))}, axis=1)
            accepted = data.download_market_data(["BAD"], downloader=lambda *a, **k: invalid)
            out["all_nan_ticker_accepted"] = len(accepted)
            escaped = data.cache_path("../outside.csv").resolve()
            out["cache_path_escapes_directory"] = not escaped.is_relative_to(empty_cache)
        with patch.object(api_data, "CACHE_DIR", empty_cache):
            empty_cache = empty_cache / "truly-empty"
            empty_cache.mkdir()
            api_data.CACHE_DIR = empty_cache
            empty_client = TestClient(app, raise_server_exceptions=False)
            out["empty_cache_tickers"] = empty_client.get("/api/data/tickers").json()
            out["empty_cache_ohlcv_status"] = empty_client.get("/api/data/ohlcv?ticker=AAPL").status_code

    combined = ROOT / "data/cache/AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv"
    raw = pd.read_csv(combined, parse_dates=["Date"])
    aapl = raw[raw.Ticker == "AAPL"].reset_index(drop=True)
    label_frame, _, _ = features.build_features(aapl, target_kind="direction", label_horizon=1, feature_set="scale_free")
    test_indices = np.concatenate([te for _, te in walk_forward_splits(label_frame, label_horizon=1, embargo_bars=1)])
    baseline = {"n": len(test_indices), "positive_label_fraction": float(label_frame.iloc[test_indices].Label.mean()), "interpretation": "Always-up descriptive direction baseline on default CV test rows; no deployable price-return claim"}
    out["always_up_baseline"] = baseline
    Path(__file__).with_name("direction-baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    price_cols = ["Open", "High", "Low", "Close"]
    out["cache_quality"] = {"rows": len(raw), "duplicates": int(raw.duplicated(["Ticker", "Date"]).sum()),
                            "nulls": raw.isna().sum().to_dict(), "nonpositive_prices": int((raw[price_cols] <= 0).any(axis=1).sum()),
                            "nonfinite_prices": int((~np.isfinite(raw[price_cols])).any(axis=1).sum()),
                            "ohlc_violations": int(((raw.High < raw[price_cols].max(axis=1)) | (raw.Low > raw[price_cols].min(axis=1))).sum()),
                            "dates": {k: [str(v.Date.min().date()), str(v.Date.max().date()), len(v)] for k, v in raw.groupby("Ticker")},
                            "missing_sessions": len(data.find_missing_bars(raw))}
    out["combined_vs_requested_cache"] = {"combined_exists": combined.exists(), "requested": {t: (ROOT / "data/cache" / data._cache_key([t], "10y")).exists() for t in mt.TICKER_UNIVERSE}}
    with patch.object(data.yf, "download", side_effect=AssertionError("No network allowed")):
        client = TestClient(app, raise_server_exceptions=False)
        out["invalid_backtest_requests"] = {query: client.get("/api/backtest/tearsheet?ticker=AAPL&" + query).status_code for query in ["short_window=30&long_window=10", "commission=-1", "commission=nan", "slippage_bps=10000", "short_window=0"]}
        out["cors_untrusted_origin"] = dict(client.get("/api/health", headers={"Origin": "https://audit-untrusted.example"}).headers)
        out["significance_aapl"] = client.get("/api/diagnostics/significance?ticker=AAPL").json()
        out["significance_nvda"] = client.get("/api/diagnostics/significance?ticker=NVDA").json()
        out["capital_gate"] = client.get("/api/capital_gate/status").json()
        ml = client.get("/api/ml/rundown?ticker=AAPL").json()
        out["ml_rundown"] = {"as_of": ml["as_of_date"], "forecast": ml["insights"][0]["technical_reading"]}
        ts = client.get("/api/backtest/tearsheet?ticker=AAPL").json()
        bars = raw[raw.Ticker == "AAPL"].reset_index(drop=True)
        positions = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(bars.Date)}
        out["holding_bars"] = [{"reported": t["holding_bars"], "actual": positions[t["exit_date"]] - positions[t["entry_date"]]} for t in ts["trade_log"][:5]]
        out["cached_sma_tearsheet"] = {k: ts[k] for k in ["capital_base", "total_pnl", "total_return", "sharpe_ratio", "max_drawdown", "comparison_table"]}
    out["actual_screening_artifact"] = json.loads((ROOT / "data/cache/feature_set_comparison.json").read_text())
    dest = Path(__file__).with_name("probe-results.json")
    dest.write_text(json.dumps(out, indent=2, default=str, allow_nan=True), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str, allow_nan=True))


if __name__ == "__main__":
    main()
