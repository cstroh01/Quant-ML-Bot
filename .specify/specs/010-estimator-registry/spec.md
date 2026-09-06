# Feature Specification: Estimator Registry

**Feature Branch**: `010-estimator-registry`

**Created**: 2026-09-06

**Revised**: 2026-09-06 — see *Revision note* below.

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
`scripts/estimators.py`. It declares which model families exist, builds them,
and runs one plain (untuned) walk-forward fit/predict loop. It imports
`walk_forward_cv` and `sklearn`, and nothing else project-side. It does not
import `signals.py` or `backtest_harness.py` (Rule 8): turning a prediction
into a trade decision is a separate concern (spec 012), and this module has
no opinion on it. It does not import `features.py` or `targets.py` either —
it is handed columns to use, not a target kind to interpret.

### Revision note

This spec was first drafted deferring gradient boosting to "a later spec" and
defining the registry as a bare `task -> factory` mapping. Both were corrected
before implementation:

- **Gradient boosting is in scope here.** It is the first of the five Phase 3
  features Camden asked for, and deferring it to an unnamed later spec left it
  owned by nothing. It is added as a registry *entry*, which costs this
  module's loop nothing — that is the whole argument for building a registry.
- **The registry carries a parameter grid and a declared default per entry.**
  Spec 011 tunes hyperparameters; if the registry only stores a factory, 011
  must invent its own grids, and the "one place a model is declared" property
  this spec exists to create is gone on its first use. The plan of record
  (`Phase 3` plan, spec 010) specified `EstimatorSpec` with `param_grid` and
  `default_params`; that is restored.

The untuned `fit_predict_walk_forward` loop is kept — it was not in the plan
of record, and it is an improvement on it. It gives an equivalence checkpoint
against `logistic_baseline.walk_forward_predictions` *before* nested tuning
adds a second source of difference, so a divergence found in spec 011 can only
have come from the tuning.

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
registry keyed on `(name, task)` is what lets a caller hand over a task name
instead of an estimator class, and get back predictions of the right shape
either way — without `logistic_baseline.py` changing at all, since it is the
pinned control (spec 009 FR-011) and stays that way.

### Why `HistGradientBoosting*` and not LightGBM or XGBoost

Rule 6 requires one line on what a new dependency does that existing ones
cannot, and here there is nothing to say: scikit-learn is already a dependency
(`logistic_baseline.py:5`), and `HistGradientBoostingClassifier` /
`HistGradientBoostingRegressor` are a histogram-based GBDT in the same
tradition as LightGBM — good enough to answer "does a nonlinear model beat the
linear baseline net of costs," which is the actual question. LightGBM and
XGBoost become registry entries with no change to this module's loop the day
there is a Rule 6 argument that scikit-learn's implementation is the binding
constraint. Today there is not one, because there is no result yet.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One fit/predict loop, either task (Priority: P1)

As the project owner, I need a single walk-forward fit/predict function that
works for both the direction and return targets, so a new model family is
added once instead of once per task.

**Independent Test**: Call the new loop with `task="classification"`,
`name="logistic"` on the exact frame/columns `logistic_baseline.py` uses and
assert its output equals `walk_forward_predictions`'s output element for
element. Call it again with `task="regression"` on a return-labeled frame and
assert every prediction is a finite float, with `NaN` before the first fold.

**Acceptance Scenarios**:

1. **Given** `task="classification"`, `name="logistic"` and the Phase 2
   feature frame, **When** the new loop runs, **Then** its predictions equal
   `logistic_baseline.walk_forward_predictions`'s, row for row, including
   which rows are unpredicted.
2. **Given** `task="regression"` and a frame built with
   `features.build_features(target_kind="return", ...)`, **When** the loop
   runs, **Then** every fold's test rows get a finite-float prediction and
   every row before the first fold is null.
3. **Given** an unregistered `(name, task)` pair, **When** the loop is called,
   **Then** it raises `ValueError` naming the registered pairs — no default
   estimator is ever silently substituted.

### User Story 2 - The registry is the only place a model is declared (Priority: P1)

As the project owner, I need the model choice, its parameter grid, and its
fallback parameters centralized in one small mapping, so adding gradient
boosting is a registry entry rather than a second copy of the fit/predict
loop, and so spec 011's tuner has a grid to search without inventing one.

**Acceptance Scenarios**:

1. **Given** `name="hgb"` and either task, **When** `build_estimator` is
   called, **Then** it returns an unfitted `HistGradientBoosting*` of the
   matching family with `random_state` set to the supplied seed.
2. **Given** any registered `(name, task)`, **When** `param_grid_points` is
   called, **Then** it returns a list of complete parameter dicts (the
   Cartesian product of `param_grid`), every one of which
   `build_estimator` accepts without raising.
3. **Given** any registered entry, **When** its `default_params` are read,
   **Then** they are a member of that entry's own grid points — so spec
   011's no-inner-folds fallback lands on a declared, tested configuration
   rather than on whichever point happens to sort first.

### Edge Cases

- **Zero folds** (frame too short for even one walk-forward window): raise,
  matching `evaluate_walk_forward`'s existing `RuntimeError` rather than
  returning an all-null series that looks like "no signal yet" instead of
  "this configuration is broken."
- **A fold with a single class present in `y_train`** (classification only):
  `LogisticRegression` handles this; `HistGradientBoostingClassifier` does
  too. The loop must not special-case it — only test that it does not crash
  the walk-forward loop.
- **`random_state` propagation**: every estimator in the registry takes an
  explicit seed (Conventions → Determinism), including the ones for which it
  is inert (`LogisticRegression` with the default solver, `Ridge` with
  `solver="auto"`). Passing it unconditionally means no future registry entry
  is stochastic by accident.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: An `EstimatorSpec` frozen dataclass MUST carry `name`, `task`,
  `factory`, `param_grid: dict[str, list]`, and `default_params: dict`.
  `ESTIMATOR_REGISTRY` MUST key on `(name, task)`.
- **FR-002**: The registry MUST contain four entries:
  `("logistic", "classification")`, `("ridge", "regression")`,
  `("hgb", "classification")`, `("hgb", "regression")`.
  `("logistic", "classification")`'s factory MUST construct
  `LogisticRegression(max_iter=1000, random_state=seed)` — identical to
  `logistic_baseline.py`'s, so the FR-006 equivalence test can pass.
- **FR-003**: `build_estimator(name, *, task, params, random_state)` MUST
  return an unfitted estimator built from the registered factory with
  `params` applied and `random_state` forwarded. `random_state` is
  keyword-only with no default (Conventions → Determinism).
- **FR-004**: `param_grid_points(name, *, task)` MUST return the Cartesian
  product of the entry's `param_grid` as a list of complete parameter dicts,
  in a deterministic order. Each entry's grid MUST be small — target ~4
  points, hard cap 8. With this much selection noise a large grid is a
  lottery, and spec 011 fits one model per point per inner fold per outer
  fold.
- **FR-005**: `fit_predict_walk_forward(frame, *, feature_columns,
  label_column, task, name, label_horizon, embargo_bars, random_state,
  params=None) -> pd.Series` MUST fit one estimator per walk-forward fold
  (via `walk_forward_cv.walk_forward_splits`, never fit-once-predict-all —
  Rule 2) and return predictions aligned to `frame`'s index. `params=None`
  MUST mean the entry's `default_params`, never an empty dict.
- **FR-006** *(equivalence)*: Calling `fit_predict_walk_forward` with
  `name="logistic"`, `task="classification"`,
  `feature_columns=logistic_baseline.FEATURE_COLUMNS`,
  `label_column="Label"`, `label_horizon=1`, `embargo_bars=1`,
  `random_state=42` on the Phase 2 feature frame MUST equal
  `logistic_baseline.walk_forward_predictions`'s output element for element.
- **FR-007**: The returned series' dtype MUST depend on `task`: `Int64` for
  `"classification"` (rows before the first fold are `pd.NA`), `float64` for
  `"regression"` (rows before the first fold are `NaN`).
- **FR-008**: An unregistered `(name, task)` MUST raise `ValueError` naming
  the registered pairs. No silent default. Same "never default" contract as
  `targets.build_target` (spec 009 FR-005).
- **FR-009**: Each entry's `default_params` MUST be one of that entry's own
  `param_grid_points` — asserted by test, so the spec-011 fallback cannot
  drift onto an untested configuration.
- **FR-010** *(Rule 8)*: `scripts/estimators.py` imports `walk_forward_cv`
  and scikit-learn only. It MUST NOT import `signals`, `backtest_harness`,
  `features`, or `targets`.
- **FR-011**: `logistic_baseline.py` MUST NOT be modified (its result is the
  pinned control, spec 009 FR-011).
- **FR-012** *(Rule 6)*: No new dependency. `HistGradientBoosting*` and
  `Ridge` both ship with the scikit-learn already in use.
- **FR-013** *(Rule 5, tests)*: Coverage for the classification-equivalence
  case, the regression finite-output case, both `hgb` entries building and
  fitting, the unregistered-pair error, the zero-fold error, grid/default
  consistency (FR-009), seed propagation, and the module-boundary import set.

### Key Entities

- **Task**: `"classification"` or `"regression"` — the same vocabulary
  `targets.build_target` produces (spec 009), consumed here rather than
  re-derived.
- **Estimator name**: `"logistic"`, `"ridge"`, `"hgb"` — the model family,
  independent of task. `hgb` exists for both tasks; the other two for one
  each.
- **Estimator factory**: a callable taking params and a seed and returning an
  unfitted scikit-learn estimator with `.fit`/`.predict`. The registry stores
  factories, not instances, because a fresh unfitted estimator is needed once
  per fold.

---

## Success Criteria *(mandatory)*

- **SC-001**: The classification path reproduces
  `logistic_baseline.walk_forward_predictions` exactly (row-for-row equality,
  same dtype, same null placement).
- **SC-002**: The regression path yields a finite `float64` prediction for
  every fold's test rows and `NaN` for every row before the first fold, on a
  frame built via `features.build_features(target_kind="return", ...)`.
- **SC-003**: Both `hgb` entries build, fit, and predict on their task's
  frame without raising, and `hgb` predictions differ from the linear
  entry's on the same data — proving the registry key actually selects a
  different model rather than silently returning one family for everything.
- **SC-004**: An unregistered `(name, task)` raises `ValueError` naming the
  valid pairs; it never falls back to a default.
- **SC-005**: Every entry's `default_params` is a member of its own grid
  points.
- **SC-006**: Two calls with the same `random_state` produce identical
  predictions; the `hgb` entries produce different predictions under
  different seeds *or* are provably deterministic — whichever is true is
  asserted, not assumed.
- **SC-007**: A mutation check (swap two registry entries, drop
  `random_state` propagation, swap the null-filler dtype per task, let
  `params=None` mean `{}` instead of `default_params`) fails the test suite
  for each injected defect.

---

## Assumptions

- The regression linear default is a plain `Ridge`. Selecting its `alpha`
  without leakage is spec 011's problem; this spec only needs *a* working
  regression estimator to prove the loop is task-general, plus a declared
  grid for 011 to search.
- Grids are deliberately coarse and are not claimed to be well-chosen. They
  are a starting point that spec 011's machinery can select over; revising
  them once there is a real result is a later, evidence-driven change.
- This spec produces predictions only. Turning a continuous prediction into a
  trade decision against a cost hurdle is spec 012. Tuning is spec 011 — the
  loop here always fits one fixed parameter set per fold.
