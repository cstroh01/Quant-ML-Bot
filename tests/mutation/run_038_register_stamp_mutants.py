"""Rule 12 driver for spec 038 T022: the limitations register and provenance stamp (FR-001, FR-002).

Run: python tests/mutation/run_038_register_stamp_mutants.py. One-site mutants of `scripts/disclosure.py`
(and, for M1-scope, of the `docs/SCOPE-V1.md` copy) in an isolated copy; a kill is a FAILURE (never an
error) whose message carries the witness. Same control and byte-identity checks as run_058_t007_mutants.py.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import time
from xml.etree import ElementTree

from driver_support import copy_into, guarded, run_pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = "scripts/disclosure.py"
SCOPE = "docs/SCOPE-V1.md"
TESTS = ("tests/test_038_register.py", "tests/test_038_stamp.py")
COPIED = ("scripts", "tests/context.py", SCOPE, *TESTS)
COLLECTED = 24
DIVIDEND = (
    '    "Dividend payment dates are a declared conservative bound, not observed data. No free source "\n'
    '    "provides them historically. Dividend cash is credited no earlier than it could have arrived, "\n'
    '    "so the ledger is never optimistic.",\n')
FUNDAMENTALS = '    "No point-in-time fundamentals. Nothing knowable-on-date beyond price and volume.",\n'
DAILY = '    "Daily bars only. No intraday, no microstructure, no order-book data.",\n'
SCOPE_DAILY = "- **Daily bars only.** No intraday, no microstructure, no order-book data.\n"
UTC = "run = run.astimezone(timezone.utc)"
RUN_LINE = "f\"run (UTC): {run.date().isoformat()} {run.strftime('%H:%M:%S')}Z\","
IDENTITY = "identity = source_identity(root, workspace_state=workspace_state)"
# (name, file, exact old fragment, mutant fragment, witness, needs time.tzset)
MUTANTS = (
    ("M1 dividend-bound item dropped", GUARD, DIVIDEND, "", "038 REGISTER drift", False),
    ("M1-scope SCOPE copy gains a bullet", SCOPE, SCOPE_DAILY,
     SCOPE_DAILY + "- **Weekly rebalancing only.**\n", "038 REGISTER drift", False),
    ("M2 commit cached across calls", GUARD, IDENTITY,
     f'identity = globals().setdefault("_IDENTITY", {IDENTITY.split(" = ")[1]})', "038 STAMP M2 stale commit", False),
    ("M3 run date from the last bar", GUARD, RUN_LINE, RUN_LINE.replace(
        "{run.date().isoformat()}", "{_session_label(data_end) if data_end is not None else run.date().isoformat()}"),
     "038 STAMP M3 run date", False),
    ("M3b local zone instead of UTC", GUARD, UTC, "run = run.astimezone()", "038 STAMP M3b local zone", True),
    ("review: workspace hard-coded", GUARD, "f\"workspace: {identity['workspace_state']}\",", '"workspace: unknown",',
     "038 STAMP workspace", False),
    ("review: zone east of UTC", GUARD, UTC, "run = datetime.fromtimestamp(run.timestamp() + 3600, timezone.utc)",
     "038 STAMP M3b midnight", False),
    ("review: data_end after run accepted", GUARD, "if label > run.date().isoformat():", "if False:",
     "DID NOT RAISE", False),
    ("review: register entries reordered", GUARD, FUNDAMENTALS + DAILY, DAILY + FUNDAMENTALS,
     "038 REGISTER drift", False),
    ("review: naive clock accepted", GUARD, "if not isinstance(run, datetime) or run.tzinfo is None or run.utcoffset() is None:",
     "if not isinstance(run, datetime):", "DID NOT RAISE", False),
    ("review: Sharpe status reworded", GUARD, 'SHARPE_STATUS = "provisional, undeflated (Rule 15)"',
     'SHARPE_STATUS = "provisional (Rule 15)"', "038 REGISTER sharpe_status", False),
)
FAILURE = ("AssertionError", "assert ", "Failed: DID NOT RAISE")


def tree_digest(relatives) -> dict[str, str]:
    paths = [p for r in relatives for p in ([ROOT / r] if (ROOT / r).is_file() else sorted((ROOT / r).rglob("*")))]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def run_copy(mutant) -> list[tuple[str, str, str]]:
    """(kind, test name, message) for every failure/error; raises unless COLLECTED were collected."""
    with tempfile.TemporaryDirectory(prefix="t022-") as temporary:
        root = copy_into(Path(temporary), COPIED)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            assert text.count(mutant[2]) == 1, f"{mutant[0]}: expected one site, found {text.count(mutant[2])}"
            path.write_text(text.replace(mutant[2], mutant[3]), encoding="utf-8")
            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
        xml = root / "r.xml"
        result = run_pytest(root, *TESTS, "-q", "-p", "no:cacheprovider", f"--junitxml={xml}")
        assert xml.exists(), f"no JUnit report: {result.stderr[-800:]}"
        suite = ElementTree.parse(xml).getroot().iter("testsuite")
        assert sum(int(s.get("tests", 0)) for s in suite) == COLLECTED, f"collection: {result.stdout[-800:]}"
        cases = ElementTree.parse(xml).getroot().iter("testcase")
        return [(kind, case.get("name", ""), el.get("message") or "")
                for case in cases for kind in ("failure", "error") for el in case.findall(kind)]


def main() -> int:
    watched = [GUARD, SCOPE, *TESTS]
    sources = tree_digest(watched)
    ledger = tree_digest(["docs/trials"])
    runnable = [m for m in MUTANTS if not m[5] or hasattr(time, "tzset")]
    with guarded():
        control = run_copy(None)
        assert not control, f"unchanged copy is not green: {control}"
        print(f"CONTROL green (unchanged copy, {COLLECTED} collected)")
        killed = 0
        for mutant in MUTANTS:
            if mutant not in runnable:
                print("SKIPPED ", f"{mutant[0]} (time.tzset unavailable; 'zone east of UTC' covers conversion)")
                continue
            results = run_copy(mutant)
            ok = not any(k == "error" for k, _, _ in results) and any(
                k == "failure" and name.startswith("test_") and msg.startswith(FAILURE) and mutant[4] in msg
                for k, name, msg in results)
            killed += ok
            print("KILLED  " if ok else "SURVIVED", f"{mutant[0]} -> {mutant[4]}")
    assert tree_digest(watched) == sources, "sources changed"
    assert tree_digest(["docs/trials"]) == ledger, "docs/trials changed"
    print(f"{killed}/{len(runnable)} killed; sources and docs/trials ({len(ledger)} files) byte-identical")
    return 0 if killed == len(runnable) else 1


if __name__ == "__main__":
    sys.exit(main())
