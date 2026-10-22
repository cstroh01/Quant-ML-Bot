"""064 T001: actual helper contracts with strict fake gh; no real child/network.
All credential values are synthetic canaries. EXAMPLE — NOT A RESULT.
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import warnings

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import fidelity_provision as fp  # noqa: E402
from mode_config import load_profiles  # noqa: E402

REPO = "cstroh01/Quant-ML-Bot-private"
LIST_ARGV = ["gh", "api", "--paginate", "repos/cstroh01/Quant-ML-Bot-private/actions/secrets",
             "--jq", ".secrets[].name"]
NAMES = ["FIDELITY_LIVE_USERNAME", "FIDELITY_LIVE_PASSWORD", "FIDELITY_LIVE_TOTP",
         "FIDELITY_LIVE_ACCOUNT", "FIDELITY_LIVE_FP_KEY", "QMB_FIDELITY_PROFILES_JSON"]
VERSION = "2026-10-14-alloc-v1"  # exact installed contract; no risk value changes
VALUES = {"FIDELITY_LIVE_USERNAME": "canary-user-7Q", "FIDELITY_LIVE_PASSWORD": "canary pass!9Z",
          "FIDELITY_LIVE_TOTP": "JBSWY3DPEHPK3PXP", "FIDELITY_LIVE_ACCOUNT": "Z99999999-CANARY",
          "FIDELITY_LIVE_FP_KEY": "0123456789abcdef" * 4}
EXPECTED_DIGEST = hmac.new(bytes.fromhex(VALUES["FIDELITY_LIVE_FP_KEY"]),
                           VALUES["FIDELITY_LIVE_ACCOUNT"].encode("utf-8"), hashlib.sha256).hexdigest()
PLAIN_SHA = hashlib.sha256(VALUES["FIDELITY_LIVE_ACCOUNT"].encode("utf-8")).hexdigest()
LEAK = b"LEAKY-CHILD-OUTPUT " + VALUES["FIDELITY_LIVE_PASSWORD"].encode("utf-8")
CANARIES = list(VALUES.values()) + [EXPECTED_DIGEST, PLAIN_SHA, "LEAKY-CHILD-OUTPUT", "child crashed"]
DROP = object()

def template(**changes):
    base = {"name": "live_fidelity", "mode": "LIVE", "broker": "fidelity", "credential_refs": NAMES[:5],
            "state_dir": "state/live_fidelity", "log_namespace": "live_fidelity", "bot_budget_usd": 200.0,
            "daily_deploy_fraction": 0.2, "instruments": ["etf"], "fractional": True,
            "safety_config_version": VERSION}
    for key, value in changes.items():
        if value is DROP:
            base.pop(key)
        else:
            base[key] = value
    return base

def write_template(tmp_path, data):
    path = tmp_path / "template.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path

def apply_args(path):
    return ["--apply", "--template", str(path), "--expected-safety-config-version", VERSION]

def assert_clean(text):
    for canary in CANARIES:
        assert canary not in text

class FakeGh:
    """Strict: only the fixed listing and fixed six-name, fixed-repository writes."""

    def __init__(self, existing=("PAPER_SMALL_KEY_ID", "PAPER_SMALL_SECRET"), fail_on=None, raise_on=None,
                 list_code=0, list_out=None):
        self.existing, self.fail_on, self.raise_on = existing, fail_on, raise_on
        self.list_code, self.list_out = list_code, list_out
        self.calls, self.unexpected = [], []

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append((argv, kwargs))
        if argv == LIST_ARGV:
            out = self.list_out if self.list_out is not None else ("\n".join(self.existing) + "\n").encode()
            return subprocess.CompletedProcess(argv, self.list_code, out, LEAK)
        if len(argv) == 6 and argv[:3] == ["gh", "secret", "set"] and argv[3] in NAMES \
                and argv[4:] == ["--repo", REPO]:
            if argv[3] == self.raise_on:
                raise OSError("child crashed with " + VALUES["FIDELITY_LIVE_PASSWORD"])
            return subprocess.CompletedProcess(argv, 1 if argv[3] == self.fail_on else 0, LEAK, LEAK)
        self.unexpected.append(argv)
        raise AssertionError("unexpected external call")

    def writes(self):
        return [(argv, kwargs) for argv, kwargs in self.calls if argv[:3] == ["gh", "secret", "set"]]

class Prompter:
    """Answers each prompt by the name it starts with; ``confirm`` overrides the second entry."""

    def __init__(self, values=None, confirm=None):
        self.values, self.confirm, self.labels = dict(values or VALUES), dict(confirm or {}), []

    def __call__(self, label):
        name = next(n for n in NAMES[:5] if label.startswith(n))
        repeat = any(seen.startswith(name) for seen in self.labels)
        self.labels.append(label)
        return self.confirm.get(name, self.values[name]) if repeat else self.values[name]

def run(tmp_path, data=None, prompt=None, gh=None):
    path = write_template(tmp_path, template() if data is None else data)
    return fp.provision(template_path=path, expected_safety_config_version=VERSION,
                        prompt=Prompter() if prompt is None else prompt, runner=FakeGh() if gh is None else gh)

def test_default_cli_refuses_without_apply_and_calls_nothing(tmp_path, capsys):
    gh, prompt = FakeGh(), Prompter()
    path = write_template(tmp_path, template())
    assert fp.main([], prompt=prompt, runner=gh) == 2
    assert fp.main(apply_args(path)[1:], prompt=prompt, runner=gh) == 2
    assert fp.main(["--apply"], prompt=prompt, runner=gh) == 2
    assert gh.calls == [] and prompt.labels == []
    assert capsys.readouterr().out == ""

def test_clean_apply_writes_six_fixed_names_via_stdin(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    gh, prompt = FakeGh(), Prompter()
    path = write_template(tmp_path, template())
    files, environ = sorted(tmp_path.iterdir()), dict(os.environ)
    assert fp.main(apply_args(path), prompt=prompt, runner=gh) == 0
    assert gh.unexpected == [] and len(prompt.labels) == 10
    assert [argv for argv, _ in gh.calls] == [LIST_ARGV] + [
        ["gh", "secret", "set", name, "--repo", REPO] for name in NAMES]
    listing = gh.calls[0][1]
    assert "input" not in listing and listing.get("shell") is False and listing.get("capture_output") is True
    for (argv, kwargs), name in zip(gh.writes(), NAMES):
        assert kwargs.get("shell") is False and kwargs.get("capture_output") is True
        assert isinstance(kwargs.get("input"), bytes)
        if name in VALUES:
            assert kwargs["input"] == VALUES[name].encode("utf-8")
        assert_clean(" ".join(argv) + repr({k: v for k, v in kwargs.items() if k != "input"}))
    assert dict(os.environ) == environ
    assert sorted(tmp_path.iterdir()) == files
    out, err = capsys.readouterr()
    assert err == "" and all(name in out for name in NAMES)
    assert_clean(out + err)

@pytest.mark.parametrize("fractional", [True, False])
def test_profile_payload_is_keyed_hmac_and_consumable(tmp_path, monkeypatch, fractional):
    monkeypatch.setenv("FIDELITY_LIVE_ACCOUNT", "OTHER-ENV-ACCOUNT")  # entered value must win
    monkeypatch.setenv("FIDELITY_LIVE_FP_KEY", "f" * 64)
    gh = FakeGh()
    assert run(tmp_path, template(fractional=fractional), gh=gh) == tuple(NAMES)
    payload = gh.writes()[-1][1]["input"].decode("utf-8")
    raw = json.loads(payload)
    assert isinstance(raw, list) and len(raw) == 1
    assert set(raw[0]) == set(template()) | {"account_fingerprint"}
    assert {k: v for k, v in raw[0].items() if k != "account_fingerprint"} == template(fractional=fractional)
    assert raw[0]["account_fingerprint"] == EXPECTED_DIGEST != PLAIN_SHA
    profile = load_profiles(json.loads(payload))["live_fidelity"]  # exec/live_loop.py main loader
    assert (profile.mode, profile.broker, profile.bot_budget_usd) == ("LIVE", "fidelity", 200.0)
    assert set(profile.credential_refs) == set(NAMES[:5]) and len(profile.credential_refs) == 5
    assert profile.fractional is fractional and profile.safety_config_version == VERSION
    for value in VALUES.values():
        assert value not in payload

BAD_TEMPLATES = {
    "extra_fingerprint": template(account_fingerprint="a" * 64),
    "extra_risk_field": template(max_position_pct=0.5),
    "missing_fractional": template(fractional=DROP),
    "budget_above_pilot": template(bot_budget_usd=250.0),
    "budget_below_pilot": template(bot_budget_usd=199.99),
    "budget_string": template(bot_budget_usd="200"),
    "daily_fraction": template(daily_deploy_fraction=0.25),
    "paper_mode": template(mode="PAPER"),
    "paper_broker": template(broker="alpaca_paper"),
    "other_name": template(name="live_fidelity2"),
    "other_state_dir": template(state_dir="state/paper_small"),
    "other_namespace": template(log_namespace="paper_small"),
    "four_refs": template(credential_refs=NAMES[:4]),
    "hidden_extra_ref": template(credential_refs=NAMES[:5] + ["FIDELITY_LIVE_EXTRA"]),
    "profiles_ref": template(credential_refs=NAMES),
    "stock_instruments": template(instruments=["etf", "us_equity"]),
    "string_fractional": template(fractional="true"),
    "safety_mismatch": template(safety_config_version="other-version"),
    "list_not_object": [template()],
    "duplicate_key": '{"fractional": "x", ' + json.dumps(template())[1:],
    "not_json": "{",
}

@pytest.mark.parametrize("case", sorted(BAD_TEMPLATES))
def test_invalid_template_refuses_before_prompt_or_external_call(tmp_path, case):
    gh, prompt = FakeGh(), Prompter()
    with pytest.raises(fp.ProvisionRefused) as caught:
        run(tmp_path, BAD_TEMPLATES[case], prompt, gh)
    assert caught.value.category == "invalid_template" and caught.value.completed == ()
    assert gh.calls == [] and prompt.labels == []

BAD_VALUES = {
    "fp_key_uppercase": ("FIDELITY_LIVE_FP_KEY", "0123456789ABCDEF" * 4),
    "fp_key_short": ("FIDELITY_LIVE_FP_KEY", "0" * 63),
    "fp_key_trailing_space": ("FIDELITY_LIVE_FP_KEY", "0" * 64 + " "),
    "account_leading_space": ("FIDELITY_LIVE_ACCOUNT", " Z99999999-CANARY"),
    "username_trailing_newline": ("FIDELITY_LIVE_USERNAME", "canary-user-7Q\n"),
    "password_empty": ("FIDELITY_LIVE_PASSWORD", ""),
    "totp_not_base32": ("FIDELITY_LIVE_TOTP", "JBSWY3DPEHPK3PX1"),
    "totp_bad_length": ("FIDELITY_LIVE_TOTP", "JBSWY3D"),
    "totp_too_short": ("FIDELITY_LIVE_TOTP", "JBSWY3DP"),
}

@pytest.mark.parametrize("case", sorted(BAD_VALUES))
def test_invalid_value_refuses_before_any_external_call(tmp_path, case):
    name, bad = BAD_VALUES[case]
    gh = FakeGh()
    with pytest.raises(fp.ProvisionRefused) as caught:
        run(tmp_path, prompt=Prompter(dict(VALUES, **{name: bad})), gh=gh)
    assert caught.value.category == "invalid_value:" + name and gh.calls == []
    assert_clean(str(caught.value) + repr(caught.value))
    if bad.strip():
        assert bad.strip() not in str(caught.value) + repr(caught.value)

def test_mismatched_confirmation_refuses_before_external_call(tmp_path):
    gh = FakeGh()
    with pytest.raises(fp.ProvisionRefused) as caught:
        run(tmp_path, prompt=Prompter(confirm={"FIDELITY_LIVE_ACCOUNT": "Z99999998-CANARY"}), gh=gh)
    assert caught.value.category == "entry_mismatch" and gh.calls == []
    assert "Z99999998-CANARY" not in str(caught.value)

def test_echoing_getpass_fallback_refuses(tmp_path, monkeypatch):
    def echoing(prompt=""):
        warnings.warn("Can not control echo on the terminal.", getpass.GetPassWarning)
        return next(VALUES[n] for n in NAMES[:5] if prompt.startswith(n))
    monkeypatch.setattr(fp.getpass, "getpass", echoing)
    gh = FakeGh()
    with pytest.raises(fp.ProvisionRefused) as caught:
        fp.provision(template_path=write_template(tmp_path, template()), expected_safety_config_version=VERSION,
                     runner=gh)
    assert caught.value.category == "insecure_prompt" and gh.calls == []

def test_no_echo_getpass_control_completes(tmp_path, monkeypatch):
    monkeypatch.setattr(fp.getpass, "getpass",
                        lambda prompt="": next(VALUES[n] for n in NAMES[:5] if prompt.startswith(n)))
    gh = FakeGh()
    assert fp.provision(template_path=write_template(tmp_path, template()), expected_safety_config_version=VERSION,
                        runner=gh) == tuple(NAMES)
    assert len(gh.writes()) == 6 and gh.unexpected == []

@pytest.mark.parametrize("name", NAMES)
def test_preexisting_target_secret_refuses_without_any_write(tmp_path, name):
    gh = FakeGh(existing=("PAPER_SMALL_KEY_ID", name))
    with pytest.raises(fp.ProvisionRefused) as caught:
        run(tmp_path, gh=gh)
    assert caught.value.category == "secret_exists" and caught.value.completed == ()
    assert [argv for argv, _ in gh.calls] == [LIST_ARGV] and gh.writes() == []

@pytest.mark.parametrize("kwargs", [{"list_code": 1}, {"list_out": b"<html>rate limited</html>\n"}])
def test_listing_failure_refuses_without_any_write(tmp_path, kwargs):
    gh = FakeGh(**kwargs)
    with pytest.raises(fp.ProvisionRefused) as caught:
        run(tmp_path, gh=gh)
    assert caught.value.category == "listing_failed" and gh.writes() == []

@pytest.mark.parametrize("index", range(6))
def test_partial_failure_stops_remaining_writes(tmp_path, capsys, index):
    gh, environ = FakeGh(fail_on=NAMES[index]), dict(os.environ)
    assert fp.main(apply_args(write_template(tmp_path, template())), prompt=Prompter(), runner=gh) == 2
    assert [argv[3] for argv, _ in gh.writes()] == NAMES[:index + 1] and gh.unexpected == []
    out, err = capsys.readouterr()
    assert out == "" and "write_failed" in err
    assert all(name in err for name in NAMES[:index])
    assert not any(name in err for name in NAMES[index:])
    assert_clean(out + err)
    assert dict(os.environ) == environ

def test_child_exception_is_redacted_and_stops(tmp_path):
    gh = FakeGh(raise_on="FIDELITY_LIVE_TOTP")
    with pytest.raises(fp.ProvisionRefused) as caught:
        run(tmp_path, gh=gh)
    error = caught.value
    assert error.category == "write_failed" and error.completed == tuple(NAMES[:2])
    assert error.__cause__ is None and (error.__context__ is None or error.__suppress_context__)
    assert_clean(str(error) + repr(error) + repr(error.args))
    assert len(gh.writes()) == 3

def test_import_performs_no_external_operation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("external operation at import")
    for target, name in ((subprocess, "run"), (subprocess, "Popen"), (getpass, "getpass")):
        monkeypatch.setattr(target, name, forbidden)
    importlib.reload(fp)

def test_matching_supplied_versions_cannot_override_installed_contract(tmp_path):
    gh, prompt = FakeGh(), Prompter()
    path = write_template(tmp_path, template(safety_config_version="other-installed-contract"))
    with pytest.raises(fp.ProvisionRefused, match="invalid_template"):
        fp.provision(template_path=path, expected_safety_config_version="other-installed-contract",
                     prompt=prompt, runner=gh)
    assert not gh.calls and not prompt.labels

@pytest.fixture(autouse=True)
def no_real_process_or_network(monkeypatch):
    import socket
    def refuse(*args, **kwargs):
        raise AssertionError("real process/network forbidden")
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
