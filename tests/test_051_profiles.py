"""Spec 051 U1: mode profiles, default PAPER, isolation and LIVE arming.

EXAMPLE — NOT A RESULT. Every profile and account value here is synthetic.
"""
from datetime import datetime, timedelta, timezone

import pytest

import context  # noqa: F401
from mode_config import (
    ArmingRecord,
    ModeProfile,
    ProfileError,
    default_profile_name,
    load_profiles,
    require_armed,
)
from mode_fixtures import fp, raw

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def three():
    return [
        raw(),
        raw("paper_large", account="PA-2", bot_budget_usd=100000.0, daily_deploy_fraction=0.5),
        raw("live_fidelity", mode="LIVE", broker="fidelity", account="F-1", bot_budget_usd=300.0),
    ]


def test_valid_profiles_load_and_default_is_small_paper():
    profiles = load_profiles(three())
    assert set(profiles) == {"paper_small", "paper_large", "live_fidelity"}
    assert default_profile_name(profiles) == "paper_small"
    assert profiles[default_profile_name(profiles)].mode == "PAPER"


def test_live_requires_live_capable_broker_and_paper_requires_paper_broker():
    with pytest.raises(ProfileError, match="broker"):
        load_profiles([raw("live_x", mode="LIVE", broker="alpaca_paper", account="X")])
    with pytest.raises(ProfileError, match="broker"):
        load_profiles([raw("paper_x", mode="PAPER", broker="fidelity", account="Y")])


@pytest.mark.parametrize("field", ["state_dir", "log_namespace", "account_fingerprint", "credential_refs"])
def test_shared_namespace_or_identity_refuses(field):
    profiles = three()
    profiles[2][field] = profiles[0][field]
    with pytest.raises(ProfileError, match=field):
        load_profiles(profiles)


def test_fingerprint_must_be_a_digest_not_a_raw_account_id():
    with pytest.raises(ProfileError, match="account_fingerprint"):
        load_profiles([raw(account_fingerprint="Z53642611")])


def test_credential_refs_are_names_never_values():
    with pytest.raises(ProfileError, match="credential_refs"):
        load_profiles([raw(credential_refs=["PKA1B2C3 secret value"])])


@pytest.mark.parametrize("field,value", [("bot_budget_usd", 0.0), ("daily_deploy_fraction", 1.5),
                                         ("daily_deploy_fraction", 0.0), ("instruments", ["options"])])
def test_numeric_and_instrument_bounds(field, value):
    with pytest.raises(ProfileError, match=field):
        load_profiles([raw(**{field: value})])


def test_profile_is_immutable():
    profile = load_profiles(three())["paper_small"]
    with pytest.raises(Exception):
        profile.mode = "LIVE"
    assert "PAPER_SMALL_KEY_ID" in repr(profile)  # names only; values never reach a profile


def arming(profile: ModeProfile, **extra) -> ArmingRecord:
    values = dict(profile_name=profile.name, account_fingerprint=profile.account_fingerprint,
                  capital_gate_evidence_sha256="e" * 64, activated_by="Camden",
                  activated_at=NOW - timedelta(hours=1), expires_at=NOW + timedelta(days=1))
    values.update(extra)
    return ArmingRecord(**values)


def test_paper_needs_no_arming_and_live_without_record_refuses():
    profiles = load_profiles(three())
    require_armed(profiles["paper_small"], None, now=NOW)
    with pytest.raises(ProfileError, match="not armed"):
        require_armed(profiles["live_fidelity"], None, now=NOW)


def test_valid_arming_allows_live():
    live = load_profiles(three())["live_fidelity"]
    require_armed(live, arming(live), now=NOW)


@pytest.mark.parametrize("change,reason", [
    (dict(account_fingerprint=fp("OTHER")), "account"),
    (dict(profile_name="paper_small"), "profile"),
    (dict(expires_at=NOW - timedelta(seconds=1)), "expired"),
    (dict(activated_at=NOW + timedelta(minutes=5)), "future"),
    (dict(capital_gate_evidence_sha256="not-a-digest"), "evidence"),
    (dict(activated_by="agent"), "Camden"),
])
def test_bad_arming_refuses(change, reason):
    live = load_profiles(three())["live_fidelity"]
    with pytest.raises(ProfileError, match=reason):
        require_armed(live, arming(live, **change), now=NOW)


def test_naive_now_is_refused():
    live = load_profiles(three())["live_fidelity"]
    with pytest.raises(ProfileError, match="aware"):
        require_armed(live, arming(live), now=NOW.replace(tzinfo=None))


def test_default_refuses_a_live_profile_named_as_default():
    profiles = load_profiles([raw("paper_small", mode="LIVE", broker="fidelity", account="F-9")])
    with pytest.raises(ProfileError, match="default"):
        default_profile_name(profiles)
