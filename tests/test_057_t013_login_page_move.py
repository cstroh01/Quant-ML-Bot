"""057 T013 / D-6a: only the SDK's pre-credential page load may follow Fidelity's login-page move.

Synthetic fakes and an in-memory httpx transport only; every socket is blocked.
"""
from types import SimpleNamespace as NS
import httpx
import pytest
import context  # noqa: F401
from test_057_q139 import blocked  # noqa: F401  (autouse fixture)
from test_057_t012_failure_diagnostics import broker
from fidelity_live import LibraryBroker, SecurityChallenge

QUERY = 'exp=new&AuthRedUrl=https%3A%2F%2Fdigital.fidelity.com%2Fftgw%2Fdigital%2Fportfolio%2Fextendsession'
OLD = 'https://digital.fidelity.com/prgw/digital/login/atp'
NEW = 'https://digital.fidelity.com/prgw/digital/signin/atp'
AUTH = 'https://ecaap.fidelity.com/user/session/login'


def fresh():
    b = broker()
    b._auth_started = False
    return b


def moved(b, source=OLD + '?' + QUERY, location=NEW + '?' + QUERY, status=308, method='GET'):
    b._response_hook(httpx.Response(status, headers={'location': location}, request=httpx.Request(method, source)))


def sdk_client(b, routes):
    """An httpx client built like the SDK's (follow_redirects=True) with the broker's hooks installed."""
    seen = []
    def handler(request):
        seen.append((request.method, request.url.host, request.url.path))
        status, headers = routes.get(request.url.path, (200, {}))
        return httpx.Response(status, headers=headers, json={})
    client = httpx.Client(follow_redirects=True, transport=httpx.MockTransport(handler),
                          event_hooks={'request': [b._request_hook], 'response': [b._response_hook]})
    return client, seen


def test_new_broker_has_not_started_auth(monkeypatch):
    import fidelity_sdk
    http = NS(event_hooks={'request': [], 'response': []}, headers={})
    monkeypatch.setattr(fidelity_sdk, 'client', lambda: NS(_http=http))
    assert LibraryBroker('FIDELITY_LIVE_ACCOUNT', environ={'FIDELITY_LIVE_ACCOUNT': 'FIXTURE'})._auth_started is False


def test_sdk_page_load_follows_the_moved_login_page():
    b = fresh()
    client, seen = sdk_client(b, {'/prgw/digital/login/atp': (308, {'location': NEW + '?' + QUERY})})
    client.get(OLD, params={'exp': 'new', 'AuthRedUrl': 'https://digital.fidelity.com/ftgw/digital/portfolio/extendsession'})
    assert b._auth_started is False
    client.request('DELETE', AUTH, json={})
    assert seen == [('GET', 'digital.fidelity.com', '/prgw/digital/login/atp'),
                    ('GET', 'digital.fidelity.com', '/prgw/digital/signin/atp'),
                    ('DELETE', 'ecaap.fidelity.com', '/user/session/login')]
    assert b._auth_started is True and b.diagnostic()['reason'] is None
    assert b.diagnostic()['responses'][0]['redirect'] == '/prgw/digital/signin/atp'


def test_moved_page_may_not_redirect_again():
    b = fresh()
    client, seen = sdk_client(b, {'/prgw/digital/login/atp': (308, {'location': NEW + '?' + QUERY}),
                                  '/prgw/digital/signin/atp': (308, {'location': NEW.replace('atp', 'retail') + '?' + QUERY})})
    with pytest.raises(SecurityChallenge, match='Fidelity redirect refused'): client.get(OLD + '?' + QUERY)
    assert len(seen) == 2 and b.diagnostic()['reason'] == 'Fidelity redirect refused'


def test_exact_move_allowed_directly():
    b = fresh()
    moved(b)
    assert b.diagnostic()['reason'] is None


def test_move_refused_after_any_auth_request():
    b = fresh()
    b._request_hook(httpx.Request('DELETE', AUTH, json={}))
    with pytest.raises(SecurityChallenge, match='Fidelity redirect refused'): moved(b)


def test_move_refused_when_the_flag_is_missing():
    b = broker()
    assert not hasattr(b, '_auth_started')
    with pytest.raises(SecurityChallenge, match='Fidelity redirect refused'): moved(b)


@pytest.mark.parametrize('change', [
    {'status': 301}, {'status': 302}, {'status': 307}, {'method': 'POST'},
    {'location': 'https://digital.fidelity.com/prgw/digital/signin/retail?' + QUERY},
    {'location': 'https://digital.fidelity.com/prgw/digital/login/full-page?' + QUERY},
    {'location': 'https://www.fidelity.com/prgw/digital/signin/atp?' + QUERY},
    {'location': 'http://digital.fidelity.com/prgw/digital/signin/atp?' + QUERY},
    {'location': NEW + '?exp=new&AuthRedUrl=https%3A%2F%2Fevil.test%2F'},
    {'location': NEW},
    {'source': 'https://digital.fidelity.com/prgw/digital/login/full-page?' + QUERY},
    {'source': 'https://ecaap.fidelity.com/prgw/digital/login/atp?' + QUERY},
    {'source': 'http://digital.fidelity.com/prgw/digital/login/atp?' + QUERY},
    {'source': 'https://www.fidelity.com/prgw/digital/login/atp?' + QUERY,
     'location': 'https://www.fidelity.com/prgw/digital/signin/atp?' + QUERY},
], ids=['301', '302', '307', 'post', 'signin-retail', 'login-full-page', 'other-fidelity-host', 'http-target',
        'query-changed', 'query-dropped', 'other-source-path', 'other-source-host', 'http-source', 'both-other-host'])
def test_every_near_miss_still_refused(change):
    b = fresh()
    with pytest.raises(SecurityChallenge, match='Fidelity redirect refused|Fidelity request host refused'): moved(b, **change)
    assert b.diagnostic()['reason'] in ('Fidelity redirect refused', 'Fidelity request host refused')


def test_page_load_does_not_start_auth():
    b = fresh()
    b._request_hook(httpx.Request('GET', NEW + '?' + QUERY))
    assert b._auth_started is False
