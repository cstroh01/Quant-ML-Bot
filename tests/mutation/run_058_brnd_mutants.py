"""Spec 058 T013 B-RND (queue Q132) Rule 12 mutants: each must fail a named assertion; bytes restored.

Usage: python tests/mutation/run_058_brnd_mutants.py <output-dir>
"""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
TARGET = "scripts/edge_walk_forward.py"
SELECT = "brnd or dispersion"
MUTANTS = {
    "M1 one seed accepted": ("    if len(seeds) != BRND_SEED_COUNT or seeds != BRND_SEEDS:", "    if not seeds:"),
    "M2 seed ignored": ("selection = random_selection(closes, decision_mask=mask, seed=seed, **activity)",
                        "selection = random_selection(closes, decision_mask=mask, seed=BRND_SEEDS[0], **activity)"),
    "M3 B-RND recorded as candidate": ('role="random_signal_baseline", family=FAMILY', 'role="candidate", family=FAMILY'),
    "M4 sizing class swapped": ('    return "inverse_vol_vol_target"  # H1-*', '    return "equal_legs_vol_target"  # H1-*'),
    "M5 activity fitted past RESEARCH_END": ("    _require_research_panel(closes, closes)\n", "    pass\n"),
    "M6 cadence ignored": ('    return "weekly" if config_id in WEEKLY else "monthly"', '    return "monthly"'),
}


def run(directory: Path, label: str) -> tuple[int, int]:
    report = directory / f"{label}.xml"
    proc = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_058_walk_forward.py", "-q", "-k", SELECT,
                           "-p", "no:cacheprovider", f"--junitxml={report}"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8")
    (directory / f"{label}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    tree = ET.parse(report)
    assert tree.findall(".//testcase") and not tree.findall(".//error"), label
    return proc.returncode, len(tree.findall(".//failure"))


def main() -> None:
    directory = Path(sys.argv[1])
    directory.mkdir(parents=True, exist_ok=True)
    path = ROOT / TARGET
    original = path.read_bytes()
    results = []
    try:
        assert run(directory, "control") == (0, 0), "unchanged-copy control must pass"
        for i, (name, (old, new)) in enumerate(MUTANTS.items()):
            source = original.decode("utf-8")
            assert source.count(old) == 1, name
            path.write_bytes(source.replace(old, new).encode("utf-8"))
            code, failures = run(directory, f"m{i + 1}")
            assert code == 1 and failures, f"{name} survived"
            results.append({"mutant": name, "killed": True, "assertion_failures": failures})
            path.write_bytes(original)
    finally:
        path.write_bytes(original)
    (directory / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"control": "PASS", "killed": len(results), "total": len(MUTANTS),
                      "source_restored": path.read_bytes() == original}))


if __name__ == "__main__":
    main()
