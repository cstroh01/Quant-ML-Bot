"""Spec 053 U3: champion/challenger registry, promotion and rollback. EXAMPLE — NOT A RESULT."""
from datetime import date

import pytest

import context  # noqa: F401
from model_registry import Evidence, PromotionError, Registry

GOOD = Evidence(gate3_pass=True, gate3_digest="a" * 64, gate3_session=date(2026, 10, 1),
                oos_beats_baselines=True, shadow_sessions=25, breaches=0)


def reg(tmp_path):
    r = Registry(tmp_path / "registry.json")
    r.register("m1", stage="champion", approver="Camden", session=date(2026, 9, 1))
    r.register("m2", stage="challenger")
    return r


def test_retrain_registers_only_a_challenger(tmp_path):
    r = reg(tmp_path)
    r.register("m3", stage="challenger")
    assert r.champion() == "m1"
    with pytest.raises(PromotionError, match="Camden"):
        r.register("m4", stage="champion", approver="cloud-runner", session=date(2026, 10, 8))


def test_promotion_requires_camden_and_complete_fresh_evidence(tmp_path):
    r = reg(tmp_path)
    r.promote("m2", GOOD, approver="Camden", session=date(2026, 10, 8), max_evidence_age_sessions=10)
    assert r.champion() == "m2"


@pytest.mark.parametrize("change,reason", [
    (dict(gate3_pass=False), "Gate 3"), (dict(oos_beats_baselines=False), "baselines"),
    (dict(shadow_sessions=5), "shadow"), (dict(breaches=1), "breach"), (dict(gate3_digest="x"), "digest"),
    (dict(gate3_session=date(2026, 8, 1)), "stale"),
])
def test_incomplete_or_stale_evidence_refuses(tmp_path, change, reason):
    r = reg(tmp_path)
    evidence = Evidence(**(GOOD.__dict__ | change))
    with pytest.raises(PromotionError, match=reason):
        r.promote("m2", evidence, approver="Camden", session=date(2026, 10, 8), max_evidence_age_sessions=10)
    assert r.champion() == "m1"


def test_non_camden_promotion_refuses(tmp_path):
    with pytest.raises(PromotionError, match="Camden"):
        reg(tmp_path).promote("m2", GOOD, approver="agent", session=date(2026, 10, 8), max_evidence_age_sessions=10)


def test_rollback_restores_the_previous_champion_and_keeps_history(tmp_path):
    r = reg(tmp_path)
    r.promote("m2", GOOD, approver="Camden", session=date(2026, 10, 8), max_evidence_age_sessions=10)
    r.rollback(reason="drawdown breach", session=date(2026, 10, 9))
    assert r.champion() == "m1"
    events = [e["event"] for e in Registry(tmp_path / "registry.json").history()]
    assert events == ["register", "register", "promote", "rollback"]
