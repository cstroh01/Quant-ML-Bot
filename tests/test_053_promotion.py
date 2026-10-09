"""Spec 053 U3: champion/challenger registry, promotion and rollback. EXAMPLE — NOT A RESULT."""
from dataclasses import replace
from datetime import date

import pytest

import context  # noqa: F401
from model_registry import Evidence, PromotionError, Registry

A1, A2, A3 = "1" * 64, "2" * 64, "3" * 64
CFG = "c" * 64
GOOD = Evidence(gate3_pass=True, gate3_digest="a" * 64, gate3_session=date(2026, 10, 1),
                oos_beats_baselines=True, shadow_sessions=25, breaches=0,
                artifact_sha256=A2, config_sha256=CFG, mode="PAPER")


def promote(r, model, evidence=GOOD, session=date(2026, 10, 8), **kw):
    r.promote(model, evidence, approver=kw.pop("approver", "Camden"), session=session,
              max_evidence_age_sessions=kw.pop("max_age", 10))


def reg(tmp_path):
    r = Registry(tmp_path / "registry.json", mode="PAPER")
    r.register("m1", stage="challenger", artifact_sha256=A1, config_sha256=CFG)
    promote(r, "m1", replace(GOOD, artifact_sha256=A1), session=date(2026, 10, 2))
    r.register("m2", stage="challenger", artifact_sha256=A2, config_sha256=CFG)
    return r


def test_retrain_registers_only_a_challenger(tmp_path):
    r = reg(tmp_path)
    r.register("m3", stage="challenger", artifact_sha256=A3, config_sha256=CFG)
    assert r.champion() == "m1"
    for approver in ("cloud-runner", "Camden"):
        with pytest.raises(PromotionError, match="promote"):
            r.register("m4", stage="champion", approver=approver, artifact_sha256=A3, config_sha256=CFG)
    assert r.champion() == "m1"


def test_promotion_requires_camden_and_complete_fresh_evidence(tmp_path):
    r = reg(tmp_path)
    promote(r, "m2")
    assert r.champion() == "m2"
    event = r.history()[-1]
    assert event["evidence"]["artifact_sha256"] == A2 and event["mode"] == "PAPER"


@pytest.mark.parametrize("change,reason", [
    (dict(gate3_pass=False), "Gate 3"), (dict(oos_beats_baselines=False), "baselines"),
    (dict(shadow_sessions=5), "shadow"), (dict(breaches=1), "breach"), (dict(gate3_digest="x"), "digest"),
    (dict(gate3_session=date(2026, 8, 1)), "stale"),
    (dict(gate3_session=date(2026, 10, 9)), "future"),
    (dict(artifact_sha256=A1), "artifact"), (dict(config_sha256="d" * 64), "config"),
    (dict(mode="LIVE"), "mode"),
])
def test_incomplete_stale_or_unbound_evidence_refuses(tmp_path, change, reason):
    r = reg(tmp_path)
    with pytest.raises(PromotionError, match=reason):
        promote(r, "m2", replace(GOOD, **change))
    assert r.champion() == "m1"


def test_unregistered_model_cannot_be_promoted(tmp_path):
    with pytest.raises(PromotionError, match="registered"):
        promote(reg(tmp_path), "m9", replace(GOOD, artifact_sha256=A3))


def test_non_camden_promotion_refuses(tmp_path):
    with pytest.raises(PromotionError, match="Camden"):
        promote(reg(tmp_path), "m2", approver="agent")


def test_registry_refuses_a_file_written_for_another_mode(tmp_path):
    reg(tmp_path)
    with pytest.raises(PromotionError, match="mode"):
        Registry(tmp_path / "registry.json", mode="LIVE").champion()


def test_rollback_restores_the_previous_champion_and_keeps_history(tmp_path):
    r = reg(tmp_path)
    promote(r, "m2")
    r.rollback(reason="drawdown breach", session=date(2026, 10, 9))
    assert r.champion() == "m1"
    events = [e["event"] for e in Registry(tmp_path / "registry.json", mode="PAPER").history()]
    assert events == ["register", "promote", "register", "promote", "rollback"]


def test_rollback_without_a_previous_champion_refuses(tmp_path):
    r = Registry(tmp_path / "registry.json", mode="PAPER")
    r.register("m1", stage="challenger", artifact_sha256=A1, config_sha256=CFG)
    promote(r, "m1", replace(GOOD, artifact_sha256=A1))
    with pytest.raises(PromotionError, match="previous"):
        r.rollback(reason="x", session=date(2026, 10, 9))
    assert r.champion() == "m1"


NAN = float("nan")


@pytest.mark.parametrize("change", [dict(shadow_sessions=NAN), dict(shadow_sessions=25.0), dict(breaches=NAN),
                                    dict(breaches=-1), dict(shadow_sessions=True)])
def test_non_integer_evidence_counts_refuse(tmp_path, change):
    r = reg(tmp_path)
    with pytest.raises(PromotionError, match="non-negative integer"):
        promote(r, "m2", replace(GOOD, **change))
    assert r.champion() == "m1"


@pytest.mark.parametrize("max_age", [NAN, float("inf"), 10.0, -1])
def test_invalid_evidence_age_limit_refuses(tmp_path, max_age):
    r = reg(tmp_path)
    with pytest.raises(PromotionError, match="max_evidence_age_sessions"):
        promote(r, "m2", max_age=max_age)


@pytest.mark.parametrize("change", [dict(gate3_pass="yes"), dict(oos_beats_baselines=1)])
def test_truthy_non_boolean_passes_refuse(tmp_path, change):
    with pytest.raises(PromotionError, match="literal passes"):
        promote(reg(tmp_path), "m2", replace(GOOD, **change))
