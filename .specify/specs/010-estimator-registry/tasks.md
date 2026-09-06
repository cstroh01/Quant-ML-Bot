# Tasks — 010 Estimator Registry

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Registry

- [ ] **T001** `ESTIMATOR_REGISTRY` — maps `"classification"` ->
  `LogisticRegression(max_iter=1000, random_state=seed)` factory,
  `"regression"` -> `Ridge(random_state=seed)`-or-equivalent factory.
  (FR-001)

## Phase 2 — Walk-forward loop

- [ ] **T002** `fit_predict_walk_forward` — one fit per fold via
  `walk_forward_splits`; looks up the registry by `task` unless
  `estimator_factory` is given; raises on an unregistered task, naming the
  valid ones. (FR-002, FR-004)
- [ ] **T003** Dtype branch by `task`: `Int64`/`pd.NA` for classification,
  `float64`/`NaN` for regression. (FR-003)
- [ ] **T004** Zero-fold guard — raise `RuntimeError` rather than returning
  an all-null series.

## Phase 3 — Tests (Rule 5, FR-009)

- [ ] **T005** [P] Classification equivalence: `fit_predict_walk_forward`
  vs. `logistic_baseline.walk_forward_predictions`, element for element.
  (SC-001)
- [ ] **T006** [P] Regression path: finite floats in every fold's test
  window, `NaN` before the first fold, on a `target_kind="return"` frame.
  (SC-002)
- [ ] **T007** [P] Unregistered task raises `ValueError` naming the valid
  tasks; no default is substituted. (SC-003)
- [ ] **T008** [P] Zero-fold input raises rather than returning an all-null
  series.
- [ ] **T009** [P] `estimator_factory` override is used verbatim and the
  registry is not consulted (assert via a spy/counter, not by reading
  source).
- [ ] **T010** [P] Module boundaries by AST import-set comparison
  (`estimator.py` imports only `walk_forward_cv` and sklearn). (FR-006)

## Phase 4 — Evidence

- [ ] **T011** Mutation check — at minimum: swap the two registry entries,
  drop `random_state` propagation, swap the null-filler dtype per task.
  Each must fail at least one test. (SC-004)
- [ ] **T012** Confirm `logistic_baseline.py` is unmodified and its own test
  suite still passes unchanged. (FR-007)
- [ ] **T013** Full suite passes; record the new total in this file's PR.
