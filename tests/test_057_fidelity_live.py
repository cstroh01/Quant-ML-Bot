"""Spec 057: Fidelity LIVE adapter contracts with a fake broker only.

No real Fidelity call, credential or library import happens here. EXAMPLE — NOT A RESULT.
"""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pytest

import context  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exec"))
from fidelity_live import (  # noqa: E402
    BrokerError, FidelityLive, HaltProfile, NotArmed, SecurityChallenge, SubmissionUnknown,
)
from live_safety_gate import OrderIntent  # noqa: E402
from mode_config import ArmingRecord, load_profiles  # noqa: E402
from mode_fixtures import raw  # noqa: E402

NOW = datetime(2026, 10, 8, 13, 0, tzinfo=timezone.utc)
ENV = {"LIVE_FIDELITY_USERNAME": "u-synthetic", "LIVE_FIDELITY_PASSWORD": "p-synthetic-hunter2",
       "LIVE_FIDELITY_TOTP": "TOTPSYNTHETIC"}


class FakeBroker:
    def __init__(self, *, login_error=None, place_error=None, preview_error=None):
        self.calls, self.logins = [], 0
        self.login_error, self.place_error, self.preview_error = login_error, place_error, preview_error

    def login(self, username, password, totp_secret):
        self.logins += 1
        if self.login_error:
            raise self.login_error

    def preview(self, symbol, side, quantity):
        self.calls.append(("preview", symbol, side, quantity))
        if self.preview_error:
            raise self.preview_error
        return "CONF-1"

    def place(self, symbol, side, quantity, conf_num):
        self.calls.append(("place", symbol, side, quantity, conf_num))
        if self.place_error:
            raise self.place_error
        return conf_num

    def status(self, conf_num):
        return "FILLED" if conf_num == "CONF-1" else None

    def positions(self):
        return {"AAA": 1.0}


def live_profile():
    return load_profiles([raw("live_fidelity", mode="LIVE", broker="fidelity", account="F-1",
                              credential_refs=list(ENV), bot_budget_usd=300.0)])["live_fidelity"]


def armed(profile):
    return ArmingRecord(profile.name, profile.account_fingerprint, "e" * 64, "Camden",
                        NOW - timedelta(hours=1), NOW + timedelta(days=1))


def intent(qty=2.0):
    return OrderIntent(client_order_id="qmb-20261008-abc", instrument="AAA", delta_quantity=qty)


def adapter(tmp_path, broker=None, **kw):
    return FidelityLive(live_profile(), broker=broker or FakeBroker(), state_dir=tmp_path, environ=ENV, **kw)


def test_paper_profile_is_refused(tmp_path):
    paper = load_profiles([raw()])["paper_small"]
    with pytest.raises(Exception, match="LIVE fidelity"):
        FidelityLive(paper, broker=FakeBroker(), state_dir=tmp_path, environ=ENV)


def test_placement_without_arming_refuses_and_sends_nothing(tmp_path):
    broker = FakeBroker()
    live = adapter(tmp_path, broker)
    live.connect()
    with pytest.raises(NotArmed):
        live.submit(intent(), arming=None, now=NOW)
    assert broker.calls == []


def test_armed_placement_previews_records_then_places(tmp_path):
    broker = FakeBroker()
    live = adapter(tmp_path, broker)
    live.connect()
    assert live.submit(intent(), arming=armed(live_profile()), now=NOW) == "CONF-1"
    assert [c[0] for c in broker.calls] == ["preview", "place"]
    assert live.order_status("qmb-20261008-abc") == "FILLED"


def test_intent_is_recorded_before_place_even_if_place_times_out(tmp_path):
    broker = FakeBroker(place_error=TimeoutError())
    live = adapter(tmp_path, broker)
    live.connect()
    with pytest.raises(SubmissionUnknown):
        live.submit(intent(), arming=armed(live_profile()), now=NOW)
    assert live.order_status("qmb-20261008-abc") == "FILLED"  # reconcilable by confirmation number
    assert [c[0] for c in broker.calls] == ["preview", "place"]  # never retried


def test_security_challenge_halts_the_profile(tmp_path):
    live = adapter(tmp_path, FakeBroker(login_error=SecurityChallenge("verify")))
    with pytest.raises(HaltProfile):
        live.connect()
    with pytest.raises(HaltProfile):
        live.positions()


def test_challenge_at_placement_halts(tmp_path):
    live = adapter(tmp_path, FakeBroker(place_error=SecurityChallenge("warning")))
    live.connect()
    with pytest.raises(HaltProfile):
        live.submit(intent(), arming=armed(live_profile()), now=NOW)
    with pytest.raises(HaltProfile):
        live.submit(intent(), arming=armed(live_profile()), now=NOW)


def test_one_session_per_run(tmp_path):
    broker = FakeBroker()
    live = adapter(tmp_path, broker)
    live.connect()
    with pytest.raises(BrokerError, match="one session"):
        live.connect()
    assert broker.logins == 1


def test_credentials_never_appear_in_repr_or_errors(tmp_path):
    live = adapter(tmp_path, FakeBroker(login_error=RuntimeError("boom p-synthetic-hunter2")))
    assert "hunter2" not in repr(live) and "u-synthetic" not in repr(live)
    with pytest.raises(BrokerError) as caught:
        live.connect()
    assert "hunter2" not in str(caught.value)


def test_missing_credential_refuses(tmp_path):
    env = dict(ENV); env.pop("LIVE_FIDELITY_TOTP")
    with pytest.raises(BrokerError, match="_TOTP"):
        FidelityLive(live_profile(), broker=FakeBroker(), state_dir=tmp_path, environ=env)


def test_sell_is_sent_as_sell(tmp_path):
    broker = FakeBroker()
    live = adapter(tmp_path, broker)
    live.connect()
    live.submit(intent(-1.5), arming=armed(live_profile()), now=NOW)
    assert broker.calls[0] == ("preview", "AAA", "S", 1.5)
