# Tasks — 010 Estimator Registry

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Registry

- [x] **T001** `EstimatorSpec` frozen dataclass — `name`, `task`, `factory`,
  `param_grid`, `default_params`. (FR-001)
- [x] **T002** `ESTIMATOR_REGISTRY` keyed on `(name, task)` with four
  entries: `logistic`/classification, `ridge`/regression, `hgb`/both.
  `logistic`'s construction matches `logistic_baseline.py` exactly so the
  equivalence test can pass. (FR-002)
- [x] **T003** `build_estimator(name, *, task, params, random_state)` —
  keyword-only seed, no default, forwarded unconditionally. (FR-003)
- [x] **T004** `param_grid_points(name, *, task)` — deterministic Cartesian
  product, ~4 points per entry, hard cap 8. (FR-004)

## Phase 2 — Walk-forward loop

- [x] **T005** `fit_predict_walk_forward` — one fit per fold via
  `walk_forward_splits`; `params=None` means the entry's `default_params`,
  never `{}`; raises on an unregistered pair, naming the valid ones.
  (FR-005, FR-008)
- [x] **T006** Dtype branch by `task`: `Int64`/`pd.NA` for classification,
  `float64`/`NaN` for regression. (FR-007)
- [x] **T007** Zero-fold guard — raise `RuntimeError` rather than returning
  an all-null series.

## Phase 3 — Tests (Rule 5, FR-013)

- [x] **T008** [P] Classification equivalence: `fit_predict_walk_forward`
  vs. `logistic_baseline.walk_forward_predictions`, element for element.
  (SC-001)
- [x] **T009** [P] Regression path: finite floats in every fold's test
  window, `NaN` before the first fold, on a `target_kind="return"` frame.
  (SC-002)
- [x] **T010** [P] Both `hgb` entries fit and predict; `hgb` output differs
  from the linear entry's on the same data. (SC-003)
- [x] **T011** [P] Unregistered `(name, task)` raises `ValueError` naming the
  valid pairs; no default is substituted. (SC-004)
- [x] **T012** [P] Zero-fold input raises rather than returning an all-null
  series.
- [x] **T013** [P] Every entry's `default_params` is a member of its own grid
  points; every grid point builds without raising. (SC-005)
- [x] **T014** [P] Seed handling: same `random_state` gives identical
  predictions; assert what is actually true of each entry rather than
  assuming stochasticity. (SC-006)
- [x] **T015** [P] `params` override is used verbatim and `default_params` is
  not consulted (assert via a spy/counter, not by reading source).
- [x] **T016** [P] Module boundaries by AST import-set comparison
  (`estimators.py` imports only `walk_forward_cv` and sklearn). (FR-010)

## Phase 4 — Evidence

- [x] **T017** Mutation check — eight injected defects, all caught. The
  first run caught only 3 of 5 and exposed two weak tests of my own (a
  `default_params` assertion that passed by coincidence, and a vacuous
  equivalence test on a non-learnable fixture). Both fixed; see plan.md.
  (SC-007)
- [x] **T018** Confirm `logistic_baseline.py` is unmodified and its own test
  suite still passes unchanged. (FR-011)
- [x] **T019** Full suite: **210 tests, OK** (180 after spec 009).
