"""Spec 059 T004 run command (D-11). EXAMPLE — NOT A RESULT: synthetic bodies and ledgers only."""
import json
import shutil

import numpy as np
import pandas as pd
import pytest
from context import SCRIPTS_DIR

import allocation_report as ar
import run_059_t004 as t004
from cost_model import CostConfig
from data_sources import load_058_panel
from signals import ALLOCATION_SLEEVES
from test_058_t015 import body, write_panel
from trial_registry import DECLARED_FAMILIES, TrialLedger, declare_family, verify_family
from trial_runner import injected_ledger

ROOT = SCRIPTS_DIR.parent
SEEDS = [11, 12]


def sleeve_panel(tmp_path):
    bodies = {t: body(t, price=50.0 + 10 * i, wiggle=0.004 * (i + 1)) for i, t in enumerate(ALLOCATION_SLEEVES)}
    raw, manifest, check = write_panel(tmp_path, bodies)
    return load_058_panel(raw, tiingo_manifest=manifest, data_check=check), check


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """A synthetic root whose 059 declaration already carries the D-11 additions."""
    root = tmp_path / "root"
    source = root / DECLARED_FAMILIES[t004.FAMILY]
    source.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / DECLARED_FAMILIES[t004.FAMILY], source)
    declare_family(t004.FAMILY, root=root, synthetic=True)
    log = TrialLedger(root, synthetic=True)
    monkeypatch.setattr(t004, "verify_family", lambda family: verify_family(family, root=root))
    with injected_ledger(log):
        yield log


def test_committed_source_carries_d11_and_preregistered_seeds():
    declaration = json.loads((ROOT / DECLARED_FAMILIES[t004.FAMILY]).read_text(encoding="utf-8"))
    assert declaration["random_seeds"] == list(range(20261015, 20261035)), "T004 SEEDS preregistered"
    data = declaration["research_data"]
    assert data["panel_hash"].startswith("3b80b330") and data["commission_per_fill"] == 0.0, "T004 D-11 PANEL"


def test_preflight_refusals_are_named(tmp_path, ledger):
    panel, check = sleeve_panel(tmp_path)
    declaration = dict(t004.declared(), research_data={"panel_hash": panel.panel_hash})
    ok = t004.preflight(panel, data_check=check, ledger=ledger, declaration=declaration, clean=lambda r: True)
    assert ok["n_family_after"] == 1 and ok["cap"] == 2 and len(ok["seeds"]) == 20
    cases = {"data_check_missing": dict(data=dict(check, status=None)),
             "panel_hash_mismatch": dict(data=dict(check, panel_hash="1" * 64)),
             "panel_not_declared": dict(declaration=dict(declaration, research_data={"panel_hash": "2" * 64})),
             "workspace_dirty": dict(clean=lambda r: False),
             "seeds_invalid": dict(declaration=dict(declaration, random_seeds=[5]))}
    for reason, change in cases.items():
        with pytest.raises(t004.PreflightRefused) as caught:
            t004.preflight(panel, data_check=change.get("data", check), ledger=ledger,
                           declaration=change.get("declaration", declaration), clean=change.get("clean", lambda r: True))
        assert caught.value.reason == reason, f"T004 PREFLIGHT {reason}"


def test_unfrozen_d11_refuses(tmp_path, ledger, monkeypatch):
    monkeypatch.setattr(t004, "verify_family", lambda family: {"declaration": {"n_family_cap": 2}})
    with pytest.raises(t004.PreflightRefused) as caught:
        t004.declared()
    assert caught.value.reason == "d11_not_frozen", "T004 D-11 must be frozen before any 059 trial"


def test_every_series_is_started_before_any_is_evaluated_and_recorded_once(tmp_path, ledger):
    panel, check = sleeve_panel(tmp_path)
    report, receipts = t004.run_report(panel, seeds=SEEDS, data={"sha256": panel.panel_hash})
    events = ledger.verify()["events"]
    kinds = [e["event_type"] for e in events]
    assert kinds == ["started"] * 4 + ["completed"] * 4, f"T004 ORDER started-before-evaluated: {kinds}"
    roles = [e["role"] for e in events[:4]]
    assert roles == ["synthetic_test"] * 4 and [e["config"]["model"]["name"] for e in events[:4]] == \
        ["A1", "B-BH", "B-RND", "B-RND"], "T004 ORDER A1, B-BH, B-RND"
    assert all(e["family"] == t004.FAMILY for e in events), "T004 FAMILY"
    assert [r["seed"] for r in receipts] == [None, None, *SEEDS]
    assert report["label"] == ar.LABEL and report["random_dispersion"]["seeds"] == SEEDS
    with pytest.raises(t004.PreflightRefused) as caught:
        declaration = dict(t004.declared(), research_data={"panel_hash": panel.panel_hash})
        t004.preflight(panel, data_check=check, ledger=ledger, declaration=declaration, clean=lambda r: True)
    assert caught.value.reason == "research_report_already_run", "T004 RERUN refused"


def test_production_roles_count_only_a1():
    plan = t004.series_plan(SEEDS)
    assert [role for _, role, _ in plan] == ["candidate", "buy_and_hold_baseline", "random_signal_baseline",
                                             "random_signal_baseline"], "T004 ROLES baselines never count toward N"


def test_recorded_returns_are_the_reported_equity(tmp_path, ledger):
    panel, _ = sleeve_panel(tmp_path)
    equity = {}
    bars = {t: pd.DataFrame({"Open": panel.opens[t], "Close": panel.closes[t]}) for t in ALLOCATION_SLEEVES}
    ar.allocation_report(bars, commission_per_fill=0.0, cost_config=CostConfig(), split_sessions=panel.split_sessions,
                         seeds=SEEDS, fill_cost=t004.t015.fill_cost(panel), equity_out=equity)
    t004.run_report(panel, seeds=SEEDS, data={"sha256": panel.panel_hash})
    completed = ledger.verify()["events"][4]
    side = completed["sidecar"]
    recorded = [json.loads(x) for x in (ledger.root / side["path"]).read_bytes().splitlines()]
    expected = np.log(equity["allocation"] / equity["allocation"].shift(1)).dropna()
    assert [r["session"] for r in recorded] == [s.strftime("%Y-%m-%d") for s in expected.index], "T004 RETURNS sessions"
    assert [r["log_return"] for r in recorded] == pytest.approx(expected.to_list()), "T004 RETURNS log of A1 equity"


def test_injected_fill_cost_is_the_one_applied(tmp_path):
    panel, _ = sleeve_panel(tmp_path)
    bars = {t: pd.DataFrame({"Open": panel.opens[t], "Close": panel.closes[t]}) for t in ALLOCATION_SLEEVES}
    kwargs = dict(commission_per_fill=0.0, cost_config=CostConfig(), split_sessions=panel.split_sessions, seeds=SEEDS)
    cheap, dear = {}, {}
    ar.allocation_report(bars, fill_cost=lambda *_: 0.0, equity_out=cheap, **kwargs)
    ar.allocation_report(bars, fill_cost=lambda *_: 0.01, equity_out=dear, **kwargs)
    assert dear["allocation"].iloc[-1] < cheap["allocation"].iloc[-1], "T004 COST injected fill_cost ignored"
    assert set(cheap) == {"allocation", "buy_and_hold", *SEEDS}, "T004 EQUITY every series exported"


def test_a_failure_during_evaluation_marks_every_started_series_errored(tmp_path, ledger, monkeypatch):
    panel, _ = sleeve_panel(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(t004, "allocation_report", boom)
    with pytest.raises(RuntimeError):
        t004.run_report(panel, seeds=SEEDS, data={"sha256": panel.panel_hash})
    events = ledger.verify()["events"]
    assert [e["event_type"] for e in events[4:]] == ["errored"] * 4, "T004 ERRORED every open start"
