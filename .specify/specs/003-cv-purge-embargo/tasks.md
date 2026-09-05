# Tasks — 003 Purged & Embargoed Walk-Forward CV

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Signature & validation

- [ ] **T001** Add required keyword-only `label_horizon: int` and
  `embargo_bars: int` params to `walk_forward_splits` (no defaults).
  (FR-001, FR-002)
- [ ] **T002** Validate `embargo_bars >= label_horizon` at the top of the
  function, before the fold loop; raise `ValueError` otherwise. (FR-002)

## Phase 2 — Purge

- [ ] **T003** Compute `test_start_pos = test_indices.min()` per fold and
  filter `train_indices` to `train_indices < test_start_pos - label_horizon`
  before yielding. (FR-003, FR-005)

## Phase 3 — Embargo

- [ ] **T004** Maintain a ledger of `(embargo_start, embargo_end)` position
  ranges, appending one per fold from that fold's own test window.
  (FR-004)
- [ ] **T005** [P] Apply the full ledger (not just the newest entry) to
  every fold's training indices before yielding, so earlier folds' embargo
  zones stay excluded permanently. (FR-004)

## Phase 4 — Caller update

- [ ] **T006** Update `logistic_baseline.py`'s call to
  `walk_forward_splits` to pass `label_horizon=1, embargo_bars=1`. (FR-007)
- [ ] **T007** Confirm `evaluate_walk_forward`'s existing
  `assert train_dates.max() < test_dates.min()` still holds after the
  change — no modification to that assertion. (FR-007)

## Phase 5 — Tests (Rule 5, FR-008) — new file `tests/test_walk_forward_cv.py`

- [ ] **T008** [P] Purge boundary test — row at `test_start - label_horizon`
  purged, row at `test_start - label_horizon - 1` kept. (SC-001)
- [ ] **T009** [P] Purge off-by-one-at-equality test — explicit case named
  in FR-008. (SC-001)
- [ ] **T010** [P] Embargo-immediate test — fold 2 excludes fold 1's
  embargo zone.
- [ ] **T011** [P] Embargo-persistence test — 3+ folds; fold 1's embargo
  zone still excluded from fold 3. (SC-002)
- [ ] **T012** [P] Validation test — `embargo_bars < label_horizon` raises
  `ValueError` before any fold is computed. (SC-003)
- [ ] **T013** [P] `label_horizon=0` test — no purge occurs; matches
  pre-fix positions for that case.
- [ ] **T014** [P] Empty-after-purge fold is skipped, not raised.
- [ ] **T015** [P] `logistic_baseline.py` integration test — synthetic
  features through `evaluate_walk_forward` with `label_horizon=1,
  embargo_bars=1`, no error, ordering assertion still holds. (SC-004)

## Phase 6 — Docs

- [ ] **T016** `docs/PROJECT_CONTEXT.md`: record spec 003's state — Rule 2
  purge/embargo gap closed in `walk_forward_cv.py`; note that
  `logistic_baseline.py`'s reported fold accuracies will differ from any
  prior run (expected, per SC-004 — the old numbers were leaked).
- [ ] **T017** Run `python -m unittest discover -s tests`.

## Out of scope

`scripts/data.py`, `scripts/signals.py`, `scripts/backtest_harness.py`,
`scripts/plotting.py`, `scripts/ma_crossover_backtest.py`. No new
dependency. No wiring of model predictions into signals/harness (spec 004).
