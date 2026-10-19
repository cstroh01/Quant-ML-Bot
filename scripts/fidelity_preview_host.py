"""057 T007: portable orchestration for a reviewed, private, preview-only host.

The workflow verifies the immutable main-ancestor source before invoking this
helper. No credential access, command or broker activity occurs in check mode.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from zoneinfo import ZoneInfo

from data import trading_days
from fidelity_launch import CREDENTIAL_NAMES
from allocation_policy import policy_evidence

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_NAMES = ("PATH", "SystemRoot", "WINDIR", "HOME", "TMP", "TEMP", "TMPDIR",
                 "LANG", "LC_ALL", "LD_LIBRARY_PATH", "SSL_CERT_FILE")
DATA_NAMES = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")


class HostRefused(RuntimeError):
    """Fixed-message refusal, without child/backend payloads."""


def preflight(*, now, pin, authorized_session, state):
    """Refuse late, unauthorized, uninitialized or halted runs before a child."""
    try:
        if now.utcoffset() is None:
            raise ValueError
        local = now.astimezone(ZoneInfo("America/New_York"))
        day = date.fromisoformat(authorized_session)
        if day != local.date() or trading_days(day, day) != [day]:
            raise ValueError
        if not time(9, 35) <= local.time() < time(12):
            raise ValueError
        if not re.fullmatch("[0-9a-f]{40}", pin) or sys.version_info[:2] != (3, 12):
            raise ValueError
        state = Path(state)
        if (state / "KILL").exists() or (state / "HALTED").exists():
            raise ValueError
        if json.loads((state / "host-ready.json").read_text(encoding="utf-8")) != {"schema": 1, "profile": "live_fidelity"}:
            raise ValueError
    except Exception:
        raise HostRefused("Host preflight refused; no child started") from None
    return day.isoformat()


def child_environment(environ, mode, pin):
    names = RUNTIME_NAMES + (DATA_NAMES if mode == "inputs" else CREDENTIAL_NAMES)
    return {name: environ[name] for name in names if name in environ} | {"QMB_PINNED_SHA": pin}


def run(*, mode, now, pin, authorized_session, state, profiles, inputs,
        environ=None, spawn=None):
    if mode not in ("check", "inputs", "preview"):
        raise HostRefused("Unsupported host mode")
    session = preflight(now=now, pin=pin, authorized_session=authorized_session, state=state)
    if mode == "check":
        return "CHECKED"
    state, profiles, inputs = map(lambda p: Path(p).resolve(), (state, profiles, inputs))
    if mode == "inputs":
        command = [sys.executable, str(ROOT / "scripts/fidelity_inputs.py"),
                   "--out", str(inputs), "--session", session]
    else:
        persist = "bash ops/persist_state.sh " + shlex.quote(str(state.parent)) + " fidelity-preview"
        command = [sys.executable, str(ROOT / "scripts/fidelity_launch.py"), "--",
                   sys.executable, str(ROOT / "exec/live_loop.py"),
                   "--profile", "live_fidelity", "--profiles-file", str(profiles),
                   "--state-dir", str(state), "--closes-file", str(inputs / "closes.csv"),
                   "--sources-file", str(inputs / "sources.json"), "--persist-command", persist]
        csv = state / "holdings" / (session + ".csv")
        if csv.is_file():
            command += ["--holdings-csv", str(csv)]
    try:
        env = child_environment(os.environ if environ is None else environ, mode, pin)
        result = (subprocess.run if spawn is None else spawn)(
            command, cwd=ROOT, env=env, check=False, capture_output=True)
        if result.returncode != 0:
            raise ValueError
        if mode == "preview":
            record = json.loads((state / "preview-sessions" / (session + ".json")).read_text(encoding="utf-8"))
            if (record.get("session") != session or record.get("pin_sha") != pin
                    or record.get("profile") != "live_fidelity" or record.get("mode") != "preview"
                    or record.get("clean") is not True or record.get("challenge") is not False
                    or type(record.get("place_calls")) is not int or record["place_calls"] != 0
                    or record.get("allocation") != policy_evidence() or record.get("refused")
                    or not isinstance(record.get("actions"), list)
                    or any(action.get("outcome") != "PREVIEW" for action in record["actions"])):
                raise ValueError
    except Exception:
        raise HostRefused("Preview child refused; no automatic retry") from None
    return "COMPLETED"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("check", "inputs", "preview"), default="check")
    parser.add_argument("--pin", required=True)
    parser.add_argument("--authorized-session", required=True)
    for name in ("state", "profiles", "inputs"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = vars(parser.parse_args(argv))
    try:
        print(run(now=datetime.now(timezone.utc), **args))
        return 0
    except HostRefused as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
