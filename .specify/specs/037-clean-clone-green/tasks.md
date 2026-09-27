# Tasks: Green from a clean clone

**Input**: [spec.md](spec.md), [plan.md](plan.md)
**Organization**: Sequential ownership; tests precede fixes. Template-derived task
phases do not authorize Git operations or parallel agents.

## Phase 1: Setup

- [x] T001 Read constitution, CLAUDE.md, scope and all three templates.
- [x] T002 Capture protected hashes and export committed HEAD outside the repository.
- [x] T003 Install exact requirements in isolated Python 3.12; save resolved packages.

## Phase 2: Foundational baseline

- [x] T004 Run `python -m pytest tests` in HEAD export and retain raw output.
- [x] T005 Categorize every failing/error node in `failure-table.md` with provenance.

## Phase 3: US1/US2 — Correct paired comparisons

- [x] T006 Record legitimate unknown-target decision and source evidence in `spec.md`.
- [x] T007 Write and observe red scoring regressions in `tests/test_clean_clone_037.py`.
- [x] T008 Fix scoring in `scripts/feature_set_comparison.py` without fabricated outcomes.
- [x] T009 Kill unsafe-cast mutant using `tests/mutation_support_019.py` and green control.
- [x] T010 Repair other measured clean-clone residuals within ownership boundaries.

## Phase 4: US3 — Portable bounded verification

- [x] T011 Diagnose and prove worker pinning; preserve effective one-thread assertion.
- [x] T012 Reduce equivalence workload while keeping real estimators, all registry
  entries, both feature sets, process boundaries and exact output comparisons.
- [x] T013 Add both workflow timeouts; add one README setup Python-floor sentence.

## Phase 5: Closeout

- [x] T014 Run focused regressions/mutations and the full suite in fresh HEAD-plus-patch export.
- [x] T015 Inventory skips, package/module facts, hashes and raw evidence.
- [x] T016 Finalize spec/plan/tasks and file-by-file report; leave Camden's merge gate open.

## Dependencies & Execution Order

T003 → T004 → T005 → T007 → T008 → T009. T011 requires baseline evidence.
T014 follows all implementation and T015/T016 follow final validation. No step can
replace a failed or unexecuted full suite with a focused green claim.

## Remaining scope boundary

T010 repaired the measured residuals within ownership boundaries. T014 records an
executed full suite, not a passing gate: **886 passed, 1 failed, no skips/errors**.
The original tearsheet success test requires excluded Spec 036 wiring. No skip was
added without Camden answering the scope question. Exact evidence is in
`artifacts/final-acceptance.json`; protected hashes pass in `boundary-audit.json`.

- [ ] T017 Meet SC-001: zero failed/error tests from a clean export. Blocked by the
  unchanged Spec 036 tearsheet success test; not waived or silently rebaselined.
