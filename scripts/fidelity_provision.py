"""064 T001: Camden-only local provisioning; default refuses remote mutation.

After line review, supply --apply, a reviewed NONSECRET template and its installed
safety version. Existing values use hidden input only; ACCOUNT/FP_KEY never
regenerate. Profile stays in memory. Six fixed private secret writes use stdin,
never argv/files/environment. No broker, state, workflow or schedule changes.
Remote values are unreadable; partial writes are not atomic or rolled back.
Any uncertain result requires personal review, without automatic retry.
"""
from __future__ import annotations

import argparse
import ast
import base64
import binascii
import getpass
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import warnings

from fidelity_launch import CREDENTIAL_NAMES, SERVICE, LaunchRefused, fingerprint
from mode_config import MAX_LIVE_BUDGET_USD, load_profiles

REPO = "cstroh01/Quant-ML-Bot-private"
PROFILES_SECRET = "QMB_FIDELITY_PROFILES_JSON"
SECRET_NAMES = CREDENTIAL_NAMES + (PROFILES_SECRET,)
LIST_ARGV = ("gh", "api", "--paginate", "repos/" + REPO + "/actions/secrets", "--jq", ".secrets[].name")
PROFILE_NAME = "live_fidelity"
STATE_DIR = "state/live_fidelity"
PILOT_BUDGET_USD = 200.0
DAILY_DEPLOY_FRACTION = 0.2
INSTRUMENTS = ("etf",)
TEMPLATE_FIELDS = frozenset({"name", "mode", "broker", "credential_refs", "state_dir", "log_namespace",
                             "bot_budget_usd", "daily_deploy_fraction", "instruments", "fractional",
                             "safety_config_version"})
TIMEOUT_SECONDS = 120
_SECRET_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FP_KEY = re.compile(r"[0-9a-f]{64}")
_BASE32 = re.compile(r"[A-Za-z2-7]+=*")

class ProvisionRefused(RuntimeError):
    """Fixed category only; ``completed`` names secrets already written, never values."""

    def __init__(self, category, completed=()):
        super().__init__("Provision refused: " + category)
        self.category, self.completed = category, tuple(completed)

def _number(value):
    return type(value) in (int, float) and math.isfinite(value)

def _reject_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError
    return dict(pairs)

def installed_safety_version():
    """Read the pinned source's literal version without importing any broker code."""
    try:
        source = Path(__file__).resolve().parents[1] / "exec" / "paper_loop.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        assignments = [n.value for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "ALLOCATION_SAFETY_CONFIG" for t in n.targets)]
        if len(assignments) != 1 or not isinstance(assignments[0], ast.Call):
            raise ValueError
        values = [ast.literal_eval(k.value) for k in assignments[0].keywords if k.arg == "version"]
        if len(values) != 1 or not isinstance(values[0], str) or not values[0]:
            raise ValueError
        return values[0]
    except Exception:
        raise ProvisionRefused("invalid_template") from None

def load_template(path, expected_safety_config_version):
    """Return the validated reviewed template; refuse rather than default any risk value."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    except Exception:
        raise ProvisionRefused("invalid_template") from None
    expected = expected_safety_config_version
    valid = (isinstance(raw, dict) and set(raw) == TEMPLATE_FIELDS
             and isinstance(expected, str) and expected != "" and expected == expected.strip()
             and expected == installed_safety_version()
             and raw["name"] == PROFILE_NAME and raw["log_namespace"] == PROFILE_NAME
             and raw["mode"] == "LIVE" and raw["broker"] == "fidelity" and raw["state_dir"] == STATE_DIR
             and raw["credential_refs"] == list(CREDENTIAL_NAMES)
             and _number(raw["bot_budget_usd"]) and raw["bot_budget_usd"] == PILOT_BUDGET_USD
             and PILOT_BUDGET_USD <= MAX_LIVE_BUDGET_USD
             and _number(raw["daily_deploy_fraction"]) and raw["daily_deploy_fraction"] == DAILY_DEPLOY_FRACTION
             and raw["instruments"] == list(INSTRUMENTS) and type(raw["fractional"]) is bool
             and type(raw["safety_config_version"]) is str and raw["safety_config_version"] == expected)
    if not valid:
        raise ProvisionRefused("invalid_template")
    return dict(raw)

def _no_echo_prompt(label):
    """getpass without its echoing fallback: GetPassWarning becomes an error."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(label + ": ")

def read_values(prompt):
    """Each existing value entered twice; any prompt failure or mismatch refuses."""
    values = {}
    for name in CREDENTIAL_NAMES:
        try:
            first, second = prompt(name), prompt(name + " (again)")
        except Exception:
            raise ProvisionRefused("insecure_prompt") from None
        if first != second:
            raise ProvisionRefused("entry_mismatch")
        values[name] = first
    return values

def validate_values(values):
    """Refuse, never normalize: edge whitespace, control characters, bad FP_KEY or TOTP."""
    for name in CREDENTIAL_NAMES:
        value = values.get(name)
        if (not isinstance(value, str) or not value or value != value.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise ProvisionRefused("invalid_value:" + name)
    if not _FP_KEY.fullmatch(values["FIDELITY_LIVE_FP_KEY"]):
        raise ProvisionRefused("invalid_value:FIDELITY_LIVE_FP_KEY")
    totp = values["FIDELITY_LIVE_TOTP"]
    try:
        if not _BASE32.fullmatch(totp):
            raise ValueError
        bare = totp.rstrip("=")
        if len(base64.b32decode(bare + "=" * (-len(bare) % 8), casefold=True)) < 10:
            raise ValueError
    except (ValueError, binascii.Error):
        raise ProvisionRefused("invalid_value:FIDELITY_LIVE_TOTP") from None

def build_profile_json(template, values):
    """In-memory JSON list holding only live_fidelity, keyed by the existing launcher HMAC."""
    def get_password(service, name):
        return values[name] if service == SERVICE else None
    try:
        digest = fingerprint(platform="win32", get_password=get_password)
    except LaunchRefused:
        raise ProvisionRefused("invalid_credentials") from None
    payload = json.dumps([dict(template, account_fingerprint=digest)], sort_keys=True, separators=(",", ":"))
    try:
        if set(load_profiles(json.loads(payload))) != {PROFILE_NAME}:
            raise ValueError
    except Exception:
        raise ProvisionRefused("invalid_profile") from None
    return payload

def existing_names(runner):
    """Names only (never values) of the fixed repository's Actions secrets."""
    try:
        result = runner(list(LIST_ARGV), stdin=subprocess.DEVNULL, capture_output=True, shell=False,
                        check=False, timeout=TIMEOUT_SECONDS)
        if result.returncode != 0 or not isinstance(result.stdout, bytes):
            raise ValueError
        names = result.stdout.decode("ascii").split()
        if not all(_SECRET_NAME.fullmatch(name) for name in names):
            raise ValueError
    except Exception:
        raise ProvisionRefused("listing_failed") from None
    return {name.upper() for name in names}

def write_secrets(runner, payloads):
    """Exactly six fixed writes in order; stop at the first failure, never retry."""
    completed = []
    for name in SECRET_NAMES:
        try:
            result = runner(["gh", "secret", "set", name, "--repo", REPO], input=payloads[name].encode("utf-8"),
                            capture_output=True, shell=False, check=False, timeout=TIMEOUT_SECONDS)
            written = result.returncode == 0
        except (Exception, KeyboardInterrupt):
            written = False
        if not written:
            raise ProvisionRefused("write_failed", completed)
        completed.append(name)
    return tuple(completed)

def provision(*, template_path, expected_safety_config_version, prompt=None, runner=None):
    """Validate everything, refuse existing names, then write; return completed names only."""
    prompt = _no_echo_prompt if prompt is None else prompt
    runner = subprocess.run if runner is None else runner
    template = load_template(template_path, expected_safety_config_version)
    values = read_values(prompt)
    validate_values(values)
    payloads = dict(values)
    payloads[PROFILES_SECRET] = build_profile_json(template, values)
    if existing_names(runner) & set(SECRET_NAMES):
        raise ProvisionRefused("secret_exists")
    return write_secrets(runner, payloads)

def main(argv=None, *, prompt=None, runner=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--template", type=Path)
    parser.add_argument("--expected-safety-config-version")
    args = parser.parse_args(argv)
    if not args.apply or args.template is None or args.expected_safety_config_version is None:
        print("Refused: --apply, --template and --expected-safety-config-version are required; "
              "nothing was read, prompted or written.", file=sys.stderr)
        return 2
    try:
        completed = provision(template_path=args.template,
                              expected_safety_config_version=args.expected_safety_config_version,
                              prompt=prompt, runner=runner)
    except ProvisionRefused as error:
        print(str(error) + "; completed: " + (",".join(error.completed) or "none")
              + "; no automatic retry, review remote secret names personally", file=sys.stderr)
        return 2
    except (Exception, KeyboardInterrupt):
        print("Provision refused: internal_error; completed: unknown; review remote secret names personally",
              file=sys.stderr)
        return 2
    print("COMPLETED: " + ",".join(completed))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
