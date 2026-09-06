# Feature Specification: Nested, Leakage-Safe Hyperparameter Tuning

**Feature Branch**: `011-nested-cv-tuning`

**Created**: 2026-09-06

**Revised**: 2026-09-06 — see *Revision note* below.

**Status**: Draft

**Input**: Spec 006 fixed `walk_forward_cv.py`'s embargo so the training set
actually expands, and named the consequence: after the fix, each outer fold's
training positions carry holes wherever an earlier fold's embargo gap falls
inside them. Spec 010 gives every `(name, task)` pair a fitted estimator and a
declared parameter grid, but nothing yet selects a point from that grid. A
hyperparameter search that picks the best inner-validation score using the
outer fold's own test window is Rule 2 one level deeper — silent, and it
produces a better-looking number.

**Owns / must not know about** (per CLAUDE.md's module table): a new
`scripts/model_cv.py`. It imports `walk_forward_cv` and `estimators` — and
nothing else project-side. It does not import `signals`, `backtest_harness`,
`features`, or `targets`: it is handed a frame and column names, not a target
kind to interpret, and it has no opinion on what a prediction means.

### Revision note

The first draft of this spec was internally contradictory and could not have
been implemented as written:

- **FR-002 required the inner purge/embargo to be "the same rule
  `walk_forward_splits` applies … not re-derived or approximated," while
  FR-006 forbade importing any project module.** Those cannot both hold. The
  only way to satisfy FR-006 was to hand-roll a second purge/embargo
  implementation — which is precisely the "re-derived" outcome FR-002
  existed to forbid, and a second implementation of the project's most
  correctness-critical rule is the last thing this repo should own.
- **`select_best_hyperparameters` was given `candidates` and a `scorer` but
  no way to build a model from a candidate.** With no project imports it
  could not reach `estimators.build_estimator` either.

Both are resolved the same way, following the plan of record: `model_cv.py`
*does* import `walk_forward_cv` and `estimators`, and reuses the real
splitter on a sub-frame rather than reimplementing it. The correctness
argument for that reuse is in *Design constraint* below — it is the
load-bearing part of this spec.

The first draft's `scorer`-supplied-by-caller idea is **not** kept. Scoring
must be comparable across candidates and directions ("lower is better") to
select at all; leaving it to the caller means every caller re-derives the
sign convention. `score_fold` owns it, keyed on task.

---

## Background

`walk_forward_splits` yields `train_indices` as a `np.ndarray` of row
positions with gaps already removed — not a contiguous `range(0, k)`. After
spec 006 it is sorted (rows are yielded in increasing order) but **not
gapless** whenever an earlier fold's embargo zone falls inside this fold's
training region.

The tempting implementation of an inner split is to slice the original frame:
`features.iloc[:outer_test_start - label_horizon]`. That is wrong, and wrong
in the direction that flatters the result: it re-admits every row the outer
fold deliberately embargoed. The tuner would then be selecting hyperparameters
using rows the outer fold had already ruled inadmissible — a Rule 2 violation
introduced by the tuner itself, on top of a splitter that was just fixed.

This is exactly the shape of bug Rule 5 exists to catch without an exception:
a hyperparameter search that quietly trains on a few extra rows near an
embargo boundary does not crash. It reports a slightly better cross-validated
score for whichever hyperparameter got away with it most.

---

## Design constraint — the sub-frame and the back-map

The inner splitter builds a sub-frame from the outer fold's **own**
`train_indices`, and maps results back positionally:

```python
sub = features.iloc[outer_train_indices].reset_index(drop=True)
for inner_train, inner_val in walk_forward_splits(sub, ...):
    yield outer_train_indices[inner_train], outer_train_indices[inner_val]
```

This reuses the real, tested purge/embargo rather than restating it, and it
cannot re-admit an embargoed row, because a row that is not in
`outer_train_indices` is not in `sub` at all.

**Why holes do not break the purge, which is a reviewer's first objection.**
Inside `sub`, adjacent rows can be separated by more than one real bar
wherever a hole was removed. `walk_forward_splits` measures its purge and
embargo in rows of the frame it is given, so `E` sub-frame rows span *at
least* `E` real bars — never fewer. Both purge and embargo therefore err
**conservative** across a hole: they over-purge and over-cover, never under.
That direction is the safe one, and it is the reason reuse is sound rather
than merely convenient.

`outer_train_indices` being **strictly increasing** is what the whole
positional back-map rests on, and is asserted explicitly rather than assumed.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inner splits are drawn only from the outer fold's own training data (Priority: P1)

As the project owner, I need an inner splitter that treats a fragmented
training-position array correctly, so hyperparameter selection never
silently trains across a gap spec 006 put there on purpose.

**Independent Test**: Build an outer training-position array with a
deliberate internal gap, request inner splits, and assert every yielded inner
position is a member of that array — the assertion that catches a regression
to prefix slicing.

**Acceptance Scenarios**:

1. **Given** a training-position array with an internal hole, **When**
   `inner_splits_over` is called, **Then** every yielded inner-train and
   inner-validation position is a member of `outer_train_indices`.
2. **Given** the same setup, **When** any inner fold is examined, **Then**
   `max(inner_train_dates) < min(inner_val_dates)` — ordering holds in real
   calendar time, not merely in sub-frame position.
3. **Given** a hand-built hole, **When** the separation between the last
   inner-train row and the first inner-validation row is measured in real
   bars, **Then** it is at least `label_horizon` — confirming the
   conservative direction claimed in *Design constraint*.
4. **Given** a contiguous training-position array (the very first outer fold,
   before any embargo exists), **When** the function runs, **Then** its
   splits equal what `walk_forward_splits` produces over that same range —
   the general case subsumes the simple one.

### User Story 2 - Hyperparameter selection never touches the outer test window (Priority: P1)

As the project owner, I need the grid search to score candidates only on
inner folds drawn from the outer fold's own training data, so a tuned model's
reported outer-fold score is still honest.

**Acceptance Scenarios**:

1. **Given** a grid and an outer fold's training positions, **When**
   `tune_on_fold` runs, **Then** it never receives or references the outer
   fold's test indices — enforced by corrupting every frame row outside
   `outer_train_indices` with sentinel values and asserting the selection is
   unchanged.
2. **Given** an outer fold whose training data supports no inner fold at all,
   **When** `tune_on_fold` runs, **Then** it returns the registry's declared
   `default_params` with `tuned=False` recorded — and **never** `grid[0]`.

### Edge Cases

- **Zero inner folds.** Reachable two ways: an outer training set too short
  for one inner window, or every inner fold purged empty. Both fall back to
  `default_params` with `tuned=False`. The flag is what makes the fold-results
  artifact honest — a reader can see which folds were actually tuned.
- **A single candidate in the grid**: still runs the full inner scoring loop
  rather than short-circuiting, so the no-leak guarantee does not depend on
  grid size.
- **A training fold containing a single class** (classification): `log_loss`
  silently reshapes its output unless `labels=[0, 1]` is passed explicitly.
  It is passed explicitly.
- **A gap wider than the requested embargo**: still just excluded. The
  function does not reason about *why* a position is absent, only that it is.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `inner_splits_over(features, outer_train_indices, *,
  initial_train_months, test_months, label_horizon, embargo_bars,
  date_column="Date")` MUST build a sub-frame from `outer_train_indices` and
  reuse `walk_forward_cv.walk_forward_splits` on it, mapping every yielded
  index back through `outer_train_indices`. It MUST NOT reimplement the
  purge or embargo rule.
- **FR-002**: `inner_splits_over` MUST assert `outer_train_indices` is
  strictly increasing before use, and raise if it is not — the positional
  back-map is unsound otherwise.
- **FR-003**: Every position yielded by `inner_splits_over` MUST be a member
  of `outer_train_indices`.
- **FR-004**: `score_fold(y_true, y_pred, *, task) -> float` MUST return a
  score where **lower is better** for both tasks: `log_loss` (with
  `labels=[0, 1]` passed explicitly) for classification, mean squared error
  for regression. The convention MUST be stated in the docstring, because a
  sign error here silently selects the worst candidate.
- **FR-005**: `tune_on_fold(features, outer_train_indices, *, name, task,
  feature_columns, label_column, label_horizon, embargo_bars, random_state,
  ...) -> tuple[dict, bool, pd.DataFrame]` MUST score every grid point from
  `estimators.param_grid_points` over the inner folds and return
  `(best_params, tuned, inner_scores)`.
- **FR-006**: With zero inner folds, `tune_on_fold` MUST return
  `estimators.ESTIMATOR_REGISTRY[(name, task)].default_params` and
  `tuned=False`. It MUST NOT return `grid[0]`, and MUST NOT raise — a short
  early fold is an expected condition, not a broken configuration.
- **FR-007**: `nested_walk_forward(...) -> tuple[pd.Series, np.ndarray,
  pd.DataFrame]` MUST, for each outer fold, tune on that fold's training data
  only, fit the selected parameters on that training data, and predict its
  test window — returning predictions, the covered positions, and a
  per-fold results frame carrying at minimum the fold number, chosen params,
  the `tuned` flag, and the inner best score.
- **FR-008**: Covered positions MUST equal the concatenation of the outer
  folds' test indices, with no position covered twice.
- **FR-009** *(Rule 8)*: `model_cv.py` imports `walk_forward_cv`,
  `estimators`, numpy, pandas, and scikit-learn metrics only. It MUST NOT
  import `signals`, `backtest_harness`, `features`, or `targets`.
- **FR-010** *(Rule 6)*: No new dependency.
- **FR-011** *(equivalence)*: `nested_walk_forward` restricted to a
  single-point grid equal to `logistic_baseline.py`'s own construction, with
  `name="logistic"`, `task="classification"`, `label_horizon=1`,
  `embargo_bars=1`, MUST reproduce
  `logistic_baseline.walk_forward_predictions` element for element. This
  isolates tuning as the *only* possible source of any later divergence,
  since spec 010's FR-006 already pins the untuned loop.
- **FR-012** *(Rule 5, tests)*: Coverage for membership (FR-003), calendar
  ordering, real-bar separation across a hole, contiguous equivalence, the
  corruption/isolation test, the zero-inner-fold fallback including the
  `tuned=False` flag, single-candidate non-short-circuit, determinism under a
  fixed `random_state`, coverage exactness, and the module import set.

### Key Entities

- **Outer training positions**: what a `walk_forward_splits` fold hands a
  tuner as its legal training data — sorted, possibly with internal gaps,
  never assumed to be `range(a, b)`.
- **Inner fold**: a further train/validation division of that array,
  purge/embargo-safe at the same horizon as the outer split, produced by the
  same code.
- **`tuned` flag**: per outer fold, whether a grid point was actually
  selected or the declared default was used.

---

## Success Criteria *(mandatory)*

- **SC-001**: Every inner position is a member of `outer_train_indices`,
  across a fragmented and a contiguous array.
- **SC-002**: `max(inner_train_dates) < min(inner_val_dates)` on every inner
  fold, and real-bar separation across a hand-built hole is at least
  `label_horizon`.
- **SC-003**: Over a contiguous training-position array, inner splits equal
  `walk_forward_splits` over the same range.
- **SC-004**: The selected candidate is provably unaffected by corrupting
  every frame row outside `outer_train_indices`.
- **SC-005**: Zero inner folds yields `default_params` and `tuned=False`,
  and the returned params are *not* `grid[0]` unless `default_params`
  genuinely is `grid[0]` — asserted against the registry, not against a
  position.
- **SC-006**: `nested_walk_forward` with a single-point logistic grid equals
  `logistic_baseline.walk_forward_predictions` element for element.
- **SC-007**: A mutation check (replace the sub-frame with a prefix slice;
  drop the strictly-increasing assertion; flip `score_fold`'s sign; drop
  `labels=[0, 1]`; return `grid[0]` instead of `default_params` on the
  fallback) fails the test suite for each injected defect.

---

## Assumptions

- The inner splitter reuses `initial_train_months` / `test_months` calendar
  sizing rather than a fixed inner-fold count, because that is what
  `walk_forward_splits` takes and reuse is the point. A caller wanting more
  inner folds shortens `test_months`; this module does not decide that.
- Whether a tuned estimator becomes the default for live runs, or stays an
  explicit choice at the call site, is decided by spec 013's runner — not
  here. This module returns what it selected and the flag saying whether it
  really selected it.
- Grid *contents* stay in `estimators.py` (spec 010 FR-001). This spec
  searches a grid; it does not author one.
- **Cost.** One fit per grid point per inner fold per outer fold is
  potentially thousands of fits for `hgb` over 10 years of daily bars.
  Recorded here as a known consequence, not optimized around; if a real run
  is impractically slow, shrinking `param_grid` in spec 010 is the lever,
  and it is one line.
