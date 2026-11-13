"""Rule 12 driver for 055 F01: missed-run detection and run identity guards must each go red.

Every anchor targets run_once and must occur exactly once in scripts/ops_runner.py; preview_once
repeats the strategy-version guard and the record line, so those anchors carry run_once's next line.
Anchors are matched after CRLF->LF (an earlier driver in the item 1 run may rewrite this file with CRLF);
the original bytes, whatever their line endings, are restored after every mutant, including on failure.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = ROOT / "scripts" / "ops_runner.py"
orig_bytes = p.read_bytes()
orig = orig_bytes.decode("utf-8").replace("\r\n", "\n")
muts = {
    "missed check only when due": ("    if decision.status != \"due\":\n        return {\"status\": decision.status, \"session\": decision.session.isoformat(),\n                \"new_incidents\": _deliver(ops, incidents)}",
                                   "    if decision.status != \"due\":\n        return {\"status\": decision.status, \"session\": decision.session.isoformat(),\n                \"new_incidents\": 0}"),
    "no first-seen anchor": ("    since = max([anchor] + [s for _, s in completed])", "    since = max([s for _, s in completed], default=decision.session)"),
    "strategy version optional": ("    if not str(strategy_version).strip():\n        raise ValueError(\"strategy_version is required for the run identity\")\n    require_storage_identifier(profile)  # names lease",
                                  "    if False:\n        raise ValueError(\"strategy_version is required for the run identity\")\n    require_storage_identifier(profile)  # names lease"),
    "strategy version not recorded": ('"strategy_version": strategy_version,\n              "run_id": run_id,', '\n              "run_id": run_id,'),
    "new incident exits zero": ("return 0 if ok and not result[\"new_incidents\"] else 1", "return 0 if ok else 1"),
}
for name, (a, _) in muts.items():  # every anchor is checked before any mutant is written
    assert orig.count(a) == 1, f"{name}: expected one site, found {orig.count(a)}"
killed = 0
try:
    for name, (a, b) in muts.items():
        p.write_bytes(orig.replace(a, b).encode("utf-8"))
        try:
            r = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_055_runner.py", "-q",
                                "-p", "no:cacheprovider"], capture_output=True, cwd=ROOT)
        finally:
            p.write_bytes(orig_bytes)
        ok = r.returncode != 0
        killed += ok
        print(("KILLED  " if ok else "SURVIVED"), name)
finally:
    p.write_bytes(orig_bytes)
assert p.read_bytes() == orig_bytes, "scripts/ops_runner.py not restored"
print(f"{killed}/{len(muts)} killed")
sys.exit(0 if killed == len(muts) else 1)
