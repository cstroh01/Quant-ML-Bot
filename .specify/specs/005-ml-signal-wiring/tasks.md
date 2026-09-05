# Tasks — 005 ML Signal Wiring

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Out-of-sample predictions

- [ ] **T001** Add `walk_forward_predictions(features) -> pd.Series` to
  `scripts/logistic_baseline.py`: fold loop over
  `walk_forward_splits(features, label_horizon=1, embargo_bars=1)`, one
  `LogisticRegression(max_iter=1000, random_state=42)` fit per fold,
  predictions written into an `Int64`-dtype series at each fold's
  `test_indices`. (FR-001, FR-002)

## Phase 2 — Signal construction

- [ ] **T002** Add `build_ml_signal(features) -> tuple[pd.DataFrame, int]`:
  desired-long transition detection on `walk_forward_predictions`' output,
  shifted one bar to `Buy_Next_Open`/`Sell_Next_Open`, returning the
  signalled frame and the first out-of-sample position. (FR-003)

## Phase 3 — Backtest + baseline comparison

- [ ] **T003** Add `COMMISSION_PER_TRADE`, `SLIPPAGE_BPS`,
  `RANDOM_BASELINE_SEEDS` module constants matching
  `ma_crossover_backtest.py`'s values. (FR-004)
- [ ] **T004** Import `baseline_results`, `mean_holding_bars` from
  `ma_crossover_backtest`. (FR-005)
- [ ] **T005** Add local `_format_ml_comparison` — same layout as
  `ma_crossover_backtest.format_comparison`, labeled for the logistic
  strategy instead of SMA. (FR-005)
- [ ] **T006** Update `main()`: after the existing fold-accuracy CSV save,
  build the signal, slice to the live window via `first_covered_pos`, run
  `run_backtest`/`summarize_trades`/`baseline_results`, print the
  comparison. (FR-004)

## Phase 4 — Tests, new file `tests/test_logistic_baseline.py`

- [ ] **T007** [P] Coverage test — every position across all folds' test
  windows gets exactly one prediction; pre-first-fold positions are `<NA>`.
  (SC-001)
- [ ] **T008** [P] Agreement test — `walk_forward_predictions`'s per-fold
  output matches predictions computed inline the same way
  `evaluate_walk_forward` does, on identical synthetic data.
- [ ] **T009** [P] Next-open-shift test — hand-built prediction series;
  `Buy_Next_Open`/`Sell_Next_Open` transitions land one row after the
  prediction changes, never on the same row. (SC-002)
- [ ] **T010** [P] No-repeat-fire test — consecutive "up" predictions
  produce exactly one `Buy_Next_Open`.
- [ ] **T011** [P] Pre-coverage-is-flat test — rows before
  `first_covered_pos` have both signal columns `False`.
- [ ] **T012** [P] End-to-end smoke test — `build_ml_signal` +
  `run_backtest` on synthetic features runs without error; `Cumulative P&L`
  has no NaN/inf.

## Phase 5 — Docs & verification

- [ ] **T013** `docs/PROJECT_CONTEXT.md`: record spec 005's state — the ML
  signal is wired end to end, report the honest (likely weak/near-random)
  comparison numbers once run, flagged per CLAUDE.md as expected rather
  than a problem.
- [ ] **T014** Run `python -m unittest discover -s tests`.

## Out of scope

`scripts/data.py`, `scripts/signals.py`, `scripts/backtest_harness.py`,
`scripts/plotting.py`, `scripts/walk_forward_cv.py`. No behavior change to
`scripts/ma_crossover_backtest.py` (import-only reuse). No new dependency.
No model improvement — same `LogisticRegression`, same features, same seed.
