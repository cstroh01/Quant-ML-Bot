"""Rule 12 driver for 055 F01: missed-run detection and run identity guards must each go red."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "ops_runner.py"
orig = p.read_text()
muts = {
    "missed check only when due": ("    if decision.status != \"due\":\n        return {\"status\": decision.status, \"session\": decision.session.isoformat(),\n                \"new_incidents\": _deliver(ops, incidents)}",
                                   "    if decision.status != \"due\":\n        return {\"status\": decision.status, \"session\": decision.session.isoformat(),\n                \"new_incidents\": 0}"),
    "no first-seen anchor": ("    since = max([anchor] + [s for _, s in completed])", "    since = max([s for _, s in completed], default=decision.session)"),
    "strategy version optional": ("    if not str(strategy_version).strip():", "    if False:"),
    "strategy version not recorded": ('"strategy_version": strategy_version,\n', "\n"),
    "new incident exits zero": ("return 0 if ok and not result[\"new_incidents\"] else 1", "return 0 if ok else 1"),
}
killed = 0
for name, (a, b) in muts.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_055_runner.py", "-q",
                        "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
p.write_text(orig)
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
