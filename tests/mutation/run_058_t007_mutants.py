"""Rule 12 driver for spec 058 T007: the holdout seal (FR-002, D-3).

Run: python tests/mutation/run_058_t007_mutants.py. One-site mutants of `scripts/data_sources.py` in
an isolated copy; a kill is a FAILURE (never an error) whose assertion carries the witness. Same
control and byte-identity checks as run_058_t005_mutants.py.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = "scripts/data_sources.py"
TEST = "tests/test_058_holdout.py"
SOURCE = ".specify/specs/058-edge-research-program/declaration.json"
COPIED = ("scripts", "tests/context.py", SOURCE, TEST)
COLLECTED = 16
# (name, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("cutoff one session early", "RESEARCH_END = date(2023, 9, 29)", "RESEARCH_END = date(2023, 9, 28)", "T007 CUTOFF"),
    ("cutoff one session late", "RESEARCH_END = date(2023, 9, 29)", "RESEARCH_END = date(2023, 10, 2)", "T007 CUTOFF"),
    ("cutoff inclusive", "index.normalize() > pd.Timestamp(RESEARCH_END)", "index.normalize() > pd.Timestamp(HOLDOUT_START)", "T007 CUTOFF"),
    ("token reused", 'open(spent_path, "x", encoding="utf-8")', 'open(spent_path, "w", encoding="utf-8")', "T007 REUSE"),
    ("token bound to another hash", "if token.config_hash != config_hash:", "if False:", "T007 BIND"),
    ("NaT label accepted", "if index.hasnans:", "if False:", "T007 NAT"),
)
ASSERTION = ("AssertionError", "assert ")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises unless COLLECTED were collected."""
    with tempfile.TemporaryDirectory(prefix="t007-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / GUARD
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[1]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[1])}"
            path.write_text(text.replace(mutant[1], mutant[2]), encoding="utf-8")
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
    watched = [GUARD, TEST, SOURCE]
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
                k == "failure" and name.startswith("test_") and msg.startswith(ASSERTION) and mutant[3] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[3]}")
    assert tree_digest(watched) == sources, "sources changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
