"""Spec 058 T015 run command (queue Q133) Rule 12 mutants: each must fail a named assertion; bytes restored.

Usage: python tests/mutation/run_058_t015_mutants.py <output-dir>
"""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DS, RUN, WF = "scripts/data_sources.py", "scripts/run_058_t015.py", "scripts/edge_walk_forward.py"
MUTANTS = {
    "M1 P&L on raw close": (DS, "opens[ticker], closes[ticker] = adj_open.mask(mask), adj_close.mask(mask)",
                            "opens[ticker], closes[ticker] = frame['open'].astype(float).mask(mask), "
                            "frame['close'].astype(float).mask(mask)"),
    "M2 unconverted quantity": (RUN, "nominal = quantity * float(panel.closes.at[as_of, ticker]) / "
                                     "float(panel.raw_closes.at[as_of, ticker])", "nominal = quantity"),
    "M3 T009 preflight removed": (RUN, '        raise PreflightRefused("risk_free_mismatch")\n'
                                       '    if data_check.get("status") not in ("VERIFIED", "EXCLUSIONS"):\n'
                                       '        raise PreflightRefused("data_check_missing")\n',
                                  '        raise PreflightRefused("risk_free_mismatch")\n'),
    "M4 truncation removed": (DS, 'if r["date"][:10] <= str(RESEARCH_END)]', "]"),
    "M5 rerun allowed silently": (RUN, "if prior and not (isinstance(rerun, str) and rerun.strip()):", "if False:"),
    "M6 B-BH run first": (RUN, 'for config_id in (*RUN_ORDER, "B-BH"):', 'for config_id in ("B-BH", *RUN_ORDER):'),
    "M7 mismatch not spliced": (DS, "if any(index[e] in spliced for e in gap):", "if False:"),
    "M9 resume re-runs completed pairs": (RUN, "if (c, s) not in progress[\"brnd_pairs\"]]", "]"),
    "M10 resume leaves dangling starts open": (RUN, 'receipts = [{"closed": d["trial_id"], "receipt": ledger.finish(d["trial_id"], "abandoned", reason=reason)}\n                for d in status["dangling"]]',
                                               "receipts = []"),
    "M11 resume accepts a duplicated candidate": (RUN, "    if progress[\"configs\"] != expected:\n", "    if False:\n"),
    "M8 risk-free 0": (WF, 'RISK_FREE = {"annual_rate": RISK_FREE_RATE_ANNUAL, "days_per_year": 252}',
                       'RISK_FREE = {"annual_rate": 0.0, "days_per_year": 252}'),
}


def run(directory: Path, label: str) -> tuple[int, int]:
    report = directory / f"{label}.xml"
    proc = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_058_t015.py", "-q", "-p", "no:cacheprovider",
                           f"--junitxml={report}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    (directory / f"{label}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    tree = ET.parse(report)
    assert tree.findall(".//testcase") and not tree.findall(".//error"), label
    return proc.returncode, len(tree.findall(".//failure"))


def main() -> None:
    directory = Path(sys.argv[1])
    directory.mkdir(parents=True, exist_ok=True)
    originals = {path: (ROOT / path).read_bytes() for path, _, _ in MUTANTS.values()}
    results = []
    try:
        assert run(directory, "control") == (0, 0), "unchanged-copy control must pass"
        for i, (name, (path, old, new)) in enumerate(MUTANTS.items(), 1):
            source = originals[path].decode("utf-8")
            assert source.count(old) == 1, name
            (ROOT / path).write_bytes(source.replace(old, new).encode("utf-8"))
            code, failures = run(directory, f"m{i}")
            assert code == 1 and failures, f"{name} survived"
            results.append({"mutant": name, "killed": True, "assertion_failures": failures})
            (ROOT / path).write_bytes(originals[path])
    finally:
        for path, data in originals.items():
            (ROOT / path).write_bytes(data)
    (directory / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"control": "PASS", "killed": len(results), "total": len(MUTANTS),
                      "source_restored": all((ROOT / p).read_bytes() == d for p, d in originals.items())}))


if __name__ == "__main__":
    main()
