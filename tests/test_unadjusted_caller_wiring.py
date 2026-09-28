"""Spec 036 funded-price caller contracts, using only synthetic bundles."""

import ast
from datetime import date
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import data
import ma_crossover_backtest as crossover
from backtest_harness import run_backtest as real_run_backtest
from signals import sma_crossover_signal
from trial_registry import TrialLedger
from trial_runner import injected_ledger
from unadjusted_fixtures import publish_bundle, session_prices, split_series


def test_resolver_missing_directory_and_empty_directory(tmp_path):
    for root in (tmp_path / "absent", tmp_path):
        with pytest.raises(data.UnadjustedDataUnavailable) as raised:
            data.resolve_unadjusted_manifest("AAPL", root)
        assert raised.value.reason == "missing"
        assert str(root) in raised.value.check


def test_resolver_ambiguous_lists_both_paths_sorted(tmp_path):
    first = session_prices("AAPL", date(2024, 1, 2), date(2024, 1, 5), [100.] * 4)
    second = session_prices("AAPL", date(2024, 1, 8), date(2024, 1, 12), [100.] * 5)
    paths = [publish_bundle(tmp_path, "AAPL", prices) for prices in (first, second)]
    with pytest.raises(data.UnadjustedDataUnavailable) as raised:
        data.resolve_unadjusted_manifest("AAPL", tmp_path)
    assert raised.value.reason == "ambiguous"
    assert raised.value.check == ", ".join(str(path) for path in sorted(paths))


def test_resolver_exact_stem_and_lowercase(tmp_path):
    prices = session_prices("A", date(2024, 1, 2), date(2024, 1, 5), [100.] * 4)
    a_path = publish_bundle(tmp_path, "A", prices)
    publish_bundle(tmp_path, "AA", prices)
    assert data.resolve_unadjusted_manifest("A", tmp_path) == a_path
    prices["Ticker"] = "AAPL"
    aapl_path = publish_bundle(tmp_path, "AAPL", prices)
    assert data.resolve_unadjusted_manifest("aapl", tmp_path) == aapl_path


def test_resolver_rejects_invalid_ticker_before_filesystem_access(tmp_path):
    with patch.object(Path, "iterdir", side_effect=AssertionError("filesystem accessed")):
        with pytest.raises(data.UnadjustedDataUnavailable) as raised:
            data.resolve_unadjusted_manifest("../x", tmp_path / "absent")
    assert raised.value.reason == "invalid"
    assert raised.value.ticker == "../x"


def test_loader_rejects_tampered_data_hash(tmp_path):
    prices, actions, _ = split_series()
    manifest = publish_bundle(tmp_path, "AAPL", prices, actions)
    data_file = manifest.with_name(manifest.name.replace(".manifest.json", ".ohlcv.csv"))
    payload = data_file.read_bytes()
    data_file.write_bytes(payload.replace(b"100.0", b"101.0", 1))
    with pytest.raises(data.UnadjustedDataUnavailable) as raised:
        data.load_unadjusted_for_ticker("AAPL", tmp_path)
    assert raised.value.reason == "invalid"
    assert "data file hash check failed" in raised.value.check


def test_loader_returns_verified_dollars_and_manifest_provenance(tmp_path):
    prices, actions, _ = split_series()
    publish_bundle(tmp_path, "AAPL", prices, actions)
    loaded = data.load_unadjusted_for_ticker("AAPL", tmp_path)
    assert loaded.attrs["price_basis"] == "unadjusted_dollars"
    assert loaded.attrs["source_manifest_sha256"]


def test_unavailable_is_a_lookup_error_not_a_value_error(tmp_path):
    with pytest.raises(data.UnadjustedDataUnavailable) as raised:
        data.resolve_unadjusted_manifest("AAPL", tmp_path)
    assert isinstance(raised.value, LookupError)
    assert not isinstance(raised.value, ValueError)


def test_signal_uses_causal_research_close_across_split(tmp_path):
    prices, actions, split_at = split_series()
    publish_bundle(tmp_path, "AAPL", prices, actions)
    nominal = data.load_unadjusted_for_ticker("AAPL", tmp_path)
    control = sma_crossover_signal(nominal, 10, 30)
    assert bool(control.loc[split_at + 1, "Sell_Next_Open"])
    signalled = crossover.research_close_signal(nominal, 10, 30)
    assert not bool(signalled.loc[split_at + 1, "Sell_Next_Open"])
    assert signalled["Close"].equals(nominal["Close"])
    assert signalled["Open"].equals(nominal["Open"])
    assert signalled.attrs["price_basis"] == "unadjusted_dollars"


def test_cli_unavailable_has_no_download_output_or_trial(tmp_path):
    ledger = TrialLedger(tmp_path / "ledger", synthetic=True)
    ledger.path.parent.mkdir(parents=True)
    ledger.path.write_bytes(b"")
    before = ledger.path.read_bytes()
    with injected_ledger(ledger), patch.object(data, "download_market_data", side_effect=AssertionError("download")) as download, patch.object(crossover, "cache_path") as output:
        with pytest.raises(data.UnadjustedDataUnavailable) as raised:
            crossover.main([], cache_dir=tmp_path / "empty")
    assert raised.value.reason == "missing"
    assert "AAPL" in str(raised.value) and "unavailable" in str(raised.value)
    download.assert_not_called()
    output.assert_not_called()
    assert ledger.path.read_bytes() == before


def test_cli_process_prints_named_error_and_exits_one(tmp_path):
    script = SCRIPTS / "ma_crossover_backtest.py"
    process = subprocess.run(
        [sys.executable, str(script), "--manifest", str(tmp_path / "absent.manifest.json")],
        cwd=script.parents[1], capture_output=True, text=True, check=False,
    )
    assert process.returncode == 1
    assert "AAPL: unadjusted price data unavailable (invalid)" in process.stderr
    assert process.stdout == ""


def test_cli_success_uses_verified_bundle_for_every_funded_row(tmp_path, capsys):
    prices, actions, _ = split_series()
    first = publish_bundle(tmp_path, "AAPL", prices, actions)
    other = session_prices("AAPL", date(2024, 5, 1), date(2024, 5, 8), [100.] * 6)
    publish_bundle(tmp_path, "AAPL", other)
    with patch.object(crossover, "cache_path", side_effect=lambda name: tmp_path / name), patch.object(
        crossover, "run_backtest", wraps=real_run_backtest
    ) as funded:
        crossover.main(["--manifest", str(first)], cache_dir=tmp_path)
    assert funded.call_count >= 2
    hashes = {call.args[0].attrs["source_manifest_sha256"] for call in funded.call_args_list}
    assert len(hashes) == 1
    assert all(call.args[0].attrs["price_basis"] == "unadjusted_dollars" for call in funded.call_args_list)
    report = capsys.readouterr().out
    assert "synthetic-test-source" in report
    assert "capital_gate_eligible" in report
    assert "Synthetic fixture; not market evidence." in report


def test_cli_source_contains_no_legacy_download_reference():
    source = (SCRIPTS / "ma_crossover_backtest.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.Name) and node.id == "download_market_data" for node in ast.walk(tree))
    assert not any(
        isinstance(node, ast.ImportFrom) and any(alias.name == "download_market_data" for alias in node.names)
        for node in ast.walk(tree)
    )
