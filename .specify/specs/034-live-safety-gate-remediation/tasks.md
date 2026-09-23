# Tasks: Live-Safety-Gate Remediation

**Input**: Design documents from `.specify/specs/034-live-safety-gate-remediation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/safety-api.md`, `quickstart.md`

**Tests**: Mandatory tests-first execution. Each defect receives failing or planted-defect evidence before its implementation change.

## Phase 1: Setup and Scope Controls

- [x] T001 Record the protected SHA-256 for `reports/api/routes/capital_gate.py` and the 817 passed / 18 failed / 9 errors comparison baseline in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T002 Confirm the allowed production surface is limited to `scripts/live_safety_gate.py`, `scripts/order_gateway.py`, `reports/api/main.py`, additive models in `reports/api/schemas.py`, and new `reports/api/routes/safety.py`

## Phase 2: Foundational Test Harness

- [x] T003 Verify existing spec-032 focused tests are stable with `python -m pytest tests/test_live_safety_gate.py -q` before adding spec-034 regressions
- [x] T004 Define shared temporary-gate/API fixtures in `tests/test_safety_router.py` without a broker, network call, credential, or persistent live database

## Phase 3: User Story 1 - Mandatory Order Chokepoint (Priority: P0) MVP

**Goal**: No future submission seam can treat a non-`ALLOW` result as advisory.

**Independent Test**: A fake submit callback runs once after `ALLOW`, never runs after `DENY`, and the AST guard rejects a planted broker-client import without `LiveSafetyGate` while accepting the paired control.

- [x] T005 [US1] Write failing chokepoint and planted AST-guard tests in `tests/test_order_gateway.py`
- [x] T006 [US1] Run `python -m pytest tests/test_order_gateway.py -q` and record the semantic red failure in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T007 [US1] Implement fail-closed `submit_order` and `OrderDeniedError` in `scripts/order_gateway.py`
- [x] T008 [US1] Expose the `LiveSafetyGate` public alias in `scripts/live_safety_gate.py` and make the AST production scan green in `tests/test_order_gateway.py`

## Phase 4: User Story 2 - Ordered Kill and Rolling-Halt Reset (Priority: P0)

**Goal**: The inner rolling latch can clear while the outer kill latch remains active; kill clears second.

**Independent Test**: Latch both in one incident, prove early kill reset is refused, reset rolling halt while kill stays latched, then reset kill successfully.

- [x] T009 [US2] Add the same-transaction deadlock regression test to `tests/test_live_safety_gate.py`
- [x] T010 [US2] Run the focused new test and record its pre-fix failure in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T011 [US2] Remove only the kill-latch rejection from `SafetyGate.reset_rolling_halt` in `scripts/live_safety_gate.py`, preserving reconciliation and live-breach checks
- [x] T012 [US2] Run the focused reset test and the complete `tests/test_live_safety_gate.py` file green

## Phase 5: User Story 3 - Pending-Sell Worst-Case Exposure (Priority: P0)

**Goal**: Unfilled sells never create sizing capacity for a new buy.

**Independent Test**: Position 100 plus pending sell -50 still sizes a candidate buy from the pre-fill 100-share position and denies the candidate at the configured cap.

- [x] T013 [US3] Add the pending-sell/new-buy denial regression test to `tests/test_live_safety_gate.py`
- [x] T014 [US3] Run the focused new test and record its pre-fix failure in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T015 [US3] Change pending exposure aggregation in `scripts/live_safety_gate.py` so positive pending quantities add and negative pending quantities contribute zero without altering reservations
- [x] T016 [US3] Run the focused pending-order tests and the complete `tests/test_live_safety_gate.py` file green

## Phase 6: User Story 4 - Nonpositive-Equity Fail-Closed Proof (Priority: P0)

**Goal**: Zero and negative equity always deny before division.

**Independent Test**: Both values return `DENY_NON_POSITIVE_EQUITY`; a planted mutant that removes the pre-division floor is killed.

- [x] T017 [US4] Split explicit zero-equity and negative-equity regression cases and add a planted guard-removal mutant in `tests/test_live_safety_gate.py`
- [x] T018 [US4] Run the direct cases and mutant, recording that the direct guard already passes in the current checkout while the planted defect fails in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T019 [US4] Preserve the existing pre-division equity floor and distinct `DENY_NON_POSITIVE_EQUITY` reason in `scripts/live_safety_gate.py`; make no redundant sizing-division change

## Phase 7: User Story 5 - Gate 5 Operational Router (Priority: P0)

**Goal**: Five `/api/safety` endpoints delegate to the injected live safety gate without modifying the Gate 3 router.

**Independent Test**: A temporary SQLite-backed gate exercises kill, confirm, reset, rolling reset, and status through FastAPI; missing injection returns 503 and malformed inputs return 422.

- [x] T020 [US5] Write failing endpoint/dependency tests in `tests/test_safety_router.py`
- [x] T021 [US5] Run `python -m pytest tests/test_safety_router.py -q` and record the semantic red failure in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T022 [P] [US5] Add only new `Safety*` request/response models to `reports/api/schemas.py` without modifying `CapitalGateItem` or `CapitalGateStatusResponse`
- [x] T023 [US5] Implement the dependency-injected five-endpoint router in new `reports/api/routes/safety.py`
- [x] T024 [US5] Register the new router in `reports/api/main.py` and run `tests/test_safety_router.py` green

## Phase 8: Cross-Cutting Verification and Handoff

- [x] T025 Run focused spec-034 tests together and record exact counts in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T026 Run `python -m pytest tests`, compare node outcomes with the 817 passed / 18 failed / 9 errors baseline, and name every new failure or error in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T027 Verify `reports/api/routes/capital_gate.py` retains its pre-work SHA-256 and record the result in `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md`
- [x] T028 Complete `.specify/specs/034-live-safety-gate-remediation/HANDOFF.md` with implemented requirements, red/green evidence, verification scope, protected boundaries, and open work

## Dependencies and Execution Order

- Setup and foundational checks precede all user stories.
- US1, US2, US3, and US4 are independently testable after setup; execute sequentially here to preserve unambiguous red/green evidence.
- US5 depends only on the existing safety-gate public contract and additive schema models.
- Full-suite comparison and handoff follow all five stories.

## Parallel Opportunities

- T022 can be prepared independently from the router implementation after T020 defines the contract.
- Focused tests for US1-US4 touch separate test classes/files, but this execution remains sequential because the user requested explicit tests-first evidence.

## Implementation Strategy

The MVP is US1: establish the fail-closed chokepoint before any operational API
surface exists. Then close state and exposure defects, pin the already-present
equity guard, add the router, and finish with baseline-differential full-suite
verification. No task authorizes broker integration, `exec/`, credentials,
`capital_gate.py`, T033, or any spec-033 Phase 8/9 work.
