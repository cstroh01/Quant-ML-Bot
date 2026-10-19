"""057 T007: host boundaries with synthetic environments and fake children only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

import context  # noqa: F401
import fidelity_preview_host as host

PIN = "a" * 40
NOW = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network_or_children(monkeypatch):
    # Simulate the deployment runtime; Windows CI itself also exercises 3.13.
    monkeypatch.setattr(host.sys, "version_info", (3, 12, 13, "final", 0))
    def refused(*args, **kwargs):
        pytest.fail("real network/child forbidden")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(host.subprocess, "run", refused)


def test_other_runtime_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(host.sys, "version_info", (3, 13, 0, "final", 0))
    with pytest.raises(host.HostRefused):
        host.run(mode="check", now=NOW, environ={}, **settings(tmp_path))


def settings(tmp_path):
    state = tmp_path / "state" / "live_fidelity"
    state.mkdir(parents=True, exist_ok=True)
    (state / "host-ready.json").write_text(json.dumps({"schema": 1, "profile": "live_fidelity"}))
    return dict(pin=PIN, authorized_session="2026-10-20", state=state,
                profiles=tmp_path / "profiles.json", inputs=tmp_path / "inputs")


def record(config, **changes):
    path = config["state"] / "preview-sessions" / "2026-10-20.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(dict(session="2026-10-20", pin_sha=PIN, profile="live_fidelity",
        mode="preview", clean=True, challenge=False, place_calls=0,
        allocation=host.policy_evidence(), actions=[]) | changes))


def test_check_mode_never_reads_credentials_or_starts_child(tmp_path):
    class Unreadable(dict):
        def __iter__(self):
            pytest.fail("credential environment read")
        def get(self, *args):
            pytest.fail("credential environment read")
    assert host.run(mode="check", now=NOW, environ=Unreadable(), **settings(tmp_path)) == "CHECKED"


@pytest.mark.parametrize("stamp,authorized,accepted", [
    ("2026-10-20T13:34:59+00:00", "2026-10-20", False),
    ("2026-10-20T13:35:00+00:00", "2026-10-20", True),
    ("2026-10-20T15:59:59+00:00", "2026-10-20", True),
    ("2026-10-20T16:00:00+00:00", "2026-10-20", False),
    ("2026-11-03T14:34:59+00:00", "2026-11-03", False),
    ("2026-11-03T14:35:00+00:00", "2026-11-03", True),
    ("2026-11-03T17:00:00+00:00", "2026-11-03", False),
    ("2026-10-20T14:00:00", "2026-10-20", False),
    ("2026-10-20T14:00:00+00:00", "2026-10-19", False),
    ("2026-10-20T14:00:00+00:00", "", False),
    ("2026-10-24T14:00:00+00:00", "2026-10-24", False),
    ("2026-12-25T15:00:00+00:00", "2026-12-25", False),
])
def test_window_and_session_boundaries(tmp_path, stamp, authorized, accepted):
    config = settings(tmp_path) | {"authorized_session": authorized}
    if accepted:
        assert host.run(mode="check", now=datetime.fromisoformat(stamp), environ={}, **config) == "CHECKED"
    else:
        with pytest.raises(host.HostRefused):
            host.run(mode="check", now=datetime.fromisoformat(stamp), environ={}, **config)


@pytest.mark.parametrize("defect", ["KILL", "HALTED", "missing", "wrong_profile", "invalid_pin"])
def test_preflight_refuses_before_any_child(tmp_path, defect):
    config = settings(tmp_path)
    if defect in ("KILL", "HALTED"):
        (config["state"] / defect).touch()
    elif defect == "missing":
        (config["state"] / "host-ready.json").unlink()
    elif defect == "wrong_profile":
        (config["state"] / "host-ready.json").write_text('{"schema":1,"profile":"paper_small"}')
    else:
        config["pin"] = "main"
    with pytest.raises(host.HostRefused):
        host.run(mode="preview", now=NOW, environ={}, **config)


@pytest.mark.parametrize("mode", ["inputs", "preview"])
def test_fixed_commands_and_child_environments(tmp_path, mode):
    config = settings(tmp_path)
    parent = {name: "SYNTHETIC" for name in host.CREDENTIAL_NAMES}
    parent |= {"APCA_API_KEY_ID": "FAKE-DATA", "GH_TOKEN": "FAKE-TOKEN", "QMB_PINNED_SHA": "wrong"}
    before = dict(parent)
    calls = []
    def spawn(argv, **kwargs):
        calls.append((argv, kwargs))
        assert kwargs["capture_output"] and kwargs["check"] is False
        assert kwargs["cwd"] == host.ROOT
        assert kwargs["env"]["QMB_PINNED_SHA"] == PIN
        assert "GH_TOKEN" not in kwargs["env"]
        if mode == "inputs":
            assert all(name not in kwargs["env"] for name in host.CREDENTIAL_NAMES)
            assert argv[1:] == [str(host.ROOT / "scripts/fidelity_inputs.py"), "--out", str(config["inputs"]), "--session", "2026-10-20"]
        else:
            assert all(kwargs["env"][name] == "SYNTHETIC" for name in host.CREDENTIAL_NAMES)
            assert "APCA_API_KEY_ID" not in kwargs["env"]
            assert argv[1:5] == [str(host.ROOT / "scripts/fidelity_launch.py"), "--", host.sys.executable, str(host.ROOT / "exec/live_loop.py")]
            assert "--persist-command" in argv
            assert "--arming-file" not in argv and "--submit" not in argv
            assert argv[argv.index("--profile") + 1] == "live_fidelity"
            record(config)
        return SimpleNamespace(returncode=0, stdout=b"SYNTHETIC", stderr=b"SYNTHETIC")
    assert host.run(mode=mode, now=NOW, environ=parent, spawn=spawn, **config) == "COMPLETED"
    assert len(calls) == 1 and parent == before


@pytest.mark.parametrize("failure", ["status", "exception"])
def test_child_failure_is_redacted_and_never_retried(tmp_path, failure, capsys):
    config = settings(tmp_path)
    record(config)  # A valid old artifact must not hide a broken child-exit guard.
    calls = []
    def broken(*args, **kwargs):
        calls.append(1)
        if failure == "exception":
            raise RuntimeError("SYNTHETIC-SECRET")
        return SimpleNamespace(returncode=2, stdout=b"SYNTHETIC-SECRET", stderr=b"SYNTHETIC-SECRET")
    with pytest.raises(host.HostRefused) as result:
        host.run(mode="preview", now=NOW, environ={}, spawn=broken, **config)
    assert str(result.value) == "Preview child refused; no automatic retry"
    assert calls == [1] and capsys.readouterr() == ("", "")


@pytest.mark.parametrize("mode", ["submit", "armed", "arbitrary"])
def test_unknown_modes_refuse(tmp_path, mode):
    with pytest.raises(host.HostRefused):
        host.run(mode=mode, now=NOW, environ={}, **settings(tmp_path))


@pytest.mark.parametrize("changes", [{"mode": "submit"}, {"clean": False}, {"challenge": True},
    {"place_calls": 1}, {"pin_sha": "b" * 40}, {"allocation": {}},
    {"session": "2026-10-19"}, {"refused": "unsettled_cash"},
    {"actions": [{"outcome": "DENIED"}]}])
def test_successful_child_is_not_clean_evidence(tmp_path, changes):
    config = settings(tmp_path)
    def spawn(*args, **kwargs):
        record(config, **changes)
        return SimpleNamespace(returncode=0)
    with pytest.raises(host.HostRefused):
        host.run(mode="preview", now=NOW, environ={}, spawn=spawn, **config)


@pytest.mark.parametrize("old,new,oracle", [
    ('if day != local.date() or trading_days(day, day) != [day]:', 'if False:',
     lambda p: test_window_and_session_boundaries(p, '2026-12-25T15:00:00+00:00', '2026-12-25', False)),
    ('if not time(9, 35) <= local.time() < time(12):', 'if False:',
     lambda p: test_window_and_session_boundaries(p, '2026-10-20T16:00:00+00:00', '2026-10-20', False)),
    ('local = now.astimezone(ZoneInfo("America/New_York"))', 'local = now.astimezone(timezone.utc)',
     lambda p: test_window_and_session_boundaries(p, '2026-11-03T14:35:00+00:00', '2026-11-03', True)),
    ('if (state / "KILL").exists() or (state / "HALTED").exists():', 'if False:',
     lambda p: test_check_refusal(p, 'KILL')),
    ('if json.loads((state / "host-ready.json").read_text(encoding="utf-8")) != {"schema": 1, "profile": "live_fidelity"}:', 'if False:',
     lambda p: test_check_refusal(p, 'missing')),
    ('names = RUNTIME_NAMES + (DATA_NAMES if mode == "inputs" else CREDENTIAL_NAMES)',
     'names = RUNTIME_NAMES + DATA_NAMES + CREDENTIAL_NAMES',
     lambda p: test_fixed_commands_and_child_environments(p, 'inputs')),
    ('if result.returncode != 0:', 'if False:',
     lambda p: test_child_failure_is_redacted_and_never_retried(p, 'status', SimpleNamespace(readouterr=lambda: ('', '')))),
    ('if mode == "preview":', 'if False:',
     lambda p: test_successful_child_is_not_clean_evidence(p, {"place_calls": 1})),
    ('"--persist-command", persist', '"--discarded", persist',
     lambda p: test_fixed_commands_and_child_environments(p, 'preview')),
])
def test_planted_defects_go_red(tmp_path, monkeypatch, old, new, oracle):
    source = Path(host.__file__).read_text(encoding="utf-8")
    assert source.count(old) == 1
    namespace = {"__file__": host.__file__, "__name__": "host_mutant"}
    exec(compile(source.replace(old, new), "<host-mutant>", "exec"), namespace)
    for name in ("preflight", "run", "child_environment"):
        monkeypatch.setattr(host, name, namespace[name])
    monkeypatch.setattr(host, "HostRefused", namespace["HostRefused"])
    with pytest.raises((AssertionError, pytest.fail.Exception, namespace["HostRefused"])):
        oracle(tmp_path)


@pytest.mark.parametrize("defect", ["KILL", "HALTED", "missing"])
def test_check_refusal(tmp_path, defect):
    config = settings(tmp_path)
    if defect == "missing":
        (config["state"] / "host-ready.json").unlink()
    else:
        (config["state"] / defect).touch()
    with pytest.raises(host.HostRefused):
        host.run(mode="check", now=NOW, environ={}, **config)
