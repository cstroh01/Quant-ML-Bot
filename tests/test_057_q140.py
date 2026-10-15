"""Synthetic credentials only. No real vault, broker or credential env lookup."""
import os
import socket
import sys
from types import SimpleNamespace, ModuleType
import pytest
import context  # noqa
import fidelity_launch as launcher

VALUES = {name: 'SYNTHETIC-' + str(i) + '-secret' for i, name in enumerate(launcher.CREDENTIAL_NAMES)} | {'FIDELITY_LIVE_FP_KEY':'ab'*32}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    def blocked(*a, **k): raise AssertionError('Network forbidden')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    # Mutants cannot overwrite or expose a real parent credential value.
    for name in launcher.CREDENTIAL_NAMES: monkeypatch.setenv(name, 'PARENT-FIXTURE')


@pytest.mark.parametrize('platform', ['win32', 'linux'])
def test_credentials_only_in_child_env_exit_code_and_no_output(platform, capsys):
    parent = {'PATH': 'SYNTHETIC-PATH', 'UNRELATED': 'retained'}
    if platform == 'linux': parent.update(VALUES)
    before = dict(parent); actual_parent = dict(os.environ)
    reads = []; calls = []
    def get(service, name): reads.append((service, name)); return VALUES[name]
    def spawn(argv, **kwargs):
        calls.append((argv, kwargs))
        assert argv == ['fake-child', '--flag', 'non-secret']
        assert kwargs == {'env': before | VALUES, 'check': False}
        assert kwargs['env'] is not parent
        return SimpleNamespace(returncode=23)
    assert launcher.launch(['fake-child', '--flag', 'non-secret'], platform=platform,
                           environ=parent, get_password=get, spawn=spawn) == 23
    assert parent == before and dict(os.environ) == actual_parent
    assert reads == ([(launcher.SERVICE, n) for n in launcher.CREDENTIAL_NAMES] if platform == 'win32' else [])
    assert len(calls) == 1 and capsys.readouterr() == ('', '')


@pytest.mark.parametrize('platform', ['win32', 'linux'])
@pytest.mark.parametrize('missing', list(VALUES))
@pytest.mark.parametrize('value', [None, '', '   '])
def test_each_missing_value_refuses_before_spawn(platform, missing, value):
    synthetic = VALUES | {missing: value}; calls = []
    with pytest.raises(launcher.LaunchRefused):
        launcher.launch(['fake-child'], platform=platform, environ=synthetic,
                        get_password=lambda service, name: synthetic[name], spawn=lambda *a, **k: calls.append(1))
    assert calls == []


def test_windows_never_falls_back_to_inherited_values():
    calls = []
    with pytest.raises(launcher.LaunchRefused):
        launcher.launch(['fake-child'], platform='win32', environ=VALUES,
                        get_password=lambda *a: None, spawn=lambda *a, **k: calls.append(1))
    assert not calls


def test_linux_never_imports_keyring(monkeypatch):
    import builtins
    original = builtins.__import__
    def guard(name, *a, **k):
        assert not name.startswith('keyring'), 'Linux imported keyring'
        return original(name, *a, **k)
    monkeypatch.setattr(builtins, '__import__', guard)
    assert launcher.launch(['fake-child'], platform='linux', environ=VALUES,
        spawn=lambda *a, **k: SimpleNamespace(returncode=0)) == 0


def test_windows_default_is_native_backend_with_exact_service(monkeypatch):
    module = ModuleType('keyring.backends.Windows'); reads = []
    class Vault:
        def get_password(self, service, name): reads.append((service, name)); return VALUES[name]
    module.WinVaultKeyring = Vault
    monkeypatch.setitem(sys.modules, 'keyring.backends.Windows', module)
    assert launcher.launch(['fake-child'], platform='win32', environ={},
        spawn=lambda *a, **k: SimpleNamespace(returncode=0)) == 0
    assert reads == [(launcher.SERVICE, n) for n in launcher.CREDENTIAL_NAMES]


@pytest.mark.parametrize('where', ['vault', 'child'])
def test_backend_exception_redacted_by_cli(where, monkeypatch, capsys):
    def fail(*a, **k): raise RuntimeError(VALUES['FIDELITY_LIVE_PASSWORD'])
    original = launcher.launch
    monkeypatch.setattr(launcher, 'launch', lambda command: original(command, platform='win32', environ={},
        get_password=fail if where == 'vault' else lambda service, name: VALUES[name],
        spawn=fail))
    assert launcher.main(['--', 'fake-child']) == 2
    output = capsys.readouterr()
    assert output.out == '' and output.err == 'Credential launch refused\n'


@pytest.mark.parametrize('missing', list(VALUES))
def test_missing_cli_names_only_missing_reference(missing, monkeypatch, capsys):
    original = launcher.launch; synthetic = VALUES | {missing: None}
    monkeypatch.setattr(launcher, 'launch', lambda command: original(command, platform='win32', environ={},
        get_password=lambda service, name: synthetic[name], spawn=lambda *a, **k: pytest.fail('Spawned')))
    assert launcher.main(['--', 'fake-child']) == 2
    assert capsys.readouterr() == ('', 'Missing credential: '+missing+'\n')


def test_linux_real_child_synthetic_env_and_status(capsys):
    # Exercise env= with a genuine local child; values are synthetic, never inherited credentials.
    command = [sys.executable, '-c',
        "import os,sys; sys.exit(19 if os.environ['FIDELITY_LIVE_ACCOUNT']=='SYNTHETIC-3-secret' else 91)"]
    parent = {k: v for k, v in os.environ.items() if k not in launcher.CREDENTIAL_NAMES} | VALUES
    assert launcher.launch(command, platform='linux', environ=parent) == 19
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('argv', [[], ['--'], ['fake-child'], ['--help']])
def test_bad_cli_never_loads_credentials(argv, monkeypatch, capsys):
    monkeypatch.setattr(launcher, 'launch', lambda *a: pytest.fail('Must not read credentials'))
    assert launcher.main(argv) == 2
    assert capsys.readouterr().err.startswith('Usage:')


def test_unsupported_host_refuses_before_vault_or_spawn():
    with pytest.raises(launcher.LaunchRefused):
        launcher.launch(['fake-child'], platform='darwin', environ={},
            get_password=lambda *a: pytest.fail('Vault read'), spawn=lambda *a, **k: pytest.fail('Spawned'))


@pytest.mark.parametrize('platform',['win32','linux'])
def test_fingerprint_mode_only_hmac(platform,monkeypatch,capsys):
    import hashlib,hmac
    values=VALUES|{'FIDELITY_LIVE_FP_KEY':'ab'*32}
    original=launcher.fingerprint
    monkeypatch.setattr(launcher,'fingerprint',lambda:original(platform=platform,environ=values,get_password=lambda service,name:values[name]))
    assert launcher.main(['--fingerprint'])==0
    assert capsys.readouterr()==(hmac.new(bytes.fromhex(values['FIDELITY_LIVE_FP_KEY']),values['FIDELITY_LIVE_ACCOUNT'].encode(),hashlib.sha256).hexdigest()+'\n','')

@pytest.mark.parametrize('missing',list(VALUES))
def test_fingerprint_missing_exits_two(missing,monkeypatch,capsys):
    values=VALUES|{'FIDELITY_LIVE_FP_KEY':'ab'*32,missing:None}; original=launcher.fingerprint
    monkeypatch.setattr(launcher,'fingerprint',lambda:original(platform='linux',environ=values))
    assert launcher.main(['--fingerprint'])==2 and capsys.readouterr().out==''

@pytest.mark.parametrize('key',['ab','AB'*32,'z'*64])
def test_invalid_key_never_spawns(key):
    with pytest.raises(launcher.LaunchRefused):
        launcher.launch(['fake-child'],platform='linux',environ=VALUES|{'FIDELITY_LIVE_FP_KEY':key},spawn=lambda *a,**k:pytest.fail('Spawned'))
