"""Rule 12 driver for spec 033 T035: Rule 1/5 matrix alignment, boundaries and future-row perturbation.

Run: python tests/mutation/run_033_t035_mutants.py

Each mutant edits ONE site in an isolated copy (spec 043 D-4 helper). A kill counts only when the
JUnit report shows a FAILURE (never an error) in the T035 test whose assertion message carries the
named witness. An unchanged copy must pass with exactly one collected test, every mutated file must
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
COPIED = ("scripts", "tests/context.py", "tests/spec033_support.py", "tests/test_033_dsr.py")
ORACLE = "tests/test_033_dsr.py::test_t035_session_alignment_boundaries_and_perturbation"
SB, TR = "scripts/selection_bias.py", "scripts/trial_registry.py"
DATES = "dates = sorted(set.intersection(*(set(m) for m in maps))) if maps else []"
UNION = "dates = sorted(set.union(*(set(m) for m in maps))) if maps else []\n    "
VALUES = '"values": [[m[d] for m in maps] for d in dates]'
# (name, file, exact old fragment, mutant fragment, witness in the assertion message)
MUTANTS = (
    ("value read from the next shared session (lookahead)", SB, VALUES,
     '"values": [[m[e] for m in maps] for d, e in zip(dates, dates[1:] + dates[-1:])]', "T035 FUTURE"),
    ("value read from the previous shared session (stale)", SB, VALUES,
     '"values": [[m[p] for m in maps] for p, d in zip(dates[:1] + dates[:-1], dates)]', "T035 CURRENT"),
    ("positional join instead of a session join", SB, VALUES,
     '"values": [[t["returns"][i]["log_return"] for t in included] for i in range(len(dates))]', "T035 CURRENT"),
    ("union of sessions with backfill", SB, DATES,
     UNION + "maps = [{d: m[d] if d in m else next((m[e] for e in dates if e > d and e in m), 0.) for d in dates} for m in maps]",
     "T035 DATES"),
    ("union of sessions with forward fill", SB, DATES,
     UNION + "maps = [{d: m[d] if d in m else next((m[e] for e in reversed(dates) if e < d and e in m), 0.) for d in dates} for m in maps]",
     "T035 DATES"),
    ("first shared session dropped", SB, DATES, DATES.replace(")) if maps", "))[1:] if maps"), "T035 DATES"),
    ("last shared session dropped", SB, DATES, DATES.replace(")) if maps", "))[:-1] if maps"), "T035 DATES"),
    ("duplicate session accepted", TR, "if session <= previous:", "if session < previous:", "T035 REJECT duplicate"),
    ("reordered session accepted", TR, "if session <= previous:", "if session == previous:", "T035 REJECT swapped"),
    ("naive-label regex dropped (fromisoformat alone)", TR,
     'if not isinstance(session, str) or not re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", session):',
     "if not isinstance(session, str):", "T035 REJECT compact"),
)
ASSERTION = ("AssertionError", "assert ")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises if nothing was collected."""
    with tempfile.TemporaryDirectory(prefix="t035-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            path.write_text(text.replace(mutant[2], mutant[3]), encoding="utf-8")
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, ORACLE, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == 1, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), el.get("message") or "")
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    sources = tree_digest(sorted({m[1] for m in MUTANTS}) + ["tests/test_033_dsr.py"])
    ledger = tree_digest(["docs/trials"])
    with guarded():
        control = run_copy(None)
        assert not control, f"unchanged copy is not green: {control}"
        print("CONTROL green (unchanged copied modules, 1 collected)")
        killed = 0
        for mutant in MUTANTS:
            results = run_copy(mutant)
            ok = not any(k == "error" for k, _, _ in results) and any(
                k == "failure" and name == ORACLE.rsplit("::", 1)[1] and msg.startswith(ASSERTION) and mutant[4] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[4]}")
    assert tree_digest(sorted({m[1] for m in MUTANTS}) + ["tests/test_033_dsr.py"]) == sources, "source changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
