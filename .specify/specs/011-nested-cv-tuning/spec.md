# Feature Specification: Nested, Leakage-Safe Hyperparameter Tuning

**Feature Branch**: `011-nested-cv-tuning`

**Created**: 2026-09-06

**Status**: Draft

**Input**: Spec 006 fixed `walk_forward_cv.py`'s embargo so the training set
actually expands, and its own Background explicitly named the consequence:
*"the now-non-contiguous training indices is spec 011"* — after the fix,
each outer fold's training positions carry holes wherever an earlier fold's
embargo gap falls inside them. Spec 010 gives every task a fitted estimator,
but every registry default (`LogisticRegression`, `Ridge`) has at least one
hyperparameter that changes results (`C`, `alpha`) and nothing in this repo
selects one without either hardcoding it or risking a leak. A hyperparameter
search that picks the best inner-validation score using the outer fold's own
test window is Rule 2 one level deeper — silent, and it produces a better-
looking number.

**Owns / must not know about** (per CLAUDE.md's module table): a new
`scripts/nested_cv.py`. It takes an outer fold's training positions (an
arbitrary, possibly non-contiguous `np.ndarray` of row indices — never a
full frame) and the dates at those positions, and yields further inner
train/validation splits from them. It imports `numpy`/`pandas` only; no
project imports. It has no opinion on what is fit inside a split — that stays
`estimator.py`'s job (spec 010).

---

## Background

`walk_forward_splits` (spec 003, spec 006) yields `train_indices` as a
`np.ndarray` of row positions with gaps already removed — not a contiguous
range like `range(0, k)`. A caller that slices those further with
`train_indices[:m]` is not taking "the first `m` rows chronologically" unless
the array happens to be sorted and gapless; after spec 006 it is sorted (rows
are yielded in increasing order) but **not gapless** whenever an earlier
fold's embargo zone falls inside this fold's training region.

Two things follow from that:

- **Positional slicing must be relative to the array's own order, not to raw
  row-number arithmetic.** `train_indices[:m]` (the first `m` entries of the
  given array) is safe; `train_indices[train_indices < k]` for some absolute
  `k` silently drops however many real rows an embargo gap removed before
  that point, shrinking the inner split for a reason that has nothing to do
  with the horizon being tuned.
- **The inner purge/embargo still applies**, sized from the same
  `label_horizon` the outer split used. An inner validation window's test
  rows must not be reachable from inner training rows whose label overlaps
  them — the identical Rule 2 requirement as the outer split, one level in.

This is exactly the shape of bug Rule 5 exists to catch without an exception:
a hyperparameter search that quietly trains on a few extra rows near an
embargo boundary does not crash. It reports a slightly better cross-validated
score for the hyperparameter that happened to get away with it most.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inner splits respect the array's own gaps (Priority: P1)

As the project owner, I need an inner splitter that treats a fragmented
training-position array correctly, so hyperparameter selection never
silently trains across a gap spec 006 put there on purpose.

**Independent Test**: Build a training-position array with a deliberate
internal gap (simulating a post-spec-006 outer fold), request inner splits,
and assert no inner training position falls inside the gap and no inner
validation window's label horizon reaches into inner training data drawn
from *after* it.

**Acceptance Scenarios**:

1. **Given** a training-position array with an artificial internal hole,
   **When** `inner_walk_forward_splits` is called, **Then** every yielded
   inner-train/inner-validation pair is drawn only from real (non-hole)
   positions, in their existing relative order.
2. **Given** the same setup, **When** the label horizon is `h`, **Then** no
   inner-train position within `h` positions (by the array's own order, not
   by absolute row number) of an inner-validation window's start is
   included in that split's training set.
3. **Given** a contiguous training-position array (no gaps — e.g. the very
   first outer fold, before any embargo exists), **When** the function
   runs, **Then** its splits are equivalent to what `walk_forward_splits`
   itself would produce over that same sub-range, confirming the general
   case subsumes the simple one.

### User Story 2 - Hyperparameter selection never touches the outer test window (Priority: P1)

As the project owner, I need a small hyperparameter search that scores
candidates only on inner-validation folds drawn from the outer fold's own
training data, so a tuned model's reported outer-fold score is still honest.

**Acceptance Scenarios**:

1. **Given** a small grid of candidate hyperparameters and an outer fold's
   training positions, **When** `select_best_hyperparameters` runs,
   **Then** it fits and scores every candidate using only
   `inner_walk_forward_splits` of that training data, and never receives or
   references the outer fold's test indices.
2. **Given** too few positions to form even one inner split at the
   requested `label_horizon`/`embargo_bars`, **When** the search runs,
   **Then** it raises rather than silently returning the first candidate or
   a default.

### Edge Cases

- **A gap wider than the requested embargo**: still just excluded; the
  function does not need to reason about *why* a position is absent, only
  that it is.
- **All training positions fall inside one contiguous run** (no embargo
  history yet): degrades to the ordinary walk-forward case (User Story 1,
  Scenario 3).
- **A single candidate in the grid**: `select_best_hyperparameters` still
  runs the full inner-CV scoring loop rather than short-circuiting, so the
  "no leak" guarantee does not depend on the grid's size.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `inner_walk_forward_splits(train_positions, dates, *,
  label_horizon, embargo_bars, n_inner_splits)` MUST treat `train_positions`
  as an arbitrary sorted (not necessarily contiguous) array of row indices
  and yield inner `(inner_train_positions, inner_val_positions)` pairs drawn
  only from entries of that array, in their existing relative order.
- **FR-002**: The purge/embargo rule applied at each inner boundary MUST be
  the same rule `walk_forward_splits` applies at the outer boundary (spec
  003/006), parameterized by the same `label_horizon`/`embargo_bars` the
  caller supplies — not re-derived or approximated.
- **FR-003**: `inner_walk_forward_splits` MUST raise `ValueError` if
  `train_positions` cannot support `n_inner_splits` splits at the given
  `label_horizon`/`embargo_bars` (too few usable positions) — it must not
  silently reduce the split count.
- **FR-004**: `select_best_hyperparameters(train_positions, dates, frame, *,
  feature_columns, label_column, task, label_horizon, embargo_bars,
  candidates, scorer)` MUST score every candidate using only
  `inner_walk_forward_splits` output over `train_positions`, and MUST NOT
  accept or reference any position outside `train_positions` (enforced by a
  test that passes it a `frame` whose rows outside `train_positions` are
  corrupted with sentinel values, and asserts the result is unaffected).
- **FR-005**: `scorer` is task-aware but supplied by the caller (e.g.
  accuracy for classification, negative mean squared error for regression)
  — this module does not hardcode a metric, since spec 010's registry
  already separates task from estimator and the scoring choice belongs with
  the caller, not the splitter.
- **FR-006** *(Rule 8)*: `nested_cv.py` imports `numpy`/`pandas` only. No
  project imports — this keeps it usable from `estimator.py` or a future
  script without either importing the other.
- **FR-007** *(Rule 6)*: No new dependency.
- **FR-008** *(Rule 5, tests)*: Coverage for a fragmented training-position
  array, the equivalence-to-contiguous case, the too-few-positions error,
  and the outer-test-window isolation guarantee (FR-004's corruption test).

### Key Entities

- **Training-position array**: what an outer `walk_forward_splits` fold
  hands a hyperparameter search as its legal training data — sorted,
  possibly with internal gaps, never assumed to be `range(a, b)`.
- **Inner split**: a further train/validation division of that array,
  purge/embargo-safe at the same horizon as the outer split.

---

## Success Criteria *(mandatory)*

- **SC-001**: No inner-train position lies within `label_horizon` (by the
  array's own relative order) of an inner-validation window's start, across
  a fragmented and a contiguous training-position array.
- **SC-002**: Over a contiguous training-position array, the inner splits
  are equivalent to `walk_forward_splits` applied to that same sub-range.
- **SC-003**: `select_best_hyperparameters`'s chosen candidate is provably
  unaffected by corrupting frame rows outside `train_positions`.
- **SC-004**: Too few usable positions for the requested `n_inner_splits`
  raises `ValueError` rather than silently reducing the count.
- **SC-005**: A mutation check (inner purge dropped, embargo shortened,
  positional slicing replaced with absolute-row-number slicing) fails the
  test suite for each injected defect.

---

## Assumptions

- `n_inner_splits` is fixed per call, not adaptive — a caller wanting more
  inner folds asks for more; this module does not decide that for itself.
- The hyperparameter grid itself (which values of `C`/`alpha` to try) is out
  of scope here; `select_best_hyperparameters` takes `candidates` as given.
  Deciding a sensible default grid is a small follow-on, not this spec.
- This spec does not change `estimator.py`'s registry defaults. Whether a
  tuned estimator becomes the new default, or stays an opt-in
  `estimator_factory` override per spec 010's FR-002, is a decision for
  whichever spec first wires tuning into a live run (spec 012 or later) —
  flagged here rather than decided.
