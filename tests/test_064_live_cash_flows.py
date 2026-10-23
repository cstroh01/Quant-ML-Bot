"""064 T003b: the LIVE loop feeds attributable flows to the real gate once per run.

EXAMPLE — NOT A RESULT. Fake broker, synthetic bars and synthetic transfer
evidence; sockets blocked. No real Fidelity capability is proven here: the only
real source remains 'unsupported' until a transfer feed passes its own check.
"""
from datetime import timedelta
import sqlite3

import context  # noqa: F401
from test_057_q139 import blocked, NOW  # noqa: F401
from test_057_q135 import process  # noqa: F401
from test_057_q137 import Broker, Gate, execute, profile
from live_safety_gate import BrokerSnapshot, FlowObservation, DENY_CASH_FLOW_QUARANTINE, DENY_LOSS_HALT, LiveSafetyGate
from types import SimpleNamespace as NS
import live_loop as loop

EQUITY = 10.0  # fake broker: settled cash 10, only SPAXX held


def real_gate(tmp_path):
    return LiveSafetyGate(tmp_path / 'live-gate.sqlite', loop.ALLOCATION_SAFETY_CONFIG)


def seed_prior_session(gate, equity):
    """A previous-day observation, so today's change is judged by the breaker."""
    at = NOW - timedelta(days=1)
    gate.observe_equity(BrokerSnapshot(at, 'OK', equity, 0.0, {}, {}), now=at)


def transfer(**changes):
    at = (NOW - timedelta(hours=2)).isoformat()
    return dict(transfer_id='withdrawal-1', account_fingerprint=profile().account_fingerprint,
                source_id='fixture_transfer_feed', evidence_ref='c' * 64, direction='withdrawal',
                amount='-100', currency='USD', observed_at=at, effective_at=at, status='settled') | changes


def source(*events):
    return NS(source_id='fixture_transfer_feed', events=lambda live, now: list(events))


def observations(tmp_path):
    with sqlite3.connect(tmp_path / 'live-gate.sqlite') as db:
        return db.execute('SELECT observation_id, result FROM flow_observations').fetchall()


def test_unsupported_default_observes_once_with_zero_flow(tmp_path):
    gate = real_gate(tmp_path)
    try:
        r = execute(tmp_path, gate=gate)
    finally:
        gate.close()
    assert not r.get('aborted')
    assert r['cash_flows'] == {'source': 'unsupported', 'net_flow': '0', 'quarantined': False, 'reasons': []}
    rows = observations(tmp_path)
    assert len(rows) == 1 and rows[0][0].startswith('live_fidelity:2026-10-15:')


def test_observation_follows_reconciliation_and_precedes_every_order(tmp_path, monkeypatch):
    trace = []
    original_reconcile, original_flow = loop.require_reconciled, LiveSafetyGate.observe_equity_with_flows
    original_eval = LiveSafetyGate.evaluate_order
    monkeypatch.setattr(loop, 'require_reconciled', lambda *a, **k: trace.append('reconcile') or original_reconcile(*a, **k))

    def flow(self, snapshot, **kw):
        trace.append(('flow', snapshot.external_cash_flow)); return original_flow(self, snapshot, **kw)

    def evaluate(self, snapshot, intent, **kw):
        trace.append(('order', snapshot.external_cash_flow)); return original_eval(self, snapshot, intent, **kw)
    monkeypatch.setattr(LiveSafetyGate, 'observe_equity_with_flows', flow)
    monkeypatch.setattr(LiveSafetyGate, 'evaluate_order', evaluate)
    gate = real_gate(tmp_path)
    try:
        r = execute(tmp_path, gate=gate)
    finally:
        gate.close()
    flows = [i for i, t in enumerate(trace) if t[0] == 'flow']
    orders = [i for i, t in enumerate(trace) if t[0] == 'order']
    assert not r.get('aborted') and flows == [trace.index('reconcile') + 1] and orders
    assert flows[0] < min(orders) and all(trace[i][1] == 0.0 for i in flows + orders)


def test_attributed_withdrawal_is_not_a_loss(tmp_path):
    gate = real_gate(tmp_path)
    try:
        seed_prior_session(gate, EQUITY + 100.0)
        r = execute(tmp_path, gate=gate, flow_source=source(transfer()))
    finally:
        gate.close()
    assert not r.get('aborted') and r['cash_flows']['net_flow'] == '-100'
    assert any(a['outcome'] == 'PREVIEW' for a in r['actions'])
    assert not any(a.get('reason') == DENY_LOSS_HALT for a in r['actions'])


def test_control_unattributed_withdrawal_halts_as_loss(tmp_path):
    gate = real_gate(tmp_path)
    try:
        seed_prior_session(gate, EQUITY + 100.0)
        r = execute(tmp_path, gate=gate)
    finally:
        gate.close()
    denied = [a for a in r['actions'] if a['outcome'] == 'DENIED']
    assert denied and all(a['reason'] == DENY_LOSS_HALT for a in denied)
    assert not any(a['outcome'] == 'PREVIEW' for a in r['actions'])


def test_quarantined_flow_blocks_buys_without_aborting(tmp_path):
    gate = real_gate(tmp_path)
    try:
        r = execute(tmp_path, gate=gate, flow_source=source(transfer(account_fingerprint='b' * 64)))
    finally:
        gate.close()
    assert not r.get('aborted') and r['cash_flows']['quarantined'] is True
    assert r['cash_flows']['reasons'] == ['account_mismatch'] and r['cash_flows']['net_flow'] == '0'
    buys = [a for a in r['actions'] if a.get('delta_quantity', 0) > 0 and a['outcome'] != 'BUDGET_REFUSED']
    assert buys and all(a['outcome'] == 'DENIED' and a['reason'] == DENY_CASH_FLOW_QUARANTINE for a in buys)


def test_stale_observation_halts_before_any_broker_order(tmp_path):
    class StaleGate(Gate):
        def observe_equity_with_flows(self, snapshot, *, observation_id, **kw):
            return FlowObservation(observation_id, '0', False, (), True, None)
    b, g = Broker(), StaleGate()
    r = execute(tmp_path, gate=g, broker=b)
    assert r.get('aborted') and not b.calls and not g.calls and r['place_calls'] == 0
