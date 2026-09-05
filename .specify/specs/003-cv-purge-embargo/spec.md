# Feature Specification: Purged & Embargoed Walk-Forward CV

**Feature Branch**: `003-cv-purge-embargo`

**Created**: 2026-09-05

**Status**: Draft

**Input**: Fix the Rule 2 violation found while scoping the ML-signal work
(spec 004 candidate): `scripts/walk_forward_cv.py`'s expanding-window split
has no purge and no embargo. The last training row before each fold
boundary has a label computed from `Close[t+1]`, and `t+1` is the first row
of that fold's test window — training leaks a label derived from inside the
test set. This spec also closes a standalone Rule 5 gap: `walk_forward_cv.py`
currently has zero tests.

**Owns / must not know about** (per CLAUDE.md's module table): this spec's
changes live entirely in `scripts/walk_forward_cv.py`. It has no signal,
harness, or plotting knowledge before this spec and gains none — it only
decides which row *positions* are legal training data for a given fold. It
does not know what a label is, how it's computed, or what model consumes it;
callers (`scripts/logistic_baseline.py`) pass in the numbers that describe
their own label horizon.

---

## Background — what already exists, and the bug

`walk_forward_splits` builds expanding calendar-month windows: everything
before `train_end` is training, everything in `[train_end, test_end)` is
test, and `train_end` grows by `test_months` each fold. This ordering is
correct — no test row is ever chronologically before a training row. The bug
is not ordering; it is **label overlap at the boundary**.

`logistic_baseline.py`'s `build_features` computes a next-day-direction
label: row `i`'s `Label` is `Close[i+1] > Close[i]`. The training row
immediately before `train_end` therefore has a label built from the price at
position `i+1` — and today, nothing stops `i+1` from being the very first
row of the test window. The model is trained on a label that is a direct
function of a price inside the set it will be evaluated on.

This is exactly the failure Rule 2 names: "a label at `t` computed over the
next `h` bars overlaps every training sample within `h` bars of it. Without
purging, the model is graded on data it effectively memorized."

| Behavior | Present today? |
|---|---|
| Chronological train-before-test ordering | Yes |
| Purge (drop training rows whose label horizon reaches into the test window) | **No** |
| Embargo (gap after each test window before that period can become training data) | **No** |
| Tests on `walk_forward_cv.py` of any kind | **No** |
| `label_horizon`/`embargo_bars` as explicit, caller-supplied parameters (Rule 1/8: the CV module must not guess another module's label horizon) | **No** |

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Purge the boundary leak (Priority: P1)

As the project owner, I need `walk_forward_splits` to drop any training row
whose label reaches into the upcoming test window, so a walk-forward
accuracy number is one I can actually report under Rule 2.

**Why this priority**: This is the leak itself. Everything else in this spec
(embargo, tests) supports or verifies this fix; without it the fix doesn't
exist.

**Independent Test**: Build a small synthetic date range with a known fold
boundary. Call `walk_forward_splits(data, label_horizon=1, ...)`. Assert the
returned training indices for that fold do not include the last row before
`train_end` — the row whose label would reach into the test window.

**Acceptance Scenarios**:

1. **Given** a fold boundary at position `b` (first test row) and
   `label_horizon=h`, **When** `walk_forward_splits` yields that fold,
   **Then** the training indices exclude every position `p` such that
   `p + h >= b` — i.e., the last `h` positions immediately before the test
   window are purged from training.
2. **Given** `label_horizon=0` (a caller whose label needs no future bar —
   not this project's current label, but a legal input), **When**
   `walk_forward_splits` is called, **Then** no purge occurs (nothing to
   purge) and the fold's training set is unchanged from today's positions.
3. **Given** the existing `logistic_baseline.py` label (`Close[i+1]`, a
   1-bar horizon), **When** `walk_forward_splits` is called with
   `label_horizon=1` (the caller-supplied value matching that label),
   **Then** exactly one training row per fold boundary is purged relative to
   today's (buggy) output.

---

### User Story 2 - Embargo after each test window (Priority: P2)

As the project owner, I need a gap after each test window before that
period's bars are eligible to become training data in a later fold, so
bars immediately adjacent to a test window — whose own trailing-window
features were computed close to, but not using, test-period prices — don't
give a later fold's model near-duplicate information about a period it was
just evaluated on, per Rule 2's embargo requirement.

**Why this priority**: Depends on User Story 1 existing first (purge is the
larger, more obviously wrong gap); embargo is the second half of what Rule 2
requires and cannot be reviewed as "Rule 2 done" without it.

**Independent Test**: Run two folds. Confirm the second fold's training
positions exclude both the first `embargo_bars` positions after fold 1's
test window *and* fold 1's own test positions being immediately reusable —
i.e., there is a genuine gap, not just chronological adjacency.

**Acceptance Scenarios**:

1. **Given** fold `k`'s test window ends at position `e` (exclusive), and
   `embargo_bars=g`, **When** any later fold `k+1, k+2, ...` builds its
   training set, **Then** positions in `[e, e+g)` are excluded from that
   training set even though they are chronologically before that later
   fold's own `train_end`.
2. **Given** `g` less than the caller's own `label_horizon`, **When**
   `walk_forward_splits` is called, **Then** it raises `ValueError` —
   Rule 2 requires the embargo be "sized to at least the label horizon,"
   so an under-sized embargo is a caller error, not a silently accepted
   input.
3. **Given** multiple folds in sequence, **When** every fold's train/test
   split is inspected, **Then** every previously-embargoed range remains
   excluded from every subsequent fold's training set (the embargo is
   permanent for that range, not just enforced one fold ahead).

---

### Edge Cases

- A fold whose test window has fewer rows than `label_horizon` or
  `embargo_bars` — purge/embargo must not turn a fold's training set
  negative or crash; the position ranges are computed by clamping, never by
  producing invalid indices.
- The very first fold — no prior test window exists yet, so no embargo
  range applies; only purge (User Story 1) affects it.
- `label_horizon` or `embargo_bars` large enough that an entire fold's
  training data is purged/embargoed away to nothing — the fold must still
  be skipped cleanly (same as today's existing empty-test-window skip), not
  raise.
- Calling `walk_forward_splits` with the current defaults unspecified: per
  FR-001 below, `label_horizon` has no safe default and must be supplied
  explicitly by the caller (Rule 1/8 — the CV module does not get to guess
  another module's label horizon).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** *(Rule 2, Rule 8)*: `walk_forward_splits` MUST accept
  `label_horizon: int` as a required keyword argument (no default) — the
  number of bars a caller's label reaches forward. Forcing an explicit value
  keeps the CV module ignorant of what any specific label computation does,
  per the module boundary in Background.
- **FR-002** *(Rule 2)*: `walk_forward_splits` MUST accept
  `embargo_bars: int` as a required keyword argument (no default) and MUST
  raise `ValueError` if `embargo_bars < label_horizon`.
- **FR-003** *(Rule 2)*: For each fold, the yielded training indices MUST
  exclude every position `p` with `p + label_horizon >= test_start_position`
  (the purge).
- **FR-004** *(Rule 2)*: For each fold, the yielded training indices MUST
  exclude every position in `[test_end_position, test_end_position +
  embargo_bars)` for every **prior** fold's test window — permanently, for
  all subsequent folds (the embargo).
- **FR-005** *(Rule 1)*: Purge and embargo exclusions are computed
  positionally (by row count), not by calendar date — matching how the
  existing label (`Close[i+1]`, a positional shift) is computed. A calendar
  gap (e.g. a holiday) must not change how many rows are purged or
  embargoed.
- **FR-006** *(Rule 8, layer separation)*: `walk_forward_cv.py` gains no
  import of, or reference to, `signals.py` or `backtest_harness.py`. It
  still knows only about row positions and dates.
- **FR-007** *(caller update)*: `scripts/logistic_baseline.py`'s call to
  `walk_forward_splits` MUST pass `label_horizon=1` (matching its
  `Close[i+1]` label) and an explicit `embargo_bars` (>= 1).
  `evaluate_walk_forward`'s existing
  `assert train_dates.max() < test_dates.min()` stays as an ordering
  sanity check; it is not weakened or removed by this spec.
- **FR-008** *(Rule 5, tests)*: `walk_forward_cv.py` — currently untested —
  ships with tests before merge covering: the purge boundary (off-by-one:
  does a training row at exactly `test_start - label_horizon` get purged or
  kept — it must be purged, since `p + label_horizon >= test_start` is
  satisfied at equality), the embargo persistence across folds, and the
  `embargo_bars < label_horizon` validation error.
- **FR-009** *(Rule 6, dependencies)*: No new dependency.

### Key Entities

- **`label_horizon`**: bars a caller's label looks forward, supplied by the
  caller (never inferred), used only to size the purge window.
- **`embargo_bars`**: bars excluded from training immediately after each
  test window, for all future folds; must be `>= label_horizon`.
- **Excluded-range ledger**: the set of `[start, end)` position ranges
  (embargo zones from every fold seen so far) that `walk_forward_splits`
  must keep excluding from every subsequent fold's training positions.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A synthetic-data test proves the last `label_horizon`
  positions before each fold's test start are absent from that fold's
  training indices.
- **SC-002**: A synthetic-data test with 3+ folds proves fold 1's embargo
  zone is still excluded from fold 3's training indices, not just fold 2's.
- **SC-003**: Calling with `embargo_bars < label_horizon` raises
  `ValueError` before any fold is computed.
- **SC-004**: Running `logistic_baseline.py` end-to-end after this change
  completes without error and reports fold accuracies computed on a
  strictly smaller, non-overlapping training set than before — the exact
  accuracy numbers are expected to change from the pre-fix run and that
  change is the point, not a regression.

---

## Assumptions

- `label_horizon=1` and `embargo_bars=1` are the values `logistic_baseline.py`
  passes in (its label is exactly one bar forward). A future model with a
  multi-bar label horizon passes larger values; `walk_forward_cv.py` itself
  hardcodes neither number.
- Purge/embargo are computed on row *position*, not calendar time. This
  project's data is daily bars with no intraday gaps to worry about, so
  position and trading-day count coincide; the choice is recorded here so a
  future intraday-bar caller doesn't assume otherwise.
- This spec does not touch `scripts/data.py`, `scripts/signals.py`,
  `scripts/backtest_harness.py`, or `scripts/plotting.py`. It also does not
  wire model predictions into the harness — that is spec 004, deliberately
  kept separate for reviewability.
