# Feature Specification: Selectable Prediction Target

**Feature Branch**: `009-selectable-target`

**Created**: 2026-09-05

**Status**: Draft

**Input**: The only prediction target in the repository is next-day binary
direction, computed inline in `logistic_baseline.build_features` with a
hardcoded `shift(-1)`. Direction-only discards magnitude, and magnitude is
what a cost-aware entry rule needs: a model that says "up" cannot say whether
"up" is worth more than the round-trip cost of acting on it. Phase 3 needs a
continuous target — forward log return — selectable beside the existing
binary one so the two can be graded on identical folds and costs.

**Owns / must not know about** (per CLAUDE.md's module table): `targets.py`
and `features.py` are **signal-layer** modules. Neither may import
`backtest_harness.py`. `targets.py` knows only about prices and a horizon;
it has no model, no estimator, and no notion of a fold. `features.py` reuses
`signals.sma_crossover_signal` rather than recomputing moving averages.

---

## Background

`logistic_baseline.build_features` (`:36-55`) does four things at once:
builds SMA/crossover columns, derives two more features, computes the label,
and drops warm-up rows. The label is:

```python
next_close = features["Close"].shift(-1)
features["Label"] = (next_close > features["Close"]).astype("Int64")
features.loc[next_close.isna(), "Label"] = pd.NA
```

The horizon is the literal `-1`. It is not a parameter, and nothing connects
it to the `label_horizon=1` that the same file passes to
`walk_forward_splits` at `:65` and `:149`. Those two numbers must agree — the
purge exists precisely to stop a label reaching into a test window — and
today they agree by coincidence rather than by construction.

That coupling is the real reason this spec exists ahead of the estimator and
tuning work. A selectable target with an unstated horizon would let a caller
choose a 5-bar label and inherit a 1-bar purge, which is a Rule 2 violation
that produces no error and a better-looking Sharpe.

### Why a continuous target

- **Direction throws away the signal that decides whether to trade.** With a
  round-trip cost hurdle of roughly 90 bps on a $250 one-share position, "up"
  is not actionable; "up by 15 bps" is, and it says *don't*.
- **It is the statistically easier problem.** Regression on a forward return
  uses the whole distribution of the response. Thresholding to a sign first
  discards most of it and then asks the model to recover a decision boundary
  from what remains.
- **The existing binary result stays the control.** `docs/PROJECT_CONTEXT.md`
  records AAPL direction accuracy of 0.519 against a 0.542 majority-class
  baseline. Keeping both targets selectable is what makes "did the continuous
  target help?" answerable rather than assumed.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A target is chosen, not assumed (Priority: P1)

As the project owner, I need the prediction target and its horizon to be
explicit parameters, so a model, its purge, and its embargo are all sized to
the same label.

**Why this priority**: Every later spec depends on this contract.

**Independent Test**: Call `build_target` with each target kind and a range
of horizons; assert the returned horizon matches what was asked for and the
returned task name matches the target's type.

**Acceptance Scenarios**:

1. **Given** `kind="direction"`, **When** `build_target` is called, **Then**
   it returns an `Int64` series, the task name `"classification"`, and the
   horizon it was given.
2. **Given** `kind="return"`, **When** `build_target` is called, **Then** it
   returns a float series of forward log returns, the task name
   `"regression"`, and the horizon it was given.
3. **Given** an unrecognized `kind`, **When** `build_target` is called,
   **Then** it raises `ValueError` naming the valid kinds — never falls back
   to a default target.
4. **Given** `horizon=0` or a negative horizon, **When** any label function
   is called, **Then** it raises `ValueError`. A zero-horizon direction label
   is `Close[t] > Close[t]`, which is silently `False` on every row.

---

### User Story 2 - The existing label is reproduced exactly (Priority: P1)

As the project owner, I need the new `direction_label(..., horizon=1)` to
produce the identical column `logistic_baseline.build_features` produces, so
the committed AAPL result remains a valid control for everything Phase 3
compares against it.

**Why this priority**: If the two differ, every comparison in Phase 3 is
against a moved goalpost, and nothing would say so.

**Independent Test**: Run both on the same price frame and assert the label
columns are equal element for element, including their `<NA>` placement and
`Int64` dtype.

**Acceptance Scenarios**:

1. **Given** any price frame, **When** `direction_label(prices, horizon=1)`
   and `logistic_baseline.build_features`'s `Label` are compared over the
   rows both produce, **Then** they are identical in value, dtype, and null
   placement.
2. **Given** the same frame, **When** the new `build_features` is called with
   `target_kind="direction", label_horizon=1` and the same window sizes,
   **Then** its output frame matches `logistic_baseline.build_features`'s on
   every shared column, row for row.

---

### User Story 3 - Unobservable labels are absent, not zero (Priority: P1)

As the project owner, I need rows whose label cannot yet be observed to carry
a null rather than a fabricated value, so no model is ever trained on a
target that does not exist.

**Why this priority**: This is Rule 1 at the label. A `False` standing in for
"unknown" is a lookahead bug that improves results.

**Acceptance Scenarios**:

1. **Given** a frame of `n` rows and `horizon=h`, **When** a label is built,
   **Then** exactly the last `h` rows are null.
2. **Given** a direction label, **When** its dtype is inspected, **Then** it
   is `Int64` (nullable), not `bool` or `int64` — neither of which can carry
   a null, and both of which would coerce the unobservable rows to `False`
   or `0`.

---

### Edge Cases

- **Horizon at least as long as the frame.** Every label is null and
  `build_features` returns an empty frame. This must not raise; a caller
  asking for a 300-bar horizon on 200 bars gets nothing, which is correct.
- **A frame shorter than the warm-up window.** `build_features` drops the
  first `long_window` rows; a shorter frame yields an empty result, not an
  error.
- **A gap in the sessions.** Labels are computed by **row offset**, not
  calendar offset. Across a holiday, a 1-bar label spans more than one
  calendar day. That is the same positional convention spec 003 chose for the
  purge (its FR-005), and the two must match or the purge would be sized in
  different units from the label it is purging. Tested explicitly rather than
  left implicit.
- **A zero or negative close.** A forward log return is undefined there. Real
  equity prices are positive; the label is `NaN` rather than `-inf`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `direction_label(prices, *, horizon)` MUST return an `Int64`
  series that is `1` where `Close[t+horizon] > Close[t]`, `0` where it is
  not, and `<NA>` where `Close[t+horizon]` does not exist.
- **FR-002**: `forward_log_return_label(prices, *, horizon)` MUST return
  `log(Close[t+horizon] / Close[t])` as a float series, `NaN` where
  unobservable or where either close is non-positive.
- **FR-003**: Both label functions MUST raise `ValueError` for
  `horizon < 1`.
- **FR-004**: `build_target(prices, *, kind, horizon)` MUST return
  `(label, task, label_horizon)`. Returning the horizon alongside the label
  is what keeps `walk_forward_splits`' "the caller states its own label
  horizon" contract (`walk_forward_cv.py:26-28`) honest once the target is
  selectable — a caller passes through what it was given rather than
  restating a literal.
- **FR-005**: `build_target` MUST raise `ValueError` for an unknown `kind`,
  naming the valid kinds. It MUST NOT default.
- **FR-006**: `build_features` MUST accept `short_window`, `long_window`,
  `volatility_window`, `target_kind`, and `label_horizon` as keyword-only
  arguments, and MUST return `(frame, task, label_horizon)`.
- **FR-007**: `build_features` MUST return a frame with a 0-based
  `RangeIndex`, having dropped warm-up rows and rows with no observable
  label — matching `logistic_baseline.build_features:51-55`.
- **FR-008**: `build_features(..., target_kind="direction", label_horizon=1)`
  with the same window sizes MUST reproduce
  `logistic_baseline.build_features`'s output on every shared column.
- **FR-009** *(Rule 1)*: No feature may be computed from the label, and the
  label column MUST NOT appear in `FEATURE_COLUMNS`.
- **FR-010** *(Rule 8)*: `targets.py` imports only numpy and pandas.
  `features.py` imports `signals` and `targets` and nothing else from the
  project. Neither imports `backtest_harness`.
- **FR-011**: `logistic_baseline.py` MUST NOT be modified. Its results are
  the control this spec is measured against, and its behavior is pinned by
  `tests/test_logistic_baseline.py`.
- **FR-012** *(Rule 6)*: No new dependency.
- **FR-013** *(Rule 5, tests)*: Coverage for the off-by-one (label at `t`
  uses `Close[t+h]` and nothing further), the boundaries (first row, last
  `h` rows, horizon >= frame length), and the gap case (positional, not
  calendar).

### Key Entities

- **Target kind**: `"direction"` or `"return"`. Chosen by the caller.
- **Task**: `"classification"` or `"regression"`. Derived from the kind, not
  chosen independently — it selects which estimator family applies.
- **Label horizon**: bars the label looks forward. Must equal the
  `label_horizon` the caller passes to `walk_forward_splits`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `direction_label(..., horizon=1)` equals
  `logistic_baseline.build_features`'s `Label` element for element, with the
  same dtype.
- **SC-002**: The new `build_features` reproduces the old one on every shared
  column for `target_kind="direction", label_horizon=1`.
- **SC-003**: For a frame of `n` rows and horizon `h`, exactly the last `h`
  labels are null, for every `h` in a range and both target kinds.
- **SC-004**: Perturbing `Close[t+h+1]` leaves the label at `t` unchanged;
  perturbing `Close[t+h]` changes it.
- **SC-005**: `horizon=0`, a negative horizon, and an unknown target kind
  each raise `ValueError`.
- **SC-006**: A horizon at least as long as the frame yields an empty
  `build_features` result without raising.
- **SC-007**: A frame with a missing session produces labels spanning more
  than one calendar day, confirming the positional convention.

---

## Assumptions

- The five feature columns are unchanged from
  `logistic_baseline.FEATURE_COLUMNS`. Making them scale-free — ratios rather
  than the price levels `Short_SMA`, `Long_SMA`, `Volume` currently are — is
  a real weakness for a linear model and a prerequisite for a pooled
  cross-sectional model, but it is a separate change with its own effect on
  results and does not belong in the same PR as a new target.
- `features.py` defines its own `FEATURE_COLUMNS` rather than importing
  `logistic_baseline`'s, because importing that module pulls in scikit-learn
  for a list of five strings. A test asserts the two lists are equal, so the
  duplication cannot drift.
- Task names are `"classification"` and `"regression"`, matching
  scikit-learn's vocabulary, so spec 010's estimator registry can key on them
  directly.
