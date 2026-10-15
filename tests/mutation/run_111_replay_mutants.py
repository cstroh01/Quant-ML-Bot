"""Rule 12 driver for spec 059 FR-006 / SCOPE §11.3.5 (queue Q111): the PAPER replay harness.

Run: python tests/mutation/run_111_replay_mutants.py

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
REPLAY, TARGETS, LOOP = "scripts/replay_runner.py", "scripts/paper_targets.py", "exec/paper_loop.py"
TEST = "tests/test_111_replay.py"
COPIED = ("scripts", "exec", "docs/trials", "tests/context.py", "tests/test_110_paper_allocation.py", TEST)
COLLECTED = 7
MUTANTS = (
    ("unhandled error swallowed", REPLAY,
     '                    report["errors"].append({"session": session.isoformat(), "error": f"{type(exc).__name__}: {exc}"})\n',
     '                    pass\n', "Q111 ERROR"),
    ("denials not reported", REPLAY, '                    report["denied"] += [', '                    report["denied"] += [] and [',
     "Q111 DENIED"),
    ("verdict ignores aborts", REPLAY, "not w[\"errors\"] and not w[\"aborted\"] and", "not w[\"errors\"] and", "Q111 ABORT"),
    ("fill at the close", REPLAY, "        price_row = self.opens.loc[pd.Timestamp(self.session)]",
     "        price_row = self.closes.loc[pd.Timestamp(self.session)]", "Q111 FILL"),
    ("buys sent with unfilled sells", TARGETS,
     '    frame.attrs["deferred_buys"] = len(buys) if sells_before_buys and sells else 0',
     '    frame.attrs["deferred_buys"] = 0', "Q111 DEFER"),
    ("no-trade band removed", TARGETS, " or abs(delta) * price < min_trade_fraction * equity:", ":",
     "Q111 DECISIONS"),
    ("deferred decision marked done", LOOP, " and not plan.deferred and", " and", "Q111 DECISIONS"),
)


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file() and "__pycache__" not in p.parts}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    with tempfile.TemporaryDirectory(prefix="q111-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            text = text.replace(mutant[2], mutant[3])
            path.write_text(text, encoding="utf-8")
            compile(text, str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, TEST, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == COLLECTED, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), (el.get("message") or "") + (el.text or ""))
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    watched = [REPLAY, TARGETS, LOOP, TEST]
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
