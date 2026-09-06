# Feature Specification: Out-of-Sample Coverage Index

**Feature Branch**: `007-oos-coverage-index`

**Created**: 2026-09-05

**Status**: Draft

**Input**: While scoping the Phase 3 ML work, a latent index/position
confusion was found in `scripts/logistic_baseline.py`'s `build_ml_signal`.
It reads a pandas **index label** and uses it as a **row position**. The two
coincide only because every current caller happens to pass a 0-based
`RangeIndex`. On any other index the backtest's live window is silently
truncated and the reported P&L changes; on a `DatetimeIndex` it raises.

**Owns / must not know about** (per CLAUDE.md's module table): the change is
confined to `scripts/logistic_baseline.py` and its test file. No signal,
harness, data, or CV module is touched. No public signature changes.

---

## Background — the defect

`build_ml_signal` (`logistic_baseline.py:192-210`) must report the first row
that has an out-of-sample prediction, so `main()` can slice the frame down to
the window where trading is actually possible:

```python
predictions = walk_forward_predictions(features)
first_covered_pos = predictions.first_valid_index()
...
return features, int(first_covered_pos)
```

and at `main():292`:

```python
live = signalled.iloc[first_covered_pos:].reset_index(drop=True)
```

`predictions` is built at `:146` with `index=features.index`.
`Series.first_valid_index()` returns an **index label**, not a position.
`.iloc` takes a **position**. The two are the same number only when the index
is a 0-based `RangeIndex`.

Every current caller satisfies that by accident:

- `build_features` ends with `.reset_index(drop=True)` (`:54`).
- `tests/test_logistic_baseline.py::_synthetic_features` builds a fresh frame.

So the code is correct today and wrong in principle — the exact shape of
defect Rule 5 exists to catch, and the same class as the `datetime64[s]`
vs `[us]` cache bug spec 001 found: no exception, just a mismatch waiting for
the right caller.

### Measured

Using the existing `_synthetic_features("2024-01-01", "2024-10-31")` fixture,
calling `build_ml_signal` on the same data under three indexes:

```
RangeIndex            -> first_covered_pos = 182   (rows kept: 123)
index starting at 100 -> first_covered_pos = 282   (rows kept:  23)
DatetimeIndex         -> TypeError: int() argument must be ... not 'Timestamp'
```

The middle row is the dangerous one. The live window loses 100 of 123 rows —
81% of the backtest — with no error. `run_backtest` then reports a P&L
computed over a fifth of the intended period, and nothing in the output says
so.

Reaching it requires only an ordinary pandas operation between
`build_features` and `build_ml_signal` that does not reset the index — a
`features[features["Date"] >= x]` filter, a `.dropna()`, a `.query()`, or a
per-ticker `groupby` slice. Phase 3's multi-ticker runner does exactly this
kind of slicing, which is why this is fixed before it is written rather than
after.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The live window is correct on any index (Priority: P1)

As the project owner, I need `build_ml_signal` to report a real row position
regardless of what index the features frame carries, so a backtest cannot
silently run over the wrong window.

**Why this priority**: It is the whole spec.

**Independent Test**: Call `build_ml_signal` on the same synthetic data
three times — with a 0-based `RangeIndex`, with an offset integer index, and
with a `DatetimeIndex` — and assert all three return the identical position.

**Acceptance Scenarios**:

1. **Given** a features frame with a 0-based `RangeIndex`, **When**
   `build_ml_signal` is called, **Then** the returned position is unchanged
   from today's value — this change is behavior-preserving for every current
   caller.
2. **Given** the same frame reindexed to start at a non-zero integer,
   **When** `build_ml_signal` is called, **Then** the returned position is
   identical to the `RangeIndex` case.
3. **Given** the same frame carrying a `DatetimeIndex`, **When**
   `build_ml_signal` is called, **Then** it returns that same position
   instead of raising `TypeError`.
4. **Given** any of the above, **When** the returned position is used as
   `features.iloc[pos:]`, **Then** the first row of the result is the first
   row carrying an out-of-sample prediction.

---

### Edge Cases

- **No predictions at all** (a frame too short to produce a fold): the
  existing `RuntimeError("walk_forward_predictions produced no predictions.")`
  must still be raised. Position 0 is a legitimate answer and must not be
  confused with "nothing found" — an index-based check using truthiness would
  make that mistake, since `0` is falsy.
- **First row covered** (`first_covered_pos == 0`): must return `0`, not
  raise, and `iloc[0:]` keeps the whole frame.
- A duplicated or unsorted index: irrelevant after this change, because
  nothing reads the index at all.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** *(Rule 1, Rule 5)*: `build_ml_signal` MUST derive the first
  covered row **positionally**, never by reading a pandas index label.
- **FR-002**: The returned value MUST be identical to today's for any frame
  with a 0-based `RangeIndex`. This spec fixes a latent defect; it changes no
  current result.
- **FR-003**: The `RuntimeError` raised when there are no predictions MUST be
  preserved, and MUST be distinguishable from a legitimate position of `0`.
- **FR-004**: No public signature changes. `walk_forward_predictions` keeps
  returning a `pd.Series`, and `build_ml_signal` keeps returning
  `tuple[pd.DataFrame, int]`, so spec 005's tests continue to exercise the
  same API.
- **FR-005** *(Rule 8)*: No new imports of other project modules. No change
  to `walk_forward_cv.py`, `signals.py`, `backtest_harness.py`, or `data.py`.
- **FR-006** *(Rule 6)*: No new dependency.
- **FR-007** *(Rule 5, tests)*: A regression test MUST cover all three index
  shapes from Background, and MUST fail against the pre-fix code.

### Key Entities

- **Index label**: what `Series.first_valid_index()` returns. Meaningful to
  `.loc`.
- **Row position**: a 0-based offset. What `.iloc` takes, and what
  `walk_forward_splits` yields.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `build_ml_signal` returns the same position for `RangeIndex`,
  offset-integer, and `DatetimeIndex` versions of one frame.
- **SC-002**: The `DatetimeIndex` case no longer raises `TypeError`.
- **SC-003**: The returned position, applied as `iloc[pos:]`, yields a frame
  whose first row has a non-null prediction, on all three index shapes.
- **SC-004**: Every spec-005 test in `tests/test_logistic_baseline.py` passes
  **unmodified** — the evidence for FR-002.
- **SC-005**: The new regression test fails against the pre-fix
  implementation.

---

## Assumptions

- `predictions.notna()` is exactly the definition of "this row has an
  out-of-sample prediction". `walk_forward_predictions` fills only fold test
  windows and leaves everything else `pd.NA` (`:146`, `:161`), so a null
  check and a fold-coverage check are the same set. Spec 005's
  `test_coverage_matches_fold_test_windows_exactly` already pins that
  equivalence, and it is left unmodified so it keeps pinning it.
- This spec does not address the duplicated fit/predict loop between
  `evaluate_walk_forward` and `walk_forward_predictions`. Spec 005 ruled
  deliberately in favor of that duplication (`:139-144`); reversing it is a
  decision, not a cleanup, and is out of scope here.
