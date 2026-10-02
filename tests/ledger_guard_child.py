"""EXAMPLE \u2014 NOT A RESULT. Real entry points, offline copy-only inputs."""
import json
import ipaddress
import os
from pathlib import Path
import socket
import sys
import traceback
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
from ledger_copy_support import REAL_ROOT, ledger_counts
ORIGINAL_CONNECT = socket.socket.connect


def deny_network(*args, **kwargs):
    raise AssertionError("spec043: network forbidden")


def local_connect(sock, address):
    # Windows asyncio uses a loopback socket pair for its internal wakeup pipe.
    if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
        return ORIGINAL_CONNECT(sock, address)
    return deny_network()


def check_isolation():
    assert not ROOT.is_relative_to(REAL_ROOT.parent), ROOT
    assert "SPEC033_SYNTHETIC_ROOT" not in os.environ
    import trial_registry
    assert trial_registry.ROOT.resolve() == ROOT, trial_registry.ROOT
    socket.socket.connect = local_connect
    socket.create_connection = deny_network


def fake_features(prices, *, target_kind="return", **kwargs):
    """Model computation stub only; research_attempt remains real."""
    frame = prices.copy()
    task = "classification" if target_kind == "direction" else "regression"
    frame["Label"] = [i % 2 for i in range(len(frame))]
    return frame, task, 1


def fake_nested(frame, **kwargs):
    return frame["Label"].copy(), list(range(len(frame))), [{}]


def worker_init(*args):
    """Install offline model stubs in actual spawned E4 workers."""
    check_isolation()
    import feature_set_comparison as module
    module._worker_init(*args)
    module.build_features = fake_features
    module.nested_walk_forward = fake_nested


def fixture():
    import data
    from unadjusted_fixtures import publish_bundle, split_series
    prices, actions, _ = split_series()
    cache = ROOT / "data/cache"
    publish_bundle(cache / "unadjusted", "AAPL", prices, actions)
    frame = data.load_unadjusted_for_ticker("AAPL", cache / "unadjusted")
    frame.attrs["example_label"] = "EXAMPLE \u2014 NOT A RESULT"
    return cache, frame


def recompute_forbidden(*args, **kwargs):
    raise AssertionError("spec043 E5: GET recomputed instead of serving the recorded trial")


def tearsheet_requests(cache, outcome, recorded=(), decoys=()):
    """Two identical GETs; per request: status, byte deltas, N, body, trial ids named.

    `recorded` are the candidate trial ids the E1 recording appended; `decoys`
    are the candidate trial ids that already existed. Rule 11 provenance means a
    served tearsheet names the trial it came from, so the body is searched for both.
    """
    import hashlib
    from fastapi.testclient import TestClient
    from reports.api.main import create_app
    from reports.api.routes.data import get_cache_dir
    from trial_registry import TrialLedger
    app = create_app(dist_dir=None)
    app.dependency_overrides[get_cache_dir] = lambda: cache
    outcome["requests"] = []
    with TestClient(app, raise_server_exceptions=False) as client:
        for _ in range(2):
            before, n_before = ledger_counts(ROOT), TrialLedger().verify()["n_post_ledger"]
            response = client.get("/api/backtest/tearsheet")
            after, n_after = ledger_counts(ROOT), TrialLedger().verify()["n_post_ledger"]
            outcome["requests"].append(dict(status=response.status_code,
                records=after[0] - before[0], sidecars=after[1] - before[1],
                n_before=n_before, n_after=n_after,
                body_sha256=hashlib.sha256(response.content).hexdigest(),
                body=None if response.status_code == 200 else body_of(response),
                names_recorded=[i for i in recorded if i in response.text],
                names_decoys=[i for i in decoys if i in response.text]))


def body_of(response):
    try:
        return response.json()
    except ValueError:
        return response.text


def dispatch(entry, enabled, outcome):
    import pandas as pd
    from signals import buy_and_hold_signal
    cache, frame = fixture()

    def download(tickers, **kwargs):
        result = frame.copy()
        result["Ticker"] = tickers[0]
        return result

    sys.argv = [entry] + (["--record-trial"] if enabled else [])
    if entry == "E1":
        import ma_crossover_backtest as module
        module.main(cache_dir=cache / "unadjusted")
    elif entry == "E2":
        import logistic_baseline as module
        module.download_market_data = download
        module.build_features = lambda prices: prices.copy()
        module.evaluate_walk_forward = lambda prices: pd.DataFrame({"fixture": [True]})
        module.build_ml_signal = lambda prices: (buy_and_hold_signal(prices), 0)
        module.main()
    elif entry == "E3":
        import multi_ticker_comparison as module
        module.download_market_data = download
        module.build_features = fake_features
        module.nested_walk_forward = fake_nested
        # Satisfy the real CLI's cached-universe preflight with synthetic data.
        name = f"{'-'.join(sorted(set(module.TICKER_UNIVERSE)))}_{module.PERIOD}.csv"
        frame.to_csv(cache / name, index=False)
        sys.argv += ["--starting-capital", "10000", "--liquidate"]
        module.main()
        output = pd.read_csv(cache / module._output_filename(module.TICKER_UNIVERSE))
        assert len(output) == 3 * len(module.TICKER_UNIVERSE), "E3 incomplete pipeline"
    elif entry == "E4":
        import feature_set_comparison as module
        module.download_market_data = download
        module._worker_init = worker_init
        module.main(max_workers=2)
    elif entry == "E5":
        tearsheet_requests(cache, outcome)
    elif entry == "E5_recorded":
        # AC-10 green branch: record via the E1 CLI flag, then forbid recompute.
        import ma_crossover_backtest as module
        sys.argv = ["E1", "--record-trial"]
        from trial_registry import TrialLedger
        prior = len(TrialLedger().verify()["events"])
        module.main(cache_dir=cache / "unadjusted")
        events = TrialLedger().verify()["events"]
        recorded = [event["trial_id"] for event in events[prior:]
                    if event["event_type"] == "started" and event["role"] == "candidate"]
        outcome["recorded_candidates"] = recorded
        decoys = sorted({event["trial_id"] for event in events[:prior]
                         if event["role"] == "candidate"})
        import reports.api.routes.backtest as route
        for name in ("run_backtest", "research_attempt", "baseline_results"):
            setattr(route, name, recompute_forbidden)
        tearsheet_requests(cache, outcome, recorded, decoys)
    elif entry == "incident":
        import multi_ticker_comparison as module
        trades = pd.DataFrame({"Entry Date": [frame.Date.iloc[10]],
                               "Exit Date": [frame.Date.iloc[15]]})
        module._baseline_rows("AAPL", frame, trades, starting_capital=10000,
                              liquidate=True, commission_per_trade=1,
                              slippage_bps=5, seed_count=2)
    else:
        raise AssertionError(f"unknown entry {entry}")


def main():
    check_isolation()
    initial_records = ledger_counts(ROOT)[0]
    outcome = {}
    code = 0
    try:
        dispatch(sys.argv[1], "--record-trial" in sys.argv[2:], outcome)
        outcome["completed"] = True
    except BaseException as error:
        code = error.code if isinstance(error, SystemExit) else 1
        code = code if isinstance(code, int) else 1
        outcome["exception"] = type(error).__name__
        traceback.print_exc(file=sys.stderr)
    finally:
        from trial_registry import TrialLedger
        try:
            verification = TrialLedger().verify()
            outcome["verified"] = True
            outcome["n_post_ledger"] = verification["n_post_ledger"]
            appended = verification["events"][initial_records:]
            outcome["events"] = dict(Counter(event["event_type"] for event in appended))
            outcome["roles"] = dict(Counter(event["role"] for event in appended
                                            if event["event_type"] == "started"))
        except Exception as error:
            outcome["verification_error"] = str(error)
        (ROOT / "guard-outcome.json").write_text(json.dumps(outcome), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
