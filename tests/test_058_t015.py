"""Spec 058 T015 run command (queue Q133). EXAMPLE — NOT A RESULT: synthetic bodies and ledgers only."""
from dataclasses import replace
import hashlib
import json
import shutil

import numpy as np
import pandas as pd
import pytest
from context import SCRIPTS_DIR

import edge_walk_forward as wf
import run_058_t015 as t015
from cost_model import CostConfig, estimate_fill_cost
from data import trading_days
from data_sources import RESEARCH_END, canonical_hash, load_058_panel, PanelRefused
from trial_registry import DECLARED_FAMILIES, TrialLedger, declare_family, verify_family
from trial_runner import injected_ledger

ROOT = SCRIPTS_DIR.parent
DAYS = trading_days(pd.Timestamp("2021-06-01").date(), pd.Timestamp("2023-10-31").date())  # 2023-10 rows are sealed


def body(ticker, *, price=100.0, actions=None, wiggle=0.0):
    """Raw Tiingo-style rows: flat raw price, optional {session: (divCash, splitFactor)}."""
    rows, level = [], price
    for i, day in enumerate(DAYS):
        div, split = (actions or {}).get(str(day), (0.0, 1.0))
        level = level / split - div
        close = level * (1 + wiggle * np.sin(i))
        rows.append({"date": f"{day}T00:00:00.000Z", "open": close, "high": close * 1.01, "low": close * 0.99,
                     "close": close, "volume": 1e6, "divCash": div, "splitFactor": split,
                     "adjClose": None, "adjOpen": None})
    return json.dumps(rows).encode()


def write_panel(tmp_path, bodies, *, exclusions=None, mismatched=None):
    raw = tmp_path / "raw"
    raw.mkdir()
    hashes = {}
    for i, (ticker, payload) in enumerate(sorted(bodies.items()), 1):
        (raw / f"response-{i:02}.bin").write_bytes(payload)
        hashes[ticker] = hashlib.sha256(payload).hexdigest()
    manifest = {"requests": [{"endpoint_path": f"/tiingo/daily/{t}/prices", "sha256": h} for t, h in hashes.items()]}
    hash_input = {"alpaca_check_bodies": [], "d10": "fixture", "research_end": str(RESEARCH_END),
                  "exclusions": {t: list((exclusions or {}).get(t, [])) for t in hashes},
                  "tiingo_bodies": [[t, h] for t, h in sorted(hashes.items())]}
    check = {"status": "EXCLUSIONS", "panel_hash_input": hash_input, "panel_hash": canonical_hash(hash_input),
             "tickers": {t: {"actions": {"mismatched_sessions": list((mismatched or {}).get(t, []))}} for t in hashes}}
    return raw, manifest, check


def test_holdout_rows_never_reach_the_frames(tmp_path):
    raw, manifest, check = write_panel(tmp_path, {"SPY": body("SPY"), "IEF": body("IEF")})
    panel = load_058_panel(raw, tiingo_manifest=manifest, data_check=check)
    assert panel.closes.index.max() == pd.Timestamp(RESEARCH_END), "Q133 M4 TRUNCATION"
    assert all(h.index.max() <= pd.Timestamp(RESEARCH_END) for h in panel.cost_history.values())


def test_verified_dividend_gives_total_return(tmp_path):
    raw, manifest, check = write_panel(tmp_path, {"SPY": body("SPY", actions={"2022-03-18": (1.0, 1.0)})})
    panel = load_058_panel(raw, tiingo_manifest=manifest, data_check=check)
    close = panel.closes["SPY"]
    assert panel.raw_closes["SPY"].iloc[-1] == pytest.approx(99.0)
    assert np.allclose(close.to_numpy(), close.iloc[-1]), "Q133 M1 TOTAL RETURN: $1 dividend on $100 is no loss"


def test_action_mismatch_is_spliced_never_a_phantom_loss(tmp_path):
    ex = "2022-09-16"
    raw, manifest, check = write_panel(tmp_path, {"XLF": body("XLF", actions={ex: (5.0, 1.0)})},
                                       exclusions={"XLF": [ex]}, mismatched={"XLF": [ex]})
    panel = load_058_panel(raw, tiingo_manifest=manifest, data_check=check)
    marks = panel.closes["XLF"].ffill()
    assert np.isnan(panel.closes.at[pd.Timestamp(ex), "XLF"]), "excluded session is not tradable"
    assert float(np.log(marks / marks.shift(1)).abs().max()) < 1e-12, "Q133 SPLICE: unverified drop booked"


def test_split_fill_quantity_is_converted_to_nominal(tmp_path):
    raw, manifest, check = write_panel(tmp_path, {"QQQ": body("QQQ", price=200.0, actions={"2022-01-03": (0.0, 2.0)}, wiggle=0.01)})
    panel = load_058_panel(raw, tiingo_manifest=manifest, data_check=check)
    as_of = pd.Timestamp("2021-12-01")
    q_adj = 50.0
    nominal = q_adj * panel.closes.at[as_of, "QQQ"] / panel.raw_closes.at[as_of, "QQQ"]
    assert nominal == pytest.approx(25.0), "same dollars at the decision close"
    oracle = estimate_fill_cost(panel.cost_history["QQQ"], as_of=as_of, quantity=nominal, config=CostConfig(),
                                split_sessions=panel.split_sessions["QQQ"]).total
    unconverted = estimate_fill_cost(panel.cost_history["QQQ"], as_of=as_of, quantity=q_adj, config=CostConfig(),
                                     split_sessions=panel.split_sessions["QQQ"]).total
    assert oracle != pytest.approx(unconverted), "fixture must make quantity matter"
    assert t015.fill_cost(panel)("QQQ", as_of, q_adj) == pytest.approx(oracle), "Q133 M2 QUANTITY BASIS"
    assert panel.split_sessions["QQQ"] == (pd.Timestamp("2022-01-03"),)


@pytest.mark.parametrize("case", ["body", "hash", "status", "research_end"])
def test_loader_refuses_before_parsing(tmp_path, case):
    raw, manifest, check = write_panel(tmp_path, {"SPY": body("SPY")})
    if case == "body":
        (raw / "response-01.bin").write_bytes(b"[]")
    elif case == "hash":
        check["panel_hash"] = "0" * 64
    elif case == "status":
        check["status"] = "PARTIAL"
    else:
        check["panel_hash_input"]["research_end"] = "2023-10-31"
        check["panel_hash"] = canonical_hash(check["panel_hash_input"])
    with pytest.raises(PanelRefused):
        load_058_panel(raw, tiingo_manifest=manifest, data_check=check)


def test_recorded_risk_free_is_the_declared_gate3_rate():
    declared = verify_family(wf.FAMILY, root=ROOT)["declaration"]["gate3"]["risk_free"]
    assert wf.RISK_FREE == declared == {"annual_rate": 0.0378, "days_per_year": 252}, \
        "Q133 RISK FREE: build_matrix excludes every trial whose risk_free differs"


@pytest.fixture
def ledger(tmp_path):
    source = tmp_path / DECLARED_FAMILIES[wf.FAMILY]
    source.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / DECLARED_FAMILIES[wf.FAMILY], source)
    for extra in ("058-edge.amend-1.json",):
        shutil.copyfile(ROOT / "docs/trials/families" / extra, source.parent / extra)
    declare_family(wf.FAMILY, root=tmp_path, synthetic=True)
    log = TrialLedger(tmp_path, synthetic=True)
    with injected_ledger(log):
        yield log


def fake_panel(check):
    return type("P", (), {"panel_hash": check["panel_hash"]})()


def test_preflight_refusals_are_named(tmp_path, ledger):
    _, _, check = write_panel(tmp_path, {"SPY": body("SPY")})
    ok = t015.preflight(fake_panel(check), data_check=check, ledger=ledger, root=ROOT, clean=lambda r: True)
    assert ok["n_family_after"] == 15 and ok["cap"] >= 15
    cases = {"data_check_missing": (dict(check, status=None), lambda r: True),
             "panel_hash_mismatch": (dict(check, panel_hash="1" * 64), lambda r: True),
             "workspace_dirty": (check, lambda r: False)}
    for reason, (data, clean) in cases.items():
        with pytest.raises(t015.PreflightRefused) as info:
            t015.preflight(fake_panel(check), data_check=data, ledger=ledger, root=ROOT, clean=clean)
        assert info.value.reason == reason, f"Q133 M3 PREFLIGHT {reason}"


def test_a_second_run_needs_an_explicit_rerun_reason(tmp_path, ledger):
    rng = np.random.default_rng(3)
    index = pd.bdate_range("2019-01-02", str(RESEARCH_END))
    closes = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(index), 2)), axis=0)), index=index,
                          columns=["SPY", "IEF"])
    wf.run_configuration("H4", closes, closes, fill_cost=lambda *a: 5e-4,
                         costs={"commission": 0.0, "slippage": {"model": wf.COST_MODEL}}, data={"sha256": "d" * 64})
    _, _, check = write_panel(tmp_path, {"SPY": body("SPY")})
    with pytest.raises(t015.PreflightRefused) as info:
        t015.preflight(fake_panel(check), data_check=check, ledger=ledger, root=ROOT, clean=lambda r: True)
    assert info.value.reason == "family_already_run", "Q133 M5 RERUN"
    again = t015.preflight(fake_panel(check), data_check=check, ledger=ledger, root=ROOT, rerun="fixture",
                           clean=lambda r: True)
    assert again["prior_candidates"] == 1 and again["n_family_after"] == 16


def test_run_order_is_declared_candidates_then_bbh_then_brnd(monkeypatch):
    calls = []
    monkeypatch.setattr(wf, "run_configuration", lambda c, *a, **k: calls.append(("cfg", c)) or {"id": c})
    monkeypatch.setattr(wf, "run_brnd", lambda c, s, *a, **k: calls.append(("brnd", c, s)) or {"id": (c, s)})
    panel = type("P", (), {"opens": None, "closes": None, "panel_hash": "e" * 64})()
    receipts = t015.run_family(panel, data_check_name="fixture.json", progress=lambda *_: None)
    assert [c[1] for c in calls[:16]] == [*t015.RUN_ORDER, "B-BH"], "Q133 M6 ORDER"
    assert calls[16:] == [("brnd", c, s) for c in t015.RUN_ORDER for s in wf.BRND_SEEDS]
    declared = [c["id"] for c in verify_family(wf.FAMILY, root=ROOT)["declaration"]["configurations"]]
    assert len(receipts) == 316 and list(t015.RUN_ORDER) == declared and set(declared) == set(wf.CANDIDATES)


def test_first_error_stops_the_run(monkeypatch):
    calls = []

    def boom(c, *a, **k):
        calls.append(c)
        if c == "H2-100":
            raise RuntimeError("fixture")
        return {}
    monkeypatch.setattr(wf, "run_configuration", boom)
    panel = type("P", (), {"opens": None, "closes": None, "panel_hash": "e" * 64})()
    with pytest.raises(RuntimeError):
        t015.run_family(panel, data_check_name="fixture.json", progress=lambda *_: None)
    assert calls == ["H1-3", "H1-6", "H1-12", "H2-100"], "Q133 STOP: no skipping ahead"
