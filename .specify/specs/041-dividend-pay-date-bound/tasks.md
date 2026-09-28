# Tasks: Dividend pay date as a declared conservative bound

**Input**: [spec.md](spec.md), [plan.md](plan.md)
**Organization**: sequential and single-threaded. Tests come before fixes. Template
phases do not authorize Git operations or parallel agents.

## Phase 0: Precondition

- [ ] T000 Confirm spec 036 has merged (Camden). Do not start otherwise: 036 and
  041 both edit `scripts/data.py`.
- [ ] T001 Re-measure: run `python -m pytest tests` and record the passed count as
  041's baseline in this file. Confirm `data.py:634-635`, `:886-888` and
  `:985-988` still hold the B-1 lines, and update the references if 036 moved them.

## Phase 1: Red tests (`tests/test_041_pay_date_bound.py`)

- [ ] T002 SC-004: parametrized FR-004 table, with exact message fragments and a
  green control. Must fail today: a version-2 bound dividend is rejected, and
  there is no basis column yet.
- [ ] T003 SC-002: offline twin of the AAPL flow via `ticker_factory`. Must fail
  today with `dividend payment date missing`.
- [ ] T004 SC-003: the three fail-closed scenarios, each asserting that the cache
  directory is empty afterwards.
- [ ] T005 SC-005 oracles for M1 (full-allocation re-entry inside the ex→pay
  window), M2 and M3, written against `tests/mutation_support_019.killed`.
- [ ] T006 SC-006: direction checks for `unbounded` and for `bound_sessions:N` with
  a test-only synthetic citation.

## Phase 2: Implementation (`scripts/data.py`)

- [ ] T007 FR-001: `DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS = None`,
  `DIVIDEND_PAY_DATE_BOUND_SOURCE = None`, one policy-derivation function, and
  the `UNBOUNDED_PAY_DATE` sentinel. No literal lag at any call site.
- [ ] T008 FR-002: refuse a finite lag without a citation, a zero lag, and a
  negative lag (M4).
- [ ] T009 FR-003: add `Dividend_Pay_Date_Basis` to the action columns; add
  `dividend_pay_date_policy` to `UnadjustedSourceSnapshot` (default
  `"sourced"`); make the yfinance adapter declare the policy and write basis
  `bound`.
- [ ] T010 FR-004: `_validate_corporate_actions(..., pay_date_policy="sourced")`.
  Keep every existing check verbatim and add only the one relaxed cell plus the
  new basis checks.
- [ ] T011 FR-003: manifest version 2 (policy and conditional bound source), and
  version-1 strict compatibility in `_validate_manifest_bundle`.
- [ ] T012 FR-005: loader resolution and the new `attrs` keys.

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
- [ ] T019 Hand off, stating that Rule 14 is still owed and Q-1 is open (if unanswered).

## Dependencies & Execution Order

T000 → T001 → T002–T006 (red) → T007 → T008 → T009 → T010 → T011 → T012 → T013 →
T014 → T015–T017 → T018 → T019. Spec 040 may not start until T017 is green and
this spec has merged.
