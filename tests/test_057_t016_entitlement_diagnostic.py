"""057 T016 / D-9: redacted entitlement facts in the FR-013 record. Synthetic fixtures only; every socket is blocked."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import httpx
import pytest
import context  # noqa: F401
from test_057_q139 import blocked, broker as bare  # noqa: F401  (autouse fixture)
from test_057_q135 import Broker, process, ENV  # noqa: F401  (autouse fixture)
from test_057_q137 import execute
import fidelity_live
from fidelity_live import SecurityChallenge, _label

URL = 'https://digital.fidelity.com/ftgw/digital/pico/api/v1/context/security'
ROOT = Path(__file__).resolve().parents[1]
ATP = {'display': 'ATP', 'value': 'true', 'classification': 'product'}
RESPONSE = {
    'employeeIndicator': 'SYNTHETIC_EMPLOYEE',
    'personaReferences': [{'realm': 'SYNTHETIC_REALM', 'role': 'SYNTHETIC_ROLE'}],
    'internalSystemIds': [{'type': 'SYNTHETIC_TYPE', 'ID': 'SYNTHETIC_INTERNAL_ID'}],
    'entitlements': [ATP, {'display': 'RTQ', 'value': 'FALSE', 'classification': 'quotes'}],
    'errors': [],
}


def broker(client=None):
    b = bare(client)
    b.failure, b.trace = None, []
    return b


def respond(b, payload, url=URL, method='POST', status=200):
    b._response_hook(httpx.Response(status, json=payload, request=httpx.Request(method, url, json={})))


def facts(payload):
    b = broker()
    respond(b, payload)
    return b.diagnostic()['entitlement']


def context_of(payload):
    """The refusal's inputs as the audited model derives them from the same payload."""
    rows = payload.get('entitlements', [])
    has = any(r.get('display') == 'ATP' and r.get('value', '').lower() == 'true' for r in rows)
    return NS(has_atp_access=has, errors=payload.get('errors', []))


def login_with(b, payload):
    def login(*a, **k):
        respond(b, payload)
    b._client = NS(login=login, security_context=NS(get_context=lambda: context_of(payload)))
    b.login('fixture', 'fixture', 'fixture')


def test_healthy_response_records_names_and_normalized_values():
    d = facts(RESPONSE)
    assert d['entitlement_count'] == 2 and d['error_count'] == 0 and d['errors'] == []
    assert d['entitlements'] == [{'display': 'ATP', 'classification': 'product', 'value': 'true'},
                                 {'display': 'RTQ', 'classification': 'quotes', 'value': 'false'}]
    assert d['keys'] == sorted(RESPONSE)


def test_internal_ids_personas_and_other_values_never_recorded():
    text = json.dumps(facts(RESPONSE))
    assert 'SYNTHETIC' not in text


@pytest.mark.parametrize('value', ['Z12345678', 'x123', 'A' * 33, 'has.dot', 'a@b.example', '12ab', '', None, 7, ['ATP'], 'line\nbreak', 'ATP\n'])
def test_label_masks_anything_but_short_plain_text(value):
    assert _label(value) == '*'


@pytest.mark.parametrize('value', ['ATP', 'Trader Plus', 'FT-Plus_2', 'L2', 'A' * 32])
def test_label_keeps_short_plain_names(value):
    assert _label(value) == value


def test_account_like_entitlement_fields_are_masked():
    d = facts({'entitlements': [{'display': 'Z12345678', 'classification': 'acct 99887766', 'value': 'Z12345678'}], 'errors': []})
    assert d['entitlements'] == [{'display': '*', 'classification': '*', 'value': 'other'}]
    assert '12345678' not in json.dumps(d) and '99887766' not in json.dumps(d)


@pytest.mark.parametrize('value,expected', [('true', 'true'), ('TRUE', 'true'), ('false', 'false'), ('False', 'false'),
                                            ('Y', 'other'), ('', 'other'), (True, 'other'), (None, 'other'), (1, 'other')])
def test_value_is_only_true_false_or_other(value, expected):
    assert facts({'entitlements': [{'display': 'ATP', 'value': value}]})['entitlements'][0]['value'] == expected


def test_top_level_key_names_masked_and_capped():
    payload = {'acct Z12345678': 1, **{f'key{chr(97 + i % 26)}{chr(97 + i // 26)}': i for i in range(60)}}
    d = facts(payload)
    assert '*' in d['keys'] and len(d['keys']) == 40 and '12345678' not in json.dumps(d)


def test_rows_and_errors_are_capped_but_counted():
    d = facts({'entitlements': [ATP] * 100, 'errors': [{'code': 1}] * 9})
    assert d['entitlement_count'] == 100 and len(d['entitlements']) == 60
    assert d['error_count'] == 9 and len(d['errors']) == 5


def test_error_records_shape_and_short_codes_never_message_text():
    d = facts({'errors': [{'code': 4031, 'type': 'NOT_ENTITLED', 'status': 'Denied', 'message': 'SECRET TEXT acct Z12345678',
                           'detail': 'SECRET DETAIL'}]})
    assert d['errors'] == [{'keys': ['code', 'detail', 'message', 'status', 'type'], 'code': 4031, 'type': 'NOT_ENTITLED', 'status': 'Denied'}]
    assert 'SECRET' not in json.dumps(d) and '12345678' not in json.dumps(d)


@pytest.mark.parametrize('code', [12345678, 'Z12345678', 'A long free text error message over limit', True, {'x': 'SECRET'}, 1.5])
def test_error_code_that_could_be_an_identifier_is_masked(code):
    assert facts({'errors': [{'code': code}]})['errors'][0]['code'] == '*'


def test_non_dict_error_records_only_its_type():
    d = facts({'errors': ['SECRET TEXT', 7]})
    assert d['errors'] == [{'kind': 'str'}, {'kind': 'int'}]


@pytest.mark.parametrize('payload,kind', [(['SECRET'], 'list'), ('SECRET', 'str'), (7, 'int'), (False, 'bool')])
def test_unknown_top_level_shape_records_only_its_type(payload, kind):
    assert facts(payload) == {'kind': kind}


@pytest.mark.parametrize('rows', ['SECRET', {'ATP': 'true'}, None, 7])
def test_entitlements_of_another_type_add_no_rows(rows):
    d = facts({'entitlements': rows, 'accessList': ['SECRET']})
    assert 'entitlements' not in d and 'entitlement_count' not in d
    assert d['keys'] == ['accessList', 'entitlements'] and 'SECRET' not in json.dumps(d)


def test_non_dict_rows_record_only_their_type():
    assert facts({'entitlements': ['SECRET', 7]})['entitlements'] == [{'kind': 'str'}, {'kind': 'int'}]


def test_missing_errors_and_entitlements_are_distinguishable_from_empty():
    d = facts({'other': 1})
    assert d == {'keys': ['other']}


def test_only_the_security_context_path_is_read():
    b = broker()
    respond(b, RESPONSE, url='https://digital.fidelity.com/ftgw/digital/pico/api/v1/context/other')
    assert 'entitlement' not in b.diagnostic()


def test_no_entitlement_key_until_observed():
    assert broker().diagnostic() == {'reason': None, 'totp_step': False, 'responses': []}


def test_unparseable_body_records_trace_and_no_facts():
    b = broker()
    b._response_hook(httpx.Response(200, content=b'<html>SECRET</html>', request=httpx.Request('POST', URL, json={})))
    d = b.diagnostic()
    assert 'entitlement' not in d and d['responses'][0]['status'] == 200 and 'SECRET' not in json.dumps(d)


def test_trace_entry_is_kept_when_facts_cannot_be_built(monkeypatch):
    def boom(_): raise RuntimeError('SECRET')
    monkeypatch.setattr(fidelity_live, '_entitlement_facts', boom)
    b = broker()
    respond(b, RESPONSE)
    d = b.diagnostic()
    assert 'entitlement' not in d and d['responses'][-1]['status'] == 200 and 'SECRET' not in json.dumps(d)


def test_broken_facts_never_change_a_guard(monkeypatch):
    def boom(_): raise RuntimeError('diagnostic defect')
    monkeypatch.setattr(fidelity_live, '_entitlement_facts', boom)
    b = broker()
    with pytest.raises(SecurityChallenge, match='Fidelity entitlement refused|authentication or entitlement'):
        login_with(b, {'entitlements': [], 'errors': []})
    assert b.diagnostic()['reason'] == 'Fidelity entitlement refused'
    with pytest.raises(SecurityChallenge, match='Fidelity session refused'):
        respond(b, {}, status=403)


def test_response_account_guard_still_fires_on_this_path():
    b = broker()
    with pytest.raises(SecurityChallenge, match='Fidelity response account refused'):
        respond(b, {'acctNum': 'OTHER', 'entitlements': []})
    assert b.diagnostic()['reason'] == 'Fidelity response account refused'
    assert 'OTHER' not in json.dumps(b.diagnostic())


def test_healthy_context_still_logs_in():
    b = broker()
    login_with(b, RESPONSE)
    assert b.diagnostic()['reason'] is None and b.diagnostic()['entitlement']['entitlements'][0]['display'] == 'ATP'


@pytest.mark.parametrize('payload', [
    {'entitlements': [{'display': 'TraderPlus', 'value': 'true'}], 'errors': []},
    {'entitlements': [{'display': 'ATP', 'value': 'false'}], 'errors': []},
    {'entitlements': [], 'errors': []},
    {'errors': []},
    {'entitlements': [ATP], 'errors': [{'code': 1}]},
    {'entitlements': [ATP], 'errors': ['x']},
])
def test_every_refusal_condition_still_refuses_and_is_explained(payload):
    b = broker()
    with pytest.raises(SecurityChallenge, match='Fidelity authentication or entitlement refused'):
        login_with(b, payload)
    d = b.diagnostic()
    assert d['reason'] == 'Fidelity entitlement refused' and 'entitlement' in d


def test_refusal_condition_is_byte_identical():
    source = (ROOT / 'exec/fidelity_live.py').read_text(encoding='utf-8')
    assert source.count("if getattr(context, 'has_atp_access', None) is not True or getattr(context, 'errors', None) != []:\n"
                        "                raise SecurityChallenge('Fidelity entitlement refused')\n") == 1


class DiagBroker(Broker):
    def __init__(self, payload, **kw):
        super().__init__(**kw)
        self._payload = payload
    def diagnostic(self):
        b = broker()
        respond(b, self._payload)
        return b.diagnostic()


def saved(tmp_path):
    return json.loads(next((tmp_path / 'preview-sessions').glob('*.json')).read_text(encoding='utf-8'))


def test_facts_reach_the_saved_failure_record_and_the_halt_still_latches(tmp_path):
    r = execute(tmp_path, broker=DiagBroker(RESPONSE, login_error=SecurityChallenge('PRIVATE')))
    assert r['aborted'] and (tmp_path / 'HALTED').exists() and r['place_calls'] == 0
    assert saved(tmp_path)['failure']['login']['entitlement']['entitlements'][0]['display'] == 'ATP'
    assert 'SYNTHETIC' not in json.dumps(saved(tmp_path))


def test_credential_in_a_label_still_blanks_the_record(tmp_path):
    password = ENV['FIDELITY_LIVE_PASSWORD']
    b = Broker(login_error=SecurityChallenge('x'))
    b.diagnostic = lambda: {'reason': None, 'totp_step': False, 'responses': [],
                            'entitlement': {'entitlements': [{'display': password, 'classification': '*', 'value': 'true'}]}}
    r = execute(tmp_path, broker=b)
    assert r['checks'] == ['sensitive output refused'] and 'failure' not in r
    assert (tmp_path / 'HALTED').exists() and password not in json.dumps(saved(tmp_path))


def test_real_audited_model_agrees_with_the_recorded_facts():
    """With the SDK installed, the real model and client transport give the same answer as the facts."""
    pytest.importorskip('pydantic')
    try:
        import fidelity_sdk
        client = fidelity_sdk.client()
    except Exception:
        pytest.skip('audited SDK not installed')
    client._http._transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        'entitlements': [{'display': 'TraderPlus', 'value': 'true', 'classification': 'product'}], 'errors': [],
        'internalSystemIds': [{'type': 'x', 'ID': 'SYNTHETIC_INTERNAL_ID'}]}))
    b = broker(NS(login=lambda *a, **k: None, security_context=client.security_context))
    client._http.event_hooks['response'].append(b._response_hook)
    with pytest.raises(SecurityChallenge):
        b.login('fixture', 'fixture', 'fixture')
    d = b.diagnostic()
    assert d['reason'] == 'Fidelity entitlement refused'
    assert d['entitlement']['entitlements'] == [{'display': 'TraderPlus', 'classification': 'product', 'value': 'true'}]
    assert 'SYNTHETIC' not in json.dumps(d)
