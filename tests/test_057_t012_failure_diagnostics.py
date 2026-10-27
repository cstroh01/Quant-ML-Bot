"""057 T012 / FR-013: redacted failure diagnostics. Synthetic fakes only; every socket is blocked."""
import json
from types import SimpleNamespace as NS
import httpx
import pytest
import context  # noqa: F401
from test_057_q139 import blocked, broker as bare  # noqa: F401  (autouse fixture)
from test_057_q135 import Broker, process, ENV  # noqa: F401  (autouse fixture)
from test_057_q137 import execute
import fidelity_live
from fidelity_live import SecurityChallenge
import live_loop as loop

LOGIN = 'https://ecaap.fidelity.com/user/session/login'


def broker(client=None):
    """The q139 inert broker plus the two attributes LibraryBroker.__init__ now sets."""
    b = bare(client)
    b.failure, b.trace = None, []
    return b


def written(tmp_path):
    return ''.join(p.read_text(encoding='utf-8') for p in tmp_path.rglob('*') if p.is_file() and p.suffix in ('.json', '.jsonl', ''))


def test_library_login_error_records_type_name_only():
    def fail(*a, **k): raise RuntimeError('SYNTHETIC_PRIVATE_TOKEN acct Z12345678')
    b = broker(NS(login=fail))
    with pytest.raises(SecurityChallenge) as caught: b.login('fixture', 'fixture', 'fixture')
    assert str(caught.value) == 'Fidelity authentication or entitlement refused'
    d = b.diagnostic()
    assert d['reason'] == 'library RuntimeError' and d['responses'] == []
    assert 'SYNTHETIC' not in json.dumps(d) and '12345678' not in json.dumps(d)


def test_own_refusal_kept_even_when_the_library_swallows_it():
    b = broker()
    def login(*a, **k):
        req = httpx.Request('POST', 'https://digital.fidelity.com/ftgw/context', json={})
        try:
            b._response_hook(httpx.Response(200, json={'acctNum': 'OTHER'}, request=req))
        except Exception:
            pass  # the SDK's context initialization swallows exceptions (research.md row 3)
        raise RuntimeError('later library failure')
    b._client = NS(login=login)
    with pytest.raises(SecurityChallenge): b.login('fixture', 'fixture', 'fixture')
    d = b.diagnostic()
    assert d['reason'] == 'Fidelity response account refused'
    assert d['responses'] == [{'host': 'digital.fidelity.com', 'method': 'POST', 'path': '/ftgw/context', 'status': 200}]
    assert 'OTHER' not in json.dumps(d)


def test_entitlement_refusal_is_recorded_as_its_fixed_text():
    b = broker(NS(login=lambda *a, **k: None, security_context=NS(get_context=lambda: NS(has_atp_access=False, errors=[]))))
    with pytest.raises(SecurityChallenge): b.login('fixture', 'fixture', 'fixture')
    assert b.diagnostic()['reason'] == 'Fidelity entitlement refused'


def test_response_trace_masks_paths_and_drops_queries():
    b = broker()
    response = httpx.Response(302, headers={'location': '/prgw/digital/login/full-page?token=SECRETQUERY&acct=Z12345678'},
                              request=httpx.Request('POST', LOGIN + '?session=SECRETQUERY'))
    with pytest.raises(SecurityChallenge): b._response_hook(response)
    req = httpx.Request('POST', 'https://digital.fidelity.com/accounts/Z12345678/' + 'abcdefghijklmnopqrstuvwxyz' + '/positions', json={'acctNum': 'FIXTURE'})
    b._response_hook(httpx.Response(200, json={'acctNum': 'FIXTURE'}, request=req))
    first, second = b.diagnostic()['responses']
    assert first == {'host': 'ecaap.fidelity.com', 'method': 'POST', 'path': '/user/session/login', 'status': 302,
                     'redirect': '/prgw/digital/login/full-page', 'auth_code': None}
    assert second['path'] == '/accounts/*/*/positions'
    assert b.diagnostic()['reason'] == 'Fidelity redirect refused'
    text = json.dumps(b.diagnostic())
    assert 'SECRETQUERY' not in text and '12345678' not in text and 'FIXTURE' not in text


def test_foreign_host_is_named_other():
    b = broker()
    with pytest.raises(SecurityChallenge): b._response_hook(httpx.Response(200, request=httpx.Request('GET', 'https://evil.test/x')))
    assert b.diagnostic()['responses'][0]['host'] == 'other'
    assert b.diagnostic()['reason'] == 'Fidelity request host refused'


@pytest.mark.parametrize('code,raises', [(1201, False), (1200, False), (9999, True)])
def test_integer_auth_code_recorded(code, raises):
    b = broker(); b._totp_present = True
    response = httpx.Response(200, json={'responseBaseInfo': {'status': {'code': code}}}, request=httpx.Request('POST', LOGIN))
    if raises:
        with pytest.raises(SecurityChallenge): b._response_hook(response)
    else:
        b._response_hook(response)
    assert b.diagnostic()['responses'][0]['auth_code'] == code
    assert b.diagnostic()['totp_step'] is (code == 1201)


def test_non_integer_auth_code_is_none():
    b = broker()
    response = httpx.Response(200, json={'responseBaseInfo': {'status': {'code': 'SECRET'}}}, request=httpx.Request('POST', LOGIN))
    with pytest.raises(SecurityChallenge): b._response_hook(response)
    assert b.diagnostic()['responses'][0]['auth_code'] is None and 'SECRET' not in json.dumps(b.diagnostic())


def test_trace_keeps_the_latest_twenty():
    b = broker()
    for status in range(200, 225):
        b._response_hook(httpx.Response(status, request=httpx.Request('GET', 'https://digital.fidelity.com/x')))
    assert [r['status'] for r in b.diagnostic()['responses']] == list(range(205, 225))


@pytest.mark.parametrize('request_, reason', [
    (httpx.Request('GET', 'https://evil.test/x'), 'Fidelity request host refused'),
    (httpx.Request('POST', 'https://digital.fidelity.com/position/v2', json={}), 'Fidelity account filter refused'),
    (httpx.Request('POST', 'https://digital.fidelity.com/position/v2', content=b'not json'), 'Fidelity account filter missing')])
def test_request_time_refusal_recorded_before_any_response(request_, reason):
    b = broker()
    with pytest.raises(SecurityChallenge, match=reason): b._request_hook(request_)
    assert b.diagnostic() == {'reason': reason, 'totp_step': False, 'responses': []}


def test_broken_diagnostics_never_change_a_guard(monkeypatch):
    def boom(*a, **k): raise RuntimeError('diagnostic defect')
    monkeypatch.setattr(fidelity_live, '_masked_path', boom)
    b = broker()
    b._response_hook(httpx.Response(200, request=httpx.Request('GET', 'https://digital.fidelity.com/x')))
    with pytest.raises(SecurityChallenge, match='Fidelity session refused'):
        b._response_hook(httpx.Response(403, request=httpx.Request('GET', 'https://digital.fidelity.com/x')))
    assert b.diagnostic()['responses'] == [] and b.diagnostic()['reason'] == 'Fidelity session refused'


class DiagBroker(Broker):
    def __init__(self, diagnostic=None, **kw):
        super().__init__(**kw)
        self._diagnostic = diagnostic or {'reason': 'Fidelity redirect refused', 'totp_step': False, 'responses': []}
    def diagnostic(self):
        if isinstance(self._diagnostic, Exception): raise self._diagnostic
        return self._diagnostic


def test_login_halt_records_stage_and_login_facts(tmp_path):
    r = execute(tmp_path, broker=DiagBroker(login_error=SecurityChallenge('PRIVATE')))
    assert r['aborted'] and r['abort_kind'] == 'HaltProfile' and (tmp_path / 'HALTED').exists()
    assert r['failure'] == {'stage': 'login', 'kind': 'HaltProfile', 'detail': 'live_fidelity: Fidelity security challenge; halted',
                            'login': {'reason': 'Fidelity redirect refused', 'totp_step': False, 'responses': []}}
    saved = json.loads(next((tmp_path / 'preview-sessions').glob('*.json')).read_text(encoding='utf-8'))
    assert saved['failure'] == r['failure'] and r['place_calls'] == 0
    assert 'PRIVATE' not in written(tmp_path)


def test_stage_and_own_message_after_login(tmp_path):
    b = Broker()
    def cash(now): raise ValueError('library text Z12345678')
    b.settled_cash = cash
    r = execute(tmp_path, broker=b)
    assert r['failure'] == {'stage': 'settled_cash', 'kind': 'BrokerError', 'detail': 'settled_cash failed: ValueError', 'login': None}
    assert '12345678' not in written(tmp_path)


def test_foreign_exception_message_never_written(tmp_path, monkeypatch):
    def plan(*a, **k): raise RuntimeError('LIBRARY_TEXT acct Z12345678')
    monkeypatch.setattr(loop.AllocationPlanner, 'plan', plan)
    r = execute(tmp_path)
    assert r['failure'] == {'stage': 'allocation', 'kind': 'RuntimeError', 'detail': None, 'login': None}
    assert 'LIBRARY_TEXT' not in written(tmp_path) and (tmp_path / 'HALTED').exists()


def test_credential_in_diagnostic_blanks_the_record(tmp_path):
    password = ENV['FIDELITY_LIVE_PASSWORD']
    b = DiagBroker(diagnostic={'reason': password, 'totp_step': False, 'responses': []}, login_error=SecurityChallenge('x'))
    r = execute(tmp_path, broker=b)
    assert r['checks'] == ['sensitive output refused'] and 'failure' not in r
    assert password not in written(tmp_path) and (tmp_path / 'HALTED').exists()


def test_raising_diagnostic_still_latches_the_halt(tmp_path):
    r = execute(tmp_path, broker=DiagBroker(diagnostic=RuntimeError('SECRET'), login_error=SecurityChallenge('x')))
    assert r['failure']['login'] is None and r['failure']['stage'] == 'login'
    assert (tmp_path / 'HALTED').exists() and 'SECRET' not in written(tmp_path)


def test_clean_record_unchanged(tmp_path):
    r = execute(tmp_path)
    assert r['clean'] and not r.get('aborted') and 'failure' not in r
