"""Spec 038 T030 (queue Q47): P1 terminal panels carry a stamp, a register reference and the Sharpe flag.

Captured stdout is what a reader sees, so every contract reads it. Synthetic
prices only (EXAMPLE — NOT A RESULT); no network, no `data/cache/` access.
"""

import re
import socket
from datetime import datetime, timezone
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import disclosure
import feature_diagnostics
import return_stats
from mutation_support_019 import killed

CLOCK = lambda: datetime(2026, 10, 12, 0, 30, tzinfo=timezone.utc)  # just after midnight UTC
BEFORE_MIDNIGHT = lambda: datetime(2026, 10, 11, 23, 30, tzinfo=timezone.utc)
LAST = pd.Timestamp("2026-10-09")
# Spec 038 FR-008's Sharpe pattern: case-insensitive, a number on either side of the word,
# within the same sentence (e.g. "0.17 Sharpe" and "Sharpe ratio = 0.5").
SHARPE_LINE = re.compile(r"\d[^!?;\n]*?\bsharpe\b|\bsharpe\b[^!?;\n]*?\d", re.IGNORECASE)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def deny_network(*args, **kwargs):
        pytest.fail("Spec 038 tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def prices(ticker, n=7, seed=0):
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.DataFrame({"Ticker": ticker, "Date": pd.bdate_range(end=LAST, periods=n),
                         "Open": closes * (1 + rng.normal(0, 0.002, n)), "High": closes * 1.01,
                         "Low": closes * 0.99, "Close": closes,
                         "Volume": rng.integers(500_000, 2_000_000, n).astype(float)})


def cache_file(tmp_path, name):
    path = tmp_path / "data" / "cache" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Date,Ticker,Close\n2026-10-09,SYNTHETIC,104\n")
    return path


def run_return_stats(monkeypatch, capsys, tmp_path, clock=CLOCK):
    source = cache_file(tmp_path, "SYNTHETIC_2y.csv")
    monkeypatch.setattr(return_stats, "TICKERS", ["SYNTHETIC"])
    monkeypatch.setattr(return_stats, "download_market_data", Mock(return_value=prices("SYNTHETIC")))
    monkeypatch.setattr(return_stats.plt, "subplots", Mock(return_value=(Mock(), [[Mock()]])))
    monkeypatch.setattr(return_stats, "save_figure", Mock())
    monkeypatch.setattr(return_stats, "cache_path", lambda name: tmp_path / "data" / "cache" / name)
    return_stats.main(clock=clock, root=tmp_path)
    return capsys.readouterr().out.splitlines(), source


def run_feature_diagnostics(monkeypatch, capsys, tmp_path, clock=CLOCK):
    name = "AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv"
    source = cache_file(tmp_path, name)
    monkeypatch.setattr(feature_diagnostics, "download_market_data",
                        Mock(return_value=prices("AAPL", n=300)))
    monkeypatch.setattr(feature_diagnostics, "cache_path",
                        lambda key: tmp_path / "data" / "cache" / key)
    feature_diagnostics.main(clock=clock, root=tmp_path)
    return capsys.readouterr().out.splitlines(), source


def expected_stamp(source, tmp_path, clock):
    return disclosure.provenance_stamp(source, root=tmp_path, clock=clock, data_end=LAST)


@pytest.mark.parametrize("clock, run_line", [
    (CLOCK, "run (UTC): 2026-10-12 00:30:00Z"), (BEFORE_MIDNIGHT, "run (UTC): 2026-10-11 23:30:00Z"),
], ids=["after-midnight", "before-midnight"])
@pytest.mark.parametrize("runner, first_figure", [
    (run_return_stats, "Daily log-return summary:"),
    (run_feature_diagnostics, "AAPL feature diagnostics over 10y"),
], ids=["return_stats", "feature_diagnostics"])
def test_stamp_and_register_reference_precede_the_first_figure(monkeypatch, capsys, tmp_path,
                                                              runner, first_figure, clock, run_line):
    lines, source = runner(monkeypatch, capsys, tmp_path, clock)
    stamp = expected_stamp(source, tmp_path, clock)
    assert lines[:len(stamp)] == stamp
    assert lines[len(stamp)] == return_stats.LIMITATIONS_REFERENCE
    assert lines.index(first_figure) > len(stamp)
    assert f"source: data/cache/{source.name} sha256=" in stamp[0]
    assert "trial: none (descriptive, not a trial)" in stamp
    assert run_line in stamp
    assert "data through (last session): 2026-10-09" in stamp  # run date and last bar both shown


def test_register_reference_names_the_register_and_its_size():
    ref = return_stats.LIMITATIONS_REFERENCE
    assert "docs/SCOPE-V1.md §6" in ref and f"{len(disclosure.LIMITATIONS)} " in ref
    assert feature_diagnostics.LIMITATIONS_REFERENCE == ref


def test_sharpe_pattern_is_fr008():
    for line in ("0.17 Sharpe", "Sharpe ratio = 0.5", "Sharpe ratio (risk-free rate: 3.78%):"):
        assert SHARPE_LINE.search(line), line
    assert not SHARPE_LINE.search("Annualized return and Sharpe ratio:")


def test_every_sharpe_line_carries_the_rule_15_flag(monkeypatch, capsys, tmp_path):
    lines, _ = run_return_stats(monkeypatch, capsys, tmp_path)
    sharpe = [line for line in lines if SHARPE_LINE.search(line)]
    assert sharpe, "control: at least one printed Sharpe line"
    for line in sharpe:
        assert disclosure.SHARPE_STATUS in line, line
        assert "not evidence of skill" in line, line


def test_stamp_uses_the_actual_cache_key(monkeypatch, capsys, tmp_path):
    """The stamped file is the one download_market_data reads for this ticker set and period."""
    seen = []
    monkeypatch.setattr(return_stats, "_cache_key", lambda tickers, period: seen.append(
        (tuple(tickers), period)) or "SYNTHETIC_2y.csv")
    run_return_stats(monkeypatch, capsys, tmp_path)
    assert seen == [(("SYNTHETIC",), return_stats.PERIOD)]
    assert return_stats.download_market_data.call_args.kwargs["period"] == return_stats.PERIOD


# --- Rule 12: M4 (spec 038 §6) and a dropped register reference ---

@pytest.mark.parametrize("module, old, new", [
    # M4: return_stats prints the Sharpe without the Rule 15 flag.
    (return_stats, "Sharpe ratio = {sharpe_ratio:.6f} [{SHARPE_STATUS}; ",
     "Sharpe ratio = {sharpe_ratio:.6f} ["),
    # The feature-diagnostics panel drops its register reference.
    (feature_diagnostics, "    print(LIMITATIONS_REFERENCE)\n", "    pass\n"),
], ids=["M4-sharpe-flag", "register-reference"])
def test_planted_defects_are_killed(monkeypatch, capsys, tmp_path, module, old, new):
    def oracle():
        capsys.readouterr()
        if module is return_stats:
            test_every_sharpe_line_carries_the_rule_15_flag(monkeypatch, capsys, tmp_path)
        else:
            lines, _ = run_feature_diagnostics(monkeypatch, capsys, tmp_path)
            assert feature_diagnostics.LIMITATIONS_REFERENCE in lines
    killed(module, old, new, oracle)
