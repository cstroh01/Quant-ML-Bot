# Tasks — 002 Backtest Costs & Baselines

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Costs (Rule 3)

- [ ] **T001** Add `commission_per_trade=0.0`, `slippage_bps=0.0`
  keyword-only params to `run_backtest`. (FR-001)
- [ ] **T002** Apply slippage to the entry fill (worsens buy price) and both
  exit paths — the normal `Sell_Next_Open` exit and the end-of-data close.
  (FR-002)
- [ ] **T003** Subtract commission once at entry, once at exit, from each
  trade's `P&L`. (FR-001)
- [ ] **T004** Add `commission_per_trade`, `slippage_bps` to
  `summarize_trades`'s returned dict. (FR-003)

## Phase 2 — Baseline signals (Rule 4)

- [ ] **T005** `buy_and_hold_signal(prices)` in `scripts/signals.py` —
  single shifted entry at row 1, no exit signal. (FR-004)
- [ ] **T006** [P] `random_signal(prices, n_trades, avg_holding_days,
  seed)` — seeded, non-overlapping, fixed-length round trips via
  `numpy.random.default_rng`. (FR-005)

## Phase 3 — Wiring (`ma_crossover_backtest.py`)

- [ ] **T007** Add `COMMISSION_PER_TRADE` / `SLIPPAGE_BPS` module constants
  and pass them into every `run_backtest` call in the script. (FR-006)
- [ ] **T008** Compute `avg_holding_days` and `n_trades` from the SMA
  strategy's own trade log; run buy-and-hold and 20 seeded random baselines
  through the same harness and cost constants. (FR-006)
- [ ] **T009** Print all three summaries in one block; cost parameters
  printed once. (FR-006, SC-004)

## Phase 4 — Tests (Rule 5, FR-008)

- [ ] **T010** [P] Zero-cost regression test — today's exact SMA numbers
  reproduced with default params. (SC-001)
- [ ] **T011** [P] Cost math test — hand-built 2-trade log, non-zero
  commission + slippage, exact expected output. (SC-002)
- [ ] **T012** [P] Slippage-direction test — high enough `slippage_bps`
  flips a winning trade to a loss.
- [ ] **T013** [P] `buy_and_hold_signal` tests — one trade, correct entry
  row, single-row edge case.
- [ ] **T014** [P] `random_signal` determinism test — same seed twice ->
  identical output. (SC-003)
- [ ] **T015** [P] `random_signal` edge cases — `n_trades=0`, insufficient
  bars for one trade.
- [ ] **T016** [P] End-to-end test or manual run — `ma_crossover_backtest.py`
  prints three cost-adjusted summaries side by side. (SC-004)

## Phase 5 — Docs

- [ ] **T017** `docs/PROJECT_CONTEXT.md`: spec 002 state — Rule 3 and
  Rule 4 gaps closed, real numbers once run.
- [ ] **T018** Run `python -m unittest discover -s tests`.

---

## Out of scope

`scripts/data.py`, `scripts/plotting.py`, `scripts/return_stats.py`,
`scripts/logistic_baseline.py`, `scripts/walk_forward_cv.py`. No new
dependency. No bid-ask-spread slippage model (deferred — spec Assumptions).
