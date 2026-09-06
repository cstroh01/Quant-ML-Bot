# Tasks — 009 Selectable Prediction Target

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Labels

- [x] **T001** `_validate_horizon` — reject `horizon < 1` and non-integers.
  The degenerate case is silent, not loud, which is why it is rejected rather
  than documented. (FR-003)
- [x] **T002** `_future_close` — `shift(-horizon)`, rows not calendar days,
  matching spec 003's positional purge convention.
- [x] **T003** `direction_label` — nullable `Int64`, `<NA>` on the final
  `horizon` rows, flat close counts as down (matching
  `logistic_baseline.build_features:47`). (FR-001)
- [x] **T004** `forward_log_return_label` — `log(Close[t+h]/Close[t])`,
  `NaN` where unobservable or either close is non-positive. (FR-002)
- [x] **T005** `build_target` — returns `(label, task, label_horizon)`;
  raises on an unknown kind, naming the valid kinds; never defaults.
  (FR-004, FR-005)

## Phase 2 — Features

- [x] **T006** `features.FEATURE_COLUMNS` — the same five columns, restated
  rather than imported (importing `logistic_baseline` pulls in scikit-learn).
- [x] **T007** `build_features` — keyword-only windows plus `target_kind`
  and `label_horizon`; reuses `signals.sma_crossover_signal`; returns
  `(frame, task, label_horizon)`. (FR-006)
- [x] **T008** Drop warm-up rows then unobservable rows, and
  `reset_index(drop=True)` — same sequence as
  `logistic_baseline.build_features:51-55`. (FR-007)

## Phase 3 — Tests (Rule 5, FR-013)

- [x] **T009** [P] Direction and return label values at horizons 1 and 2,
  including the log-additivity property.
- [x] **T010** [P] Off-by-one both ways: perturbing `Close[t+h+1]` changes
  nothing; perturbing `Close[t+h]` does. (SC-004)
- [x] **T011** [P] Boundaries: exactly the last `h` rows null across several
  horizons and both kinds; first row labelled; horizon ≥ frame length is all
  null and yields an empty feature frame without raising. (SC-003, SC-006)
- [x] **T012** [P] Validation: `horizon=0`, negative horizon, unknown kind,
  missing `Close` column. (SC-005)
- [x] **T013** [P] Gap case: a five-calendar-day hole still spans one bar.
  (SC-007)
- [x] **T014** [P] Equivalence with `logistic_baseline`: `FEATURE_COLUMNS`
  equal; `direction_label(h=1)` matches its `Label` element for element;
  `build_features` reproduces its frame on every shared column.
  (SC-001, SC-002)
- [x] **T015** [P] Rule 1 shape: the label is not in `FEATURE_COLUMNS`, and
  perturbing future closes moves no feature.
- [x] **T016** [P] Module boundaries by AST import-set comparison, not a
  source grep. (FR-010)

## Phase 4 — Evidence

- [x] **T017** Mutation check — four injected defects in `targets.py`, all
  caught (15, 1, 2, and 9 failures respectively).
- [x] **T018** Confirm `logistic_baseline.py` is unmodified and every one of
  its tests still passes. (FR-011)
- [x] **T019** Full suite: **180 tests, OK**.
