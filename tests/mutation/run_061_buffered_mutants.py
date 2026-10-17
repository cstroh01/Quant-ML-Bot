"""061 T004: serial semantic mutants, named pytest failures, exact byte restoration.

Run before the full suite, with no other process editing these files:
python tests/mutation/run_061_buffered_mutants.py <private-output-directory>
"""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
WEIGHTS, RUNNER = "scripts/buffered_allocation.py", "scripts/run_061_buffered_trial.py"
WTEST = "tests/test_061_buffered_allocation.py"
RTEST = "tests/test_061_buffered_trial.py"
RETURN = "return equal_weight_book(closes.notna(), max_gross=1.0 - CASH_RESERVE).loc[decisions]"
RECORD = "test_every_series_started_before_evaluation_costs_applied_and_returns_bound"
MUTANTS = [
    ("A1 restored", WEIGHTS, RETURN,
     "return __import__('portfolio_risk').allocation_weights(__import__('signals').allocation_selection(closes), closes, decisions) * (1.0 - CASH_RESERVE)", WTEST),
    ("reserve removed", WEIGHTS, "CASH_RESERVE = 0.07", "CASH_RESERVE = 0.0", WTEST),
    ("reserve twice", WEIGHTS, "max_gross=1.0 - CASH_RESERVE", "max_gross=(1.0 - CASH_RESERVE)**2", WTEST),
    ("daily retarget", WEIGHTS, ".loc[decisions]", "", WTEST),
    ("future eligibility", WEIGHTS, "closes.notna()", "closes.shift(-1).notna()", WTEST),
    ("costs ignored", RUNNER, "fill_cost=t015.fill_cost(panel)", "fill_cost=lambda *_: 0.0", f"{RTEST}::{RECORD}"),
    ("repeat allowed", RUNNER, 'if any(e["family"] == FAMILY for e in state["events"]):', "if False:",
     f"{RTEST}::test_evaluation_failure_consumes_attempt_and_blocks_rerun"),
    ("holdout allowed", RUNNER, "if sealed_sessions(panel.closes.index).any():", "if False:",
     f"{RTEST}::test_preflight_is_read_only_and_refuses_bad_panel_holdout_and_seeds"),
    ("source binding ignored", RUNNER,
     'if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:', "if False:",
     f"{RTEST}::test_source_drift_refuses_before_any_ledger_byte"),
]


def run(out: Path, label: str, tests: list[str]) -> tuple[int, list[str]]:
    xml = out / f"{label}.xml"
    process = subprocess.run([sys.executable, "-B", "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider",
                              f"--junitxml={xml}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    (out / f"{label}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    tree = ET.parse(xml)
    assert tree.findall(".//testcase") and not tree.findall(".//error"), label
    return process.returncode, [case.get("name") for case in tree.findall(".//testcase") if case.find("failure") is not None]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    originals = {name: (ROOT / name).read_bytes() for name in (WEIGHTS, RUNNER)}
    for label, path, old, _, _ in MUTANTS:
        assert originals[path].decode("utf-8").count(old) == 1, label
    results = []
    try:
        assert run(out, "control", [WTEST, RTEST]) == (0, []), "clean control failed"
        for index, (label, path, old, new, target) in enumerate(MUTANTS, 1):
            (ROOT / path).write_bytes(originals[path].decode("utf-8").replace(old, new).encode("utf-8"))
            code, failures = run(out, f"m{index}", [target])
            assert code == 1 and failures, f"surviving mutant: {label}"
            results.append({"mutant": label, "killed": True, "failed_tests": failures})
            (ROOT / path).write_bytes(originals[path])
            print(f"KILLED {label}", flush=True)
    finally:
        for path, content in originals.items():
            (ROOT / path).write_bytes(content)
    restored = all((ROOT / path).read_bytes() == content for path, content in originals.items())
    assert restored
    (out / "results.json").write_text(json.dumps({"control": "PASS", "source_restored": restored,
        "killed": len(results), "total": len(MUTANTS), "results": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
