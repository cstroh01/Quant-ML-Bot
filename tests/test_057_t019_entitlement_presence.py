"""057 T019 / D-11: login needs a clean, non-empty entitlement list, not ATP. Synthetic fakes only; every socket is blocked."""
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
import context  # noqa: F401
from test_057_q139 import blocked, broker  # noqa: F401  (autouse fixture)
from fidelity_live import SecurityChallenge

ROOT = Path(__file__).resolve().parents[1]


def row(display, value, classification='access'):
    return NS(display=display, value=value, classification=classification)


# The shape probe 1 recorded on 2026-11-02 (names and normalized values only): ATP false, quotes on.
PROBE_1 = [row('ATP', 'false'), row('RTQ', 'true'), row('ATBT', 'false'), row('ProfessionalQuotes', 'false'),
           row('ALL', 'other', 'fortress'), row('p1', 'other', 'CVI')]


def login(context):
    b = broker(NS(login=lambda *a, **k: None, security_context=NS(get_context=lambda: context)))
    b.login('fixture', 'fixture', 'fixture')
    return b


@pytest.mark.parametrize('rows', [PROBE_1, [row('RTQ', 'true')], [row('ATP', 'true')], [row('ATP', 'false')]],
                         ids=['probe-1-shape', 'no-atp-row', 'atp-true', 'atp-false-only'])
def test_clean_non_empty_context_logs_in_whatever_atp_says(rows):
    b = login(NS(entitlements=list(rows), errors=[]))
    assert b.diagnostic()['reason'] is None


@pytest.mark.parametrize('context', [
    NS(entitlements=[], errors=[]),
    NS(entitlements=[NS(display='')], errors=[]),
    NS(entitlements=[NS(value='true')], errors=[]),
    NS(errors=[]),
    NS(entitlements=None, errors=[]),
    NS(entitlements=tuple(PROBE_1), errors=[]),
    NS(entitlements='ATP', errors=[]),
    NS(entitlements=list(PROBE_1), errors=[{'code': 1}]),
    NS(entitlements=list(PROBE_1), errors=None),
    NS(entitlements=list(PROBE_1)),
], ids=['empty', 'blank-name', 'unnamed', 'missing', 'none', 'tuple', 'string', 'errors', 'errors-none', 'errors-missing'])
def test_anything_else_still_refuses_with_the_fixed_text(context):
    with pytest.raises(SecurityChallenge, match='Fidelity authentication or entitlement refused'):
        login(context)


def test_entitlement_refusal_still_records_its_reason():
    b = broker(NS(login=lambda *a, **k: None, security_context=NS(get_context=lambda: NS(entitlements=[], errors=[]))))
    with pytest.raises(SecurityChallenge):
        b.login('fixture', 'fixture', 'fixture')
    assert b.diagnostic()['reason'] == 'Fidelity entitlement refused'


def test_a_failed_library_login_still_refuses_before_the_context():
    def fail(*a, **k):
        raise RuntimeError('PRIVATE')
    calls = []
    b = broker(NS(login=fail, security_context=NS(get_context=lambda: calls.append(1))))
    with pytest.raises(SecurityChallenge):
        b.login('fixture', 'fixture', 'fixture')
    assert calls == [] and b.diagnostic()['reason'] == 'library RuntimeError'


def test_no_exec_module_requires_atp():
    sources = [p.read_text(encoding='utf-8') for p in (ROOT / 'exec').glob('*.py')]
    assert not any(word in s for s in sources for word in ('has_atp_access', "'ATP'", '"ATP"'))


def real_context(payload):
    """The audited SDK's own model and transport; skipped where the pinned SDK is absent."""
    import httpx
    pytest.importorskip('pydantic')
    try:
        import fidelity_sdk
        client = fidelity_sdk.client()
    except Exception:
        pytest.skip('audited SDK not installed')
    client._http._transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    return client.security_context


def test_real_model_logs_in_the_probe_1_shape():
    rows = [{'display': r.display, 'value': r.value, 'classification': r.classification} for r in PROBE_1]
    b = broker(NS(login=lambda *a, **k: None, security_context=real_context({'entitlements': rows, 'errors': []})))
    b.login('fixture', 'fixture', 'fixture')
    assert b.diagnostic()['reason'] is None


@pytest.mark.parametrize('payload', [{}, {'entitlements': [{}]}, {'entitlements': [{'display': 'RTQ'}], 'errors': [{'code': 1}]}],
                         ids=['empty-body', 'unnamed-row', 'errors'])
def test_real_model_refuses_placeholder_responses(payload):
    b = broker(NS(login=lambda *a, **k: None, security_context=real_context(payload)))
    with pytest.raises(SecurityChallenge):
        b.login('fixture', 'fixture', 'fixture')
