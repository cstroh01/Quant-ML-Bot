# Tasks — 012 Cost-Aware Entry Rule

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Hurdle

- [ ] **T001** `cost_hurdle` — simple-return break-even
  `(2s + 2c/(shares·P))/(1-s)`, derived from the harness's own fills; raises
  on a non-positive price. (FR-001)
- [ ] **T002** `log_hurdle` — `ln(1 + g*)`, because the spec 009 target is a
  log return. (FR-002)

## Phase 2 — Positions

- [ ] **T003** `positions_from_predicted_return` — hysteresis: strict entry
  above the hurdle, hold until below `exit_threshold`, null is flat, forced
  flat at the end. (FR-003)
- [ ] **T004** `positions_from_direction` — the classification counterpart.
  (FR-004)
- [ ] **T005** `signal_from_positions` — transition-detector-then-shift, a
  documented copy of `_signal_from_predictions`, not an import.
  (FR-005, FR-007)

## Phase 3 — Tests (Rule 5, FR-011)

- [ ] **T006** [P] Hurdle arithmetic at known prices/costs, including the
  `1/(1-s)` divisor. (SC-001)
- [ ] **T007** [P] Boundary: a prediction exactly equal to the hurdle does
  not enter. (SC-001)
- [ ] **T008** [P] Null predicted return reads as flat, distinctly from
  `0.0`. (SC-001)
- [ ] **T009** [P] Zero-cost limit: hurdle exactly `0.0`; mask matches
  "strictly positive." (SC-002)
- [ ] **T010** [P] Rule 1: perturbing `Close[t+1]` leaves `hurdle[t]`
  bit-identical. (SC-005)
- [ ] **T011** [P] Hysteresis: `[+2h, +0.5h, +0.5h, -h]` gives exactly one
  entry and one exit. (SC-004)
- [ ] **T012** [P] Harness reconciliation: opens at exactly `g*` give net
  P&L within `1e-9` of zero through the **real** `run_backtest`. (SC-003)
- [ ] **T013** [P] Log-vs-simple: a prediction between `g*` and `ln(1+g*)`
  is correctly declined — the test that catches the unit error directly.
- [ ] **T014** [P] Module boundaries by AST import-set comparison; no
  `backtest_harness`, no `logistic_baseline`. (FR-009)

## Phase 4 — Evidence

- [ ] **T015** Mutation check — at minimum: inclusive boundary; slippage term
  dropped; `1/(1-s)` dropped; `ln(1+g)` replaced by `g`; null treated as
  `0.0`; per-bar gate instead of hysteresis; shift applied before the
  comparison. Each must fail at least one test. (SC-007)
- [ ] **T016** Full suite passes; record the new total in this file's PR.

## Deferred to spec 013

End-to-end wiring (the `main()`-level three-way comparison, SC-006) belongs
with the multi-ticker runner, which already owns per-ticker composition and
both Rule 4 baselines. Building a single-ticker runner here and then
replacing it one spec later is duplicated work and a second reporting path to
keep honest. This spec ships the rule and its tests; spec 013 runs it.
