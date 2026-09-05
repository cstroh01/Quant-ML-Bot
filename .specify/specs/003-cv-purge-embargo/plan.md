# Implementation Plan — 003 Purged & Embargoed Walk-Forward CV

**Spec**: `.specify/specs/003-cv-purge-embargo/spec.md`

---

## Scope

One module touched, plus its first test file:

- `scripts/walk_forward_cv.py` — `walk_forward_splits` gains
  `label_horizon` and `embargo_bars` required keyword args, purge logic, and
  cross-fold embargo tracking (FR-001–006)
- `scripts/logistic_baseline.py` — one call site updated to pass
  `label_horizon=1, embargo_bars=1` (FR-007)
- `tests/test_walk_forward_cv.py` — **new file**; this module has never had
  one (FR-008)

Explicitly **not** touched: `scripts/data.py`, `scripts/signals.py`,
`scripts/backtest_harness.py`, `scripts/plotting.py`,
`scripts/ma_crossover_backtest.py`. No wiring of predictions into the
harness — that's spec 004.

**No new dependency.**

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | This is what the whole spec restores at the train/test boundary; FR-005 keeps the fix positional so it matches how the label itself is computed. |
| 2 — Purged, embargoed CV | The entire point of this spec. Both halves (purge and embargo) implemented; `embargo_bars < label_horizon` rejected outright. |
| 5 — Tests | `walk_forward_cv.py` had zero tests; this spec is also the first one for that module (FR-008). |
| 6 — Dependencies | None added. |
| 8 — Layer separation | `label_horizon`/`embargo_bars` are required, caller-supplied arguments — the CV module never imports or inspects `signals.py`/`logistic_baseline.py` to guess a label's shape. |
| 10 — Version control | Same Actions-lane carve-out as specs 001/002: implementing agent pushes only to the branch it was invoked on. |

---

## Design

### Signature change

```
def walk_forward_splits(
    data: pd.DataFrame,
    *,
    label_horizon: int,
    embargo_bars: int,
    initial_train_months: int = DEFAULT_INITIAL_TRAIN_MONTHS,
    test_months: int = DEFAULT_TEST_MONTHS,
    date_column: str = "Date",
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
```

`label_horizon` and `embargo_bars` become keyword-only with **no default** —
existing callers must be updated, which is intentional: a silent default
would let a future caller inherit a horizon that doesn't match its own
label without ever being told. Validate `embargo_bars >= label_horizon` at
the top of the function, before the fold loop, so a bad call fails
immediately rather than after computing folds.

### Purge (per fold, at yield time)

The existing loop already computes `test_indices` (a positional array) each
iteration. Before yielding:

```
test_start_pos = test_indices.min()
purge_cutoff = test_start_pos - label_horizon
train_indices = train_indices[train_indices < purge_cutoff]
```

This drops exactly the last `label_horizon` positions immediately before
the test window — the rows whose `Close[i + label_horizon]`-style label
would read into `[test_start_pos, ...)`.

### Embargo (cross-fold, stateful within one generator call)

Maintain a running list of `(embargo_start, embargo_end)` position tuples,
one appended per fold *after* that fold's test window is known:

```
embargo_start = test_indices.max() + 1
embargo_end = embargo_start + embargo_bars
embargoed_ranges.append((embargo_start, embargo_end))
```

Before yielding **every** fold's training indices (including folds before
this one was appended — i.e., apply the full ledger each time, not just the
newest entry), filter:

```
for start, end in embargoed_ranges:
    train_indices = train_indices[(train_indices < start) | (train_indices >= end)]
```

Apply purge first, then the full embargo ledger (order does not matter for
correctness here since both are pure exclusion filters on disjoint-by-
construction reasoning, but purge-then-embargo mirrors the spec's User
Story ordering and keeps the diff easy to read against the two FRs).

Because `embargoed_ranges` accumulates fold-over-fold and is applied in
full every iteration, User Story 2's Acceptance Scenario 3 (fold 1's
embargo still excluded from fold 3) falls out of the loop structure rather
than needing separate handling.

### Caller update, `logistic_baseline.py`

Both call sites (`evaluate_walk_forward`'s loop, and any doctest/example if
present) pass `label_horizon=1, embargo_bars=1` — matching the module's
`Close[i+1]` label exactly. No other change to that file.

### Not doing

- No change to how folds are windowed by calendar month — only which
  *positions within* a fold's training set are legal.
- No inference of `label_horizon` from a label column's own shift — the
  caller states it explicitly (FR-001), keeping the module boundary intact.
- No change to `scripts/ma_crossover_backtest.py`, `signals.py`, or
  `backtest_harness.py` — those baselines don't do walk-forward CV at all
  today.

---

## Test plan (Rule 5, FR-008)

`tests/test_walk_forward_cv.py` is new. Cases:

| Case | Test |
|---|---|
| Purge, interior boundary | Synthetic date range, one fold boundary; row at `test_start - label_horizon` is absent from training indices; row at `test_start - label_horizon - 1` is present. |
| Purge, off-by-one at equality | `p + label_horizon == test_start` is purged (FR-008's explicit off-by-one case). |
| Embargo, immediate | Fold 2's training indices exclude `[fold-1-test-end, fold-1-test-end + embargo_bars)`. |
| Embargo, persistence | 3+ synthetic folds; fold 1's embargo zone is still excluded from fold 3's training indices. |
| Validation | `embargo_bars < label_horizon` raises `ValueError` before any fold is yielded. |
| `label_horizon=0` | No purge occurs; training set for a fold matches the pre-fix positions (User Story 1, Acceptance Scenario 2). |
| Empty-after-purge fold | A fold whose entire training set is purged/embargoed away is skipped, not raised (mirrors today's existing empty-test-window skip). |
| Caller integration | `logistic_baseline.py`'s `evaluate_walk_forward` runs end-to-end on synthetic features without error, with `label_horizon=1, embargo_bars=1`; its own `assert train_dates.max() < test_dates.min()` still passes. |

---

## Risks

| Risk | Mitigation |
|---|---|
| Requiring `label_horizon`/`embargo_bars` with no default is a breaking API change for any other caller of `walk_forward_splits` | Only caller today is `logistic_baseline.py`, updated in this same PR (FR-007). No other module imports this function. |
| Embargo ledger is generator-local state — fine for a single call, but a caller re-entering the generator (e.g. `list()` then iterating again) would recompute it from scratch each time | Acceptable: `walk_forward_splits` is a generator meant to be consumed once per call, same as today; not a new constraint this spec introduces. |
| Purging/embargoing shrinks every fold's training set size, changing `logistic_baseline.py`'s reported accuracy numbers | Expected and correct per SC-004 — the old numbers were computed on leaked data and were never a real result to preserve. |
