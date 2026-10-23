"""057 T011: armed LIVE host boundaries with synthetic arming, fake children only.

No credential, broker, network or real child. The real repository's gate
manifest is read once to prove today's source is NOT ARMABLE.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

import context  # noqa: F401
import fidelity_live_host as live
import fidelity_preview_host as preview

PIN = "a" * 40
NOW = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
FINGERPRINT = "f" * 64
WORKFLOW = Path(live.ROOT) / "ops" / "workflows" / "fidelity-live.yml"


@pytest.fixture(autouse=True)
def no_network_or_children(monkeypatch):
    monkeypatch.setattr(preview.sys, "version_info", (3, 12, 13, "final", 0))
    def refused(*args, **kwargs):
        pytest.fail("real network/child forbidden")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(live.subprocess, "run", refused)


@pytest.fixture
def armable(monkeypatch):
    monkeypatch.setattr(live, "checklist", lambda manifest, root: (True, []))


def root_with_manifest(tmp_path, content=b'{"items": {}}'):
    root = tmp_path / "root"
    path = root / live.MANIFEST
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    return root, hashlib.sha256(content).hexdigest()


def arming(digest, **changes):
    return json.dumps(dict(profile_name="live_fidelity", account_fingerprint=FINGERPRINT,
                           capital_gate_evidence_sha256=digest, activated_by="Camden",
                           activated_at=(NOW - timedelta(days=1)).isoformat(),
                           expires_at=(NOW + timedelta(days=30)).isoformat()) | changes)


def settings(tmp_path):
    state = tmp_path / "state" / "live_fidelity"
    state.mkdir(parents=True, exist_ok=True)
    (state / "host-ready.json").write_text(json.dumps({"schema": 1, "profile": "live_fidelity"}))
    profiles = tmp_path / "runner" / "profiles.json"
    profiles.parent.mkdir(exist_ok=True)
    return dict(pin=PIN, authorized_session="2026-10-20", state=state, profiles=profiles, inputs=tmp_path / "inputs")


def child(config, seen, **changes):
    def spawn(command, **kwargs):
        arm = Path(command[command.index("--arming-file") + 1])
        seen.update(command=command, env=kwargs["env"], arming=json.loads(arm.read_text()))
        path = config["state"] / "preview-sessions" / "2026-10-20.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(dict(session="2026-10-20", pin_sha=PIN, profile="live_fidelity",
            mode="submit", account_fingerprint=FINGERPRINT, clean=True, challenge=False, place_calls=1,
            allocation=live.policy_evidence(), actions=[{"outcome": "SUBMITTED"}]) | changes))
        return SimpleNamespace(returncode=0)
    return spawn


def submit(tmp_path, spawn, text, root):
    config = settings(tmp_path)
    return live.run(mode="submit", now=NOW, environ={"PATH": "x", "APCA_API_KEY_ID": "k"}, spawn=spawn,
                    arming_text=text, root=root, **config)


def test_armed_submit_passes_arming_file_once_then_removes_it(tmp_path, armable):
    root, digest = root_with_manifest(tmp_path)
    config, seen = settings(tmp_path), {}
    assert live.run(mode="submit", now=NOW, environ={"PATH": "x", "APCA_API_KEY_ID": "k"},
                    spawn=child(config, seen), arming_text=arming(digest), root=root, **config) == "COMPLETED"
    assert seen["arming"]["capital_gate_evidence_sha256"] == digest and "exec/live_loop.py" in " ".join(seen["command"]).replace("\\", "/")
    assert "APCA_API_KEY_ID" not in seen["env"] and seen["env"]["QMB_PINNED_SHA"] == PIN
    assert not list(config["profiles"].parent.glob("fidelity-arming.json"))


def test_check_mode_starts_no_child(tmp_path, armable):
    root, digest = root_with_manifest(tmp_path)
    assert live.run(mode="check", now=NOW, arming_text=arming(digest), root=root, **settings(tmp_path)) == "CHECKED"


def test_todays_real_gate_manifest_is_not_armable(tmp_path):
    digest = hashlib.sha256((Path(live.ROOT) / live.MANIFEST).read_bytes()).hexdigest()
    with pytest.raises(live.HostRefused):
        live.run(mode="check", now=NOW, arming_text=arming(digest), **settings(tmp_path))


@pytest.mark.parametrize("change", [
    {"capital_gate_evidence_sha256": "0" * 64}, {"profile_name": "paper_small"}, {"activated_by": "agent"},
    {"expires_at": (NOW - timedelta(seconds=1)).isoformat()}, {"activated_at": (NOW + timedelta(seconds=1)).isoformat()},
    {"expires_at": "2026-11-20T14:00:00"}, {"account_fingerprint": "F" * 64}, {"extra": 1},
])
def test_bad_arming_refuses_before_any_child(tmp_path, armable, change):
    root, digest = root_with_manifest(tmp_path)
    with pytest.raises(live.HostRefused):
        submit(tmp_path, lambda *a, **k: pytest.fail("child started"), arming(digest, **change), root)


@pytest.mark.parametrize("text", ["", "{}", "not json"])
def test_missing_arming_secret_refuses(tmp_path, armable, text):
    root, _ = root_with_manifest(tmp_path)
    with pytest.raises(live.HostRefused):
        submit(tmp_path, lambda *a, **k: pytest.fail("child started"), text, root)


def test_not_armable_manifest_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "checklist", lambda manifest, root: (False, []))
    root, digest = root_with_manifest(tmp_path)
    with pytest.raises(live.HostRefused):
        submit(tmp_path, lambda *a, **k: pytest.fail("child started"), arming(digest), root)


def test_kill_refuses_before_arming_is_read(tmp_path, armable):
    root, digest = root_with_manifest(tmp_path)
    config = settings(tmp_path)
    (config["state"] / "KILL").write_text("x")
    with pytest.raises(live.HostRefused):
        live.run(mode="check", now=NOW, arming_text=arming(digest), root=root, **config)


@pytest.mark.parametrize("change", [
    {"mode": "preview"}, {"clean": False}, {"challenge": True}, {"place_calls": 2},
    {"actions": [{"outcome": "DENIED"}], "place_calls": 0},{"refused": "unsettled_cash"}, {"pin_sha": "b" * 40},
    {"account_fingerprint": "e" * 64},
])
def test_child_record_that_is_not_a_clean_submit_refuses(tmp_path, armable, change):
    root, digest = root_with_manifest(tmp_path)
    config, seen = settings(tmp_path), {}
    with pytest.raises(live.HostRefused):
        live.run(mode="submit", now=NOW, environ={}, spawn=child(config, seen, **change),
                 arming_text=arming(digest), root=root, **config)
    assert not list(config["profiles"].parent.glob("fidelity-arming.json"))


def test_quiet_day_with_no_orders_completes(tmp_path, armable):
    root, digest = root_with_manifest(tmp_path)
    config, seen = settings(tmp_path), {}
    assert live.run(mode="submit", now=NOW, environ={}, spawn=child(config, seen, place_calls=0, actions=[]),
                    arming_text=arming(digest), root=root, **config) == "COMPLETED"


def test_workflow_is_dormant_exclusive_and_attempts_once():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "vars.QMB_FIDELITY_LIVE_ENABLED == 'true' && vars.QMB_FIDELITY_PREVIEW_ENABLED != 'true'" in text
    assert "group: paper-loop" in text and "cancel-in-progress: false" in text
    assert text.count("secrets.QMB_FIDELITY_ARMING_JSON") == 2
    check, marker = text.index("--mode check"), text.index("Persist today's single attempt")
    login = text.index("--mode submit")
    assert text.index("Skip quietly if today already had an attempt") < check < marker < login
    assert "FIDELITY_LIVE_PASSWORD" not in text[:login - 600]


def unsettled(**changes):
    """The record live_loop writes when settled cash lags: refused before any order snapshot."""
    return dict(session="2026-10-20", pin_sha=PIN, profile="live_fidelity", account_fingerprint=FINGERPRINT,
                clean=False, challenge=False, place_calls=0, previews=[], refused="unsettled_cash") | changes


def test_clean_unsettled_cash_day_is_a_quiet_skip(tmp_path, armable):
    root, digest = root_with_manifest(tmp_path)
    config, seen = settings(tmp_path), {}
    spawn = child(config, seen)

    def skip(command, **kwargs):
        spawn(command, **kwargs)
        (config["state"] / "preview-sessions" / "2026-10-20.json").write_text(json.dumps(unsettled()))
        return SimpleNamespace(returncode=0)
    assert live.run(mode="submit", now=NOW, environ={}, spawn=skip, arming_text=arming(digest),
                    root=root, **config) == "UNSETTLED"
    assert not list(config["profiles"].parent.glob("fidelity-arming.json"))


@pytest.mark.parametrize("change", [
    {"place_calls": 1}, {"place_calls": False}, {"actions": [{"outcome": "SUBMITTED"}]}, {"challenge": True},
    {"aborted": "Fidelity loop halted; Camden review required"}, {"pin_sha": "b" * 40},
    {"account_fingerprint": "e" * 64}, {"session": "2026-10-19"}, {"refused": "preview_unaffordable"}, "HALTED",
])
def test_unsettled_skip_that_is_not_clean_refuses(tmp_path, armable, change):
    root, digest = root_with_manifest(tmp_path)
    config, seen = settings(tmp_path), {}
    spawn = child(config, seen)

    def skip(command, **kwargs):
        spawn(command, **kwargs)
        record = unsettled() if change == "HALTED" else unsettled(**change)
        (config["state"] / "preview-sessions" / "2026-10-20.json").write_text(json.dumps(record))
        if change == "HALTED":
            (config["state"] / "HALTED").write_text("Camden review required\n")
        return SimpleNamespace(returncode=0)
    with pytest.raises(live.HostRefused):
        live.run(mode="submit", now=NOW, environ={}, spawn=skip, arming_text=arming(digest), root=root, **config)


def test_failure_issue_opens_at_most_once_per_day():
    text = WORKFLOW.read_text(encoding="utf-8")
    step = text[text.index("Notify host failure"):]
    assert step.index("gh issue list") < step.index("gh issue create")
