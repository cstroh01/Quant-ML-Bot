# Spec 037 review handoff

Run family: `spec037-20260925`, continued 2026-09-26. Camden owns review, Git and merge.
No Git commands were run. HEAD was exported through a read-only object-store reader.

## File-by-file changes

| File | Change and reason |
|---|---|
| `scripts/feature_set_comparison.py` | Joint observable-truth mask for classification and regression; reject invalid scored inputs; report scored/unscored bars; explicitly spawn workers so native thread limits take effect before import. |
| `tests/test_feature_set_comparison.py` | Two real orchestrator runs instead of repeated fits; short non-vacuous fixture; exact prediction comparisons; retain worker invariant; AST-based external-dependency guard with red controls. |
| `tests/test_clean_clone_037.py` | Missing-truth, pairing, invalid-input and empty-sample regressions; unsafe-cast and start-method mutants using the existing 019 helper; one-ULP equivalence perturbation; funding-forwarding control and mutant. |
| `scripts/multi_ticker_comparison.py` | Explicit required capital and liquidation parameters forwarded to strategy and baselines; CLI requires those choices. No loader rewiring or invented funding defaults. |
| `tests/test_multi_ticker_comparison.py` | Declare synthetic unadjusted price basis and explicit account choices; derive purge/embargo from actual target metadata; CSV round-trip uses temporary storage. |
| `.github/workflows/test.yml` | Python job timeout 20 minutes; web job timeout 10 minutes. |
| `README.md` | One setup sentence: exact pins require Python >=3.12 because of NumPy; pandas/contourpy alone require >=3.11. |
| `.specify/specs/037-clean-clone-green/spec.md` | Template-derived requirements, root-cause decision, observed scope boundaries, Python-floor correction and report-only license/package decisions. |
| `.specify/specs/037-clean-clone-green/plan.md` | Template-derived implementation/verification plan and constitutional checks. |
| `.specify/specs/037-clean-clone-green/tasks.md` | Template-derived checklist with explicit unresolved scope gate. |
| `.specify/specs/037-clean-clone-green/failure-table.md` | Every baseline failed/error node categorized; links to raw evidence and environment. |
| `.specify/specs/037-clean-clone-green/artifacts/` | Installation, baseline, red/green/mutation output, source/package provenance, review diff and protected-file audit. |
| This file | Review record, final evidence and remaining work. |

## Root-cause answer

**(i): NaN truth is legitimate.** Feature generation retains inference-eligible rows
with unobservable future outcomes; nested CV returns those covered positions.
The comparison cast ignored that distinction. The fix excludes unknown outcomes
jointly from both sides of each paired statistic, without substituting a class,
changing inference or shortening the calendar. Scored and unscored counts travel
with the results. Regression uses the same observation boundary.

## Evidence

- Clean HEAD baseline: 12 failed, 840 passed, 9 errors, no skips. Source:
  `artifacts/baseline.txt`, `baseline.xml`, `baseline-environment.json`.
- New semantic controls/mutants: 24 passed. Source: `artifacts/mutation-green.txt`.
- Multi-ticker focused suite: 11 passed. Source: `artifacts/funding-green.txt`.
- Earlier red evidence: `scoring-red.txt`, `pinning-red.txt`, `funding-red.txt`.
  `comparison-first-run.txt` records the intermediate AST guard false positive,
  subsequently fixed without allowing external parallelism libraries.
- Protected-file hashes and exact reversible README delta: `artifacts/boundary-audit.json`.
- Fresh HEAD-plus-patch source identity: `artifacts/final-source.json`.
- Final full-suite result: **886 passed, 1 failed, 0 errors, 0 skips** on 2026-09-26,
  pytest 619.53 seconds. Sources: `artifacts/final.txt`, `final.xml`,
  `final-environment.json`, `final-acceptance.json`. Exactly 20 baseline failure/error
  nodes resolved; zero new failing nodes. The green-from-clean-clone gate is **not met**.

All counts above are test outcomes, not investment results. Full dependency/OS/CPU
provenance is in the corresponding environment JSON. Linux CI has not been run here;
local execution is Windows 11, Python 3.12.13, with the exact pinned requirements.

## Outstanding boundary

`tests/test_reports_api.py::TestReportsApi::test_backtest_tearsheet` expects the old
success contract from an unverified CSV. Its route needs Spec 036's funded-ledger
caller wiring, expressly excluded from this task. The route and test remain unchanged.
No new skip has been authorized or applied. Camden was asked whether to retain the
success test under a documented pending-036 skip plus a live rejection regression,
or leave it red until Spec 036. The current implementation takes no answer as no approval.

Real multi-ticker adjusted downloads are still rejected; synthetic test success is
not evidence that real unadjusted data wiring, funded execution, or capital gates
are complete. No paid data, runtime dependency, license, or packaging conversion was added.
