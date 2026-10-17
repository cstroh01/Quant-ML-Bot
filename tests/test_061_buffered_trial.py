"""061 recorder: EXAMPLE — NOT A RESULT. All writes use isolated synthetic roots."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from context import SCRIPTS_DIR

import run_061_buffered_trial as trial
from buffered_allocation import buffered_weights
from portfolio_backtest import run_portfolio_backtest
from test_059_t004 import sleeve_panel
from trial_registry import TrialLedger, declare_family, digest, verify_family
from trial_runner import injected_ledger

ROOT = SCRIPTS_DIR.parent


@pytest.fixture(scope="module")
def panel_check(tmp_path_factory):
    return sleeve_panel(tmp_path_factory.mktemp("061-panel"))


@pytest.fixture
def frozen(tmp_path, panel_check):
    root = tmp_path / "root"
    source = root / trial.SOURCE
    source.parent.mkdir(parents=True)
    declaration = json.loads((ROOT / trial.SOURCE).read_text(encoding="utf-8"))
    declaration["panel_hash"] = panel_check[0].panel_hash
    source.write_text(json.dumps(declaration), encoding="utf-8")
    declare_family(trial.FAMILY, root=root, synthetic=True)
    ledger = TrialLedger(root, synthetic=True)
    with injected_ledger(ledger):
        yield ledger, declaration


def test_declared_rule_is_new_post_hoc_family_and_source_bound():
    declaration = trial.source_declaration()
    assert declaration["decision"]["post_hoc"] is True
    assert declaration["decision"]["adopted_historical_trial_id"] is None
    assert declaration["cash_reserve"] == 0.07 and declaration["n_family_cap"] == 1
    assert declaration["family"] != "059-allocation"
    assert declaration["random_seeds"] == list(range(20261015, 20261035))
    assert declaration["costs"]["slippage"]["config"]["impact_coef"] == 1


def test_source_drift_refuses_before_any_ledger_byte(tmp_path):
    declaration = trial.source_declaration()
    for relative in [trial.SOURCE, *declaration["source_sha256"]]:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    with (tmp_path / "scripts/buffered_allocation.py").open("a", encoding="utf-8") as handle:
        handle.write("\n# changed after declaration\n")
    with pytest.raises(ValueError, match="source binding changed"):
        trial.source_declaration(tmp_path)
    assert not (tmp_path / "docs/trials").exists()


def test_preflight_is_read_only_and_refuses_bad_panel_holdout_and_seeds(frozen, panel_check):
    ledger, declaration = frozen
    panel, check = panel_check
    before = list((ledger.root / "docs/trials").rglob("*"))
    status = trial.preflight(panel, check, declaration, ledger)
    assert len(status["weights_sha256"]) == 64
    cases = [(dict(check, status="UNKNOWN"), declaration, "data_check_missing"),
             (dict(check, panel_hash="0" * 64), declaration, "panel_not_declared"),
             (check, dict(declaration, random_seeds=[1, 2]), "seeds_not_declared")]
    for other_check, other_declaration, message in cases:
        with pytest.raises(ValueError, match=message):
            trial.preflight(panel, other_check, other_declaration, ledger)
    from dataclasses import replace
    future = panel.closes.copy()
    future.loc[pd.Timestamp("2023-10-02")] = future.iloc[-1]
    with pytest.raises(ValueError, match="holdout forbidden"):
        trial.preflight(replace(panel, closes=future), check, declaration, ledger)
    assert list((ledger.root / "docs/trials").rglob("*")) == before


def test_freeze_required_before_evaluation(frozen, panel_check, monkeypatch):
    ledger, declaration = frozen
    (ledger.root / "docs/trials/families" / f"{trial.FAMILY}.json").unlink()
    monkeypatch.setattr(trial, "run_portfolio_backtest", lambda *_a, **_k: pytest.fail("evaluation before freeze"))
    with pytest.raises(ValueError, match="requires its declaration"):
        trial.run_report(panel_check[0], declaration=declaration, data={})
    assert not ledger.verify()["events"]


def test_every_series_started_before_evaluation_costs_applied_and_returns_bound(frozen, panel_check, monkeypatch):
    ledger, declaration = frozen
    panel, _ = panel_check
    original = trial.run_portfolio_backtest
    evaluated = []

    def observe(opens, closes, weights, **kwargs):
        events = ledger.verify()["events"]
        assert sum(e["event_type"] == "started" for e in events) == 22, "061 START ALL before evaluation"
        evaluated.append(weights.copy())
        assert kwargs["commission_per_fill"] == 0.0
        return original(opens, closes, weights, **kwargs)

    monkeypatch.setattr(trial, "run_portfolio_backtest", observe)
    report = trial.run_report(panel, declaration=declaration, data={"sha256": panel.panel_hash})
    events = ledger.verify()["events"]
    assert [e["event_type"] for e in events] == ["started"] * 22 + ["completed"] * 22
    assert [r["role"] for r in report["series"][:2]] == ["candidate", "buy_and_hold_baseline"]
    pd.testing.assert_frame_equal(evaluated[0], buffered_weights(panel.closes))
    expected = original(panel.opens[list(trial.ALLOCATION_SLEEVES)], panel.closes[list(trial.ALLOCATION_SLEEVES)],
                        buffered_weights(panel.closes), starting_capital=100_000.0,
                        commission_per_fill=0.0, fill_cost=trial.t015.fill_cost(panel))
    side = events[22]["sidecar"]
    rows = [json.loads(row) for row in (ledger.root / side["path"]).read_bytes().splitlines()]
    assert rows == trial.daily_rows(expected.equity), "061 RETURNS match costed funded equity"
    assert expected.fills["Cost_Fraction"].gt(0).any(), "061 COST fixture must charge actual primary costs"
    assert report["series"][0]["fills"] > 0
    assert digest(report["candidate_weights"]) == events[0]["config"]["model"]["params"]["weights_sha256"]
    assert report["random_dispersion"]["std_sharpe"] is not None
    assert trial.LABEL in trial.render(report) and "Post-hoc" in trial.render(report)
    with pytest.raises(ValueError, match="already_started"):
        trial.run_report(panel, declaration=declaration, data={})


def test_evaluation_failure_consumes_attempt_and_blocks_rerun(frozen, panel_check, monkeypatch):
    ledger, declaration = frozen

    def fail(*_a, **_k):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(trial, "run_portfolio_backtest", fail)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        trial.run_report(panel_check[0], declaration=declaration, data={})
    events = ledger.verify()["events"]
    assert [e["event_type"] for e in events] == ["started"] * 22 + ["errored"] * 22
    with pytest.raises(ValueError, match="already_started"):
        trial.run_report(panel_check[0], declaration=declaration, data={})
    with pytest.raises(ValueError, match="already has trials"):
        declare_family(trial.FAMILY, root=ledger.root, synthetic=True)
    assert verify_family(trial.FAMILY, root=ledger.root)["declaration"] == declaration


def test_monthly_decision_fills_next_open_across_gap_and_cost_changes_equity():
    from test_061_buffered_allocation import prices
    closes = prices()
    book = buffered_weights(closes)
    results = [run_portfolio_backtest(closes, closes, book, starting_capital=1000.0,
                                     commission_per_fill=0.0, fill_cost=lambda *_: cost)
               for cost in (0.001, 0.02)]
    fills = results[0].fills
    assert (fills["Decision"] == pd.Timestamp("2023-02-01")).all()
    assert (fills["Session"] == pd.Timestamp("2023-02-03")).all(), "061 NEXT OPEN after calendar gap"
    assert results[1].equity.iloc[-1] < results[0].equity.iloc[-1], "061 COST must affect equity"
