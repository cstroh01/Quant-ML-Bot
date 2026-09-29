# Tasks: Dividend pay date as a declared conservative bound

**Input**: [spec.md](spec.md), [plan.md](plan.md)
**Organization**: sequential and single-threaded. Tests come before fixes. Template
phases do not authorize Git operations or parallel agents.

## Phase 0: Precondition

- [x] T000 Sequencing cleared by Camden's 2026-09-28 instruction to begin 041:
  this is the sole running lane and `scripts/data.py` is exclusively owned here.
  Git merge state was not queried; no Git command is authorized.
- [x] T001 Re-measure: run `python -m pytest tests` and record the passed count as
  041's baseline in this file. Verified B-1 at `data.py:634-635` (strict null
  rejection), `:929-931` (validation before writing), and `:1029-1031` (adapter
  retains a null vendor pay date). Earlier `:886-888` / `:985-988` refs moved.

## Phase 1: Red tests (`tests/test_041_pay_date_bound.py`)

- [x] T002 SC-004: parametrized FR-004 table, with exact message fragments and a
  green control. Must fail today: a version-2 bound dividend is rejected, and
  there is no basis column yet.
- [x] T003 SC-002: offline twin of the AAPL flow via `ticker_factory`. Must fail
  today with `dividend payment date missing`.
- [x] T004 SC-003: the three fail-closed scenarios, each asserting that the cache
  directory is empty afterwards.
- [x] T005 SC-005 oracles for M1 (full-allocation re-entry inside the ex→pay
  window), M2 and M3, written against `tests/mutation_support_019.killed`.
  Oracles written and tested directly (2026-09-28, Unit 2). **The `killed()`
  wiring is deferred to T015**, because its `old` strings are production lines
  that do not exist yet. Rule 12 proof for M1–M3 is not claimed until then.
- [x] T006 SC-006: direction checks for `unbounded` and for `bound_sessions:N` with
  a test-only synthetic citation. Unit 2 also added the SC-005 M4 / FR-002
  configuration cases and five v2 manifest-field cases (see `artifacts/unit-2.md`).

## Phase 2: Implementation (`scripts/data.py`)

- [x] T007 FR-001: `DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS = None`,
  `DIVIDEND_PAY_DATE_BOUND_SOURCE = None`, one policy-derivation function, and
  the `UNBOUNDED_PAY_DATE` sentinel. No literal lag at any call site.
- [x] T008 FR-002: refuse a finite lag without a citation, a zero lag, and a
  negative lag (M4).
- [x] T009 FR-003: add `Dividend_Pay_Date_Basis` to the action columns; add
  `dividend_pay_date_policy` to `UnadjustedSourceSnapshot` (default
  `"sourced"`); make the yfinance adapter declare the policy and write basis
  `bound`.
- [x] T010 FR-004: `_validate_corporate_actions(..., pay_date_policy="sourced")`.
  Keep every existing check verbatim and add only the one relaxed cell plus the
  new basis checks.
- [x] T011 FR-003: manifest version 2 (policy and conditional bound source), and
  version-1 strict compatibility in `_validate_manifest_bundle`.
- [x] T012 FR-005: loader resolution and the new `attrs` keys.

## Phase 3: Recording and disclosure

- [ ] T013 FR-003: `backtest_harness.run_backtest` records `Pay_Date_Basis` on
  each `dividend` event (`unspecified` when the column is absent). No arithmetic
  change.
- [ ] T014 FR-007: pay-date line in 036's provenance renderer(s), plus the SC-007
  CLI and API tests.

## Phase 4: Verification

- [ ] T015 Run the focused tests green; run M1–M3 killed with green controls; M4
  raises.
- [ ] T016 Confirm the pinned 019 tests (FR-006) are byte-identical and green.
- [ ] T017 Full suite: `python -m pytest tests`. The count equals the T001
  baseline plus the tests in `tests/test_041_pay_date_bound.py`, with 0 failed.
- [ ] T018 **Camden, online, once:** run SC-001 and save
  `artifacts/aapl-bundle.txt` with the date and commit. If it fails on a
  non-pay-date check, record the finding. Do not relax.
- [ ] T019 Hand off, stating that Rule 14 is still owed and Q-1 is confirmed: `unbounded`.

## Dependencies & Execution Order

T000 → T001 → T002–T006 (red) → T007 → T008 → T009 → T010 → T011 → T012 → T013 →
T014 → T015–T017 → T018 → T019. Spec 040 may not start until T017 is green and
this spec has merged.

## Unit 1 evidence (2026-09-28)

Source: [unit-1.md](artifacts/unit-1.md), run `spec041-unit1-20260928T205954-0400`.
Windows, Python 3.14.6, pytest 9.1.1. This is a tests-first checkpoint, not a
green implementation or permission to use bound bundles.

- T001: `python -m pytest tests`: **903 passed, 0 failed, exit 0** (363.11s).
- New tests: **53 cases** = 23 table rows x 2 policies + 3 legacy cases +
  1 offline flow + 3 fail-closed cases. New-file run: **6 passed, 47 failed**.
- All 46 v2 cases currently fail at the unsupported-version guard; their deeper
  semantic checks are not reached yet. The offline flow fails with
  `dividend payment date missing`. No other new test failed.
- Combined run with the unchanged Spec 020 module: **21 passed, 47 failed**;
  all 15 existing Spec 020 tests pass. Its old yfinance refusal assertion will
  need a narrow update when T009 changes that declared-policy behavior.
- Full collection: **956 cases = 903 + 53**, exit 0. No post-edit full execution
  is claimed; the deliberate red tests precede T005–T014 implementation work.
- Every run preserved both trial artifact hashes, both 174 counts, and the
  absent `returns/` directory. Protected/pinned files checked by hash are unchanged.
- T002–T004 are checked as written and observed; v2 green controls, funded-flow
  completion, and M1–M4 proof remain pending. Next unit starts with T005.

## Unit 2 evidence (2026-09-28)

Source: [unit-2.md](artifacts/unit-2.md). Tests only; no production file changed.
New file: 71 cases (53 + 18). Linux/Python 3.12 run in a copy: 7 passed, 64 failed
(17 new red, 1 new green control). Collection: 974 = 903 + 71. Full suite not run.
The Windows gate has not been run for this unit.

## Unit 3 evidence (2026-09-28)

Source: [unit-3.md](artifacts/unit-3.md). Production edits in `scripts/data.py`
(+185 / -13) and one authorized assertion change in
`tests/test_020_unadjusted_price_data.py` (+7 / -1). Windows, repository venv.

- T007-T012 are checked because their tests are green. These are the rule table,
  version-1 strictness, M1-M3 oracles, M4/FR-002, finite-bound and unbounded
  direction, and the manifest-field cases.
- Focused 041 + 020 run: **85 passed, 1 failed**. Full suite `python -m pytest tests`:
  **973 passed, 1 failed, exit 1** (974 = 903 + 71). The one failure is the
  offline flow test at its `Pay_Date_Basis` ledger assertion, owed by T013.
- Ledger tripwire matched before and after every run: 174 lines, both hashes,
  and `returns/` absent. The pinned 019 files are byte-identical.
- Open flags for T015 and Camden are in unit-3.md. They cover the sentinel
  conflict, the M2 oracle gap, new gates still lacking red proof, and the manual
  `tests/mutation/run_mutation_check.py` target string, which no longer matches.
