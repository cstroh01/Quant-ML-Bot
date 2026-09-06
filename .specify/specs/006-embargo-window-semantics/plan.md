# Implementation Plan — 006 Embargo Window Semantics

**Spec**: `.specify/specs/006-embargo-window-semantics/spec.md`

---

## Scope

One module, one test file:

- `scripts/walk_forward_cv.py` — the embargo range recorded per fold changes
  from `[test_start_pos, test_end_pos + embargo_bars)` to
  `[test_end_pos, test_end_pos + embargo_bars)`; docstrings updated to
  describe the gap semantics (FR-001, FR-006)
- `tests/test_walk_forward_cv.py` — two existing embargo tests rewritten to
  the gap semantics, four tests added (FR-005, FR-009)

Explicitly **not** touched: `scripts/logistic_baseline.py`,
`scripts/data.py`, `scripts/signals.py`, `scripts/backtest_harness.py`,
`scripts/ma_crossover_backtest.py`, `scripts/plotting.py`,
`docs/PROJECT_CONTEXT.md`.

The call sites in `logistic_baseline.py` (`:65`, `:149`) already pass
`label_horizon=1, embargo_bars=1` and need no change — the signature is
untouched. Their *results* change; their *code* does not.

**No new dependency.**

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | Unaffected in the safe direction. Training still strictly precedes test in every fold; the purge is untouched. This spec adds *older* data back to training, never newer. FR-005 asserts the ordering per fold rather than trusting it. |
| 2 — Purged, embargoed CV | The point of the spec. Restores the "before training resumes" half of the rule that the current implementation cannot satisfy, while keeping the purge and the cumulative ledger spec 003 built. |
| 5 — Tests | Every changed behavior is covered before merge: growth, re-admission, gap exclusion, per-fold ordering. The purge and validation tests from spec 003 pass unmodified, which is itself the evidence that the purge was not disturbed. |
| 6 — Dependencies | None added. |
| 8 — Layer separation | No new imports. The module still knows only positions and dates. |
| 9 — The merge gate | The mechanism is one changed tuple element. The explanation is the Background measurement in the spec: contiguous test windows make a start-anchored ledger tile into a permanent truncation. |
| 10 — Version control | No `git` run by the implementing agent outside the Actions lane. |

---

## Design

### The change

`walk_forward_cv.py:93-94` currently reads:

```python
test_end_pos = int(test_indices.max()) + 1
embargoed_ranges.append((test_start_pos, test_end_pos + embargo_bars))
```

It becomes:

```python
test_end_pos = int(test_indices.max()) + 1
embargoed_ranges.append((test_end_pos, test_end_pos + embargo_bars))
```

`test_start_pos` remains in use by the purge at `:77-81` and is not removed.

Nothing else in the function changes. The ledger is still appended once per
fold, still applied in full at `:85-88`, and still applied *before* the fold
is yielded, so a fold's own gap cannot affect its own training set (it is
recorded after the yield in program order, and it lies after that fold's
test window in any case).

### Why the holes start at fold 3

Worked through on the `_daily_frame("2024-01-01", "2024-04-30")` fixture with
`initial_train_months=1, test_months=1, label_horizon=1, embargo_bars=3`:

| Fold | Test window | Gap recorded | Training set |
|---|---|---|---|
| 1 | `[31, 60)` (Feb) | `[60, 63)` | `[0, 30)` — purge only |
| 2 | `[60, 91)` (Mar) | `[91, 94)` | `[0, 59)` — the gap `[60,63)` lies inside fold 2's own test window, so it excludes nothing |
| 3 | `[91, 121)` (Apr) | `[121, 124)` | `[0, 60) ∪ [63, 90)` — **the hole appears** |

Fold 3 is the first fold whose `train_end` has moved past fold 1's gap. This
is the mechanism behind spec Edge Case 3, and it is why SC-002 and SC-003
both test at fold 3 rather than fold 2.

Note also what fold 3 demonstrates for SC-002: positions 31-59 are inside
fold 1's *test* window and are present in fold 3's *training* set. Under the
current code they are permanently excluded.

### What is deliberately not changed

- **The purge.** `p + label_horizon >= test_start_pos` still governs, with
  the same at-equality behavior spec 003's `test_purge_boundary_and_off_by_one`
  pins. That test passing unmodified is the regression evidence.
- **The validation.** `embargo_bars < label_horizon` still raises.
- **The signature.** No caller updates, no new parameters. A parameterized
  `embargo_mode` was considered and rejected: two CV semantics in one
  repository is exactly the silent-inconsistency failure the constitution's
  preamble describes, and the old semantics has no defensible use once the
  measurement in the spec is on the record.

---

## Test plan (Rule 5)

Fixture: the existing `_daily_frame(start, end)` in
`tests/test_walk_forward_cv.py:15`. One row per calendar day means position
equals day offset, so every expected value below is hand-computable rather
than derived from the code under test.

### Rewritten (FR-009)

Both existing embargo tests assert that fold 1's **entire test window** stays
excluded. That is the behavior being removed, so both are rewritten rather
than deleted — the embargo must not lose coverage in the same commit that
changes it.

- `test_embargo_gap_excluded_from_later_folds` (was
  `test_embargo_excludes_fold_one_zone_from_fold_two`) — asserts
  `[e, e+g)` is absent from fold 3's training set, and asserts the same for
  every later fold, not just one.
- `test_prior_test_window_re_enters_training` (was
  `test_embargo_persists_to_later_folds`) — the inverse assertion: positions
  in fold 1's test window that are outside every gap and survive the purge
  **are present** in fold 3's training set. Named to state the new
  behavior rather than the old one.

### Added

- `test_training_set_grows_across_folds` (SC-001) — strict growth fold over
  fold.
- `test_every_fold_trains_strictly_before_it_tests` (SC-004, FR-005) — the
  ordering guarantee, asserted for **every** fold. This is the test that
  would catch a fix that restored growth by breaking chronology.
- `test_all_prior_gaps_still_excluded_from_final_fold` (SC-003, FR-002) —
  the ledger is still cumulative, checked against every prior fold's gap at
  once rather than one fold ahead.
- `test_zero_embargo_records_an_empty_gap` (Edge Case 1) — `embargo_bars=0`
  with `label_horizon=0` excludes nothing and does not error.

### Unmodified, and expected to pass (SC-005)

`test_purge_boundary_and_off_by_one`,
`test_label_horizon_zero_matches_pre_fix_positions`,
`test_embargo_shorter_than_label_horizon_raises`,
`test_fully_purged_fold_is_skipped`.

`TestLogisticBaselineIntegration.test_evaluate_walk_forward_runs_without_error`
is also unmodified, and its assertion (`Train_End < Test_Start` for every
fold) still holds.

---

## Verification — as run

Run from the repository root with `venv/` active (the repo venv carries
`scikit-learn==1.9.0`; the machine's system interpreter does not, and
`tests/test_logistic_baseline.py` will fail to import under it):

```powershell
python -m unittest discover -s tests
```

**Result: 121 tests, OK.** No failures, no errors.

The suite was 117 before this spec. The four added tests are
`test_training_set_grows_across_folds`,
`test_every_fold_trains_strictly_before_it_tests`,
`test_all_prior_gaps_still_excluded_from_final_fold`, and
`test_zero_embargo_records_an_empty_gap`; the two rewritten tests replace
two existing ones and so do not change the count.

### SC-006 measurement, re-run

Same date range as the spec's Background section
(`pd.bdate_range("2024-01-01", "2026-06-30")`, `label_horizon=1`,
`embargo_bars=1`), 24 folds:

```
before:  [129, 130, 130, 130, ... , 130]     constant
after:   [129, 152, 173, 193, 215, 235, 256, 278, 297, 317, 338, 359,
          379, 401, 421, 442, 464, 483, 505, 526, 545, 566, 587, 607]
```

Strictly increasing across all 24 folds. Every fold still satisfies
`max(train) < min(test)`. The final fold now trains on 607 rows instead of
130.

### Worked table, confirmed against the implementation

The fold-by-fold table in Design above was verified by running the fixture:
fold 1 trains `[0, 30)`, fold 2 trains `[0, 59)`, fold 3 trains
`[0, 60) ∪ [63, 90)` — 87 rows, with the hole at positions 60-62 exactly
where fold 1's gap was recorded.
