"""066 Rule 12: each planted defect in ops/workflows/restore-drill.yml must fail the real tests.

Usage: python tests/mutation/run_066_restore_workflow_mutants.py. Restores every source.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "ops/workflows/restore-drill.yml"
TESTS = ["tests/test_066_restore_drill_workflow.py"]
MUTANTS = {
    "writer check fails open": (FLOW, 'echo "::error::cannot check $wf: $active"; exit 1', "continue"),
    "oldest backup chosen": (FLOW, "sort_by(.created_at) | last", "sort_by(.created_at) | first"),
    "expired backups allowed": (FLOW, "select(.expired | not) | ", ""),
    "LIVE host backups ignored": (FLOW, """prefixes='["fidelity-live-state-","fidelity-state-"]'""",
                                  """prefixes='["fidelity-state-"]'"""),
    "ops-state not pinned": (FLOW, "ref: ${{ env.STATE_SHA }}", "ref: ops-state"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    originals = {FLOW: FLOW.read_bytes()}; results = {}
    try:
        assert run() == 0, "control"
        for name, (path, old, new) in MUTANTS.items():
            source = originals[path].decode("utf-8").replace("\r\n", "\n"); assert source.count(old) == 1, name
            path.write_bytes(source.replace(old, new).encode("utf-8"))
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
