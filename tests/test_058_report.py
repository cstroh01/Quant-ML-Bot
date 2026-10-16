"""Spec 058 T017/T018: the published verdict is PASS only with research Gate 3 AND D-4.

EXAMPLE — NOT A RESULT. Synthetic summaries only.
"""
import context  # noqa: F401
import report_058


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
