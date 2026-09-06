# Tasks — 011 Nested, Leakage-Safe Hyperparameter Tuning

Dependency-ordered. `[P]` = parallelizable with the task above it.

Split point, if this exceeds ~250 changed lines: Phase 1 + T007–T010 land as
`011a`, the tuning loop as `011b`. Reviewability is a hard constraint
(CLAUDE.md), not a preference.

---

## Phase 1 — Inner splitter

- [x] **T001** Strictly-increasing assertion on `outer_train_indices` — the
  positional back-map is unsound without it. (FR-002)
- [x] **T002** `inner_splits_over` — sub-frame via
  `features.iloc[outer_train_indices].reset_index(drop=True)`, reuse
  `walk_forward_splits`, map back by fancy-indexing. No reimplementation of
  purge or embargo. (FR-001, FR-003)

## Phase 2 — Scoring and tuning

- [x] **T003** `score_fold` — lower-is-better for both tasks; `log_loss` with
  `labels=[0, 1]` passed explicitly; MSE for regression. Convention stated in
  the docstring. (FR-004)
- [x] **T004** `tune_on_fold` — score every `param_grid_points` entry over the
  inner folds; return `(best_params, tuned, inner_scores)`. (FR-005)
- [x] **T005** Zero-inner-fold fallback — registry `default_params` and
  `tuned=False`; never `grid[0]`; never raises. (FR-006)
- [x] **T006** `nested_walk_forward` — tune, fit, predict per outer fold;
  return predictions, covered positions, per-fold results frame.
  (FR-007, FR-008)

## Phase 3 — Tests (Rule 5, FR-012)

- [x] **T007** [P] Membership: every inner position is in
  `outer_train_indices`, on a fragmented array. This is the test that catches
  a regression to prefix slicing. (SC-001)
- [x] **T008** [P] Calendar ordering per inner fold, and real-bar separation
  of at least `label_horizon` across a hand-built hole. (SC-002)
- [x] **T009** [P] Contiguous array: inner splits equal `walk_forward_splits`
  over the same range. (SC-003)
- [x] **T010** [P] Isolation: corrupt every frame row outside
  `outer_train_indices` with sentinels; the selection is unchanged. (SC-004)
- [x] **T011** [P] Zero inner folds returns registry `default_params` with
  `tuned=False`, asserted against the registry rather than a grid position.
  (SC-005)
- [x] **T012** [P] Single-candidate grid still runs the full inner loop (no
  short-circuit).
- [x] **T013** [P] Determinism under a fixed `random_state`.
- [x] **T014** [P] Covered positions equal the concatenated outer test
  indices; no position covered twice. (FR-008)
- [x] **T015** [P] Equivalence: single-point logistic grid reproduces
  `logistic_baseline.walk_forward_predictions` element for element. (SC-006)
- [x] **T016** [P] Module boundaries by AST import-set comparison. (FR-009)

## Phase 4 — Evidence

- [x] **T017** Mutation check — at minimum: prefix slice instead of the
  sub-frame; drop the strictly-increasing assertion; flip `score_fold`'s
  sign; drop `labels=[0, 1]`; return `grid[0]` on the fallback. Each must
  fail at least one test. (SC-007)
- [x] **T018** Full suite passes; record the new total in this file's PR.
- [x] **T019** Record the observed fit count and wall-clock for one `hgb`
  nested run, so spec 010's grid size can be revised against a real number
  rather than a guess.
