"""061 T006 serial mutants in disposable copies; production source/ledger are read-only."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import xml.etree.ElementTree as ET

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/test_061_adoption.py"
COPIED = ("scripts", "exec", "docs/trials", "tests/context.py", "tests/mode_fixtures.py",
          "tests/test_110_paper_allocation.py", "tests/test_057_q138_inputs.py", TEST,
          ".specify/specs/061-buffered-allocation/declaration.json")
TARGETS, LOOP = "scripts/paper_targets.py", "exec/paper_loop.py"
MUTANTS = [
    ("A1 restored", TARGETS, "targets = buffered_weights(history).loc[decision].fillna(0.0)",
     "targets = __import__('portfolio_risk').allocation_weights(__import__('signals').allocation_selection(history), history, mask).loc[decision].fillna(0.0) * (1.0 - CASH_RESERVE)"),
    ("reserve doubled", TARGETS, "targets = buffered_weights(history).loc[decision].fillna(0.0)",
     "targets = buffered_weights(history).loc[decision].fillna(0.0) * (1.0 - CASH_RESERVE)"),
    ("legacy policy accepted", LOOP, 'if not isinstance(saved, dict) or saved.get("allocation") != policy_evidence():', "if False:"),
    ("record identity missing", LOOP, '"allocation": plan.allocation,', '"allocation": None,'),
    ("input identity missing", "scripts/fidelity_inputs.py", '"allocation": allocation}', '"allocation": {}}'),
]


def run_copy(out, label, mutant=None):
    with tempfile.TemporaryDirectory(prefix="qmb-061-adopt-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant:
            _, relative, old, new = mutant
            path = root / relative
            text = path.read_text(encoding="utf-8")
            assert text.count(old) == 1, label
            path.write_text(text.replace(old, new), encoding="utf-8")
        xml = root / "result.xml"
        result = run_pytest(root, TEST, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        (out / f"{label}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        tree = ET.parse(xml)
        (out / f"{label}.xml").write_bytes(xml.read_bytes())
        assert len(tree.findall(".//testcase")) == 7 and not tree.findall(".//error"), label
        failures = [case.get("name") for case in tree.findall(".//testcase") if case.find("failure") is not None]
        return result.returncode, failures


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    watched = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
               for path in {item[1] for item in MUTANTS}}
    results = []
    with guarded():
        assert run_copy(out, "control") == (0, [])
        for index, mutant in enumerate(MUTANTS, 1):
            code, failures = run_copy(out, f"m{index}", mutant)
            assert code == 1 and failures, mutant[0]
            results.append({"mutant": mutant[0], "killed": True, "failed_tests": failures})
            print(f"KILLED {mutant[0]}", flush=True)
    assert watched == {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in watched}
    (out / "results.json").write_text(json.dumps({"control": "PASS", "killed": len(results),
        "total": len(MUTANTS), "production_source_unchanged": True, "results": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
