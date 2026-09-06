# Tasks — 007 Out-of-Sample Coverage Index

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Record the defect

- [x] **T001** Reproduce the label-vs-position confusion end to end through
  `build_ml_signal` on three index shapes; record the measured positions in
  the spec's Background section. (SC-005 baseline)

## Phase 2 — The fix

- [x] **T002** In `build_ml_signal`, replace `predictions.first_valid_index()`
  with `np.flatnonzero(predictions.notna().to_numpy())`. (FR-001)
- [x] **T003** Guard on `covered_positions.size == 0`, not on falsiness, so a
  legitimate position of `0` is not mistaken for "no predictions". Preserve
  the existing `RuntimeError` and its message. (FR-003)
- [x] **T004** Drop the now-redundant `int(...)` cast at the return; the
  value is already an `int`. Confirm the return type annotation
  `tuple[pd.DataFrame, int]` is still accurate. (FR-004)
- [x] **T005** Update the `build_ml_signal` docstring to say the returned
  value is a row position derived positionally, and why that is not the same
  as an index label.

## Phase 3 — Regression tests (Rule 5, FR-007)

- [x] **T006** [P] `test_same_position_regardless_of_index` — one frame,
  three index shapes, identical returned position. (SC-001, SC-002)
- [x] **T007** [P] `test_returned_position_points_at_the_first_prediction` —
  `iloc[pos:]` starts on a non-null prediction and `iloc[pos-1]` does not.
  Catches an off-by-one that SC-001 alone would miss. (SC-003)

## Phase 4 — Evidence

- [x] **T008** Confirm the new tests **fail** against the pre-fix
  implementation. A regression test that passes both ways proves nothing.
  (SC-005)
- [x] **T009** Confirm `build_ml_signal` returns the identical position on a
  0-based `RangeIndex` before and after the change. (FR-002)
- [x] **T010** Confirm every existing `tests/test_logistic_baseline.py` test
  passes **unmodified**. (SC-004)
- [x] **T011** Run the full suite: `python -m unittest discover -s tests`
  from the repository root with `venv/` active.
