"""057 T011: portable orchestration for the armed, private, ordinary LIVE host.

Reuses the preview host's preflight (window, NYSE date, pin, KILL/HALTED,
host-ready). In addition, before any child runs, Camden's arming record must
name exactly this profile, be inside its validity window and carry the SHA-256
of the pinned SCOPE §11.3 gate manifest, and that manifest must still check
ARMABLE. The arming record is Camden's activation; this helper never creates,
extends or repairs one. A child that silently fell back to preview, saw a gate
denial or recorded anything but a clean submit session is a refusal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from allocation_policy import policy_evidence
from fidelity_preview_host import ROOT, HostRefused, child_environment, preflight
from gate_checklist import checklist

MANIFEST = Path("docs/implementation/spec-059/gate-manifest.json")
ARMING_KEYS = frozenset({"profile_name", "account_fingerprint", "capital_gate_evidence_sha256",
                         "activated_by", "activated_at", "expires_at"})
OUTCOMES = frozenset({"SUBMITTED", "BUDGET_REFUSED"})


def require_arming(text, *, now, root=ROOT):
    """Return the validated arming row; refuse unless the pinned gate manifest is ARMABLE."""
    try:
        row = json.loads(text)
        if not isinstance(row, dict) or set(row) != ARMING_KEYS:
            raise ValueError
        if row["profile_name"] != "live_fidelity" or row["activated_by"] != "Camden":
            raise ValueError
        if not all(isinstance(row[k], str) and re.fullmatch("[0-9a-f]{64}", row[k])
                   for k in ("account_fingerprint", "capital_gate_evidence_sha256")):
            raise ValueError
        start, end = (datetime.fromisoformat(row[k]) for k in ("activated_at", "expires_at"))
        if start.utcoffset() is None or end.utcoffset() is None or not start <= now < end:
            raise ValueError
        raw = (Path(root) / MANIFEST).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["capital_gate_evidence_sha256"]:
            raise ValueError
        if not checklist(json.loads(raw), Path(root))[0]:
            raise ValueError
    except Exception:
        raise HostRefused("LIVE arming refused; no child started") from None
    return row


def run(*, mode, now, pin, authorized_session, state, profiles, inputs, arming_text,
        environ=None, spawn=None, root=ROOT):
    if mode not in ("check", "submit"):
        raise HostRefused("Unsupported host mode")
    session = preflight(now=now, pin=pin, authorized_session=authorized_session, state=state)
    row = require_arming(arming_text, now=now, root=root)
    if mode == "check":
        return "CHECKED"
    state, profiles, inputs = map(lambda p: Path(p).resolve(), (state, profiles, inputs))
    arming = profiles.parent / "fidelity-arming.json"
    persist = "bash ops/persist_state.sh " + shlex.quote(str(state.parent)) + " fidelity-live"
    command = [sys.executable, str(ROOT / "scripts/fidelity_launch.py"), "--",
               sys.executable, str(ROOT / "exec/live_loop.py"),
               "--profile", "live_fidelity", "--profiles-file", str(profiles),
               "--state-dir", str(state), "--closes-file", str(inputs / "closes.csv"),
               "--sources-file", str(inputs / "sources.json"), "--persist-command", persist,
               "--arming-file", str(arming)]
    try:
        descriptor = os.open(arming, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(row, stream)
        env = child_environment(os.environ if environ is None else environ, "preview", pin)
        result = (spawn or subprocess.run)(command, cwd=ROOT, env=env, check=False, capture_output=True)
        if result.returncode != 0:
            raise ValueError
        record = json.loads((state / "preview-sessions" / (session + ".json")).read_text(encoding="utf-8"))
        if (record.get("session") != session or record.get("pin_sha") != pin
                or record.get("profile") != "live_fidelity" or record.get("mode") != "submit"
                or record.get("account_fingerprint") != row["account_fingerprint"]
                or record.get("clean") is not True or record.get("challenge") is not False
                or record.get("allocation") != policy_evidence() or record.get("refused")
                or type(record.get("place_calls")) is not int
                or not isinstance(record.get("actions"), list)
                or any(action.get("outcome") not in OUTCOMES for action in record["actions"])
                or record["place_calls"] != sum(a.get("outcome") == "SUBMITTED" for a in record["actions"])):
            raise ValueError
    except Exception:
        raise HostRefused("LIVE child refused; no automatic retry") from None
    finally:
        arming.unlink(missing_ok=True)
    return "COMPLETED"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("check", "submit"), default="check")
    parser.add_argument("--pin", required=True)
    parser.add_argument("--authorized-session", required=True)
    for name in ("state", "profiles", "inputs"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = vars(parser.parse_args(argv))
    try:
        print(run(now=datetime.now(timezone.utc), arming_text=os.environ.get("QMB_FIDELITY_ARMING_JSON", ""), **args))
        return 0
    except HostRefused as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
