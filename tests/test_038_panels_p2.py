"""Spec 038 T031 (queue Q48): P2 terminal panels print the stamp and register reference before any figure.

Captured stdout is what a reader sees. Saved plots are recorded as a `PLOT` marker in the same
stream, so "before any figure" covers plots too. Synthetic prices only (EXAMPLE — NOT A RESULT);
no network, no `data/cache/` access.
"""

import socket
from datetime import datetime, timezone
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

import context  # noqa: F401 -- existing repository import bootstrap
import autocorrelation_check
import disclosure
import stationarity_check
from mutation_support_019 import killed

CLOCK = lambda: datetime(2026, 10, 12, 0, 30, tzinfo=timezone.utc)  # noqa: E731
LAST = pd.Timestamp("2026-10-09")


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def deny_network(*args, **kwargs):
        pytest.fail("Spec 038 tests must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def prices(ticker, n=300, seed=0):
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.DataFrame({"Ticker": ticker, "Date": pd.bdate_range(end=LAST, periods=n), "Close": closes})


def run(module, monkeypatch, capsys, tmp_path):
    source = tmp_path / "data" / "cache" / "SYNTHETIC_2y.csv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("Date,Ticker,Close\n2026-10-09,SYNTHETIC,104\n")
    monkeypatch.setattr(module, "TICKERS", ["SYNTHETIC"])
    monkeypatch.setattr(module, "download_market_data", Mock(return_value=prices("SYNTHETIC")))
    monkeypatch.setattr(module, "cache_path", lambda name: tmp_path / "data" / "cache" / name)
    monkeypatch.setattr(module, "save_acf_plot", Mock(side_effect=lambda *a: print("PLOT")))
    module.main(clock=CLOCK, root=tmp_path)
    return capsys.readouterr().out.splitlines(), source


MODULES = [(autocorrelation_check, "Ticker"), (stationarity_check, "SYNTHETIC log-return ACF (lags 1-5):")]
IDS = ["autocorrelation_check", "stationarity_check"]


@pytest.mark.parametrize("module, first_figure", MODULES, ids=IDS)
def test_stamp_and_register_reference_precede_every_figure_and_plot(monkeypatch, capsys, tmp_path, module,
                                                                    first_figure):
    lines, source = run(module, monkeypatch, capsys, tmp_path)
    stamp = disclosure.provenance_stamp(source, root=tmp_path, clock=CLOCK, data_end=LAST)
    assert lines[:len(stamp)] == stamp, "T031 STAMP"
    assert lines[len(stamp)] == module.LIMITATIONS_REFERENCE, "T031 REGISTER"
    figure = next(i for i, line in enumerate(lines) if line.strip().startswith(first_figure))
    assert min(lines.index("PLOT"), figure) > len(stamp), "T031 ORDER"
    assert f"source: data/cache/{source.name} sha256=" in stamp[0] and "data through (last session): 2026-10-09" in stamp


@pytest.mark.parametrize("module", [autocorrelation_check, stationarity_check], ids=IDS)
def test_register_reference_is_the_shared_one_and_the_period_is_stamped(monkeypatch, capsys, tmp_path, module):
    assert "docs/SCOPE-V1.md §6" in module.LIMITATIONS_REFERENCE
    assert module.LIMITATIONS_REFERENCE.startswith("Limitations (Rule 16):")
    run(module, monkeypatch, capsys, tmp_path)
    assert module.download_market_data.call_args.kwargs["period"] == module.PERIOD == "2y"


# --- Rule 12: a figure before the stamp (spec 038 T031's mutant) and a dropped register line ---

@pytest.mark.parametrize("module, old, new", [
    (autocorrelation_check, "    market_data = download_market_data(TICKERS, period=PERIOD)\n",
     "    market_data = download_market_data(TICKERS, period=PERIOD)\n    save_acf_plot(None, 'early')\n"),
    (stationarity_check, "    market_data = download_market_data(TICKERS, period=PERIOD)\n",
     "    market_data = download_market_data(TICKERS, period=PERIOD)\n    print('SYNTHETIC log-return ACF (lags 1-5):')\n"),
    (stationarity_check, "    print(LIMITATIONS_REFERENCE)\n", "    pass\n"),
], ids=["autocorrelation-plot-first", "stationarity-figure-first", "stationarity-register-dropped"])
def test_planted_defects_are_killed(monkeypatch, capsys, tmp_path, module, old, new):
    figure = dict(MODULES)[module]

    def oracle():
        capsys.readouterr()
        test_stamp_and_register_reference_precede_every_figure_and_plot(monkeypatch, capsys, tmp_path, module, figure)
    killed(module, old, new, oracle)
