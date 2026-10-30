"""057 T017 Rule 12: each planted defect in the D-5a login probe must fail the real tests.

Usage: python tests/mutation/run_057_t017_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "exec/fidelity_login_probe.py"
FLOW = ROOT / "ops/workflows/fidelity-login-probe.yml"
TESTS = ["tests/test_057_t017_login_probe.py"]
GATE = "not re.fullmatch('[0-9a-f]{40}', pin) or (state / 'KILL').exists() or not (state / 'HALTED').is_file()"
WINDOW = "if now.utcoffset() is None or trading_days(day, day) != [day] or not time(9, 35) <= local.time() < time(16):"
MUTANTS = {
    "KILL ignored": (PROBE, GATE, "not re.fullmatch('[0-9a-f]{40}', pin) or not (state / 'HALTED').is_file()"),
    "HALTED not required": (PROBE, GATE, "not re.fullmatch('[0-9a-f]{40}', pin) or (state / 'KILL').exists()"),
    "HALTED refuses": (PROBE, GATE, "not re.fullmatch('[0-9a-f]{40}', pin) or (state / 'KILL').exists() or (state / 'HALTED').is_file()"),
    "pin unchecked": (PROBE, GATE, "(state / 'KILL').exists() or not (state / 'HALTED').is_file()"),
    "cap removed": (PROBE, "        if probes_used(state) >= MAX_PROBES:\n            raise ValueError\n", ""),
    "cap three": (PROBE, "MAX_PROBES = 2", "MAX_PROBES = 3"),
    "cap counts parsable only": (PROBE, "if p.name.startswith(('probe-', '.probe-'))", "if p.name.endswith('.json') and p.name.startswith('probe-')"),
    "non-session day allowed": (PROBE, WINDOW, "if now.utcoffset() is None or not time(9, 35) <= local.time() < time(16):"),
    "window open": (PROBE, WINDOW, "if now.utcoffset() is None or trading_days(day, day) != [day]:"),
    "window start early": (PROBE, "time(9, 35)", "time(9, 30)"),
    "window end late": (PROBE, "< time(16)", "<= time(16)"),
    "window end early": (PROBE, "< time(16)", "< time(15)"),
    "weekday holiday allowed": (PROBE, "trading_days(day, day) != [day]", "day.weekday() >= 5"),
    "fixed EDT offset": (PROBE, "now.astimezone(NY)", "now.astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=-4)))"),
    "KILL file only": (PROBE, "(state / 'KILL').exists()", "(state / 'KILL').is_file()"),
    "host-ready unchecked": (PROBE, "        if json.loads((state / 'host-ready.json').read_text(encoding='utf-8')) != {'schema': 1, 'profile': 'live_fidelity'}:\n            raise ValueError\n", ""),
    "profile unchecked": (PROBE, "        if profile.name != 'live_fidelity' or profile.mode != 'LIVE' or profile.broker != 'fidelity':\n            raise ValueError\n", ""),
    "fingerprint unchecked": (PROBE, "        if account_hmac(environ.get('FIDELITY_LIVE_ACCOUNT'), environ.get('FIDELITY_LIVE_FP_KEY')) != profile.account_fingerprint:\n            raise ValueError\n", ""),
    "marker not persisted": (PROBE, "        persist()\n", "        pass\n"),
    "push failure ignored": (PROBE, "        raise ProbeRefused('Login probe marker not durable; no login') from None\n", "        pass\n"),
    "no marker before login": (PROBE, "    atomic_write(path, json.dumps(record, sort_keys=True, allow_nan=False))\n    try:\n        persist()", "    try:\n        persist()"),
    "order objects kept": (PROBE, "    client.equity_orders = None\n", ""),
    "status object kept": (PROBE, "    client.order_status = None\n", ""),
    "order hook absent": (PROBE, "    client._http.event_hooks['request'].insert(0, refuse_orders)\n", ""),
    "order hook ignores equity": (PROBE, "if 'order' in path or 'equity' in path:", "if 'order' in path:"),
    "order hook ignores order": (PROBE, "if 'order' in path or 'equity' in path:", "if 'equity' in path:"),
    "order hook case sensitive": (PROBE, "path = request.url.path.lower()", "path = request.url.path"),
    "read-only step skipped": (PROBE, "        _read_only(broker)\n", ""),
    "reads before entitlement": (PROBE, "        stage = 'login'\n", "        broker.positions()\n        stage = 'login'\n"),
    "exception text recorded": (PROBE, "{'stage': stage, 'kind': type(exc).__name__}", "{'stage': stage, 'kind': str(exc)}"),
    "stage lost": (PROBE, "{'stage': stage, 'kind': type(exc).__name__}", "{'stage': 'login', 'kind': type(exc).__name__}"),
    "symbol unmasked": (PROBE, "sorted(s if _SYMBOL.fullmatch(s) else '*' for s in held)", "sorted(held)"),
    "credential guard removed": (PROBE, "if any(secret and any(secret in s for s in _strings(record)) for secret in secrets):", "if False:"),
    "guard skips keys": (PROBE, "[s for k, v in value.items() for s in [k, *_strings(v)]]", "[s for v in value.values() for s in _strings(v)]"),
    "failure counts as passed": (PROBE, "    record['status'] = REFUSED\n", "    record['status'] = PASSED\n"),
    "record marked clean": (PROBE, "'library': LIBRARY,\n", "'library': LIBRARY, 'clean': True,\n"),
    "record mode preview": (PROBE, "{'kind': 'fidelity_login_probe', 'mode': 'probe', 'status': 'started'", "{'kind': 'fidelity_login_probe', 'mode': 'preview', 'status': 'started'"),
    "writes HALTED on failure": (PROBE, "    secrets = [environ.get(name, '') for name in profile.credential_refs]\n", "    (state / 'HALTED').write_text('probe')\n    secrets = [environ.get(name, '') for name in profile.credential_refs]\n"),
    "clears HALTED on pass": (PROBE, "    secrets = [environ.get(name, '') for name in profile.credential_refs]\n", "    (state / 'HALTED').unlink()\n    secrets = [environ.get(name, '') for name in profile.credential_refs]\n"),
    "writes attempts": (PROBE, "    secrets = [environ.get(name, '') for name in profile.credential_refs]\n", "    atomic_write(state / 'attempts' / session, 'x')\n    secrets = [environ.get(name, '') for name in profile.credential_refs]\n"),
    "credentials reach persist": (PROBE, "if not k.startswith('FIDELITY_') and k != 'QMB_FIDELITY_PROFILES_JSON'", "if k != 'QMB_FIDELITY_PROFILES_JSON'"),
    "non-pass exits zero": (PROBE, "    if status != PASSED:\n", "    if False:\n"),
    "imports FidelityLive": (PROBE, "from fidelity_live import LibraryBroker, SecurityChallenge, account_hmac", "from fidelity_live import FidelityLive, LibraryBroker, SecurityChallenge, account_hmac"),
    "workflow scheduled": (FLOW, "on:\n  workflow_dispatch:\n", "on:\n  schedule:\n    - cron: '0 14 * * 1-5'\n  workflow_dispatch:\n"),
    "workflow other concurrency": (FLOW, "group: paper-loop", "group: fidelity-probe"),
    "workflow any actor": (FLOW, "github.actor == 'cstroh01' && ", ""),
    "workflow unhashed": (FLOW, "pip install --require-hashes --only-binary=:all: -r", "pip install -r"),
    "workflow no ancestor check": (FLOW, "not in ('ahead','identical')", "not in ('ahead','identical','behind','diverged')"),
    "workflow runs preview": (FLOW, "python exec/fidelity_login_probe.py", "python exec/live_loop.py"),
    "workflow no persist": (FLOW, 'run: bash ops/persist_state.sh "$GITHUB_WORKSPACE/state" fidelity-login-probe', "run: 'true'"),
    "workflow persist not always": (FLOW, "        if: ${{ always() }}\n", ""),
    "workflow any repository": (FLOW, "github.repository == 'cstroh01/Quant-ML-Bot-private' &&\n      ", ""),
    "workflow any branch": (FLOW, " && github.ref == 'refs/heads/main'", ""),
    "workflow secrets at job level": (FLOW, "      PIN: ${{ vars.QMB_FIDELITY_PIN }}\n", "      PIN: ${{ vars.QMB_FIDELITY_PIN }}\n      FIDELITY_LIVE_PASSWORD: ${{ secrets.FIDELITY_LIVE_PASSWORD }}\n"),
    "workflow no umask": (FLOW, "          umask 077\n", ""),
    "workflow traces shell": (FLOW, "          umask 077\n", "          set -x\n          umask 077\n"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    paths = {path for path, _, _ in MUTANTS.values()}
    originals = {path: path.read_bytes() for path in paths}; results = {}
    try:
        assert run() == 0, "control"
        for name, (path, old, new) in MUTANTS.items():
            raw = originals[path].decode("utf-8"); crlf = "\r\n" in raw
            source = raw.replace("\r\n", "\n"); assert source.count(old) == 1, name
            mutated = source.replace(old, new)
            path.write_bytes((mutated.replace("\n", "\r\n") if crlf else mutated).encode("utf-8"))
            results[name] = "killed" if run() else "SURVIVED"
            path.write_bytes(originals[path])
    finally:
        for path, data in originals.items():
            path.write_bytes(data)
    print(json.dumps({"control": "PASS", "killed": sum(v == "killed" for v in results.values()),
                      "total": len(MUTANTS), "survivors": [k for k, v in results.items() if v != "killed"]}))
    return 0 if all(v == "killed" for v in results.values()) else 1
if __name__ == "__main__":
    sys.exit(main())
