"""Rule 12 driver for spec 059 T001: the preregistration record matches the rule it freezes.

Run: python tests/mutation/run_059_t001_mutants.py

Each mutant edits ONE site in an isolated copy (spec 043 D-4 helper). A kill counts only when the
JUnit report shows a FAILURE (never an error) whose assertion message carries the named witness.
The unchanged copy must pass with exactly the collected count; sources and `docs/trials/` bytes
must be identical before and after.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
DECL = ".specify/specs/059-live-allocation/declaration.json"
SPEC = ".specify/specs/059-live-allocation/spec.md"
TEST = "tests/test_059_declaration.py"
COPIED = ("scripts", "docs/trials", "tests/context.py", "tests/spec033_support.py", DECL, SPEC, TEST)
COLLECTED = 5
MUTANTS = (
    ("family unregistered", "scripts/trial_registry.py",
     '"059-allocation": ".specify/specs/059-live-allocation/declaration.json"', '"059-x": "none"', "T001 REGISTER"),
    ("sleeve dropped", DECL, '    "DBC"\n', '    "SHY"\n', "T001 RULE sleeves"),
    ("vol target moved", DECL, '"portfolio_vol_target_annual": 0.1,', '"portfolio_vol_target_annual": 0.12,', "T001 RULE vol target"),
    ("spec edited after hashing", SPEC, "## 6. Out of scope", "## 6. Out of scope (edited)", "T001 SPEC"),
)
ASSERTION = ("AssertionError", "assert ")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    with tempfile.TemporaryDirectory(prefix="t001-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            path.write_text(text.replace(mutant[2], mutant[3]), encoding="utf-8")
            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, TEST, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == COLLECTED, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), el.get("message") or "")
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    watched = ["scripts/trial_registry.py", DECL, SPEC, TEST]
    sources = tree_digest(watched)
    ledger = tree_digest(["docs/trials"])
    with guarded():
        control = run_copy(None)
        assert not control, f"unchanged copy is not green: {control}"
        print(f"CONTROL green (unchanged copy, {COLLECTED} collected)")
        killed = 0
        for mutant in MUTANTS:
            results = run_copy(mutant)
            ok = not any(k == "error" for k, _, _ in results) and any(
                k == "failure" and name.startswith("test_") and msg.startswith(ASSERTION) and mutant[4] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[4]}")
    assert tree_digest(watched) == sources, "sources changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
