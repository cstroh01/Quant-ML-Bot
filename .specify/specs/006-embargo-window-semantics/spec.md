# Feature Specification: Embargo Window Semantics

**Feature Branch**: `006-embargo-window-semantics`

**Created**: 2026-09-05

**Status**: Draft

**Input**: While scoping the Phase 3 ML work (gradient boosting, continuous
targets, nested hyperparameter tuning, multi-ticker generalization), a
measurement of `scripts/walk_forward_cv.py` showed that the training set
never grows. Spec 003 added a purge and an embargo to close a Rule 2
violation; the embargo it added is *permanent exclusion of each test window*
rather than *a gap after each test window*. Because consecutive test windows
tile contiguously, the union of those permanent exclusions swallows the
entire expanding region, and every fold trains on the same first
`initial_train_months` of data.

**Owns / must not know about** (per CLAUDE.md's module table): this spec's
changes live entirely in `scripts/walk_forward_cv.py` and its test file. The
module still knows only about row positions and dates. It gains no signal,
harness, model, or plotting knowledge.

---

## Background — the measurement

`walk_forward_cv.py:64` keeps a ledger of embargoed position ranges, and
`:85-88` re-applies **every** prior fold's range to **every** later fold's
training indices. The range recorded at `:94` is:

```python
embargoed_ranges.append((test_start_pos, test_end_pos + embargo_bars))
```

That range begins at the test window's *start*. With `test_months=1`, fold
`k+1`'s test window begins exactly where fold `k`'s ended, so the recorded
ranges tile without gaps and their union covers everything from the first
test window onward — permanently, for all later folds.

Measured on `pd.bdate_range("2024-01-01", "2026-06-30")` with
`label_horizon=1, embargo_bars=1` (the values `logistic_baseline.py` passes):

```
fold  1: train n=129  [0..128]  | test [130..152]
fold  2: train n=130  [0..129]  | test [153..174]
fold  3: train n=130  [0..129]  | test [175..195]
fold 12: train n=130  [0..129]  | test [370..390]
fold 24: train n=130  [0..129]  | test [630..651]

train sizes: [129, 130, 130, ... , 130]   # 24 folds
```

Fold 24 trains on Jan-Jun 2024 and predicts Jun 2026 — a 500-bar gap between
the last training row and the first test row. Training size is constant.

| Claim | Status |
|---|---|
| Training data strictly precedes test data (Rule 2) | Holds, before and after |
| Observations whose label horizon overlaps the test window are purged (Rule 2) | Holds, before and after — untouched by this spec |
| An embargo gap is applied after each test window **before training resumes** (Rule 2) | Training never resumes |
| The window is "expanding", as `walk_forward_cv.py:24` states | **False** — it is fixed-width |

The docstring and the behavior disagree. That disagreement is the defect this
spec closes.

---

## Why this is a defect and not a stricter reading

Rule 2 requires "an **embargo** gap is applied after each validation window
**before training resumes**, sized to at least the label horizon." The phrase
*before training resumes* presupposes that training does resume over that
period. An embargo is a buffer around a boundary; it is not a quarantine of
the data.

The current behavior is not a stricter-but-equivalent variant. It is a
different cross-validation scheme — a fixed-width walk-forward — with three
consequences that get worse as the data set grows:

1. **Training size is capped at `initial_train_months` forever.** Adding
   years of history cannot improve any model, because no fold ever sees it.
2. **The train/test gap grows without bound.** By fold 24 the model is
   extrapolating two years past its own training data. Any measured accuracy
   is dominated by regime drift, not by model quality.
3. **It makes hyperparameter tuning meaningless.** Every fold tunes on the
   same ~130 rows, so a nested search selects the same configuration every
   time, at a sample size where the selection is noise.

The last of these is what forced the measurement: Phase 3's nested
walk-forward tuning has nothing to select on until this is fixed.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Training resumes after the embargo gap (Priority: P1)

As the project owner, I need each fold's training set to include the data
that has become historical since the previous fold, so that a walk-forward
run on ten years of history is actually using ten years of history.

**Why this priority**: This is the defect. Everything else in this spec
verifies or documents it.

**Independent Test**: Run three or more folds on a synthetic daily frame.
Assert the training set grows from fold to fold, and that a position inside
fold 1's test window appears in fold 3's training set.

**Acceptance Scenarios**:

1. **Given** a frame producing `n >= 3` folds, **When** the folds are
   enumerated, **Then** each fold's training-set size is strictly greater
   than the previous fold's.
2. **Given** fold 1's test window `[s, e)`, **When** fold 3's training set is
   inspected, **Then** positions in `[s, e)` that are not inside any embargo
   gap and survive fold 3's purge **are present** in fold 3's training set.
3. **Given** the same inputs, **When** any fold's training and test indices
   are compared, **Then** every training position is still strictly less than
   every test position — the chronological guarantee is unchanged.

---

### User Story 2 - The gap after each test window is still excluded (Priority: P1)

As the project owner, I need the `embargo_bars` positions immediately
following each test window to stay out of every later fold's training data,
so the Rule 2 buffer that spec 003 added still exists after this change.

**Why this priority**: Equal priority to User Story 1. A fix that restored
the expanding window by removing the embargo entirely would trade one Rule 2
violation for another.

**Independent Test**: With `embargo_bars=3` and three or more folds, assert
positions `[e, e+3)` for fold 1's test end `e` are absent from every later
fold's training set.

**Acceptance Scenarios**:

1. **Given** fold `k`'s test window ending at exclusive position `e` and
   `embargo_bars=g`, **When** any later fold builds its training set,
   **Then** positions in `[e, e+g)` are excluded from it.
2. **Given** multiple folds, **When** the last fold's training set is
   inspected, **Then** *every* prior fold's embargo gap is still excluded —
   the ledger remains cumulative, exactly as spec 003 built it.
3. **Given** `embargo_bars=0` and `label_horizon=0`, **When** folds are
   built, **Then** no embargo gap exists and training is every position
   before the test window.

---

### Edge Cases

- `embargo_bars=0`: the recorded range `[e, e)` is empty. It must be recorded
  and applied without error, excluding nothing.
- An embargo gap that runs past the end of the data: the range is applied by
  positional comparison, so a gap extending beyond the final position simply
  matches no rows. No clamping, no index error.
- A fold whose test window is immediately adjacent to the prior fold's: the
  embargo gap falls *inside* the next fold's test window and therefore
  excludes nothing from that fold's training set. It still applies to every
  later fold, whose `train_end` has moved past it. This is correct, and it is
  why the holes appear from fold 3 onward rather than fold 2.
- The first fold: no prior test window exists, so the ledger is empty and
  only the purge applies. Unchanged from spec 003.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** *(Rule 2)*: The embargo range recorded per fold MUST be
  `[test_end_position, test_end_position + embargo_bars)` — the gap
  *following* the test window — rather than
  `[test_start_position, test_end_position + embargo_bars)`.
- **FR-002** *(Rule 2)*: The ledger MUST remain cumulative. Every recorded
  gap is applied to every subsequent fold's training indices, exactly as
  spec 003's FR-004 requires. This spec narrows what is recorded, not how
  long it is honored.
- **FR-003**: The purge MUST be unchanged. Training rows with
  `p + label_horizon >= test_start_position` are still excluded, and spec
  003's off-by-one-at-equality behavior is preserved bit for bit.
- **FR-004**: The `embargo_bars < label_horizon` validation MUST be
  unchanged.
- **FR-005** *(Rule 5)*: The chronological guarantee — every training
  position strictly precedes every test position in the same fold — MUST be
  asserted by test for every fold, not just fold 1.
- **FR-006**: The module docstring and `walk_forward_splits`' docstring MUST
  describe the embargo as a gap following each test window, and MUST state
  that prior test data re-enters training in later folds. The word
  "expanding" becomes accurate and stays.
- **FR-007** *(Rule 8)*: `walk_forward_cv.py` gains no import of, or
  reference to, any other project module beyond its existing `data` import.
- **FR-008** *(Rule 6)*: No new dependency.
- **FR-009** *(Rule 5, tests)*: The two existing tests that encode the old
  semantics — `test_embargo_excludes_fold_one_zone_from_fold_two` and
  `test_embargo_persists_to_later_folds` — MUST be rewritten to assert the
  gap semantics rather than deleted, so the embargo remains covered.

### Key Entities

- **Embargo gap**: the `embargo_bars` positions immediately after a test
  window. Excluded from all later folds' training data.
- **Ledger**: the cumulative set of embargo gaps recorded so far. Its
  lifetime is unchanged by this spec; only the extent of each entry changes.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A synthetic-data test with 3+ folds proves training-set size
  strictly increases fold over fold.
- **SC-002**: A synthetic-data test proves a position inside fold 1's test
  window is present in fold 3's training set.
- **SC-003**: A synthetic-data test proves positions in fold 1's embargo gap
  are absent from every later fold's training set.
- **SC-004**: A synthetic-data test proves, for every fold, that
  `max(train_positions) < min(test_positions)`.
- **SC-005**: Every spec-003 purge and validation test passes unmodified.
- **SC-006**: Re-running the measurement in Background on the same date range
  shows training sizes increasing across all 24 folds instead of a constant
  130.

---

## Consequences — the spec-005 numbers move

`docs/PROJECT_CONTEXT.md` quotes an AAPL result produced under the old
semantics: walk-forward accuracy 0.519 against a 0.542 majority-class
baseline, strategy P&L $47.25 against buy-and-hold $126.71 and a random
baseline of $74.26 +/- $19.00 over 20 seeds.

Every one of those numbers was produced by models trained on 130 rows. After
this change the same script trains on progressively more data, so **all of
them are expected to change.** That change is the point of the fix, not a
regression — the same position spec 003 took about its own effect (SC-004
there).

This spec does **not** re-run `logistic_baseline.py` or edit
`docs/PROJECT_CONTEXT.md`. The agent lane cannot reach Yahoo, and the honest
replacement figures come from the Phase 3 multi-ticker run. Until then the
doc's figures stand, with this spec named as the reason they are stale.

---

## Assumptions

- The positional-not-calendar convention from spec 003 (FR-005 there) is
  retained. A gap of `embargo_bars` is `embargo_bars` *rows*, not days.
- `test_end_pos` is exclusive, computed as `test_indices.max() + 1`, matching
  the existing code at `walk_forward_cv.py:93`.
- This spec touches no other module. The nested inner splitter that consumes
  the now-non-contiguous training indices is spec 011.
