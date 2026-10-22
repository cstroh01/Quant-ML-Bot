"""064 T003a: attributable cash flows reach the safety gate atomically, once.

EXAMPLE — NOT A RESULT. Synthetic equity and transfer evidence only; no broker.
Every assertion reads the real gate's durable SQLite state or its real
daily-loss / rolling-drawdown consumers, never a test-side recomputation.
"""
from datetime import datetime, timedelta, timezone
import socket

import pytest
import context  # noqa: F401
from live_safety_gate import (
    DENY_CASH_FLOW_QUARANTINE,
    BrokerSnapshot,
    FlowObservationConflict,
    OrderIntent,
    SafetyConfig,
    SafetyGate,
)

ACCOUNT, OTHER = "a" * 64, "b" * 64
SOURCES = {"fixture_transfer_feed"}
T0 = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)  # 10:00 ET, a Thursday session


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("external network forbidden")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def config():
    return SafetyConfig(version="064-t003a-test", max_position_pct=0.5, max_gross_pct=1.0,
                        daily_loss_pct=0.03, rolling_drawdown_pct=0.10, rolling_window_sessions=20,
                        max_snapshot_age_seconds=300.0, max_clock_skew_seconds=5.0)


def snap(equity, at=T0, *, positions=None, flow=0.0):
    positions = {} if positions is None else positions
    return BrokerSnapshot(as_of=at, status="OK", equity=equity, external_cash_flow=flow,
                          positions=positions, prices={"SPY": 100.0, "TLT": 100.0})


def transfer(**changes):
    return dict(transfer_id="deposit-1", account_fingerprint=ACCOUNT, source_id="fixture_transfer_feed",
                evidence_ref="c" * 64, direction="deposit", amount="100", currency="USD",
                observed_at=T0.isoformat(), effective_at=T0.isoformat(), status="settled") | changes


@pytest.fixture
def gate(tmp_path):
    g = SafetyGate(tmp_path / "gate.sqlite", config())
    yield g
    g.close()


def flows(g, snapshot, events, obs="obs-1", at=None):
    return g.observe_equity_with_flows(snapshot, observation_id=obs, events=events,
                                       account_fingerprint=ACCOUNT, approved_sources=SOURCES,
                                       now=at or snapshot.as_of)


def adjusted(g):
    return g.status()["adjusted_equity"]


def test_deposit_applies_once_and_later_order_snapshots_do_not_see_it_as_gain(gate):
    gate.observe_equity(snap(200.0), now=T0)
    later = T0 + timedelta(minutes=1)
    result = flows(gate, snap(300.0, later), [transfer()])
    assert result.net_flow == "100" and not result.quarantined and not result.replayed
    assert adjusted(gate) == 200.0, "T003a deposit counted as a trading gain"
    assert gate.status()["last_raw_equity"] == 300.0
    decision = gate.evaluate_order(snap(300.0, later), OrderIntent("o-1", "SPY", 1.0), now=later)
    assert decision.allowed and adjusted(gate) == 200.0, "T003a flow re-applied by an order snapshot"


def test_control_without_flow_api_the_same_deposit_is_a_gain(gate):
    gate.observe_equity(snap(200.0), now=T0)
    gate.observe_equity(snap(300.0, T0 + timedelta(minutes=1)), now=T0 + timedelta(minutes=1))
    assert adjusted(gate) == 300.0


def test_crash_before_commit_rolls_back_journal_and_boundary_then_retry_applies_once(gate, monkeypatch):
    gate.observe_equity(snap(200.0), now=T0)
    before = gate.status()
    real = gate._log_locked

    def crash(event_type, payload):
        if event_type == "FLOW_OBSERVATION":
            raise RuntimeError("simulated crash before COMMIT")
        return real(event_type, payload)

    monkeypatch.setattr(gate, "_log_locked", crash)
    later = T0 + timedelta(minutes=1)
    with pytest.raises(RuntimeError, match="simulated crash"):
        flows(gate, snap(300.0, later), [transfer()])
    assert gate.status() == before, "T003a partial write survived a rollback"
    assert gate.cash_flow_journal() is None
    monkeypatch.setattr(gate, "_log_locked", real)
    assert flows(gate, snap(300.0, later), [transfer()]).net_flow == "100"
    assert adjusted(gate) == 200.0


def test_same_id_same_payload_replays_and_changed_payload_refuses(gate):
    gate.observe_equity(snap(200.0), now=T0)
    later = T0 + timedelta(minutes=1)
    first = flows(gate, snap(300.0, later), [transfer()])
    logged = len(gate.evidence())
    again = flows(gate, snap(300.0, later), [transfer()])
    assert again.replayed and again.net_flow == first.net_flow and again.equity == first.equity
    assert len(gate.evidence()) == logged, "T003a replay wrote new evidence"
    state = gate.status()
    with pytest.raises(FlowObservationConflict):
        flows(gate, snap(300.0, later), [transfer(amount="99")])
    with pytest.raises(FlowObservationConflict):
        flows(gate, snap(301.0, later), [transfer()])
    assert gate.status() == state and adjusted(gate) == 200.0


def test_restart_keeps_replay_and_journal_dedupe(tmp_path):
    path = tmp_path / "gate.sqlite"
    g = SafetyGate(path, config())
    g.observe_equity(snap(200.0), now=T0)
    later = T0 + timedelta(minutes=1)
    flows(g, snap(300.0, later), [transfer()])
    g.close()
    g = SafetyGate(path, config())
    try:
        assert flows(g, snap(300.0, later), [transfer()]).replayed
        third = T0 + timedelta(minutes=2)
        repeat = flows(g, snap(300.0, third), [transfer(observed_at=third.isoformat())], obs="obs-2")
        assert repeat.net_flow == "0" and adjusted(g) == 200.0, "T003a restart re-applied a journaled flow"
    finally:
        g.close()


@pytest.mark.parametrize("bad,reason", [
    (dict(currency="EUR"), "invalid_event"),
    (dict(account_fingerprint=OTHER), "account_mismatch"),
    (dict(source_id="unapproved_feed"), "source_not_approved"),
    (dict(observed_at=(T0 + timedelta(hours=1)).isoformat()), "future_event"),
])
def test_each_quarantine_latches_blocks_adds_allows_reduce_and_survives_restart(tmp_path, bad, reason):
    path = tmp_path / "gate.sqlite"
    g = SafetyGate(path, config())
    g.observe_equity(snap(200.0, positions={"SPY": 1.0}), now=T0)
    later = T0 + timedelta(minutes=1)
    result = flows(g, snap(300.0, later, positions={"SPY": 1.0}), [transfer(**bad)])
    assert result.quarantined and reason in result.quarantine_reasons and result.net_flow == "0"
    g.close()
    g = SafetyGate(path, config())
    try:
        add = g.evaluate_order(snap(300.0, later, positions={"SPY": 1.0}), OrderIntent("add", "TLT", 1.0), now=later)
        assert not add.allowed and add.reason == DENY_CASH_FLOW_QUARANTINE
        cut = g.evaluate_order(snap(300.0, later, positions={"SPY": 1.0}), OrderIntent("cut", "SPY", -1.0), now=later)
        assert cut.allowed, "T003a quarantine blocked a reduce-only order"
    finally:
        g.close()


def test_identity_conflict_in_one_batch_quarantines(gate):
    gate.observe_equity(snap(200.0), now=T0)
    result = flows(gate, snap(300.0, T0 + timedelta(minutes=1)), [transfer(), transfer(amount="50")])
    assert result.quarantined and "identity_conflict" in result.quarantine_reasons
    assert gate.status()["cash_flow_quarantine"] is True


def test_stale_snapshot_halts_and_consumes_nothing(gate):
    gate.observe_equity(snap(200.0), now=T0)
    now = T0 + timedelta(hours=1)
    result = flows(gate, snap(300.0, T0 + timedelta(minutes=1)), [transfer()], at=now)
    assert result.reconciliation_halt and result.net_flow == "0" and result.equity is None
    assert gate.cash_flow_journal() is None and adjusted(gate) == 200.0
    assert gate.status()["reconciliation_halt"] is True


def test_withdrawal_is_not_a_loss_for_the_real_breakers(tmp_path):
    g = SafetyGate(tmp_path / "flow.sqlite", config())
    g.observe_equity(snap(200.0), now=T0)
    later = T0 + timedelta(minutes=1)
    out = flows(g, snap(50.0, later), [transfer(transfer_id="w-1", direction="withdrawal", amount="-150")])
    assert out.net_flow == "-150"
    assert not out.equity["daily_halt_active"] and not out.equity["rolling_halt_active"]
    g.close()
    control = SafetyGate(tmp_path / "control.sqlite", config())
    control.observe_equity(snap(200.0), now=T0)
    assert control.observe_equity(snap(50.0, later), now=later)["daily_halt_active"]
    control.close()


def test_aggregate_float_channel_is_refused_once_a_journal_exists(gate):
    gate.observe_equity(snap(200.0), now=T0)
    later = T0 + timedelta(minutes=1)
    assert gate.evaluate_order(snap(210.0, later, flow=10.0), OrderIntent("pre", "SPY", 1.0), now=later).allowed
    flows(gate, snap(310.0, later), [transfer()])
    with pytest.raises(ValueError, match="external_cash_flow"):
        gate.evaluate_order(snap(320.0, later, flow=10.0), OrderIntent("post", "SPY", 1.0), now=later)
    with pytest.raises(ValueError, match="external_cash_flow"):
        flows(gate, snap(320.0, later, flow=10.0), [transfer()], obs="obs-x")


def test_first_ever_observation_journals_the_flow_without_breaker_effect(gate):
    result = flows(gate, snap(300.0), [transfer()])
    assert result.net_flow == "100" and adjusted(gate) == 300.0
    assert gate.cash_flow_journal()["entries"]["deposit-1"]["applied"] is True
    later = T0 + timedelta(minutes=1)
    assert gate.observe_equity(snap(300.0, later), now=later)["adjusted_equity"] == 300.0


def test_decimal_flows_are_exact_before_the_single_float_crossing(gate):
    gate.observe_equity(snap(200.0), now=T0)
    events = [transfer(transfer_id="d-1", amount="0.1"), transfer(transfer_id="d-2", amount="0.2")]
    result = flows(gate, snap(200.3, T0 + timedelta(minutes=1)), events)
    assert result.net_flow == "0.3"
    assert abs(adjusted(gate) - 200.0) < 1e-9


def test_empty_database_and_paper_path_are_unchanged(gate):
    assert gate.status().get("cash_flow_quarantine") in (None, False)
    assert gate.cash_flow_journal() is None
    gate.observe_equity(snap(200.0), now=T0)
    later = T0 + timedelta(minutes=1)
    decision = gate.evaluate_order(snap(195.0, later, flow=-5.0), OrderIntent("p", "SPY", 0.5), now=later)
    assert decision.allowed and adjusted(gate) == 200.0
