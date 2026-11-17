"""Spec 068: Fidelity placement acceptance. Fakes shaped like fidelity-trader-api 0.2.2's order
models; every socket is blocked; no real broker, account or credential. EXAMPLE — NOT A RESULT."""
from datetime import timedelta
import json
from types import SimpleNamespace as NS

import httpx
import pytest

import context  # noqa: F401
from test_057_q139 import NOW, blocked, broker as bare  # noqa: F401  (autouse fixture)
from test_057_q135 import ENV, Broker, live_profile, process  # noqa: F401  (autouse fixture)
from test_057_q137 import bars, execute, profile
from test_057_reconcile import Gate as ReservationGate
import fidelity_session as fs
from fidelity_live import (BrokerError, FidelityLive, PlacementRejected, PreviewRefused,
                           SubmissionUnknown, _order_reply_facts)
from fidelity_reconcile import ReconciliationBlocked, reconcile, require_reconciled
from live_safety_gate import LiveSafetyGate, OrderIntent
import live_loop as loop
from mode_config import ArmingRecord

CID = 'qmb-20261015-' + 'a' * 24
ARM = ArmingRecord('live_fidelity', live_profile().account_fingerprint, 'e' * 64, 'Camden',
                   NOW - timedelta(hours=1), NOW + timedelta(hours=1))
PLACE_URL = 'https://dpservice.fidelity.com/ftgw/dp/orderentry/equity/place/v1'


class Reply:
    """Shaped like the wheel's EquityPreviewResponse / EquityPlaceResponse: the code and number sit
    in orderConfirmDetail; is_validated means "V" and is_accepted means "A"."""

    def __init__(self, code, conf='CONF-1', acct='FIXTURE', detail=True):
        self.acct_num = acct
        self.order_confirm_detail = NS(resp_type_code=code, conf_num=conf) if detail else None

    @property
    def conf_num(self):
        return self.order_confirm_detail.conf_num if self.order_confirm_detail else None

    @property
    def is_validated(self):
        return self.order_confirm_detail is not None and self.order_confirm_detail.resp_type_code == 'V'

    @property
    def is_accepted(self):
        return self.order_confirm_detail is not None and self.order_confirm_detail.resp_type_code == 'A'


def library(preview=None, place=None, hook=None):
    """The real LibraryBroker over a fake client; the wheel's request model is not installed."""
    sent = []
    def preview_order(order):
        sent.append('preview')
        return preview or Reply('V')
    def place_order(order, conf):
        sent.append(('place', conf))
        if hook:
            hook(b)
        return place or Reply('A')
    b = bare(NS(equity_orders=NS(preview_order=preview_order, place_order=place_order)))
    b._order = lambda *a: None
    b.sent = sent
    return b


class Hybrid(Broker):
    """057 Q135's fake session (login, cash, positions) with the real LibraryBroker preview/place."""

    def __init__(self, place_code='A', place_conf=None):
        super().__init__()
        self.place_code, self.place_conf, self.statuses, self.n = place_code, place_conf, {}, 0
        def preview_order(order):
            self.n += 1
            return Reply('V', conf=f'CONF-{self.n}')
        def place_order(order, conf):
            return Reply(self.place_code, conf=self.place_conf or (conf if self.place_code == 'A' else None))
        self.lib = bare(NS(equity_orders=NS(preview_order=preview_order, place_order=place_order)))
        self.lib._order = lambda *a: None

    def preview(self, symbol, side, quantity):
        self.calls.append(('preview', symbol, side, quantity))
        return self.lib.preview(symbol, side, quantity)

    def place(self, symbol, side, quantity, conf_num):
        self.calls.append(('place', symbol, side, quantity, conf_num))
        placed = self.lib.place(symbol, side, quantity, conf_num)
        self.statuses[placed] = 'WORKING'
        return placed

    def status(self, conf_num):
        return self.statuses.get(conf_num)

    def diagnostic(self):
        return self.lib.diagnostic()


def connected(tmp_path, b):
    live = FidelityLive(live_profile(), broker=b, state_dir=tmp_path, environ=ENV)
    live.connect()
    return live


def submit(live, cid=CID):
    return live.submit(OrderIntent(cid, 'DBC', 0.755), arming=ARM, now=NOW)


def outcome(tmp_path, cid=CID):
    return json.loads((tmp_path / 'order-outcomes' / f'{cid}.json').read_text(encoding='utf-8'))


def write_outcome(tmp_path, record, cid=CID):
    (tmp_path / 'order-outcomes').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'order-outcomes' / f'{cid}.json').write_text(json.dumps(record), encoding='utf-8')


# --- FR-002: LibraryBroker.place counts only "A" ---

def test_controls_validated_preview_and_accepted_reply_return_their_own_numbers():
    assert library(preview=Reply('V', conf='CONF-7')).preview('DBC', 'B', 0.755) == 'CONF-7'
    assert library(place=Reply('A', conf='CONF-9')).place('DBC', 'B', 0.755, 'CONF-1') == 'CONF-9'


def test_accepted_reply_without_a_number_is_unknown_never_the_preview_number():
    with pytest.raises(SubmissionUnknown):
        library(place=Reply('A', conf=None)).place('DBC', 'B', 0.755, 'CONF-1')


@pytest.mark.parametrize('reply', [Reply('R'), Reply('V'), Reply(None), Reply(''), Reply('a'),
                                   Reply('R', conf=None), Reply(None, detail=False)])
def test_any_other_reply_is_rejected_naming_only_the_reduced_code(reply):
    with pytest.raises(PlacementRejected) as caught:
        library(place=reply).place('DBC', 'B', 0.755, 'CONF-1')
    assert caught.value.conf_num == reply.conf_num
    assert str(caught.value).startswith('placement not accepted: respTypeCode ')
    assert 'CONF' not in str(caught.value) and 'FIXTURE' not in str(caught.value)


# --- FR-001: LibraryBroker.preview counts only "V" with a number ---

@pytest.mark.parametrize('reply', [Reply('A'), Reply('R'), Reply(None), Reply(None, detail=False), Reply('V', conf=None)])
def test_unvalidated_preview_is_refused(reply):
    with pytest.raises(PreviewRefused) as caught:
        library(preview=reply).preview('DBC', 'B', 0.755)
    assert isinstance(caught.value, BrokerError) and 'CONF' not in str(caught.value)


# --- FR-001 to FR-003 through FidelityLive.submit ---

def test_refused_preview_records_not_sent_and_never_places(tmp_path):
    b = Hybrid()
    b.lib._client.equity_orders.preview_order = lambda order: Reply('R')
    with pytest.raises(PreviewRefused, match='respTypeCode R'):
        submit(connected(tmp_path, b))
    assert [c[0] for c in b.calls] == ['preview'] and not (tmp_path / 'intents.jsonl').exists()
    assert outcome(tmp_path) == {'client_order_id': CID, 'outcome': 'not_sent', 'conf_nums': []}


def test_rejected_placement_is_rejected_not_unknown_and_marked(tmp_path):
    b = Hybrid(place_code='R')
    live = connected(tmp_path, b)
    with pytest.raises(PlacementRejected, match='respTypeCode R'):
        submit(live)
    assert [c[0] for c in b.calls] == ['preview', 'place']
    assert outcome(tmp_path) == {'client_order_id': CID, 'outcome': 'rejected', 'conf_nums': ['CONF-1']}
    assert len((tmp_path / 'intents.jsonl').read_text(encoding='utf-8').splitlines()) == 1


def test_a_different_existing_record_makes_a_rejection_unknown(tmp_path):
    write_outcome(tmp_path, {'client_order_id': CID, 'outcome': 'not_sent', 'conf_nums': []})
    with pytest.raises(SubmissionUnknown):
        submit(connected(tmp_path, Hybrid(place_code='R')))


def test_accepted_placement_with_another_number_is_recorded_and_found(tmp_path):
    b = Hybrid(place_conf='CONF-P')
    live = connected(tmp_path, b)
    assert submit(live) == 'CONF-P'
    assert outcome(tmp_path) == {'client_order_id': CID, 'outcome': 'placed', 'conf_nums': ['CONF-1', 'CONF-P']}
    assert live.order_status(CID) == 'WORKING'


def test_same_number_acceptance_writes_no_record(tmp_path):
    live = connected(tmp_path, Hybrid())
    assert submit(live) == 'CONF-1' and not (tmp_path / 'order-outcomes').exists()
    assert live.order_status(CID) == 'WORKING'


# --- FR-003: order_status says REJECTED only when Fidelity agrees ---

@pytest.mark.parametrize('listed', ['CONF-1', 'CONF-P'])
def test_an_order_fidelity_lists_keeps_its_real_status(tmp_path, listed):
    b = Hybrid(place_code='R', place_conf='CONF-P')
    live = connected(tmp_path, b)
    with pytest.raises(PlacementRejected):
        submit(live)
    assert outcome(tmp_path)['conf_nums'] == ['CONF-1', 'CONF-P']
    b.statuses[listed] = 'FILLED'
    assert live.order_status(CID) == 'FILLED'


def test_without_a_marker_nothing_found_stays_unknown(tmp_path):
    b = Hybrid()
    b.lib._client.equity_orders.place_order = lambda order, conf: (_ for _ in ()).throw(TimeoutError())
    live = connected(tmp_path, b)
    with pytest.raises(SubmissionUnknown):
        submit(live)
    assert live.order_status(CID) is None and live.order_status('qmb-20261015-' + 'b' * 24) is None


def test_not_sent_marker_counts_only_without_an_intent(tmp_path):
    live = connected(tmp_path, Hybrid())
    write_outcome(tmp_path, {'client_order_id': CID, 'outcome': 'not_sent', 'conf_nums': []})
    assert live.order_status(CID) == 'REJECTED'
    write_outcome(tmp_path, {'client_order_id': CID, 'outcome': 'rejected', 'conf_nums': ['CONF-1']})
    assert live.order_status(CID) is None  # a rejection without its intent is inconsistent: unknown


@pytest.mark.parametrize('record', [
    {'client_order_id': CID, 'outcome': 'rejected', 'conf_nums': []},
    {'client_order_id': CID, 'outcome': 'not_sent', 'conf_nums': ['CONF-1']},
    {'client_order_id': 'qmb-other', 'outcome': 'not_sent', 'conf_nums': []},
    {'client_order_id': CID, 'outcome': 'filled', 'conf_nums': ['CONF-1']},
    {'client_order_id': CID, 'outcome': 'rejected', 'conf_nums': ['CONF-1'], 'extra': 1},
    {'client_order_id': CID, 'outcome': 'rejected', 'conf_nums': [7]},
    'not json'])
def test_a_malformed_marker_refuses_and_blocks(tmp_path, record):
    live = connected(tmp_path, Hybrid(place_code='R'))
    with pytest.raises(PlacementRejected):
        submit(live)
    if record == 'not json':
        (tmp_path / 'order-outcomes' / f'{CID}.json').write_text('{', encoding='utf-8')
    else:
        write_outcome(tmp_path, record)
    with pytest.raises(BrokerError, match='unreadable'):
        live.order_status(CID)
    gate = ReservationGate(CID)
    assert reconcile(gate, live, now=NOW)[0]['state'] == 'status_unavailable' and gate.released == []


def test_marker_and_empty_status_list_is_rejected_and_released(tmp_path):
    live = connected(tmp_path, Hybrid(place_code='R'))
    with pytest.raises(PlacementRejected):
        submit(live)
    assert live.order_status(CID) == 'REJECTED'
    gate = ReservationGate(CID)
    assert require_reconciled(gate, live, now=NOW)[0] == {'client_order_id': CID, 'state': 'released', 'status': 'REJECTED'}
    assert gate.released == [(CID, 'REJECTED')]


# --- FR-004: ReconciliationBlocked says why ---

def test_blocked_message_names_each_id_and_state_with_reduced_codes():
    class Adapter:
        def order_status(self, cid):
            if cid == 'c':
                raise BrokerError('status failed: BrokerError')
            return {'a': None, 'b': 'HELD 12345678', 'd': 'Odd Status'}[cid]
    with pytest.raises(ReconciliationBlocked) as caught:
        require_reconciled(ReservationGate('a', 'b', 'c', 'd'), Adapter(), now=NOW)
    assert str(caught.value) == ('4 reservation(s) without a known outcome: a unknown, b unrecognized *, '
                                 'c status_unavailable, d unrecognized Odd Status')


# --- FR-005: reduced reply facts in the FR-013 record ---

PAYLOAD = {'place': {
    'acctNum': 'FIXTURE',
    'orderConfirmDetail': {'respTypeCode': 'R', 'confNum': 'C12345678', 'netAmount': 12.34},
    'messages': [{'code': 'ORD123', 'type': 'ERROR', 'severity': 'HIGH', 'text': 'Not held for this account'},
                 {'msgCode': 'NH', 'errorCodeDesc': 'Order cannot be placed', 'detail': 'Plain words here'}]}}


def respond(b, payload, url=PLACE_URL):
    request = httpx.Request('POST', url, json={'request': {'acctNum': 'FIXTURE'}})
    b._response_hook(httpx.Response(200, json=payload, request=request))


def rejected_diagnostic(payload):
    b = library(place=Reply('R'), hook=lambda b: respond(b, payload))
    b.failure, b.trace = None, []
    with pytest.raises(PlacementRejected):
        b.place('DBC', 'B', 0.755, 'CONF-1')
    return b, b.diagnostic()


def test_refused_placement_records_reduced_reply_facts():
    _, facts = rejected_diagnostic(PAYLOAD)
    assert facts['order_reply'] == {
        'endpoint': 'place', 'resp_type_code': 'R',
        'keys': {'top': ['place'], 'reply': ['acctNum', 'messages', 'orderConfirmDetail'],
                 'orderConfirmDetail': ['confNum', 'netAmount', 'respTypeCode']},
        'entry_count': 2,
        'entries': [{'keys': ['code', 'severity', 'text', 'type'], 'code': '*', 'type': 'ERROR', 'severity': 'HIGH'},
                    {'keys': ['detail', 'errorCodeDesc', 'msgCode'], 'msgCode': 'NH'}]}


def test_message_text_amounts_numbers_and_account_never_recorded():
    _, facts = rejected_diagnostic(PAYLOAD)
    text = json.dumps(facts)
    for secret in ('Not held', 'cannot be placed', 'Plain words', 'C12345678', '12.34', 'FIXTURE', 'ORD123', '0.755', 'CONF'):
        assert secret not in text, secret


def test_facts_are_capped_and_masked():
    payload = {'place': {'orderConfirmDetail': {f'k{i}': i for i in range(30)} | {'respTypeCode': 'R'},
                         'errors': [{'code': i, 'type': f'T{i}'} for i in range(9)] + [{'code': 123456}]}}
    facts = _order_reply_facts('place', payload)
    assert len(facts['keys']['orderConfirmDetail']) == 20 and facts['entry_count'] == 10
    assert len(facts['entries']) == 5 and facts['entries'][0] == {'keys': ['code', 'type'], 'code': 0, 'type': 'T0'}
    assert _order_reply_facts('place', ['x']) == {'endpoint': 'place', 'kind': 'list'}
    assert _order_reply_facts('place', {'errors': [123456, {'code': 123456}]})['entries'] == [{'kind': 'int'}, {'keys': ['code'], 'code': '*'}]


def test_a_later_refusal_never_reports_an_earlier_reply():
    b, _ = rejected_diagnostic(PAYLOAD)
    b._client.equity_orders.place_order = lambda order, conf: Reply('X')
    with pytest.raises(PlacementRejected):
        b.place('DBC', 'B', 0.755, 'CONF-2')
    assert b.diagnostic()['order_reply'] == {'endpoint': 'place', 'resp_type_code': 'X'}


def test_accepted_orders_add_no_reply_facts():
    b = library(place=Reply('A'), hook=lambda b: respond(b, {'place': {'orderConfirmDetail': {'respTypeCode': 'A'}}}))
    b.failure, b.trace = None, []
    b.place('DBC', 'B', 0.755, 'CONF-1')
    assert 'order_reply' not in b.diagnostic()


# --- Replay of 2026-11-16 through live_loop.run_once ---

def test_replay_refusal_halts_then_next_run_releases_and_proceeds(tmp_path, monkeypatch):
    b = Hybrid(place_code='R')
    b.settled_cash = lambda now: {'amount': 1000.0, 'settled_amt': 1000.0, 'coreBalance': 1000.0, 'as_of': now.isoformat()}
    r = execute(tmp_path, broker=b, gate=None, arming=ARM, persist=lambda: None)
    assert r['abort_kind'] == 'PlacementRejected' and r['place_calls'] == 1 and (tmp_path / 'HALTED').exists()
    assert [c[0] for c in b.calls] == ['preview', 'place']  # no other sleeve was sent
    assert r['failure']['login']['order_reply'] == {'endpoint': 'place', 'resp_type_code': 'R'}
    assert 'respTypeCode R' in r['failure']['detail']
    [marker] = (tmp_path / 'order-outcomes').glob('*.json')
    first = json.loads(marker.read_text(encoding='utf-8'))['client_order_id']

    (tmp_path / 'HALTED').unlink()  # Camden's review, then the next session
    monkeypatch.setattr(fs, '_STARTED', False)
    b.place_code = 'A'
    closes = bars().copy()
    closes.loc[closes.index[-1] + timedelta(days=1)] = closes.iloc[-1]
    later = NOW + timedelta(days=1)
    arm = ArmingRecord('live_fidelity', profile().account_fingerprint, 'e' * 64, 'Camden',
                       later - timedelta(hours=1), later + timedelta(hours=1))
    r = execute(tmp_path, now=later, broker=b, closes=closes, gate=None, arming=arm, persist=lambda: None)
    assert not r.get('aborted') and r['place_calls'] > 0
    gate = LiveSafetyGate(tmp_path / 'live-gate.sqlite', loop.ALLOCATION_SAFETY_CONFIG)
    try:
        assert [row['terminal'] for row in gate.pending_orders() if row['client_order_id'] == first] == [True]
    finally:
        gate.close()
    book = json.loads((tmp_path / 'bot-positions.json').read_text(encoding='utf-8'))
    assert book['orders'][first]['applied'] is True and book['positions'] == {}
