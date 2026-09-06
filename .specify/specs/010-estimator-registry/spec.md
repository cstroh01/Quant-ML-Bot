# Feature Specification: Estimator Registry

**Feature Branch**: `010-estimator-registry`

**Created**: 2026-09-06

**Status**: Draft

**Input**: Spec 009 made the prediction target selectable (`direction` /
`classification` or `return` / `regression`) but left model-fitting where it
was: hardcoded to `LogisticRegression` inside `logistic_baseline.py`, whose
fit/predict-per-fold loop is duplicated across `evaluate_walk_forward` and
`walk_forward_predictions` and pinned as the Phase 2 control result (spec 009
FR-011 — that file is not to be touched). There is no path today from a
`task` string (`targets.build_target`'s own return value) to a fitted
estimator, and no walk-forward loop that works for a regression target at
all. `targets.py:121` already names this future module directly: *"This is
what tells an estimator registry which model family applies."*

**Owns / must not know about** (per CLAUDE.md's module table): a new
`scripts/estimator.py`. It fits and predicts only — it takes an already-built
feature frame, a task, and fold parameters, and returns predictions. It
imports `walk_forward_cv` and `sklearn`, and nothing else project-side. It
does not import `signals.py` or `backtest_harness.py` (Rule 8): turning a
prediction into a trade decision is a separate concern (spec 012), and this
module has no opinion on it. It does not import `features.py` or `targets.py`
either — it is handed columns to use, not a target kind to interpret.

---

## Background

Two functions in `logistic_baseline.py` do the same walk-forward fit/predict
loop for two different purposes:

- `evaluate_walk_forward` — fits per fold, scores accuracy, prints/returns a
  fold table.
- `walk_forward_predictions` — fits per fold (identical loop, deliberately
  not shared — see that function's own docstring), returns one out-of-sample
  prediction per row.

Both hardcode `LogisticRegression(max_iter=1000, random_state=42)` and a
classification-shaped prediction (`model.predict`, compared against an int
label). Neither can run for `target_kind="return"`: `LogisticRegression` on a
continuous label raises, and even a regressor swapped in by hand would still
need `predict` results carried through with the right dtype (`Int64` for a
class label, `float` for a continuous one) and the right "no fold yet" filler
(`pd.NA` vs. `np.nan`).

This is the fork in the road spec 009's `task` return value exists for. A
registry keyed on `"classification"` / `"regression"` is what lets a caller
hand over a task name instead of an estimator class, and get back predictions
of the right shape either way — without `logistic_baseline.py` changing at
all, since it is the pinned control (spec 009 FR-011) and stays that way.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One fit/predict loop, either task (Priority: P1)

As the project owner, I need a single walk-forward fit/predict function that
works for both the direction and return targets, so a new model family is
added once instead of once per task.

**Independent Test**: Call the new loop with `task="classification"` on the
exact frame/columns `logistic_baseline.py` uses and assert its output equals
`walk_forward_predictions`'s output element for element. Call it again with
`task="regression"` on a return-labeled frame and assert every prediction is
a finite float, with `<NA>`-equivalent (`NaN`) before the first fold.

**Acceptance Scenarios**:

1. **Given** `task="classification"` and the Phase 2 feature frame, **When**
   the new loop runs with the default classification estimator, **Then** its
   predictions equal `logistic_baseline.walk_forward_predictions`'s, row for
   row, including which rows are unpredicted.
2. **Given** `task="regression"` and a frame built with
   `features.build_features(target_kind="return", ...)`, **When** the loop
   runs with the default regression estimator, **Then** every fold's test
   rows get a finite-float prediction and every row before the first fold is
   null.
3. **Given** an unregistered task name, **When** the loop is called,
   **Then** it raises `ValueError` naming the registered tasks — no default
   estimator is ever silently substituted.

### User Story 2 - The registry is the only place a model is chosen (Priority: P2)

As the project owner, I need the classification/regression estimator choice
centralized in one small mapping, so a stronger model (gradient boosting is
the named Phase 3 candidate) is a registry entry, not a second copy of the
fit/predict loop.

**Acceptance Scenarios**:

1. **Given** a caller supplies an explicit `estimator_factory` callable
   instead of relying on the registry default, **When** the loop runs,
   **Then** it fits that estimator and never consults the registry.
2. **Given** no `estimator_factory` is supplied, **When** the loop runs,
   **Then** it looks up the default for the given `task` in
   `ESTIMATOR_REGISTRY` and raises `KeyError`-shaped `ValueError` if the task
   is not a key there — the same "never default" contract as
   `targets.build_target` (spec 009 FR-005).

### Edge Cases

- **Zero folds** (frame too short for even one walk-forward window): raise,
  matching `evaluate_walk_forward`'s existing `RuntimeError` rather than
  returning an all-null series that looks like "no signal yet" instead of
  "this configuration is broken."
- **A fold with a single class present in `y_train`** (classification only):
  `LogisticRegression` handles this; the loop must not special-case it, only
  test that it doesn't crash the walk-forward loop.
- **`random_state` propagation**: every stochastic estimator in the registry
  takes an explicit seed (Conventions → Determinism). The loop threads one
  `random_state` parameter through to whichever estimator it builds.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ESTIMATOR_REGISTRY` MUST map `"classification"` and
  `"regression"` to a zero-argument-except-seed factory returning a fitted-
  ready scikit-learn estimator. Classification's default MUST be
  `LogisticRegression(max_iter=1000, random_state=seed)` — identical
  construction to `logistic_baseline.py`'s, so the equivalence test in User
  Story 1 can pass. Regression's default MUST be a linear model already
  available from the existing scikit-learn dependency (e.g. `Ridge`) —
  Rule 6 requires no new dependency for a baseline.
- **FR-002**: `fit_predict_walk_forward(frame, *, feature_columns,
  label_column, task, label_horizon, embargo_bars, random_state=42,
  estimator_factory=None) -> pd.Series` MUST fit one estimator per
  walk-forward fold (via `walk_forward_cv.walk_forward_splits`, never
  fit-once-predict-all — Rule 2) and return predictions aligned to
  `frame`'s index.
- **FR-003**: The returned series' dtype MUST depend on `task`: `Int64` for
  `"classification"` (rows before the first fold are `pd.NA`), `float64` for
  `"regression"` (rows before the first fold are `NaN`).
- **FR-004**: An unregistered `task` (and no `estimator_factory` override)
  MUST raise `ValueError` naming the registered tasks. No silent default.
- **FR-005** *(equivalence)*: Calling `fit_predict_walk_forward` with
  `task="classification"`, `feature_columns=logistic_baseline.FEATURE_COLUMNS`,
  `label_column="Label"`, `label_horizon=1`, `embargo_bars=1` on the Phase 2
  feature frame MUST equal `logistic_baseline.walk_forward_predictions`'s
  output element for element.
- **FR-006** *(Rule 8)*: `scripts/estimator.py` imports `walk_forward_cv` and
  scikit-learn only. It MUST NOT import `signals`, `backtest_harness`,
  `features`, or `targets`.
- **FR-007**: `logistic_baseline.py` MUST NOT be modified (its result is the
  pinned control, spec 009 FR-011).
- **FR-008** *(Rule 6)*: No new dependency — `Ridge` (or an equivalent
  already-available linear regressor) is used for the regression default.
- **FR-009** *(Rule 5, tests)*: Coverage for the classification-equivalence
  case, the regression finite-output case, the unregistered-task error, the
  zero-fold error, and an `estimator_factory` override bypassing the
  registry.

### Key Entities

- **Task**: `"classification"` or `"regression"` — the same vocabulary
  `targets.build_target` produces (spec 009), consumed here rather than
  re-derived.
- **Estimator factory**: a callable taking a seed and returning an unfitted
  scikit-learn estimator with `.fit`/`.predict`. The registry's values are
  factories, not instances, because a fresh unfitted estimator is needed
  once per fold.

---

## Success Criteria *(mandatory)*

- **SC-001**: The classification path reproduces
  `logistic_baseline.walk_forward_predictions` exactly (row-for-row equality,
  same dtype, same null placement).
- **SC-002**: The regression path yields a finite `float64` prediction for
  every fold's test rows and `NaN` for every row before the first fold, on a
  frame built via `features.build_features(target_kind="return", ...)`.
- **SC-003**: An unregistered task raises `ValueError` naming the valid
  tasks; it never falls back to a default.
- **SC-004**: A mutation check (wrong estimator per task, seed dropped,
  wrong null-filler dtype) fails the test suite for each injected defect.

---

## Assumptions

- The regression default is a plain `Ridge` regressor with default
  regularization strength. Tuning that strength without leakage is spec
  011's problem, not this one's — this spec only needs *a* working
  regression estimator to prove the loop is task-general.
- Gradient boosting (named in spec 006's Background as a Phase 3 candidate)
  is not added here. It is a registry entry a later spec can add without
  touching this module's fit/predict loop, which is the point of building
  the registry now.
- This spec produces predictions only. Turning a continuous prediction into
  a trade decision against a cost hurdle is spec 012.
