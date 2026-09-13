"""Spec 018 mutation check: restore each deleted fabricated value in a copy.

    python tests/mutation/run_spec_018_mutants.py

Spec 017's T030 shape, kept in the repository (finding 58): control first, each
mutant in a copy with no data/cache/ or reports/web/dist/, SHA-256 of the
sources before and after. Caught means a test fails that the control did not.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COPIED = (
    "scripts", "reports/__init__.py", "reports/api", "reports/web/src", "reports/requirements-ui.txt",
    "requirements-dev.txt", "tests/context.py", "tests/api_fixtures.py",
    "tests/test_reports_api.py", "tests/test_no_fabricated_values.py",
)
TEST_MODULES = ("test_reports_api.py", "test_no_fabricated_values.py")
API, WEB = "reports/api", "reports/web/src/components"
GATE_1_STATUS = '(Sharpe <= 0.3), and 2x cost stress test.",\n            status="unknown",'

# (finding, file, find, replace, restored defect). `find` must occur exactly once.
MUTANTS = (
    ("45", f"{API}/routes/diagnostics.py",
     "reason=SIGNIFICANCE_NOT_COMPUTED)", "reason=SIGNIFICANCE_NOT_COMPUTED, p_value=0.084)",
     "literal `p_value=0.084` passed to the significance response"),
    ("45", f"{API}/routes/diagnostics.py",
     '"No saved experiment run', '"Logistic McNemar p = 0.084, passed screening. No saved experiment run',
     "p-value figure written into the significance response text"),
    ("45", f"{WEB}/views/FeatureDiagnosticsView.tsx",
     "reason={significance.reason}", "reason={String(significance.p_value)}",
     "screen renders a `p_value` field again"),
    ("47", f"{API}/routes/capital_gate.py",
     GATE_1_STATUS, GATE_1_STATUS.replace('"unknown"', '"passed"'),
     "Gate 1 `passed` with no evidence"),
    ("47", f"{API}/routes/capital_gate.py",
     '"No verification artifact is recorded for this gate, so its state is unknown."', '"All 301 unit tests passing."',
     "test count restored in gate details"),
    ("47", f"{API}/schemas.py",
     'if self.status != "unknown" and not self.evidence:', "if False:",
     "evidence requirement removed from the gate schema"),
    ("47", f"{WEB}/layout/Header.tsx",
     "TESTS: NOT REPORTED", "CORE: 311/311 PASS",
     'header badge "311/311 PASS" restored'),
    ("47", f"{WEB}/views/CapitalGateView.tsx",
     "of {gateStatus.gates.length} Gates", "of 5 Gates",
     "literal gate total restored"),
    ("46", f"{API}/routes/ml_rundown.py",
     'forecast_title = "Both Trend Rules Read Down"\n',
     'forecast_title = "Both Trend Rules Read Down"\n'
     '        technical_forecast = "P(Down) = 53.8% | Logit Score = -0.15 | Forward Horizon = 1 bar"\n',
     "bearish-branch forecast literal restored"),
    ("46", f"{API}/routes/ml_rundown.py",
     "NotComputed(reason=FORECAST_NOT_COMPUTED)", 'NotComputed(reason="P(Up) = 54.2% | Logit Score = +0.17")',
     "forecast probability and logit shown as the model forecast"),
    ("46", f"{API}/routes/ml_rundown.py",
     "trend rules disagree.", "Mixed regime signals. Model advises standing down.",
     "rule summary attributed to a model"),
    ("46", f"{WEB}/layout/MLRundownPane.tsx",
     "Indicator Rule Readings", "ML Model Decision Rundown",
     "pane titled as model output"),
    ("57", f"{API}/routes/data.py",
     'without network access."""\n', 'without network access."""\n    cache_dir = CACHE_DIR\n',
     "loader bypasses the injected cache directory"),
    ("57", f"{API}/main.py",
     "StaticFiles(directory=str(dist_dir)", "StaticFiles(directory=str(DIST_DIR)",
     "static mount ignores the test's asset directory"),
)


def digest() -> str:
    """SHA-256 over every source file a mutant targets, read from the repository."""
    sha = hashlib.sha256()
    for relative in sorted({mutant[1] for mutant in MUTANTS}):
        sha.update((REPO / relative).read_bytes())
    return sha.hexdigest()


def failing_tests(mutant: tuple | None) -> tuple[int, set[str]]:
    """(tests run, ids of failing or erroring tests) in a fresh copy with `mutant` applied."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for relative in COPIED:
            source, target = REPO / relative, root / relative
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        if mutant is not None:
            path = root / mutant[1]
            text = path.read_text(encoding="utf-8")
            if text.count(mutant[2]) != 1:
                raise SystemExit(f"{mutant[1]}: find string occurs {text.count(mutant[2])} times, not once")
            path.write_text(text.replace(mutant[2], mutant[3]), encoding="utf-8")

        ran, failing = 0, set()
        for module in TEST_MODULES:
            result = subprocess.run(
                [sys.executable, "-B", "-W", "ignore", "-m", "unittest", "discover", "-s", "tests", "-p", module],
                cwd=root, capture_output=True, encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            summary = re.search(r"^Ran (\d+) tests?", result.stderr, flags=re.MULTILINE)
            ran += int(summary.group(1)) if summary else 0
            failing |= set(re.findall(r"^(?:FAIL|ERROR): (\S+ \(\S+\))", result.stderr, flags=re.MULTILINE))
            if result.returncode and not summary:
                failing.add(f"{module} did not run")
        return ran, failing


def main() -> int:
    before = digest()
    ran, control = failing_tests(None)
    print(f"Control (no mutation): {ran} tests run, {len(control)} failing")
    for test in sorted(control):
        print(f"  - {test}")
    print("\n| # | Finding | File | Restored defect | Newly failing tests | Caught |")
    print("|---|---|---|---|---|---|")
    survivors = 0
    for number, mutant in enumerate(MUTANTS, start=1):
        _, failing = failing_tests(mutant)
        new = failing - control
        survivors += not new
        print(f"| {number} | {mutant[0]} | `{Path(mutant[1]).name}` | {mutant[4]} | {len(new)} | {'yes' if new else '**NO**'} |")
    after = digest()
    print(f"\nSource SHA-256 before {before[:16]}, after {after[:16]}: {'identical' if before == after else 'CHANGED'}")
    print(f"Survivors: {survivors} of {len(MUTANTS)}")
    return 1 if control or survivors or before != after else 0


if __name__ == "__main__":
    sys.exit(main())
