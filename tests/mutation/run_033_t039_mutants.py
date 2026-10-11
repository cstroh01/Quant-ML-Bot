"""Rule 12 driver for spec 033 T039+T044: lifetime N_current and the family N beside it.

Run: python tests/mutation/run_033_t039_mutants.py

Each mutant edits ONE site in an isolated copy (spec 043 D-4 helper). A kill counts only when the
JUnit report shows a FAILURE (never an error) in a T039/T044 test whose assertion message carries the
named witness. An unchanged copy must pass with exactly two collected tests, every mutated file must
compile, and the production sources and `docs/trials/` bytes must be identical before and after.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
COPIED = ("scripts", "tests/context.py", "tests/spec033_support.py", "tests/test_033_dsr.py",
          ".specify/specs/058-edge-research-program/declaration.json")
TESTS = ("test_t039_lifetime_n_counts_every_candidate_start", "test_t044_lifetime_dsr_always_family_dsr_beside_it")
SB = "scripts/selection_bias.py"
# (name, file, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("unique config hashes counted as N", SB, 'n_post = state["n_post_ledger"]',
     'n_post = len({e["config_hash"] for e in state["events"] if e["role"] == "candidate"})', "T039 DUPLICATES"),
    ("only completed trials counted", SB, 'n_post = state["n_post_ledger"]',
     'n_post = sum(e["event_type"] == "completed" and e["role"] == "candidate" for e in state["events"])', "T039 INCOMPLETE"),
    ("baseline starts counted", SB, 'n_post = state["n_post_ledger"]',
     'n_post = sum(e["event_type"] == "started" for e in state["events"])', "T039 ROLES"),
    ("backfill dropped from N", SB, '"n_current": n_backfill + n_post', '"n_current": n_post', "T039 NCURRENT"),
    ("backfill digest unchecked", SB, 'if backfill.get("sha256") != digest(body)', 'if "sha256" not in backfill', "T039 CORRUPT"),
    ("draft backfill accepted", SB, 'if backfill.get("status") != "complete" or isinstance', "if isinstance",
     "T039 DRAFT"),
    ("breached family keeps N_family", SB, 'status["n_family"] if status["within_cap"] else counts["n_current"]',
     'status["n_family"] if status["n_family"] is not None else counts["n_current"]', "T044 CAP"),
    ("family N replaces lifetime N", SB, 'lifetime = matrix_dsr(matrix, selected_trial=selected_trial, n_current=counts["n_current"])',
     'lifetime = matrix_dsr(matrix, selected_trial=selected_trial, n_current=fam["n_dsr"] if fam else counts["n_current"])',
     "T044 LIFETIME"),
    ("matrix columns used as N", SB, 'lifetime = matrix_dsr(matrix, selected_trial=selected_trial, n_current=counts["n_current"])',
     'lifetime = matrix_dsr(matrix, selected_trial=selected_trial, n_current=len(matrix["columns"]))', "T044 NCURRENT"),
    ("unstored backfill accepted", SB, 'if backfill not in stored:', "if False:", "T039 ANCHOR"),
    ("superseded backfill accepted", SB, "if any(n_backfill < ", "if False and any(n_backfill < ", "T039 SUPERSEDED"),
    ("declaration anchored after first start", SB, "if anchor not in heads[:first]:", "if anchor not in heads:", "T044 ANCHOR"),
    ("family cap unbounded", SB, 'if not 1 <= status["cap"] <= 50:', 'if not 1 <= status["cap"]:', "T044 CAPLIMIT"),
    ("family id unchecked", SB, 'elif matrix["family"]["id"] != fam["family"]:', "elif False:", "T044 MISMATCH"),
    ("altered declaration keeps family N", SB, '"cap": None, "within_cap": False,', '"cap": None, "within_cap": True,',
     "T044 DECLARATION"),
)
ASSERTION = ("AssertionError", "assert ")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises if nothing was collected."""
    with tempfile.TemporaryDirectory(prefix="t039-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            path.write_text(text.replace(mutant[2], mutant[3]), encoding="utf-8")
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, "tests/test_033_dsr.py", "-k", "t039 or t044", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == len(TESTS), f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), el.get("message") or "")
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    sources = tree_digest(sorted({m[1] for m in MUTANTS}) + ["tests/test_033_dsr.py"])
    ledger = tree_digest(["docs/trials"])
    with guarded():
        control = run_copy(None)
        assert not control, f"unchanged copy is not green: {control}"
        print(f"CONTROL green (unchanged copied modules, {len(TESTS)} collected)")
        killed = 0
        for mutant in MUTANTS:
            results = run_copy(mutant)
            ok = not any(k == "error" for k, _, _ in results) and any(
                k == "failure" and name in TESTS and msg.startswith(ASSERTION) and mutant[4] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[4]}")
    assert tree_digest(sorted({m[1] for m in MUTANTS}) + ["tests/test_033_dsr.py"]) == sources, "source changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
