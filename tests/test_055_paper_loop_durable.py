"""Spec 055 F03a: deterministic order ids, account binding and restart blocking in the PAPER loop.

Fakes only: FakeClient from the 049 tests. No broker, no keys.
EXAMPLE — NOT A RESULT.
"""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pytest

import context  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

import paper_loop  # noqa: E402
from live_safety_gate import LiveSafetyGate  # noqa: E402
from mode_config import load_profiles  # noqa: E402
from mode_fixtures import raw  # noqa: E402
from ops_runtime import client_order_id  # noqa: E402
from test_049_paper_loop import FakeClient, trending_closes  # noqa: E402

NOW = lambda: datetime(2026, 10, 5, 12, 30, 1, tzinfo=timezone.utc)  # noqa: E731
TODAY = date(2026, 10, 5)
ACCOUNT = "PA-SYNTHETIC-1"


class Client(FakeClient):
    def __init__(self, account_number=ACCOUNT, cash="1000000", **kw):
        super().__init__(**kw)
        self.account_number, self.cash = account_number, cash

    def account(self):
        return {"equity": "1000000", "cash": self.cash, "status": "ACTIVE", "account_number": self.account_number}


def profile():
    return load_profiles([raw(account=ACCOUNT, bot_budget_usd=5000.0, daily_deploy_fraction=0.2)])["paper_small"]


@pytest.fixture
def env(tmp_path):
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", paper_loop.PAPER_SAFETY_CONFIG)
    yield tmp_path, gate
    gate.close()


def run(env, client=None, prof="default"):
    tmp, gate = env
    return paper_loop.run_once(client=client or Client(), gate=gate, closes=trending_closes(), submit=True,
                               now_fn=NOW, profile=profile() if prof == "default" else prof)


def test_client_ids_are_deterministic_per_profile_session_ticker_side(env):
    client = Client()
    run(env, client)
    assert client.submitted
    for intent in client.submitted:
        side = "buy" if intent.delta_quantity > 0 else "sell"
        assert intent.client_order_id == client_order_id("paper_small", TODAY, intent.instrument, side)


def test_restart_with_an_unknown_reservation_blocks_new_exposure(env):
    tmp, gate = env
    first = Client()
    run(env, first)
    assert first.submitted  # statuses stay None: the broker "never heard of" them
    second = Client()
    with pytest.raises(paper_loop.RunAborted, match="unresolved"):
        run(env, second)
    assert second.submitted == []


def test_restart_after_terminal_statuses_proceeds_without_duplicates(env):
    tmp, gate = env
    first = Client()
    run(env, first)
    second = Client()
    second.statuses = {i.client_order_id: "filled" for i in first.submitted}
    record = run(env, second)
    assert second.submitted == []  # same session, same ids: the gate denies duplicates
    assert {a["outcome"] for a in record["actions"] if "client_order_id" in a} <= {"DENIED"}


def test_credentials_for_another_account_abort_before_any_order(env):
    client = Client(account_number="PA-SOMEONE-ELSE")
    with pytest.raises(paper_loop.RunAborted, match="account"):
        run(env, client)
    assert client.submitted == []
    assert hashlib.sha256(ACCOUNT.encode()).hexdigest() == profile().account_fingerprint  # control

