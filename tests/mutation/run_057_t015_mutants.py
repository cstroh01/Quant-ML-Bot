"""057 T015 Rule 12: each planted defect in the D-8 non-cash marks must fail the real tests.

Usage: python tests/mutation/run_057_t015_mutants.py. Restores every source byte for byte.
"""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "exec/live_loop.py"
TESTS = ["tests/test_057_t015_core_price.py"]
MUTANTS = {
    "observation marks unfiltered (main)": (LOOP, "        marks={**noncash_prices(live),**worst}\n", "        marks={**live.prices(),**worst}\n"),
    "order marks unfiltered": (LOOP, "            prices={**noncash_prices(live),**worst}\n", "            prices={**live.prices(),**worst}\n"),
    "broker price overrides worst mark": (LOOP, "        marks={**noncash_prices(live),**worst}\n", "        marks={**worst,**noncash_prices(live)}\n"),
    "order broker price overrides worst": (LOOP, "            prices={**noncash_prices(live),**worst}\n", "            prices={**worst,**noncash_prices(live)}\n"),
    "filter keeps cash only": (LOOP, "    return {s:p for s,p in live.prices().items() if not _CASH_SYMBOLS.match(s)}", "    return {s:p for s,p in live.prices().items() if _CASH_SYMBOLS.match(s)}"),
    "filter drops priceless rows instead": (LOOP, "    return {s:p for s,p in live.prices().items() if not _CASH_SYMBOLS.match(s)}", "    return {s:p for s,p in live.prices().items() if p is not None}"),
    "filter drops every broker price": (LOOP, "    return {s:p for s,p in live.prices().items() if not _CASH_SYMBOLS.match(s)}", "    return {s:p for s,p in live.prices().items() if False}"),
    "filter keys on exact SPAXX only": (LOOP, "    return {s:p for s,p in live.prices().items() if not _CASH_SYMBOLS.match(s)}", "    return {s:p for s,p in live.prices().items() if s != 'SPAXX**'}"),
    "foreign-symbol halt removed": (ROOT / "exec/fidelity_session.py",
        "    if not set(held)<=set(ALLOCATION_SLEEVES): raise HaltProfile('foreign symbol in dedicated account')\n", ""),
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
