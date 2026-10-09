"""Rule 12 driver for 055 F02a: each crash-safety guard removed must turn a test red."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RT, RN = ROOT / "scripts" / "ops_runtime.py", ROOT / "scripts" / "ops_runner.py"
MUTS = {
    "torn lease completes": (RT, "    except (OSError, ValueError, KeyError, TypeError) as error:\n        raise LeaseHeld(f\"{profile} {session} lease is unreadable",
                             "    except ZeroDivisionError as error:\n        raise LeaseHeld(f\"{profile} {session} lease is unreadable"),
    "lease rewrite not atomic": (RT, '    atomic_write(path, json.dumps({"run_id": run_id, "state": "completed"}))',
                                 '    path.write_text(json.dumps({"run_id": run_id, "state": "completed"}), encoding="utf-8")'),
    "torn intent tail accepted": (RT, '    if text and not text.endswith("\\n"):', "    if False:"),
    "corrupt intent line accepted": (RT, "            raise IntentLogCorrupt(f\"{path.name}: line {number}", "            continue  # (f\"{path.name}: line {number}"),
    "stale lease reruns": (RN, '        incidents.append(Incident("lease_held"', '        raise held\n        incidents.append(Incident("lease_held"'),
    "sent.json not atomic": (RN, "    atomic_write(sent_path, json.dumps(sent, sort_keys=True))",
                             '    sent_path.parent.mkdir(parents=True, exist_ok=True)\n    sent_path.write_text(json.dumps(sent, sort_keys=True), encoding="utf-8")'),
}
killed = 0
for name, (path, a, b) in MUTS.items():
    orig = path.read_text()
    assert orig.count(a) == 1, name
    path.write_text(orig.replace(a, b))
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_055_durability.py", "tests/test_055_leases.py",
                            "tests/test_055_runner.py", "-q", "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    finally:
        path.write_text(orig)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
print(f"{killed}/{len(MUTS)} killed")
sys.exit(0 if killed == len(MUTS) else 1)
