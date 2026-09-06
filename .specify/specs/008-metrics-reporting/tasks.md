# Tasks — 008 Metrics Reporting Layer

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Shared constants

- [x] **T001** Create `scripts/constants.py` with `TRADING_DAYS_PER_YEAR` and
  `RISK_FREE_RATE_ANNUAL`, carrying the risk-free rate's provenance comment.
  No imports, so any module can depend on it. (FR-010)
- [x] **T002** Change `scripts/return_stats.py` to import both from
  `constants` instead of defining them. No other change. (FR-011)

## Phase 2 — The equity curve

- [x] **T003** `_validate_prices` — required columns, non-empty, 0-based
  `RangeIndex`, unique `Date`, monotonic `Date`. (FR-007)
- [x] **T004** `equity_curve` — four-part per-bar attribution, `Position` as
  shares held at the close, `Equity` anchored at the capital base before
  bar 0's P&L. (FR-003, FR-006)
- [x] **T005** Handle `entry_pos == exit_pos` (same-bar round trip) as its
  own branch; the general formula would double-count a close.
- [x] **T006** Raise `ValueError` for a trade date absent from
  `prices["Date"]`. (FR-008)
- [x] **T007** Reconcile `Bar P&L` against the trade log's `P&L` sum inside
  `equity_curve` and raise on mismatch — a runtime guard, not just a test.
  (FR-004)
- [x] **T008** Require `commission_per_trade`/`slippage_bps` as keyword args
  with no defaults; record them and the capital base in the frame's `attrs`.
  (FR-005)

## Phase 3 — Risk metrics

- [x] **T009** [P] `equity_log_returns` — log returns, matching
  `return_stats.daily_log_returns`; NaN (never `-inf`) where equity is
  non-positive.
- [x] **T010** [P] `sharpe_ratio` — `return_stats.annualize` arithmetic,
  excess over the risk-free rate; `nan` for <2 observations, zero variance,
  or any NaN input. (FR-009)
- [x] **T011** [P] `max_drawdown` — `equity / equity.cummax() - 1`, peak is
  the last high-water mark strictly before the trough.
- [x] **T012** `performance_summary` — flat dict, every key always present,
  costs and capital base echoed. (FR-005, FR-006)

## Phase 4 — Tests (Rule 5, FR-013)

- [x] **T013** [P] Reconciliation on `sawtooth_prices(200)`, costed and
  uncosted, through the real `run_backtest`. (SC-001)
- [x] **T014** [P] Off-by-one: one-bar hold puts P&L on exactly two bars;
  `Position` runs `[e, x)`; commission lands on the entry and exit bars.
  (SC-002)
- [x] **T015** [P] Boundaries: entry on bar 0, position open on the final
  bar, `e == x` same-bar round trip, bar-0 drawdown captured. (SC-005)
- [x] **T016** [P] Empty trade log: flat curve, `nan` Sharpe, `0.0`
  drawdown, complete summary dict. (SC-004)
- [x] **T017** [P] Sharpe: costed differs from uncosted (SC-003); matches
  `return_stats` arithmetic exactly; undefined cases are `nan`, never `inf`
  or `0.0`.
- [x] **T018** [P] Validation: duplicate dates, unsorted dates, non-
  `RangeIndex`, missing trade date, empty frame, negative costs. (SC-006)
- [x] **T019** [P] Gap case: a frame with a missing session is counted in
  bars, not calendar days.
- [x] **T020** [P] Constants are shared by identity, and their values are
  unchanged. (SC-007)

## Phase 5 — Evidence

- [x] **T021** Mutation check — inject three deliberate attribution defects
  and confirm the suite fails on each. All three caught (11 errors,
  1 failure, 7 errors respectively).
- [x] **T022** Confirm `return_stats.annualize` returns identical values
  after the extraction. (SC-007)
- [x] **T023** Full suite: **152 tests, OK**.
