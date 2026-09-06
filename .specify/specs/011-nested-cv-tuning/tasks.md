# Tasks — 011 Nested, Leakage-Safe Hyperparameter Tuning

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Inner splitter

- [ ] **T001** `_validate_inner_request` — raise if `train_positions` cannot
  support `n_inner_splits` at the given `label_horizon`/`embargo_bars`.
  (FR-003)
- [ ] **T002** `inner_walk_forward_splits` — operates on `train_positions`'s
  own relative order; applies the same purge/embargo rule as
  `walk_forward_splits` at each inner boundary. (FR-001, FR-002)

## Phase 2 — Hyperparameter search

- [ ] **T003** `select_best_hyperparameters` — scores each candidate via
  `inner_walk_forward_splits` only; never touches a position outside
  `train_positions`. (FR-004, FR-005)

## Phase 3 — Tests (Rule 5, FR-008)

- [ ] **T004** [P] Fragmented training-position array: no inner-train
  position falls in the gap; no inner-validation window's horizon reaches
  into training data after it. (SC-001)
- [ ] **T005** [P] Contiguous training-position array: inner splits equal
  `walk_forward_splits` over the same sub-range. (SC-002)
- [ ] **T006** [P] Outer-test-window isolation: corrupt frame rows outside
  `train_positions` with sentinel values; assert the chosen candidate is
  unchanged. (SC-003)
- [ ] **T007** [P] Too-few-positions raises `ValueError` rather than
  reducing `n_inner_splits`. (SC-004)
- [ ] **T008** [P] Single-candidate grid still runs the full inner-CV
  scoring loop (no short-circuit).
- [ ] **T009** [P] Module boundaries by AST import-set comparison
  (`nested_cv.py` imports only numpy/pandas). (FR-006)

## Phase 4 — Evidence

- [ ] **T010** Mutation check — at minimum: drop the inner purge, shorten
  the inner embargo, replace relative-order slicing with absolute-row-number
  slicing. Each must fail at least one test. (SC-005)
- [ ] **T011** Full suite passes; record the new total in this file's PR.
