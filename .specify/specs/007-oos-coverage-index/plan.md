# Implementation Plan — 007 Out-of-Sample Coverage Index

**Spec**: `.specify/specs/007-oos-coverage-index/spec.md`

---

## Scope

- `scripts/logistic_baseline.py` — three lines inside `build_ml_signal`
  (FR-001, FR-003)
- `tests/test_logistic_baseline.py` — one new test class (FR-007)

Explicitly **not** touched: every other module, and every other function in
`logistic_baseline.py`. No signature changes.

**No new dependency.**

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | Indirect but real. The defect changes *which rows are backtested*, so a P&L could be reported over a window nobody chose. Correctness of the reported period is a precondition for every other number. |
| 3 — Costs | Unaffected numerically, but relevant: a silently truncated live window produces a cost-adjusted P&L over the wrong period, and Rule 3's "recorded in the results artifact" is worthless if the period is wrong. |
| 5 — Tests | The defect is a position/label alignment bug — squarely "code that indexes … on a timestamp". FR-007 requires a test that fails against the pre-fix code, which is the only proof the fix does anything. |
| 6 — Dependencies | None added. |
| 8 — Layer separation | Change is inside one function of one module. |
| 9 — The merge gate | The mechanism is one sentence: `first_valid_index()` returns a label, `.iloc` takes a position, and they agree only on a 0-based `RangeIndex`. |
| 10 — Version control | No `git` run outside the Actions lane. |

---

## Design

### The change

`logistic_baseline.py:200-203` currently reads:

```python
predictions = walk_forward_predictions(features)
first_covered_pos = predictions.first_valid_index()
if first_covered_pos is None:
    raise RuntimeError("walk_forward_predictions produced no predictions.")
```

It becomes:

```python
predictions = walk_forward_predictions(features)
covered_positions = np.flatnonzero(predictions.notna().to_numpy())
if covered_positions.size == 0:
    raise RuntimeError("walk_forward_predictions produced no predictions.")
first_covered_pos = int(covered_positions[0])
```

and the `int(first_covered_pos)` cast at the return disappears, since the
value is already an `int`.

`np.flatnonzero` on the `.to_numpy()` mask returns **positions** by
construction. The index is never read, so no index shape can mislead it.

### Why not capture positions from the splitter

The obvious alternative is to have `walk_forward_predictions` also return the
`test_indices` it already receives from `walk_forward_splits`, which are
positional at the source. That was the original sketch for this spec, and it
was rejected:

- It changes a public return type from `pd.Series` to a tuple, which breaks
  `TestWalkForwardPredictionsCoverage` and
  `TestWalkForwardPredictionsAgreement` in `tests/test_logistic_baseline.py`.
  Those tests passing **unmodified** is the evidence for FR-002; editing them
  in the same commit that changes behavior would destroy that evidence.
- It is not more correct. `walk_forward_predictions` writes predictions only
  into fold test windows (`:146`, `:161`), so `notna()` and "the union of
  test_indices" are the same set — a fact spec 005's
  `test_coverage_matches_fold_test_windows_exactly` already asserts and
  continues to assert.
- It is a larger diff for the same result.

The three-line version is preferred on reviewability alone (Rule 9).

### Why not add a RangeIndex guard

A defensive `raise` on any non-`RangeIndex` input was considered and
rejected: it would convert the two cases this spec **fixes** into errors. The
whole path — `walk_forward_predictions` (positional `.iloc` writes),
`_signal_from_predictions` (`.shift`, index-agnostic), and now
`build_ml_signal` — is index-agnostic after this change. A guard would
narrow that back down for no gain.

### Why `size == 0` and not falsiness

`first_covered_pos == 0` is a legitimate answer meaning "the very first row
is covered". The pre-fix code tested `is None`, which was correct; a careless
rewrite to `if not first_covered_pos:` would treat position 0 as "no
predictions" and raise. The array-emptiness check keeps the two cases
distinct, and the edge case is named in the spec so a future reader does not
re-introduce the bug while tidying.

### `numpy` is already imported

`logistic_baseline.py:3` imports numpy. No new import.

---

## Test plan (Rule 5, FR-007)

New class `TestFirstCoveredPositionIsPositional` in
`tests/test_logistic_baseline.py`, using the existing
`_synthetic_features` fixture — no new generator.

One frame, three indexes, one assertion set:

- `test_same_position_regardless_of_index` (SC-001, SC-002) — build the
  features once, produce `RangeIndex`, offset-integer, and `DatetimeIndex`
  copies, and assert `build_ml_signal` returns the identical position for all
  three. Against the pre-fix code the offset case returns a different number
  and the datetime case raises `TypeError`, so this fails twice over.
- `test_returned_position_points_at_the_first_prediction` (SC-003) — for each
  index shape, `iloc[pos:]` has a non-null prediction on its first row and
  `iloc[pos - 1]` (where `pos > 0`) does not. This is the off-by-one guard:
  a fix that returned `pos + 1` or `pos - 1` would pass SC-001 and fail here.

Left unmodified, and expected to pass (SC-004): every existing test in
`tests/test_logistic_baseline.py`.

---

## Verification — as run

From the repository root with `venv/` active:

```powershell
python -m unittest discover -s tests
```

**Result: 123 tests, OK.** No failures, no errors. Suite was 121 after spec
006; two tests added here.

### SC-005 — the tests fail against the pre-fix code

`build_ml_signal` was temporarily reverted to `first_valid_index()` and the
class re-run. Both new tests fail, three ways:

```
ERROR: test_same_position_regardless_of_index
  TypeError: int() argument must be ... not 'Timestamp'

ERROR: test_returned_position_points_at_the_first_prediction (index='datetime_index')
  TypeError: int() argument must be ... not 'Timestamp'

FAIL:  test_returned_position_points_at_the_first_prediction (index='offset_index')
  AssertionError: a row before the returned position already had one
```

Note that `test_same_position_regardless_of_index` reports the *datetime*
`TypeError` rather than an offset-index inequality: its dict comprehension
reaches `datetime_index` before it can compare positions. The offset-index
defect is caught by the second test instead, and its message is the
substantive one — position 282 skips 100 rows that already carried
predictions, which is precisely the silent truncation. The `subTest` split in
the second test is what keeps the two failure modes separately visible.

### FR-002 — behavior preserved

Same fixture, all three index shapes, after the fix:

```
RangeIndex    : 182   (pre-fix 182 — unchanged)
offset index  : 182   (pre-fix 282)
DatetimeIndex : 182   (pre-fix raised TypeError)
```

The `RangeIndex` value is identical before and after, so no current caller's
results move.
