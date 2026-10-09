"""Rule 12 driver for spec 033 T014: the AST guard consumes the runner inventory's classifications.

Run: python tests/mutation/run_033_t014_mutants.py

Each mutant edits ONE site of `bypasses`/`classified` in an isolated copy (spec 043 D-4 helper). A
kill counts only when the JUnit report shows a FAILURE (never an error) in a T014 test whose
assertion message carries the named witness. The unchanged copy must pass with exactly the six T014
tests collected, every mutated file must compile, and the guard source, the read-only inventory and
the `docs/trials/` bytes must be identical before and after.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = "tests/test_033_trial_instrumentation.py"
INVENTORY = "tests/fixtures/spec_033/runner_inventory.json"
COPIED = ("scripts", "reports/api", "tests/context.py", INVENTORY, GUARD)
SELECT = (GUARD, "-k", "t014")
COLLECTED = 6
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("inventory ignored", "inventory = classified(root)", "inventory = {}", "T014 CANDIDATE"),
    ("inventoried runner paths not scanned", "paths |= {root / p for p in runners if (root / p).is_file()}",
     "paths |= set()", "T014 CANDIDATE"),
    ("test-only exemption ignored", "or (relative, name) in exempt: continue", ": continue", "T014 TEST-ONLY"),
    ("exemption keyed by path only", "(relative, name) in exempt", "relative in {q for q, _ in exempt}", "T014 SCOPE"),
    ("test-only wins over a runner class", 'if kinds == {"test-only"}}', 'if "test-only" in kinds}', "T014 CONFLICT"),
    ("unknown class exempt", 'if kinds == {"test-only"}}',
     'if kinds.isdisjoint({"candidate runner", "required baseline"})}', "T014 FAIL-CLOSED"),
    ("missing runner path silent", "if not (root / p).is_file()]", "if False]", "T014 FAIL-CLOSED"),
)
ASSERTION = ("AssertionError", "assert ")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises unless exactly six were collected."""
    with tempfile.TemporaryDirectory(prefix="t014-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / GUARD
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[1]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[1])}"
            path.write_text(text.replace(mutant[1], mutant[2]), encoding="utf-8")
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, *SELECT, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == COLLECTED, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), el.get("message") or "")
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    watched = [GUARD, INVENTORY]
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
                k == "failure" and name.startswith("test_t014_") and msg.startswith(ASSERTION) and mutant[3] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[3]}")
    assert tree_digest(watched) == sources, "guard or inventory changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; guard, inventory and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
