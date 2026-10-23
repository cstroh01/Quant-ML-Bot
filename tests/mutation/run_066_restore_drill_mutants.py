"""066 Rule 12: each planted defect in scripts/restore_drill.py must fail the real tests.

Usage: python tests/mutation/run_066_restore_drill_mutants.py. Restores every source.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
DRILL = ROOT / "scripts/restore_drill.py"
TESTS = ["tests/test_066_restore_drill.py"]
MUTANTS = {
    "byte comparison skipped": (DRILL, "passed = not differing and", "passed = True and"),
    "views not compared": (DRILL, "and not view_diff and", "and"),
    "health ignored": (DRILL, "and not view_diff and not unhealthy", "and not view_diff"),
    "latches unread": (DRILL, '"latches": sorted(name for name in LATCHES if (state / name).exists()),', '"latches": [],'),
    "leases unread": (DRILL, '"leases": {p.name: _parsed(p) for p in sorted((state / "leases").glob("*.json"))},',
                      '"leases": {},'),
    "torn intents tolerated": (DRILL, '        intents = "corrupt"', "        intents = []"),
    "run log ignored by due-run": (DRILL, 'for r in rows if r["profile"] == profile}', "for r in [] if r}"),
    "torn run log tolerated": (DRILL, '    except (KeyError, TypeError, ValueError):\n        return "corrupt"',
                               "    except (KeyError, TypeError, ValueError):\n        completed = set()"),
    "unparseable json tolerated": (DRILL, 'bad = [p for p, value in view["json"].items() if value == UNPARSEABLE]',
                                   "bad = []"),
    "lease without run_id tolerated": (DRILL, 'if not (isinstance(lease, dict) and "run_id" in lease)]', "if False]"),
    "jsonl excluded from json view": (DRILL, 'p.suffix in (".json", ".jsonl")', 'p.suffix == ".json"'),
    "sqlite unread": (DRILL, 'for p in sorted(state.rglob("*.sqlite")) if p.is_file()}', "for p in [] if p.is_file()}"),
    "wal sidecar ignored": (DRILL, 'for suffix in ("", "-wal", "-shm"):', 'for suffix in ("",):'),
    "symlinks followed": (DRILL, "        if path.is_symlink():\n            raise", "        if False:\n            raise"),
    "symlinked root accepted": (DRILL,
        '    before = {"primary": manifest(primary), "backup": manifest(backup)}  # refuses symlinked roots\n'
        '    primary, backup = Path(primary).resolve(), Path(backup).resolve()',
        '    primary, backup = Path(primary).resolve(), Path(backup).resolve()\n'
        '    before = {"primary": manifest(primary), "backup": manifest(backup)}'),
    "mid-drill change accepted": (DRILL, "    if after != before:\n        raise", "    if False:\n        raise"),
    "empty backup accepted": (DRILL, '    if not before["backup"]:', "    if False:"),
    "scratch kept": (DRILL, "            shutil.rmtree(scratch, ignore_errors=True)", "            pass"),
    "restore from primary": (DRILL, "shutil.copytree(backup, restored, symlinks=True)",
                             "shutil.copytree(primary, restored, symlinks=True)"),
    "no last-resort evidence": (DRILL, "    except Exception as error:  # last resort",
                                "    except ZeroDivisionError as error:  # last resort"),
}
def run():
    return subprocess.run([sys.executable, "-B", "-m", "pytest", *TESTS, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True).returncode
def main():
    originals = {DRILL: DRILL.read_bytes()}; results = {}
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
