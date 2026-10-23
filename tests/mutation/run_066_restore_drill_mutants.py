"""066 Rule 12: each planted defect in scripts/restore_drill.py must fail the real tests.

Usage: python tests/mutation/run_066_restore_drill_mutants.py. Restores the source.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "scripts/restore_drill.py"
TESTS = ["tests/test_066_restore_drill.py"]
MUTANTS = {
    "byte comparison skipped": ("passed = not differing and", "passed = True and"),
    "views not compared": ("and not view_diff and", "and"),
    "integrity ignored": ("and not unhealthy and", "and"),
    "latches unread": ('"latches": sorted(name for name in LATCHES if (state / name).exists()),', '"latches": [],'),
    "leases unread": ('"leases": {p.name: _parsed(p) for p in sorted((state / "leases").glob("*.json"))},', '"leases": {},'),
    "torn intents tolerated": ('        intents = "corrupt"', "        intents = []"),
    "run log ignored by due-run": ("decision = due_run(now, profile=profile, completed=completed)",
                                   "decision = due_run(now, profile=profile, completed=set())"),
    "sqlite unread": ('for p in sorted(state.rglob("*.sqlite")) if p.is_file()}', 'for p in [] if p.is_file()}'),
    "symlinks followed": ("        if path.is_symlink():\n            raise", "        if False:\n            raise"),
    "empty backup accepted": ('    if not before["backup"]:', "    if False:"),
    "scratch kept": ("            shutil.rmtree(scratch, ignore_errors=True)", "            pass"),
    "restore from primary": ("shutil.copytree(backup, restored, symlinks=True)", "shutil.copytree(primary, restored, symlinks=True)"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    original = PATH.read_bytes(); results = {}
    try:
        assert run() == 0, "control"
        for name, (old, new) in MUTANTS.items():
            source = original.decode("utf-8").replace("\r\n", "\n"); assert source.count(old) == 1, name
            PATH.write_bytes(source.replace(old, new).encode("utf-8"))
            results[name] = "killed" if run() else "SURVIVED"
            PATH.write_bytes(original)
    finally:
        PATH.write_bytes(original)
    print(json.dumps({"control": "PASS", "killed": sum(v == "killed" for v in results.values()),
                      "total": len(MUTANTS), "survivors": [k for k, v in results.items() if v != "killed"]}))
    return 0 if all(v == "killed" for v in results.values()) else 1
if __name__ == "__main__":
    sys.exit(main())
