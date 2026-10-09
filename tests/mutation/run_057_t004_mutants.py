"""Rule 12 driver for 057 T004: reconciliation and positions guards must each go red. Fakes only."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "exec" / "fidelity_reconcile.py"
orig = p.read_text()
MUTS = {
    "unknown released": ('        if code is None:\n            report.append({"client_order_id": client_id, "state": "unknown"})',
                         '        if code is None:\n            gate.record_order_outcome(client_id, terminal=True, reason="NONE", now=now)\n            report.append({"client_order_id": client_id, "state": "unknown"})'),
    "working released": ("        elif code in TERMINAL:", "        elif True:"),
    "unrecognized treated as working": ("        elif code in WORKING:", "        elif True:"),
    "lookup failure blocks nothing": ('    blocked = [r["client_order_id"] for r in report if r["state"] != "released" and r["state"] != "working"]',
                                      '    blocked = [r["client_order_id"] for r in report if r["state"] in ("unknown",)]'),
    "challenge swallowed": ("        except HaltProfile:\n            raise\n", ""),
    "unpriced valued at zero": ("                raise HoldingsImportError(f\"{symbol}: no finite positive price", "                price = 0.0  # (f\"{symbol}: no finite positive price"),
    "infinite quantity accepted": ("        if not (math.isfinite(quantity) and quantity >= 0):", "        if False:"),
}
killed = 0
for name, (a, b) in MUTS.items():
    assert orig.count(a) == 1, name
    p.write_text(orig.replace(a, b))
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_057_reconcile.py", "-q",
                            "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
    finally:
        p.write_text(orig)
    ok = r.returncode != 0
    killed += ok
    print(("KILLED  " if ok else "SURVIVED"), name)
print(f"{killed}/{len(MUTS)} killed")
sys.exit(0 if killed == len(MUTS) else 1)
