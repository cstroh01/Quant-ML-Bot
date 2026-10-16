"""Spec 059 T004 run command (D-11) Rule 12 mutants: each must fail a named assertion; bytes restored.

Usage: python tests/mutation/run_059_t004_mutants.py <output-dir>
"""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
RUN, REPORT = "scripts/run_059_t004.py", "scripts/allocation_report.py"
MUTANTS = {
    "M1 injected fill_cost ignored": (REPORT, "cost = own_fill_cost if fill_cost is None else fill_cost",
                                      "cost = own_fill_cost"),
    "M2 rerun allowed": (RUN, '    if prior:\n        raise PreflightRefused("research_report_already_run")\n', ""),
    "M3 panel not declared": (RUN, '    if declaration["research_data"]["panel_hash"] != panel.panel_hash:\n'
                                   '        raise PreflightRefused("panel_not_declared")\n', ""),
    "M4 D-11 freeze unchecked": (RUN, 'if "research_data" not in declaration or "random_seeds" not in declaration:',
                                 "if False:"),
    "M5 equity not exported": (REPORT, "        sink[key] = equity\n", ""),
    "M6 simple returns recorded": (RUN, "daily = np.log(equity / equity.shift(1)).dropna()",
                                   "daily = (equity / equity.shift(1) - 1).dropna()"),
    "M7 baseline counted as candidate": (RUN, '("B-BH", "buy_and_hold_baseline", None)', '("B-BH", "candidate", None)'),
    "M8 B-BH started first": (RUN, 'return [("A1", "candidate", None), ("B-BH", "buy_and_hold_baseline", None),',
                              'return [("B-BH", "buy_and_hold_baseline", None), ("A1", "candidate", None),'),
}


def run(directory: Path, label: str) -> tuple[int, int]:
    report = directory / f"{label}.xml"
    proc = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_059_t004.py", "-q", "-p", "no:cacheprovider",
                           f"--junitxml={report}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    (directory / f"{label}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    tree = ET.parse(report)
    assert tree.findall(".//testcase") and not tree.findall(".//error"), label
    return proc.returncode, len(tree.findall(".//failure"))


def main() -> None:
    directory = Path(sys.argv[1])
    directory.mkdir(parents=True, exist_ok=True)
    originals = {path: (ROOT / path).read_bytes() for path, _, _ in MUTANTS.values()}
    for name, (path, old, _) in MUTANTS.items():  # every anchor is checked before any mutant is written
        assert originals[path].decode("utf-8").count(old) == 1, f"{name}: expected one site"
    results = []
    try:
        assert run(directory, "control") == (0, 0), "unchanged-copy control must pass"
        for i, (name, (path, old, new)) in enumerate(MUTANTS.items(), 1):
            (ROOT / path).write_bytes(originals[path].decode("utf-8").replace(old, new).encode("utf-8"))
            code, failures = run(directory, f"m{i}")
            assert code == 1 and failures, f"{name} survived"
            results.append({"mutant": name, "killed": True, "assertion_failures": failures})
            print(f"KILLED   {name}")
            (ROOT / path).write_bytes(originals[path])
    finally:
        for path, data in originals.items():
            (ROOT / path).write_bytes(data)
    (directory / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"control": "PASS", "killed": len(results), "total": len(MUTANTS),
                      "source_restored": all((ROOT / p).read_bytes() == d for p, d in originals.items())}))


if __name__ == "__main__":
    main()
