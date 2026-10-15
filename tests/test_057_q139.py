"""Q139: inert SDK-shaped fakes only; every socket is blocked."""
from datetime import datetime, timezone
import socket
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
import context  # noqa: F401
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'exec'))
from fidelity_live import LibraryBroker, SecurityChallenge, HaltProfile, FidelityLive
from test_057_fidelity_live import live_profile, ENV

NOW = datetime(2026, 10, 15, 15, tzinfo=timezone.utc)
STAMP = int(NOW.timestamp() * 1000)

@pytest.fixture(autouse=True)
def blocked(monkeypatch):
    def deny(*a, **k): raise AssertionError('network forbidden')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)

def broker(client=None):
    b = LibraryBroker.__new__(LibraryBroker)
    b._LibraryBroker__account = 'FIXTURE'
    b._client = client or NS()
    b.totp_step = False
    return b

def test_nested_status_defect():
    order = NS(acct_num='FIXTURE', id_detail=NS(conf_num='C'), status_detail=NS(status_code='FILLED', status_desc='Filled'))
    b = broker(NS(order_status=NS(get_order_status=lambda a: NS(orders=[order]))))
    assert b.status('C') == 'FILLED'
    assert b.status('other') is None

def test_auth_halt_defect(tmp_path):
    def fail(*a, **k): raise RuntimeError('SYNTHETIC_PRIVATE_TOKEN')
    b = broker(NS(login=fail))
    live = FidelityLive(live_profile(), broker=b, state_dir=tmp_path, environ=ENV)
    with pytest.raises(HaltProfile) as caught: live.connect()
    assert 'SYNTHETIC_PRIVATE_TOKEN' not in str(caught.value)
    with pytest.raises(HaltProfile): live.positions()

def test_inner_exception_text_redacted():
    def fail(*a, **k): raise RuntimeError('SYNTHETIC_PRIVATE_TOKEN')
    with pytest.raises(SecurityChallenge) as caught: broker(NS(login=fail)).login('fixture', 'fixture', 'fixture')
    assert 'SYNTHETIC_PRIVATE_TOKEN' not in str(caught.value)
    assert caught.value.__suppress_context__

@pytest.mark.parametrize('host', ['evil.test', 'fidelity.com.evil.test', 'evilfidelity.com'])
def test_host_and_redirect_refused(host):
    import httpx
    b = broker()
    with pytest.raises(SecurityChallenge): b._request_hook(httpx.Request('GET', 'https://' + host))
    response = httpx.Response(302, headers={'location': 'https://' + host}, request=httpx.Request('GET', 'https://digital.fidelity.com/x'))
    with pytest.raises(SecurityChallenge): b._response_hook(response)

@pytest.mark.parametrize('status,payload,ok', [(200, {'responseBaseInfo': {'status': {'code': 1201}}}, True),
    (401, {}, False), (403, {}, False), (200, {}, False),
    (200, {'responseBaseInfo': {'status': {'code': 9999}}}, False)])
def test_auth_payload(status, payload, ok):
    import httpx
    b = broker(); b._totp_present = True
    response = httpx.Response(status, json=payload, request=httpx.Request('POST', 'https://ecaap.fidelity.com/user/session/login'))
    if ok:
        b._response_hook(response); assert b.totp_step
    else:
        with pytest.raises(SecurityChallenge): b._response_hook(response)

@pytest.mark.parametrize('context', [NS(has_atp_access=False, errors=[]), NS(has_atp_access=True, errors=['bad']), NS(errors=[])])
def test_context_refused(context):
    b = broker(NS(login=lambda *a, **k: None, security_context=NS(get_context=lambda: context)))
    with pytest.raises(SecurityChallenge): b.login('fixture', 'fixture', 'fixture')

def cash_client(amount=12.5, stamp=STAMP, account='FIXTURE'):
    timing = NS(as_of_date_time=stamp, cash_detail=NS(settled_amt=amount,core_balance=100.0), buying_power_detail=NS(cash=9999))
    balance = NS(acct_num=account, recent_balance_detail=timing, intraday_balance_detail=None, close_balance_detail=None)
    return NS(balances=NS(get_balances=lambda a: NS(accounts=[balance])))

def test_settled_cash_exact_and_boundary():
    b = broker(cash_client())
    assert b.settled_cash(NOW)['amount'] == 12.5
    assert b.settled_cash(NOW)['settled_amt'] == 12.5 and b.settled_cash(NOW)['coreBalance'] == 100.0
    assert b.settled_cash(NOW)['as_of'] == NOW.isoformat()
    with pytest.raises(SecurityChallenge): broker(cash_client(stamp=STAMP-86400000)).settled_cash(NOW)
    with pytest.raises(SecurityChallenge): broker(cash_client(stamp=STAMP+1000)).settled_cash(NOW)
    with pytest.raises(SecurityChallenge): b.settled_cash(NOW.replace(tzinfo=None))

@pytest.mark.parametrize('amount', [None, float('nan'), float('inf'), -1, True])
def test_bad_cash_no_buying_power_fallback(amount):
    with pytest.raises(SecurityChallenge): broker(cash_client(amount=amount)).settled_cash(NOW)

def test_wrong_account_and_missing_snapshot():
    with pytest.raises(SecurityChallenge): broker(cash_client(account='OTHER')).settled_cash(NOW)
    with pytest.raises(SecurityChallenge): broker(NS(balances=NS(get_balances=lambda a: NS(accounts=[])))).settled_cash(NOW)

def test_ny_midnight_and_missing_balance_gap():
    now = datetime(2026, 10, 15, 5, 30, tzinfo=timezone.utc)
    previous_ny_day = int(datetime(2026, 10, 15, 1, 30, tzinfo=timezone.utc).timestamp()*1000)
    with pytest.raises(SecurityChallenge): broker(cash_client(stamp=previous_ny_day)).settled_cash(now)
    with pytest.raises(SecurityChallenge): broker(cash_client(stamp=None)).settled_cash(now)

def test_place_preserves_security_challenge():
    def fail(*a): raise SecurityChallenge('synthetic')
    b = broker(NS(equity_orders=NS(place_order=fail)))
    b._order = lambda *a: None
    with pytest.raises(SecurityChallenge): b.place('SPY', 'B', 0.1, 'C')

def test_hooks_installed_without_header_changes(monkeypatch):
    import fidelity_sdk
    headers = {'User-Agent': 'SDK-static'}
    http = NS(event_hooks={'request': [], 'response': []}, headers=headers.copy())
    monkeypatch.setattr(fidelity_sdk, 'client', lambda: NS(_http=http))
    LibraryBroker('FIDELITY_LIVE_ACCOUNT', environ={'FIDELITY_LIVE_ACCOUNT': 'FIXTURE'})
    assert http.headers == headers
    assert len(http.event_hooks['request']) == len(http.event_hooks['response']) == 1

def test_sdk_source_pin_refuses_before_import(tmp_path, monkeypatch):
    import fidelity_sdk
    for name in fidelity_sdk.AUDITED:
        path = tmp_path / (name + '.py'); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('tampered')
    monkeypatch.setattr(fidelity_sdk.metadata, 'distribution', lambda _: NS(version='0.2.2', locate_file=lambda _: tmp_path))
    monkeypatch.setattr(fidelity_sdk.importlib, 'import_module', lambda _: pytest.fail('Imported unverified SDK'))
    with pytest.raises(RuntimeError, match='source hash'): fidelity_sdk.client()

def test_login_redirect_and_noninteger_auth_code():
    import httpx
    b = broker()
    req = httpx.Request('POST', 'https://ecaap.fidelity.com/user/session/login')
    with pytest.raises(SecurityChallenge): b._response_hook(httpx.Response(302, headers={'location': '/prgw/digital/signin/retail'}, request=req))
    with pytest.raises(SecurityChallenge): b._response_hook(httpx.Response(200, json={'responseBaseInfo': {'status': {'code': 1200.0}}}, request=req))

def test_cash_holiday_session_refused():
    holiday = datetime(2026, 12, 25, 15, tzinfo=timezone.utc)
    with pytest.raises(SecurityChallenge): broker(cash_client(stamp=int(holiday.timestamp()*1000))).settled_cash(holiday)

@pytest.mark.parametrize('path',['/position/v2','/balance/detail/v2','/accounts/orders/status-summary','/equity/preview/v1','/equity/place/v1'])
def test_dedicated_account_request_and_response_guards(path):
    import httpx
    b=broker()
    for payload in ({},{'acctNum':'OTHER'},{'accounts':[{'acctNum':'FIXTURE'},{'acctNum':'OTHER'}]}):
        with pytest.raises(SecurityChallenge): b._request_hook(httpx.Request('POST','https://digital.fidelity.com'+path,json=payload))
    req=httpx.Request('POST','https://digital.fidelity.com'+path,json={'acctNum':'FIXTURE'})
    b._request_hook(req)
    with pytest.raises(SecurityChallenge): b._response_hook(httpx.Response(200,json={'acctNum':'OTHER'},request=req))

def test_sdk_calls_filter_only_bound_account():
    seen=[]
    def positions(accounts): seen.append(accounts); return NS(accounts=[NS(acct_num='FIXTURE',positions=[])])
    def status(accounts): seen.append(accounts); return NS(orders=[],account_summaries=[])
    client=cash_client(); get=client.balances.get_balances
    def balances(accounts): seen.append(accounts); return get(accounts)
    client.balances.get_balances=balances; client.positions=NS(get_positions=positions); client.order_status=NS(get_order_status=status)
    b=broker(client); b.positions(); b.status('C'); b.settled_cash(NOW)
    assert seen==[['FIXTURE']]*3
