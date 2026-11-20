"""Spec 069: Fidelity fill observation. Fakes shaped like fidelity-trader-api 0.2.2's order-status
models; every socket is blocked; no real broker, account or credential. EXAMPLE — NOT A RESULT."""
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace as NS

import pytest

import context  # noqa: F401
from test_057_q139 import NOW, blocked, broker as bare  # noqa: F401  (autouse fixture)
from test_057_q135 import ENV, live_profile, process  # noqa: F401  (autouse fixture)
from test_057_q137 import bars, execute, profile
from test_068_place_acceptance import ARM, CID, Hybrid, outcome, write_outcome
import fidelity_live
import fidelity_session as fs
from fidelity_live import BrokerError, FidelityLive, HaltProfile, SecurityChallenge
from fidelity_reconcile import require_reconciled
from live_safety_gate import LiveSafetyGate, OrderIntent
import live_loop as loop
from mode_config import ArmingRecord


@pytest.fixture(autouse=True)
def waits(monkeypatch):
    """No real waiting: record each requested wait instead."""
    seen = []
    monkeypatch.setattr(fidelity_live, '_sleep', seen.append)
    return seen


class Observed(Hybrid):
    """068's fake (real LibraryBroker preview/place) plus a scripted status_detail: one item per
    look; once the script is used up it answers from the fake's own status list."""

    def __init__(self, looks=(), **kw):
        super().__init__(**kw)
        self.looks, self.asked = list(looks), []

    def status_detail(self, conf_num):
        self.asked.append(conf_num)
        if self.looks:
            item = self.looks.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return self.statuses.get(conf_num), None


def connected(tmp_path, b):
    live = FidelityLive(live_profile(), broker=b, state_dir=tmp_path, environ=ENV)
    live.connect()
    return live


def submit(live):
    return live.submit(OrderIntent(CID, 'DBC', 0.755), arming=ARM, now=NOW)


def observed(status, nums=('CONF-1',)):
    return {'client_order_id': CID, 'outcome': 'observed', 'conf_nums': list(nums), 'status': status}


# --- FR-001 / FR-002: observe after placement, record a terminal status ---

def test_filled_at_the_first_look_is_recorded_and_the_number_returned(tmp_path, waits):
    live = connected(tmp_path, Observed([('FILLED', 0.755)]))
    assert submit(live) == 'CONF-1'
    assert outcome(tmp_path) == observed('FILLED') and waits == [2.0]
    assert live.observations == [{'client_order_id': CID, 'observed': 'FILLED'}]


def test_looks_follow_d1_and_stop_at_the_first_terminal_status(tmp_path, waits):
    b = Observed([(None, None), ('WORKING', 0.0), ('Partially Filled', 0.1), ('FILLED', '0.755')])
    assert submit(connected(tmp_path, b)) == 'CONF-1'
    assert waits == [2.0, 3.0, 5.0, 10.0] and b.asked == ['CONF-1'] * 4
    assert outcome(tmp_path) == observed('FILLED')


def test_the_adapter_records_exactly_the_statuses_reconciliation_treats_as_terminal():
    import fidelity_reconcile
    assert fidelity_live.TERMINAL_STATUSES == fidelity_reconcile.TERMINAL


def test_d1_waits_are_fixed_and_bounded():
    assert fidelity_live._OBSERVE_WAITS == (2.0, 3.0, 5.0, 10.0)
    assert [sum(fidelity_live._OBSERVE_WAITS[:i + 1]) for i in range(4)] == [2.0, 5.0, 10.0, 20.0]


def test_still_working_after_the_last_look_records_nothing(tmp_path, waits):
    b = Observed([('WORKING', 0.0)] * 4)
    live = connected(tmp_path, b)
    assert submit(live) == 'CONF-1'
    assert sum(waits) == 20.0 and len(b.asked) == 4
    assert not (tmp_path / 'order-outcomes').exists()
    assert live.observations == [{'client_order_id': CID, 'observed': 'none'}]
    b.statuses.clear()  # next session: Fidelity no longer lists it
    assert live.order_status(CID) is None  # unknown, exactly as 068


@pytest.mark.parametrize('executed', [0.754, 0.756, 7.55, 'x', True, float('nan'), float('inf'), -0.755])
def test_filled_with_another_quantity_records_nothing(tmp_path, executed):
    live = connected(tmp_path, Observed([('FILLED', executed)]))
    assert submit(live) == 'CONF-1'
    assert not (tmp_path / 'order-outcomes').exists()
    assert live.observations == [{'client_order_id': CID, 'observed': 'quantity_mismatch'}]


@pytest.mark.parametrize('executed', [None, 0.755, '0.755', 0.7552])
def test_filled_with_the_same_or_no_quantity_is_recorded(tmp_path, executed):
    submit(connected(tmp_path, Observed([('FILLED', executed)])))
    assert outcome(tmp_path) == observed('FILLED')


@pytest.mark.parametrize('status,code', [('Cancelled', 'CANCELLED'), ('expired', 'EXPIRED'), ('REJECTED', 'REJECTED')])
def test_any_terminal_status_is_recorded_normalized(tmp_path, status, code):
    submit(connected(tmp_path, Observed([(status, 0.0)])))
    assert outcome(tmp_path) == observed(code)


def test_both_numbers_are_looked_up_and_supersede_the_placed_record(tmp_path):
    b = Observed([(None, None), ('FILLED', 0.755)], place_conf='CONF-P')
    assert submit(connected(tmp_path, b)) == 'CONF-P'
    assert b.asked == ['CONF-1', 'CONF-P']
    assert outcome(tmp_path) == observed('FILLED', ('CONF-1', 'CONF-P'))


@pytest.mark.parametrize('failure', [RuntimeError('SYNTHETIC_PRIVATE_TOKEN'), BrokerError('x'), TimeoutError()])
def test_a_failed_look_records_nothing_and_keeps_the_placement(tmp_path, waits, failure):
    live = connected(tmp_path, Observed([failure]))
    assert submit(live) == 'CONF-1'
    assert not (tmp_path / 'order-outcomes').exists() and waits == [2.0]
    assert live.observations == [{'client_order_id': CID, 'observed': 'error BrokerError'}]
    assert 'SYNTHETIC' not in json.dumps(live.observations)


def test_a_malformed_reply_records_nothing(tmp_path):
    live = connected(tmp_path, Observed(['FILLED']))
    assert submit(live) == 'CONF-1' and not (tmp_path / 'order-outcomes').exists()
    assert live.observations[0]['observed'].startswith('error ')


def test_a_security_challenge_while_looking_still_halts(tmp_path):
    live = connected(tmp_path, Observed([SecurityChallenge('synthetic')]))
    with pytest.raises(HaltProfile):
        submit(live)
    with pytest.raises(HaltProfile):
        live.order_status(CID)


def test_a_different_existing_record_is_never_overwritten(tmp_path):
    write_outcome(tmp_path, {'client_order_id': CID, 'outcome': 'not_sent', 'conf_nums': []})
    live = connected(tmp_path, Observed([('FILLED', 0.755)]))
    assert submit(live) == 'CONF-1'
    assert outcome(tmp_path) == {'client_order_id': CID, 'outcome': 'not_sent', 'conf_nums': []}
    assert live.observations == [{'client_order_id': CID, 'observed': 'error BrokerError'}]


def test_a_broker_without_status_detail_is_not_observed(tmp_path, waits):
    live = connected(tmp_path, Hybrid())
    assert submit(live) == 'CONF-1'
    assert waits == [] and live.observations == [] and not (tmp_path / 'order-outcomes').exists()


def test_the_record_holds_no_quantity_price_or_text(tmp_path):
    submit(connected(tmp_path, Observed([('FILLED', 0.755)])))
    raw = (tmp_path / 'order-outcomes' / f'{CID}.json').read_text(encoding='utf-8')
    assert set(json.loads(raw)) == {'client_order_id', 'outcome', 'conf_nums', 'status'}
    assert '0.755' not in raw and 'DBC' not in raw


# --- FR-003: next-session status ---

def test_next_session_empty_list_returns_the_recorded_status(tmp_path):
    b = Observed([('FILLED', 0.755)])
    live = connected(tmp_path, b)
    submit(live)
    b.statuses.clear()
    assert live.order_status(CID) == 'FILLED'


@pytest.mark.parametrize('listed', ['WORKING', 'CANCELLED'])
def test_a_status_fidelity_lists_outranks_the_record(tmp_path, listed):
    b = Observed([('FILLED', 0.755)])
    live = connected(tmp_path, b)
    submit(live)
    b.statuses['CONF-1'] = listed
    assert live.order_status(CID) == listed


def test_without_a_record_nothing_found_stays_unknown(tmp_path):
    b = Observed([('WORKING', 0.0)] * 4)
    live = connected(tmp_path, b)
    submit(live)
    b.statuses.clear()
    assert live.order_status(CID) is None


@pytest.mark.parametrize('record', [
    {'client_order_id': CID, 'outcome': 'observed', 'conf_nums': ['CONF-1'], 'status': 'WORKING'},
    {'client_order_id': CID, 'outcome': 'observed', 'conf_nums': ['CONF-1']},
    {'client_order_id': CID, 'outcome': 'observed', 'conf_nums': [], 'status': 'FILLED'},
    {'client_order_id': CID, 'outcome': 'observed', 'conf_nums': ['CONF-1'], 'status': 'FILLED', 'qty': 0.755},
    {'client_order_id': CID, 'outcome': 'placed', 'conf_nums': ['CONF-1'], 'status': 'FILLED'},
    {'client_order_id': CID, 'outcome': 'observed', 'conf_nums': ['CONF-1'], 'status': ['FILLED']}])
def test_a_malformed_observation_refuses_and_blocks(tmp_path, record):
    b = Observed([('WORKING', 0.0)] * 4)
    live = connected(tmp_path, b)
    submit(live)
    b.statuses.clear()
    write_outcome(tmp_path, record)
    with pytest.raises(BrokerError, match='unreadable'):
        live.order_status(CID)


# --- LibraryBroker.status_detail reads qtyExec from the wheel's shape ---

def test_library_status_detail_reads_the_executed_quantity():
    order = NS(acct_num='FIXTURE', id_detail=NS(conf_num='C'),
               status_detail=NS(status_code='FILLED', status_desc='Filled', amount_detail=NS(qty_exec=0.755)))
    b = bare(NS(order_status=NS(get_order_status=lambda a: NS(orders=[order], account_summaries=[]))))
    assert b.status_detail('C') == ('FILLED', 0.755) and b.status('C') == 'FILLED'
    assert b.status_detail('other') == (None, None) and b.status('other') is None
    order.status_detail.amount_detail = None
    assert b.status_detail('C') == ('FILLED', None)


def test_library_status_detail_refuses_another_account():
    order = NS(acct_num='OTHER', id_detail=NS(conf_num='C'), status_detail=NS(status_code='FILLED'))
    b = bare(NS(order_status=NS(get_order_status=lambda a: NS(orders=[order], account_summaries=[]))))
    with pytest.raises(SecurityChallenge):
        b.status_detail('C')


# --- Replay of 2026-11-18 to 11-19 through live_loop.run_once ---

class Filling(Observed):
    """Fills each accepted order at once and lists it (with qtyExec) until the next session."""

    def __init__(self):
        super().__init__()
        self.cash, self.held, self.executed = 1000.0, {}, {}

    def place(self, symbol, side, quantity, conf_num):
        placed = super().place(symbol, side, quantity, conf_num)
        self.statuses[placed], self.executed[placed] = 'FILLED', quantity
        self.held[symbol] = self.held.get(symbol, 0) + quantity
        return placed

    def status_detail(self, conf_num):
        self.asked.append(conf_num)
        return self.statuses.get(conf_num), self.executed.get(conf_num)

    def positions(self):
        return {'SPAXX': 100.0, **self.held}

    def prices(self):
        return {s: 50.0 for s in self.held}  # any finite positive mark; sizing uses the closes

    def settled_cash(self, now):
        return {'amount': self.cash, 'settled_amt': self.cash, 'coreBalance': self.cash, 'as_of': now.isoformat()}


def replay_profile():
    """As on 2026-11-18: a $200 budget the whole of which may deploy in one session, so all eight
    sleeves are bought on day one and the allocation decision is executed."""
    return replace(profile(), bot_budget_usd=200.0, daily_deploy_fraction=1.0)


def two_sessions(tmp_path, monkeypatch):
    b = Filling()
    first = execute(tmp_path, profile=replay_profile(), broker=b, gate=None, arming=ARM, persist=lambda: None)
    closes = bars().copy()
    closes.loc[closes.index[-1] + timedelta(days=1)] = closes.iloc[-1]
    b.cash -= sum(q * float(closes.iloc[-1][s]) for s, q in b.held.items())  # T+1 settlement
    b.statuses.clear()  # what happened on 2026-11-19: the list no longer shows yesterday's orders
    monkeypatch.setattr(fs, '_STARTED', False)
    later = NOW + timedelta(days=1)
    arm = ArmingRecord('live_fidelity', profile().account_fingerprint, 'e' * 64, 'Camden',
                       later - timedelta(hours=1), later + timedelta(hours=1))
    second = execute(tmp_path, profile=replay_profile(), now=later, broker=b, closes=closes, gate=None,
                     arming=arm, persist=lambda: None)
    return b, first, second


def day_one_sent_all_eight(first):
    sent = [a for a in first['actions'] if a['outcome'] == 'SUBMITTED']
    assert not first.get('aborted') and first['place_calls'] == len(sent) == len(first['actions']) == 8
    assert {a['ticker'] for a in sent} == set(loop.ALLOCATION_SLEEVES) and first['decision_executed']
    return sent


def test_replay_last_order_is_released_next_session_from_its_observation(tmp_path, monkeypatch):
    b, first, second = two_sessions(tmp_path, monkeypatch)
    sent = day_one_sent_all_eight(first)
    assert first['observations'] == [{'client_order_id': a['client_order_id'], 'observed': 'FILLED'} for a in sent]
    last = sent[-1]['client_order_id']

    # Day two: reconciles with no unknown, applies the last order, passes ownership, sends nothing.
    assert not second.get('aborted') and second.get('refused') is None and not (tmp_path / 'HALTED').exists()
    assert second['place_calls'] == 0 and second['actions'] == [] and second.get('observations', []) == []
    gate = LiveSafetyGate(tmp_path / 'live-gate.sqlite', loop.ALLOCATION_SAFETY_CONFIG)
    try:
        rows = {row['client_order_id']: row for row in gate.pending_orders()}
        assert all(rows[a['client_order_id']]['terminal'] for a in sent)
    finally:
        gate.close()
    book = json.loads((tmp_path / 'bot-positions.json').read_text(encoding='utf-8'))
    assert all(book['orders'][a['client_order_id']]['applied'] for a in sent)
    assert set(book['positions']) == set(b.held) == set(loop.ALLOCATION_SLEEVES)
    assert all(book['positions'][s] == pytest.approx(q, abs=1e-12) for s, q in b.held.items())
    assert last in {p.stem for p in (tmp_path / 'order-outcomes').glob('*.json')}


def test_replay_without_the_observation_reproduces_the_2026_11_19_halt(tmp_path, monkeypatch):
    monkeypatch.setattr(fidelity_live, '_OBSERVE_WAITS', ())
    _, first, second = two_sessions(tmp_path, monkeypatch)
    day_one_sent_all_eight(first)
    assert all(o['observed'] == 'none' for o in first['observations']) and len(first['observations']) == 8
    assert second['abort_kind'] == 'ReconciliationBlocked' and second['place_calls'] == 0
    assert 'unknown' in second['failure']['detail'] and (tmp_path / 'HALTED').exists()


def test_require_reconciled_releases_an_observed_reservation():
    class Adapter:
        def order_status(self, cid):
            return 'FILLED'
    from test_057_reconcile import Gate as ReservationGate
    gate = ReservationGate(CID)
    assert require_reconciled(gate, Adapter(), now=NOW)[0] == {'client_order_id': CID, 'state': 'released', 'status': 'FILLED'}
