"""Rule 12 driver for spec 059 FR-004 / D-9 (queue Q100, Q110): the PAPER allocation path.

Run: python tests/mutation/run_110_paper_allocation_mutants.py

Each mutant edits ONE site in an isolated copy (spec 043 D-4 helper). A kill counts only when the
JUnit report shows a FAILURE (never an error) whose message carries the named witness. The
unchanged copy must pass with exactly the collected count; sources and `docs/trials/` bytes must be
identical before and after.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
TARGETS, LOOP, BROKER = "scripts/paper_targets.py", "exec/paper_loop.py", "exec/alpaca_paper.py"
TEST = "tests/test_110_paper_allocation.py"
COPIED = ("scripts", "exec", "docs/trials", "tests/context.py", "tests/mode_fixtures.py", TEST)
COLLECTED = 13
MUTANTS = (
    ("weights from rows after t", TARGETS, "    history = closes.loc[:label, list(ALLOCATION_SLEEVES)]",
     "    history = closes.loc[:, list(ALLOCATION_SLEEVES)]", "Q110 LOOKAHEAD"),
    ("daily re-targeting", TARGETS, "    if executed_decision == decision.strftime(\"%Y-%m-%d\"):", "    if False:", "Q110 HOLD"),
    ("cash buffer dropped", TARGETS, "(weights.fillna(0.0) * (1.0 - cash_buffer))", "(weights.fillna(0.0) * 1.0)", "Q110 DECISION"),
    ("foreign holdings traded", TARGETS, "    if foreign:", "    if False:", "Q110 FOREIGN"),
    ("whole-share profile fractional", TARGETS, "        fractional = bool(fractionable.get(ticker, False))",
     "        fractional = True", "Q110 FRACTION"),
    ("run floors fractional buys", LOOP, "                                 bool(plan.fractionable.get(o.ticker, False))) for o in buys],",
     "                                 False) for o in buys],", "Q110 FRACTION"),
    ("partial decision marked done", LOOP, 'all(a.get("outcome") == "SUBMITTED" for a in actions)', "True", "Q110 PENDING"),
    ("cap shrink ignored", LOOP, "    if submit and plan.pending and not shrunk and", "    if submit and plan.pending and", "Q110 PENDING"),
    ("decision never recorded", LOOP, "        planner.complete(plan.decision_session)\n", "", "Q110 STATE"),
)


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file() and "__pycache__" not in p.parts}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    with tempfile.TemporaryDirectory(prefix="q110-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            path.write_text(text.replace(mutant[2], mutant[3]).replace("ROUND_DOWN, Decimal", "ROUND_DOWN, ROUND_UP, Decimal"),
                            encoding="utf-8")
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, TEST, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == COLLECTED, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), (el.get("message") or "") + (el.text or ""))
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    watched = [TARGETS, LOOP, BROKER, TEST]
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
                k == "failure" and name.startswith("test_") and mutant[4] in msg for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[4]}")
    assert tree_digest(watched) == sources, "sources changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(MUTANTS)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
