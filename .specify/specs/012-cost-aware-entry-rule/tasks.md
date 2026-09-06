# Tasks — 012 Cost-Aware Entry Rule

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Hurdle

- [ ] **T001** `round_trip_cost_hurdle` — per-row return-fraction threshold
  from `price`, `commission_per_trade`, `slippage_bps`, `shares`. (FR-001)

## Phase 2 — Entry rule

- [ ] **T002** `cost_aware_entry_signal` — desired-long mask strictly above
  the hurdle, null prediction treated as flat. (FR-002)
- [ ] **T003** Exit side reuses `_signal_from_predictions`'s
  transition-detector-then-shift pattern. (FR-003)

## Phase 3 — Wiring

- [ ] **T004** `main()`-level script producing the three-way comparison
  (cost-aware ML vs. buy-and-hold vs. random) with an honest empty-trade-log
  path. (FR-006)

## Phase 4 — Tests (Rule 5, FR-008)

- [ ] **T005** [P] Hurdle arithmetic at known prices/costs. (SC-001)
- [ ] **T006** [P] Boundary case: predicted return exactly equal to the
  hurdle does not enter. (SC-001)
- [ ] **T007** [P] Null predicted return reads as flat. (SC-001)
- [ ] **T008** [P] Zero-cost limit: entry mask matches "predicted return
  strictly positive." (SC-002)
- [ ] **T009** [P] Harness reconciliation: hurdle-derived predicted return
  vs. `run_backtest`'s actual net P&L on a synthetic one-trade scenario.
  (SC-003)
- [ ] **T010** [P] End-to-end run on realistic synthetic data produces a
  near-empty/empty trade log without raising; reporting path handles it.
  (SC-004)

## Phase 5 — Evidence

- [ ] **T011** Mutation check — at minimum: make the boundary inclusive,
  drop the slippage term from the hurdle, treat null prediction as `0.0`
  instead of flat. Each must fail at least one test. (SC-005)
- [ ] **T012** Full suite passes; record the new total in this file's PR.
