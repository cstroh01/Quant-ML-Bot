"""057 T019 Rule 12: each planted defect in the D-11 entitlement guard must fail the real tests.

Usage: python tests/mutation/run_057_t019_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "exec/fidelity_live.py"
TESTS = ["tests/test_057_t019_entitlement_presence.py", "tests/test_057_t016_entitlement_diagnostic.py", "tests/test_057_q139.py"]
GUARD = "if not isinstance(getattr(context, 'entitlements', None), list) or not any(getattr(row, 'display', '') for row in context.entitlements) or getattr(context, 'errors', None) != []:"
MUTANTS = {
    "ATP required again": (LIVE, GUARD, "if getattr(context, 'has_atp_access', None) is not True or getattr(context, 'errors', None) != []:"),
    "empty list accepted": (LIVE, GUARD, "if not isinstance(getattr(context, 'entitlements', None), list) or getattr(context, 'errors', None) != []:"),
    "unnamed rows accepted": (LIVE, "or not any(getattr(row, 'display', '') for row in context.entitlements)", "or not context.entitlements"),
    "any non-empty value accepted": (LIVE, "if not isinstance(getattr(context, 'entitlements', None), list) or not any(", "if not context.entitlements or not any("),
    "errors ignored": (LIVE, " or getattr(context, 'errors', None) != []:\n                raise SecurityChallenge('Fidelity entitlement refused')", ":\n                raise SecurityChallenge('Fidelity entitlement refused')"),
    "missing errors accepted": (LIVE, "or getattr(context, 'errors', None) != []:\n                raise SecurityChallenge('Fidelity entitlement refused')", "or getattr(context, 'errors', None):\n                raise SecurityChallenge('Fidelity entitlement refused')"),
    "guard removed": (LIVE, GUARD, "if False:"),
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
    return 1 if any(v != "killed" for v in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
