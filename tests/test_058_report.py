"""Spec 058 T017/T018: the published verdict is PASS only with research Gate 3 AND D-4.

EXAMPLE — NOT A RESULT. Synthetic summaries only.
"""
import context  # noqa: F401
import report_058
from datetime import datetime, timezone
import copy

import pytest
import trial_registry
from spec033_support import config, ledger, rows, SOURCE, META
from test_033_ledger import spend


def info(dsr, t, d4=None):
    rows = [{"config": c, "family_dsr": 0.01, "hac_t": 0.1} for c in report_058.RUN_ORDER]
    rows[-1].update(family_dsr=dsr, hac_t=t)
    holdout = None if d4 is None else {"event_type": "completed", "trial_id": "h", "sidecar": {"metadata": {"d4": {"pass": d4}}}}
    spend = None if d4 is None else {"trial_id": "h"}
    return {"rows": rows, "holdout": holdout, "spend": spend}


def test_pass_needs_both_research_gate3_and_d4():
    assert report_058.verdict(info(0.97, 3.5, d4=True))["pass"], "T017 both pass"
    assert not report_058.verdict(info(0.97, 3.5, d4=False))["pass"], "T017 D-4 fail must FAIL"
    assert not report_058.verdict(info(0.50, 3.5, d4=True))["pass"], "T017 research DSR fail must FAIL"
    assert not report_058.verdict(info(0.97, 2.0, d4=True))["pass"], "T017 research t fail must FAIL"
    assert not report_058.verdict(info(0.97, 3.5))["pass"], "T017 holdout not run must not PASS"


def test_unrun_and_spent_but_unfinished_holdouts_are_labelled():
    assert report_058.verdict(info(0.1, 0.1))["holdout_state"] == "not run"
    spent = info(0.1, 0.1)
    spent["spend"] = {"trial_id": "h"}
    assert "still open" in report_058.verdict(spent)["holdout_state"], "a spent holdout must never read as not run"


@pytest.mark.parametrize("event_form", ["started", "holdout_spend"])
@pytest.mark.parametrize("outcome", [None, "completed", "errored", "abandoned", "rejected"])
def test_collect_reports_both_verified_spend_forms(tmp_path, monkeypatch, event_form, outcome):
    """Q124 / 058 T017-T018: real temporary chain; stub unrelated family/statistical policy."""
    log = ledger(tmp_path)
    names = report_058.RUN_ORDER[:2]
    cv = {**META["cv"], "initial_train_months": 12, "test_months": 1}
    cfg = config(cv=cv)
    metadata = {**copy.deepcopy(META), "cv": cv}
    selected = None
    for name in names:
        trial = log.start({**cfg, "model": {"name": name, "params": {}}},
                          role="candidate", family="example", runner="fixture", source=SOURCE)
        log.finish(trial, "completed", returns=rows(), metadata=metadata)
        selected = selected or trial
    baseline = log.start(cfg, role="buy_and_hold_baseline", family="example", runner="fixture", source=SOURCE)
    log.finish(baseline, "completed", returns=rows(), metadata=metadata)
    if event_form == "holdout_spend":
        opening = spend(log, selected)["trial_id"]
    else:
        opening = log.start(cfg, role="holdout", family="example", runner="fixture", source=SOURCE)
    if outcome == "completed":
        d4 = dict(pass_=True, first_session="2020-01-02", last_session="2020-02-14", sessions=32,
                  annualized_net_excess_sharpe=1., hac_t={"value": 2.}, one_sided_threshold=1.645)
        d4["pass"] = d4.pop("pass_")
        log.finish(opening, outcome, returns=rows(), metadata={**metadata, "d4": d4})
    elif outcome:
        log.finish(opening, outcome, reason="EXAMPLE")
    before, head = log.path.read_bytes(), log.verify()["head"]
    monkeypatch.setattr(report_058, "FAMILY", "example")
    monkeypatch.setattr(report_058, "RUN_ORDER", names)
    monkeypatch.setattr(report_058, "TrialLedger", lambda root: log)
    policy = dict(alignment="exact_intersection", min_coverage=.95, objective="daily_sharpe",
                  risk_free=cfg["risk_free"], horizon=1, hac_lags=5)
    monkeypatch.setattr(report_058, "verify_family", lambda *a, **k: {"declaration": {"gate3": policy}})
    monkeypatch.setattr(report_058, "trial_counts", lambda *a, **k: {"family": {"n_dsr": 2, "cap": 50}, "n_current": 2})
    monkeypatch.setattr(report_058, "counted_dsr", lambda *a, **k: {"family": {"value": .97}, "lifetime": {"value": .97}})
    monkeypatch.setattr(report_058, "matrix_pbo", lambda *a, **k: {"value": .5})
    collected = report_058.collect(tmp_path)
    result = report_058.verdict(collected)
    assert collected["spend"] and collected["spend"]["trial_id"] == opening, "Q124 REPORT spend lost"
    assert (collected["holdout"]["event_type"] if collected["holdout"] else None) == outcome, "Q124 REPORT audit event is not an outcome"
    assert result["holdout_state"] != "not run", "Q124 REPORT spent holdout rendered as not run"
    if outcome == "completed":
        assert result["holdout_state"] == "completed" and result["d4"]["pass"]
    else:
        assert not result["pass"] and result["d4"] is None, "Q124 REPORT unfinished holdout passed"
        assert ("still open" if outcome is None else f"ended {outcome}") in result["holdout_state"]
    rendered = report_058.render(collected, result, generated_at=datetime(2026, 10, 19, tzinfo=timezone.utc))
    assert "not run" not in rendered, "Q124 REPORT publication erases spend"
    assert log.path.read_bytes() == before and log.verify()["head"] == head, "Q124 REPORT wrote ledger"
