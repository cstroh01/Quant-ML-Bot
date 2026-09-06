# Tasks — 006 Embargo Window Semantics

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Record the defect

- [x] **T001** Measure the current behavior on
  `pd.bdate_range("2024-01-01", "2026-06-30")` with `label_horizon=1,
  embargo_bars=1` and record the fold-by-fold training sizes in the spec's
  Background section. (SC-006 baseline)

## Phase 2 — The change

- [x] **T002** Change the ledger entry at `walk_forward_cv.py:94` from
  `(test_start_pos, test_end_pos + embargo_bars)` to
  `(test_end_pos, test_end_pos + embargo_bars)`. (FR-001)
- [x] **T003** Confirm `test_start_pos` is still used by the purge and is
  not left dead. (FR-003)
- [x] **T004** Update the module docstring and `walk_forward_splits`'
  docstring: the embargo is a gap *following* each test window; prior test
  data re-enters training in later folds; "expanding" is now accurate.
  (FR-006)

## Phase 3 — Rewrite the tests that encode the old semantics (FR-009)

- [x] **T005** Rewrite `test_embargo_excludes_fold_one_zone_from_fold_two`
  as `test_embargo_gap_excluded_from_later_folds` — asserts `[e, e+g)` is
  absent from fold 3 and from every later fold. (SC-003)
- [x] **T006** Rewrite `test_embargo_persists_to_later_folds` as
  `test_prior_test_window_re_enters_training` — asserts positions from
  fold 1's test window are **present** in fold 3's training set. (SC-002)

## Phase 4 — New coverage (Rule 5)

- [x] **T007** [P] `test_training_set_grows_across_folds` — strict growth
  fold over fold. (SC-001)
- [x] **T008** [P] `test_every_fold_trains_strictly_before_it_tests` —
  `max(train) < min(test)` for every fold, not just fold 1. (SC-004, FR-005)
- [x] **T009** [P] `test_all_prior_gaps_still_excluded_from_final_fold` —
  the ledger is still cumulative. (SC-003, FR-002)
- [x] **T010** [P] `test_zero_embargo_records_an_empty_gap` —
  `embargo_bars=0, label_horizon=0` excludes nothing, does not error.
  (Edge Case 1)

## Phase 5 — Regression evidence

- [x] **T011** Confirm the four spec-003 purge/validation tests pass
  **unmodified**: `test_purge_boundary_and_off_by_one`,
  `test_label_horizon_zero_matches_pre_fix_positions`,
  `test_embargo_shorter_than_label_horizon_raises`,
  `test_fully_purged_fold_is_skipped`. (SC-005)
- [x] **T012** Re-run the T001 measurement and confirm training sizes now
  increase across all folds. (SC-006)
- [x] **T013** Run the full suite: `python -m unittest discover -s tests`
  from the repository root with `venv/` active. **121 tests, OK** — no
  failures, no errors. (The machine's system interpreter lacks
  `scikit-learn` and will fail to import `tests/test_logistic_baseline.py`;
  use the repo venv, which has it pinned at 1.9.0.)
