"""§11.3.5 replay inputs from the 058 T008 bodies. EXAMPLE — NOT A RESULT: synthetic bodies only."""
import hashlib
import json

import pandas as pd
import pytest
from context import SCRIPTS_DIR

import replay_inputs_058 as ri
from data import trading_days
from data_sources import RESEARCH_END
from signals import ALLOCATION_SLEEVES

DAYS = trading_days(pd.Timestamp("2023-09-01").date(), pd.Timestamp("2023-10-31").date())


def body(price):
    rows = [{"date": f"{d}T00:00:00.000Z", "open": price, "close": price, "adjOpen": price * 0.9 + i,
             "adjClose": price * 0.9 + i + 0.5} for i, d in enumerate(DAYS)]
    return json.dumps(rows).encode()


def panel(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    requests = []
    for i, ticker in enumerate(ALLOCATION_SLEEVES, 1):
        payload = body(10.0 * i)
        (raw / f"response-{i:02}.bin").write_bytes(payload)
        requests.append({"endpoint_path": f"/tiingo/daily/{ticker}/prices", "sha256": hashlib.sha256(payload).hexdigest()})
    return raw, {"requests": requests}


def test_csvs_are_the_hashed_bodies_adjusted_prices_through_research_end(tmp_path):
    raw, manifest = panel(tmp_path)
    provenance = ri.build(raw, tmp_path / "out", manifest=manifest)
    spy = pd.read_csv(tmp_path / "out" / "SPY.csv")
    assert list(spy.columns) == ["Date", "Open", "Close"], "REPLAY INPUTS columns replay_runner reads"
    assert spy["Date"].max() == str(RESEARCH_END), "REPLAY INPUTS holdout rows dropped"
    assert spy["Open"].iloc[0] == pytest.approx(9.0) and spy["Close"].iloc[0] == pytest.approx(9.5), "REPLAY INPUTS adjusted"
    entry = provenance["files"]["SPY"]
    assert entry["csv_sha256"] == hashlib.sha256((tmp_path / "out" / "SPY.csv").read_bytes()).hexdigest()
    assert set(provenance["files"]) == set(ALLOCATION_SLEEVES)


def test_an_altered_body_is_refused(tmp_path):
    raw, manifest = panel(tmp_path)
    (raw / "response-03.bin").write_bytes(b"[]")
    with pytest.raises(ValueError, match=ALLOCATION_SLEEVES[2]):
        ri.build(raw, tmp_path / "out", manifest=manifest)


def test_output_inside_the_repo_is_refused(tmp_path):
    raw, _ = panel(tmp_path)
    assert ri.main(["--panel", str(raw), "--out", str(SCRIPTS_DIR.parent / "data" / "cache" / "replay")]) == 2
