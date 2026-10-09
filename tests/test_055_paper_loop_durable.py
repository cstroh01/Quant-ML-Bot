"""Spec 055 F03: the PAPER loop's order identities and reservations are durable before each send.

Fakes only: FakeClient from the 049 tests, a recording persist hook. No broker, no keys.
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
from ops_runtime import client_order_id, open_intents  # noqa: E402
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


class Persist:
    """Records, at each persist, which client ids are durable in the intents log and the gate."""

    def __init__(self, tmp, gate, fail_at=None):
        self.tmp, self.gate, self.fail_at, self.snapshots = tmp, gate, fail_at, []

    def __call__(self):
        if self.fail_at is not None and len(self.snapshots) == self.fail_at:
            self.snapshots.append(None)
            raise RuntimeError("push rejected")
        self.snapshots.append(({r["client_order_id"] for r in open_intents(self.tmp)},
                               {r["client_order_id"] for r in self.gate.pending_orders()}))


@pytest.fixture
def env(tmp_path):
    gate = LiveSafetyGate(tmp_path / "gate.sqlite", paper_loop.PAPER_SAFETY_CONFIG)
    yield tmp_path, gate
    gate.close()


def run(env, client=None, persist=None, prof="default"):
    tmp, gate = env
    durable = paper_loop.Durable(intents_dir=tmp, persist=persist or Persist(tmp, gate))
    return paper_loop.run_once(client=client or Client(), gate=gate, closes=trending_closes(), submit=True,
                               now_fn=NOW, profile=profile() if prof == "default" else prof, durable=durable)


def test_client_ids_are_deterministic_per_profile_session_ticker_side(env):
    client = Client()
    run(env, client)
    assert client.submitted
    for intent in client.submitted:
        side = "buy" if intent.delta_quantity > 0 else "sell"
        assert intent.client_order_id == client_order_id("paper_small", TODAY, intent.instrument, side)


def test_each_send_happens_only_after_its_intent_and_reservation_were_persisted(env):
    tmp, gate = env
    client, persist = Client(), Persist(*env)
    submitted_before = []
    original = client.submit_market_on_open

    def watch(intent):
        submitted_before.append((intent.client_order_id, persist.snapshots[-1]))
        return original(intent)

    client.submit_market_on_open = watch
    run(env, client, persist)
    assert submitted_before
    for cid, (intents, reservations) in submitted_before:
        assert cid in intents and cid in reservations


def test_failed_persist_sends_nothing_further_and_releases_the_unsent_reservation(env):
    tmp, gate = env
    client = Client()
    record = run(env, client, Persist(tmp, gate, fail_at=0))
    assert client.submitted == []
    outcomes = [a["outcome"] for a in record["actions"] if "client_order_id" in a]
    assert outcomes and outcomes[0] == "NOT_SENT" and set(outcomes[1:]) <= {"NOT_SENT"}
    assert all(r["terminal"] for r in gate.pending_orders())


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


def test_daily_deployment_counts_earlier_invocations_of_the_same_session(env):
    tmp, gate = env
    first = Client()
    run(env, first)
    spent = sum(r["intent"]["notional"] for r in open_intents(tmp) if r["intent"]["side"] == "buy")
    assert 0 < spent <= 1000.0
    # A fresh gate (e.g. a manual rerun with new reservations) must still respect today's cap.
    fresh_gate = LiveSafetyGate(tmp / "gate2.sqlite", paper_loop.PAPER_SAFETY_CONFIG)
    try:
        second = Client()
        second.statuses = {i.client_order_id: "filled" for i in first.submitted}
        record = paper_loop.run_once(client=second, gate=fresh_gate, closes=trending_closes(), submit=True,
                                     now_fn=NOW, profile=profile(),
                                     durable=paper_loop.Durable(intents_dir=tmp, persist=Persist(tmp, fresh_gate)))
    finally:
        fresh_gate.close()
    new_buys = sum(abs(i.delta_quantity) for i in second.submitted if i.delta_quantity > 0)
    assert new_buys == 0 or spent + sum(
        a.get("notional", 0) for a in record["actions"] if a.get("outcome") == "SUBMITTED") <= 1000.0 + 1e-6


def test_workflow_gives_the_paper_loop_a_persist_command_and_cli_requires_it(tmp_path):
    import shlex
    text = (ROOT / "ops" / "workflows" / "paper-loop.yml").read_text()
    line = next(l for l in text.splitlines() if "exec/paper_loop.py --submit" in l)
    inner = shlex.split(line.split("--command", 1)[1])[0]
    args = shlex.split(inner)
    assert "--persist-command" in args and args[args.index("--persist-command") + 1].startswith("bash ops/persist_state.sh")
    profiles = tmp_path / "p.json"
    profiles.write_text(json.dumps([raw(account=ACCOUNT)]))
    with pytest.raises(paper_loop.RunAborted, match="persist-command"):
        paper_loop.main(["--submit", "--profile", "paper_small", "--profiles-file", str(profiles)])
