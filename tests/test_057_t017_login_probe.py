"""057 T017 / D-5a: supervised login probe. Synthetic fixtures only; every socket is blocked."""
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace as NS
import httpx
import pytest
import context  # noqa: F401
from test_057_q139 import blocked  # noqa: F401  (autouse fixture)
from test_057_q135 import ENV, live_profile
import fidelity_live
from fidelity_live import LibraryBroker, SecurityChallenge
import fidelity_login_probe as probe
import fidelity_session
from fidelity_preview_evidence import record_session
from gate_checklist import fidelity_preview

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'exec/fidelity_login_probe.py'
WORKFLOW = ROOT / 'ops/workflows/fidelity-login-probe.yml'
NOW = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)  # Friday 13:00 ET


class Fake:
    """A broker with the three calls the probe may make, and order calls that fail the test."""
    def __init__(self, login_error=None, cash_error=None, positions_error=None, diagnostic=None):
        self._client = NS(_http=NS(event_hooks={'request': [], 'response': []}), equity_orders=object(), order_status=object())
        self.errors, self.calls = (login_error, cash_error, positions_error), []
        self._diagnostic = diagnostic or {'reason': None, 'totp_step': True, 'responses': []}
    def login(self, *credentials):
        self.calls.append('login'); self.credentials = credentials
        if self.errors[0]: raise self.errors[0]
    def settled_cash(self, now):
        self.calls.append('settled_cash')
        if self.errors[1]: raise self.errors[1]
        return {'amount': 200.94, 'settled_amt': 200.94, 'coreBalance': 200.94, 'as_of': now.isoformat()}
    def positions(self):
        self.calls.append('positions')
        if self.errors[2]: raise self.errors[2]
        return {'SPAXX**': 200.94}
    def diagnostic(self):
        if isinstance(self._diagnostic, Exception): raise self._diagnostic
        return self._diagnostic
    def preview(self, *a): pytest.fail('preview reached')
    def place(self, *a): pytest.fail('place reached')


def ready(tmp_path, halted=True):
    state = tmp_path / 'live_fidelity'
    state.mkdir()
    (state / 'host-ready.json').write_text(json.dumps({'schema': 1, 'profile': 'live_fidelity'}), encoding='utf-8')
    if halted: (state / 'HALTED').write_text('Camden review required', encoding='utf-8')
    return state


def go(state, broker=None, **kw):
    broker = broker or Fake()
    args = dict(state=state, profile=live_profile(), pin='a' * 40, now=NOW, environ=ENV, persist=lambda: None,
                broker_factory=lambda: broker)
    args.update(kw)
    return probe.run(**args)


def saved(state, n=1):
    return json.loads((state / 'login-probes' / f'probe-{n}.json').read_text(encoding='utf-8'))


def tree(state):
    return {p.relative_to(state).as_posix(): p.read_bytes() for p in state.rglob('*') if p.is_file()}


def test_pass_runs_login_then_both_reads_only(tmp_path):
    state, b = ready(tmp_path), Fake()
    assert go(state, b) == probe.PASSED
    assert b.calls == ['login', 'settled_cash', 'positions']
    assert b.credentials == (ENV['FIDELITY_LIVE_USERNAME'], ENV['FIDELITY_LIVE_PASSWORD'], ENV['FIDELITY_LIVE_TOTP'])
    r = saved(state)
    assert r['status'] == 'passed' and r['entitlement_check'] == 'passed' and r['mode'] == 'probe'
    assert r['settled_cash'] == {'amount': 200.94, 'as_of': NOW.isoformat()}
    assert r['positions'] == {'count': 1, 'symbols': ['SPAXX**']}
    assert r['place_calls'] == 0 and r['previews'] == [] and r['library'] == fidelity_session.LIBRARY


def test_entitlement_refused_stops_before_any_read_and_records_facts(tmp_path):
    state = ready(tmp_path)
    facts = {'reason': 'Fidelity entitlement refused', 'totp_step': True, 'responses': [], 'entitlement': {'keys': ['errors']}}
    b = Fake(login_error=SecurityChallenge('PRIVATE TEXT'), diagnostic=facts)
    assert go(state, b) == probe.REFUSED
    assert b.calls == ['login']
    r = saved(state)
    assert r['failure'] == {'stage': 'login', 'kind': 'SecurityChallenge'} and r['login'] == facts
    assert 'entitlement_check' not in r and 'PRIVATE' not in json.dumps(r)


@pytest.mark.parametrize('kw,stage,calls', [
    ({'cash_error': RuntimeError('LIBRARY TEXT Z12345678')}, 'settled_cash', ['login', 'settled_cash']),
    ({'positions_error': RuntimeError('LIBRARY TEXT Z12345678')}, 'positions', ['login', 'settled_cash', 'positions'])])
def test_read_failure_records_stage_and_type_only(tmp_path, kw, stage, calls):
    state, b = ready(tmp_path), Fake(**kw)
    assert go(state, b) == probe.REFUSED and b.calls == calls
    r = saved(state)
    assert r['failure'] == {'stage': stage, 'kind': 'RuntimeError'} and r['entitlement_check'] == 'passed'
    assert 'LIBRARY' not in json.dumps(r) and '12345678' not in json.dumps(r)


def test_broker_construction_failure_is_recorded_not_raised(tmp_path):
    state = ready(tmp_path)
    def factory(): raise RuntimeError('SDK TEXT')
    assert go(state, broker_factory=factory) == probe.REFUSED
    r = saved(state)
    assert r['failure'] == {'stage': 'broker', 'kind': 'RuntimeError'} and r['login'] is None


def test_raising_diagnostic_keeps_the_record(tmp_path):
    state = ready(tmp_path)
    assert go(state, Fake(diagnostic=RuntimeError('SECRET'))) == probe.PASSED
    assert saved(state)['login'] is None and 'SECRET' not in json.dumps(saved(state))


def test_kill_refuses_without_login_or_marker(tmp_path):
    state, b = ready(tmp_path), Fake()
    (state / 'KILL').write_text('x', encoding='utf-8')
    with pytest.raises(probe.ProbeRefused, match='refused before login'): go(state, b)
    assert b.calls == [] and not (state / 'login-probes').exists()


def test_missing_halted_refuses_without_login(tmp_path):
    state, b = ready(tmp_path, halted=False), Fake()
    with pytest.raises(probe.ProbeRefused): go(state, b)
    assert b.calls == [] and not (state / 'login-probes').exists()


@pytest.mark.parametrize('kw', [
    {'login_error': SecurityChallenge('x')}, {'cash_error': SecurityChallenge('x')}, {'positions_error': SecurityChallenge('x')}, {}])
def test_halted_is_never_written_cleared_or_changed(tmp_path, kw):
    state = ready(tmp_path)
    before = (state / 'HALTED').read_bytes()
    go(state, Fake(**kw))
    assert (state / 'HALTED').read_bytes() == before


def test_writes_only_its_own_probe_file(tmp_path):
    state = ready(tmp_path)
    before = tree(state)
    go(state)
    after = tree(state)
    assert set(after) - set(before) == {'login-probes/probe-1.json'}
    assert {k: after[k] for k in before} == before
    assert not (state / 'attempts').exists() and not (state / 'preview-sessions').exists() and not (state / 'leases').exists()


def test_refuses_once_two_probes_exist_and_counts_failures(tmp_path):
    state = ready(tmp_path)
    assert go(state, Fake(login_error=SecurityChallenge('x'))) == probe.REFUSED
    assert go(state) == probe.PASSED
    b = Fake()
    with pytest.raises(probe.ProbeRefused): go(state, b)
    assert b.calls == [] and sorted(p.name for p in (state / 'login-probes').iterdir()) == ['probe-1.json', 'probe-2.json']


@pytest.mark.parametrize('name', ['probe-1.json', 'probe-junk', '.probe-1.json.77.tmp'])
def test_any_probe_file_counts_even_unreadable(tmp_path, name):
    state = ready(tmp_path)
    folder = state / 'login-probes'; folder.mkdir()
    (folder / name).write_bytes(b'\xff not json')
    (folder / 'probe-other').write_bytes(b'')
    assert probe.probes_used(state) == 2
    b = Fake()
    with pytest.raises(probe.ProbeRefused): go(state, b)
    assert b.calls == []


def test_crash_after_marker_still_counts(tmp_path):
    state = ready(tmp_path)
    class Crash(BaseException): pass
    def factory(): raise Crash()
    with pytest.raises(Crash): go(state, broker_factory=factory)
    assert saved(state)['status'] == 'started' and probe.probes_used(state) == 1


def test_marker_is_durable_before_login(tmp_path):
    state, b, seen = ready(tmp_path), Fake(), []
    def persist():
        seen.append((list(b.calls), saved(state)['status']))
    go(state, b, persist=persist)
    assert seen == [([], 'started')]


def test_failed_marker_push_means_no_login_and_still_counts(tmp_path):
    state, b = ready(tmp_path), Fake()
    def persist(): raise RuntimeError('SECRET push text')
    with pytest.raises(probe.ProbeRefused, match='not durable') as caught: go(state, b, persist=persist)
    assert b.calls == [] and 'SECRET' not in str(caught.value) and probe.probes_used(state) == 1


@pytest.mark.parametrize('kw', [
    {'pin': 'short'}, {'pin': 'A' * 40},
    {'now': datetime(2026, 10, 31, 17, 0, tzinfo=timezone.utc)},   # Saturday
    {'now': datetime(2026, 10, 30, 13, 34, tzinfo=timezone.utc)},  # 09:34 ET
    {'now': datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc)},   # 16:00 ET
    {'now': datetime(2026, 10, 30, 17, 0)},                        # naive
    {'environ': {**ENV, 'FIDELITY_LIVE_ACCOUNT': 'OTHER'}},
    {'environ': {k: v for k, v in ENV.items() if k != 'FIDELITY_LIVE_FP_KEY'}}])
def test_preflight_refusals_never_log_in(tmp_path, kw):
    state, b = ready(tmp_path), Fake()
    with pytest.raises(probe.ProbeRefused): go(state, b, **kw)
    assert b.calls == [] and not (state / 'login-probes').exists()


def test_window_edges_allowed(tmp_path):
    state = ready(tmp_path)
    assert go(state, now=datetime(2026, 10, 30, 13, 35, tzinfo=timezone.utc)) == probe.PASSED


def test_uninitialized_state_refuses(tmp_path):
    state = ready(tmp_path)
    (state / 'host-ready.json').unlink()
    with pytest.raises(probe.ProbeRefused): go(state)


@pytest.mark.parametrize('field', ['name', 'mode', 'broker'])
def test_other_profiles_refuse(tmp_path, field):
    state = ready(tmp_path)
    with pytest.raises(probe.ProbeRefused): go(state, profile=NS(**{'name': 'live_fidelity', 'mode': 'LIVE', 'broker': 'fidelity',
        'account_fingerprint': live_profile().account_fingerprint, 'credential_refs': live_profile().credential_refs, field: 'other'}))


@pytest.mark.parametrize('name', ['FIDELITY_LIVE_PASSWORD', 'FIDELITY_LIVE_USERNAME', 'FIDELITY_LIVE_TOTP', 'FIDELITY_LIVE_ACCOUNT'])
def test_credential_string_blanks_the_record(tmp_path, name):
    state = ready(tmp_path)
    b = Fake(diagnostic={'reason': 'x', 'responses': [{'path': 'prefix' + ENV[name]}]})
    assert go(state, b) == probe.BLANKED
    text = (state / 'login-probes/probe-1.json').read_text(encoding='utf-8')
    assert ENV[name] not in text and 'login' not in json.loads(text) and json.loads(text)['status'] == probe.BLANKED


def test_credential_in_a_dict_key_blanks_the_record(tmp_path):
    state = ready(tmp_path)
    b = Fake(diagnostic={ENV['FIDELITY_LIVE_PASSWORD']: 1})
    assert go(state, b) == probe.BLANKED


def test_foreign_position_symbol_is_masked(tmp_path):
    state, b = ready(tmp_path), Fake()
    b.positions = lambda: {'Z12345678 acct': 1.0, 'SPY': 2.0}
    go(state, b)
    assert saved(state)['positions'] == {'count': 2, 'symbols': ['*', 'SPY']}


def real_broker(monkeypatch, handler=None):
    import fidelity_sdk
    calls = []
    def send(request):
        calls.append(request.url.path)
        return (handler or (lambda r: httpx.Response(200, json={})))(request)
    http = httpx.Client(transport=httpx.MockTransport(send))
    def order_post(path):
        return lambda *a, **k: http.post('https://dpservice.fidelity.com' + path, json={})
    client = NS(_http=http, equity_orders=NS(preview_order=order_post('/ftgw/dp/orderentry/equity/preview/v1'),
                                             place_order=order_post('/ftgw/dp/orderentry/equity/place/v1')), order_status=NS())
    monkeypatch.setattr(fidelity_sdk, 'client', lambda: client)
    return LibraryBroker('FIDELITY_LIVE_ACCOUNT', environ=ENV), client, http, calls


def test_run_strips_order_objects_before_login(tmp_path):
    state, b, seen = ready(tmp_path), Fake(), []
    original = b.login
    def login(*credentials):
        seen.append((b._client.equity_orders, b._client.order_status, len(b._client._http.event_hooks['request'])))
        original(*credentials)
    b.login = login
    go(state, b)
    assert seen == [(None, None, 1)]


def test_real_broker_loses_its_order_objects(monkeypatch):
    b, client, _, _ = real_broker(monkeypatch)
    equity = client.equity_orders
    probe._read_only(b)
    assert client.equity_orders is None and client.order_status is None
    assert equity is not None
    for call in (lambda: b.preview('SPY', 'B', 1.0), lambda: b.place('SPY', 'B', 1.0, 'CONF'), lambda: b.status('CONF')):
        with pytest.raises(Exception): call()


@pytest.mark.parametrize('path', ['/ftgw/dp/orderentry/equity/place/v1', '/ftgw/dp/ORDERENTRY/x', '/x/equity/y', '/order-status/v1'])
def test_order_shaped_request_never_leaves_the_client(monkeypatch, path):
    b, _, http, calls = real_broker(monkeypatch)
    probe._read_only(b)
    with pytest.raises(SecurityChallenge, match='order path refused'):
        http.post('https://dpservice.fidelity.com' + path, json={})
    assert calls == []


def test_read_paths_still_pass_the_order_hook(monkeypatch):
    b, _, http, calls = real_broker(monkeypatch)
    probe._read_only(b)
    for path in ('/ftgw/digital/pico/api/v1/context/security', '/user/session/login'):
        http.get('https://ecaap.fidelity.com' + path)
    assert len(calls) == 2


def test_source_has_no_order_session_or_arming_path():
    tree_ = ast.parse(SOURCE.read_text(encoding='utf-8'))
    imported = {a.name for n in ast.walk(tree_) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module for n in ast.walk(tree_) if isinstance(n, ast.ImportFrom)}
    names = {a.name for n in ast.walk(tree_) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not imported & {'live_loop', 'fidelity_session', 'order_gateway', 'fidelity_preview_session', 'paper_loop', 'live_safety_gate'}
    assert names.isdisjoint({'FidelityLive', 'require_armed', 'ArmingRecord'})
    called = {n.func.attr for n in ast.walk(tree_) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert called.isdisjoint({'preview', 'place', 'submit', 'status', 'connect', 'preview_order', 'place_order'})
    assert called >= {'login', 'settled_cash', 'positions'}


def test_probe_record_is_refused_by_the_preview_evidence_recorder(tmp_path):
    state = ready(tmp_path)
    go(state)
    with pytest.raises(ValueError):
        record_session(state / 'login-probes/probe-1.json', root=tmp_path, gate=tmp_path / 'gate-manifest.json')
    assert not (tmp_path / 'gate-manifest.json').exists()


def test_probe_record_is_refused_by_the_gate_checklist(tmp_path):
    import hashlib
    state = ready(tmp_path)
    go(state)
    path = state / 'login-probes/probe-1.json'
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'sessions': [{'artifact': path.relative_to(tmp_path).as_posix(),
                                                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]}), encoding='utf-8')
    entry = {'type': 'fidelity_preview', 'account_fingerprint': 'a' * 64, 'artifact': 'manifest.json'}
    assert fidelity_preview(entry, tmp_path)[0] is False


def test_record_has_neither_evidence_key_and_fixed_paths():
    source = SOURCE.read_text(encoding='utf-8')
    assert "'clean'" not in source and "'challenge'" not in source and "'mode': 'probe'" in source
    assert "'attempts'" not in source and "'preview-sessions'" not in source


def test_refusal_condition_is_still_byte_identical():
    source = (ROOT / 'exec/fidelity_live.py').read_text(encoding='utf-8')
    assert source.count("if getattr(context, 'has_atp_access', None) is not True or getattr(context, 'errors', None) != []:\n"
                        "                raise SecurityChallenge('Fidelity entitlement refused')\n") == 1


@pytest.mark.parametrize('required', [
    'group: paper-loop', 'cancel-in-progress: false', "github.actor == 'cstroh01'", "inputs.confirm == 'PROBE'",
    "github.event.repository.private == true", "compare/'+pin+'...main", "not in ('ahead','identical')",
    'ref: ${{ vars.QMB_FIDELITY_PIN }}', 'persist-credentials: false', 'pip install --require-hashes --only-binary=:all: -r qmb/requirements-fidelity-host.txt',
    'python scripts/fidelity_launch.py -- python exec/fidelity_login_probe.py', 'bash ops/persist_state.sh "$GITHUB_WORKSPACE/state" fidelity-login-probe',
    'if: failure()'])
def test_workflow_requires(required):
    assert required in WORKFLOW.read_text(encoding='utf-8')


@pytest.mark.parametrize('forbidden', ['schedule:', 'cron', 'pull_request', 'repository_dispatch', 'live_loop', 'fidelity_preview_host', 'arming', 'ARMING', '--mode preview', 'HALTED'])
def test_workflow_forbids(forbidden):
    text = '\n'.join(l for l in WORKFLOW.read_text(encoding='utf-8').splitlines() if not l.startswith('#'))
    assert forbidden not in text


def test_main_failure_prints_fixed_text_only(tmp_path, capsys):
    state = ready(tmp_path)
    assert probe.main(['--pin', 'a' * 40, '--state', str(state), '--profiles', str(tmp_path / 'absent')]) == 2
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == 'Login probe refused before login\n'


@pytest.mark.parametrize('status,code,stream,text', [
    (probe.PASSED, 0, 'out', 'Login probe passed\n'), (probe.REFUSED, 2, 'err', 'Login probe failed; read the persisted record\n'),
    (probe.BLANKED, 2, 'err', 'Login probe failed; read the persisted record\n')])
def test_main_exit_codes(tmp_path, capsys, monkeypatch, status, code, stream, text):
    profiles = tmp_path / 'p.json'; profiles.write_text('[]', encoding='utf-8')
    monkeypatch.setattr(probe, 'load_profiles', lambda _: {'live_fidelity': live_profile()})
    monkeypatch.setattr(probe, 'run', lambda **k: status)
    assert probe.main(['--pin', 'a' * 40, '--state', str(tmp_path), '--profiles', str(profiles)]) == code
    assert getattr(capsys.readouterr(), stream) == text


def test_persist_child_gets_no_fidelity_credential(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(probe.os, 'environ', {**ENV, 'QMB_FIDELITY_PROFILES_JSON': 'x', 'PATH': 'p'})
    monkeypatch.setattr(probe.subprocess, 'run', lambda cmd, **k: seen.update(k, cmd=cmd))
    probe._persist(tmp_path / 'state' / 'live_fidelity')()
    assert seen['env'] == {'PATH': 'p'} and seen['check'] is True
    assert seen['cmd'][2] == str(tmp_path / 'state')
    assert fidelity_live is not None
