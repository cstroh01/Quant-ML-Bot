"""Spec 051 T007: the paper loop honors a PAPER profile's budget, cap and namespace.

Fakes only: no broker, no network, no keys. EXAMPLE — NOT A RESULT.
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

import context  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "exec") not in sys.path:
    sys.path.insert(0, str(ROOT / "exec"))

import paper_loop  # noqa: E402
from live_safety_gate import LiveSafetyGate  # noqa: E402
from mode_config import load_profiles  # noqa: E402
from mode_fixtures import raw  # noqa: E402
from test_049_paper_loop import FakeClient, trending_closes  # noqa: E402


class RichClient(FakeClient):
    """Broker reports far more equity and cash than the bot's budget."""

    def account(self):
        return {"equity": "1000000", "cash": "1000000", "status": "ACTIVE"}


def run(profile, client=None):
    with tempfile.TemporaryDirectory() as tmp:
        gate = LiveSafetyGate(Path(tmp) / "gate.sqlite", paper_loop.PAPER_SAFETY_CONFIG)
        try:
            return paper_loop.run_once(client=client or RichClient(), gate=gate, closes=trending_closes(),
                                       submit=False, profile=profile)
        finally:
            gate.close()


def small(**extra):
    return load_profiles([raw(bot_budget_usd=5000.0, daily_deploy_fraction=0.2, **extra)])["paper_small"]


def test_buys_stay_inside_the_daily_cap_of_the_budget_not_the_broker_balance():
    record = run(small())
    closes = trending_closes()
    last = closes.iloc[-1]
    notional = sum(a["delta_quantity"] * float(last[a["ticker"]]) for a in record["actions"]
                   if a.get("outcome") == "DRY_RUN" and a["delta_quantity"] > 0)
    assert 0 < notional <= 1000.0
    assert record["profile"] == "paper_small"


def test_no_profile_keeps_the_original_behavior():
    assert run(None)["profile"] is None


def test_budget_refusals_are_recorded_with_reasons():
    record = run(small(), client=type("Broke", (RichClient,), {"account": lambda self: {"equity": "1000000", "cash": "0", "status": "ACTIVE"}})())
    refused = [a for a in record["actions"] if a["outcome"] == "BUDGET_REFUSED"]
    assert refused and all(a["reason"] == "insufficient_settled_cash" for a in refused)


def test_profile_state_is_namespaced():
    gate_a, log_a = paper_loop.state_paths(small())
    gate_default, log_default = paper_loop.state_paths(None)
    assert gate_a != gate_default and log_a != log_default and "paper_small" in str(gate_a)


def test_live_profile_is_refused_by_the_paper_loop(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps([raw(), raw("live_fidelity", mode="LIVE", broker="fidelity", account="F")]))
    with pytest.raises(paper_loop.RunAborted, match="PAPER"):
        paper_loop.load_paper_profile(path, "live_fidelity")
    assert paper_loop.load_paper_profile(path, "paper_small").name == "paper_small"


def test_profile_credentials_map_only_its_own_names():
    env = {"PAPER_SMALL_KEY_ID": "k1", "PAPER_SMALL_SECRET": "s1", "APCA_API_KEY_ID": "other"}
    assert paper_loop.profile_environ(small(), env) == {"APCA_API_KEY_ID": "k1", "APCA_API_SECRET_KEY": "s1"}


def test_targets_are_planned_against_the_bot_budget(monkeypatch):
    seen = []
    real = paper_loop.plan_next_open

    def spy(*args, **kwargs):
        seen.append(kwargs["equity"])
        return real(*args, **kwargs)

    monkeypatch.setattr(paper_loop, "plan_next_open", spy)
    run(small())
    run(None)
    assert seen == [5000.0, 1000000.0]
