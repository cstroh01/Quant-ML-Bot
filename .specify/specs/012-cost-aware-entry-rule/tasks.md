# Tasks — 012 Cost-Aware Entry Rule

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Hurdle

- [x] **T001** `cost_hurdle` — simple-return break-even
  `(2s + 2c/(shares·P))/(1-s)`, derived from the harness's own fills; raises
  on a non-positive price. (FR-001)
- [x] **T002** `log_hurdle` — `ln(1 + g*)`, because the spec 009 target is a
  log return. (FR-002)

## Phase 2 — Positions

- [x] **T003** `positions_from_predicted_return` — hysteresis: strict entry
  above the hurdle, hold until below `exit_threshold`, null is flat, forced
  flat at the end. (FR-003)
- [x] **T004** `positions_from_direction` — the classification counterpart.
  (FR-004)
- [x] **T005** `signal_from_positions` — transition-detector-then-shift, a
  documented copy of `_signal_from_predictions`, not an import.
  (FR-005, FR-007)

## Phase 3 — Tests (Rule 5, FR-011)

- [x] **T006** [P] Hurdle arithmetic at known prices/costs, including the
  `1/(1-s)` divisor. (SC-001)
- [x] **T007** [P] Boundary: a prediction exactly equal to the hurdle does
  not enter. (SC-001)
- [x] **T008** [P] Null predicted return reads as flat, distinctly from
  `0.0`. (SC-001)
- [x] **T009** [P] Zero-cost limit: hurdle exactly `0.0`; mask matches
  "strictly positive." (SC-002)
- [x] **T010** [P] Rule 1: perturbing `Close[t+1]` leaves `hurdle[t]`
  bit-identical. (SC-005)
- [x] **T011** [P] Hysteresis: `[+2h, +0.5h, +0.5h, -h]` gives exactly one
  entry and one exit. (SC-004)
- [x] **T012** [P] Harness reconciliation: opens at exactly `g*` give net
  P&L within `1e-9` of zero through the **real** `run_backtest`. (SC-003)
- [x] **T013** [P] Log-vs-simple: a prediction between `ln(1+g*)` and `g*`
  is correctly **taken** — the test that catches the unit error directly.
  **Wording corrected against FR-002.** This line read "correctly declined",
  which reads the inequality the other way round: `ln(1+g*) < g*`, so a
  prediction in that band clears the log hurdle and is declined only by the
  unit error. `LogVersusSimpleHurdleTests` asserts both halves — taken under
  `log_hurdle`, declined under `cost_hurdle` — so the discriminating case is
  covered whichever way the sentence is read. Flagged rather than silently
  reinterpreted; the arithmetic is in spec.md's *Revision note* point 2 and
  did not change.
- [x] **T014** [P] Module boundaries by AST import-set comparison; no
  `backtest_harness`, no `logistic_baseline`. (FR-009) Extended to cover
  FR-012's `estimators.py` prohibition as well — same check, one more name in
  the forbidden set. `ml_signal.py`'s import set is exactly
  `{__future__, numpy, pandas}`.
- [x] **T014b** [P] **Added — SC-008 was written into spec.md on 2026-09-08,
  after this task list.** `EstimatorAgnosticTests` parameterizes over
  `ESTIMATOR_REGISTRY` itself, fits each entry on deterministic offline
  synthetic data, and routes its predictions through the matching positions
  function and the one shift. A new registry entry is covered by registering
  it and nothing else. (FR-012, SC-008)

## Phase 4 — Evidence

- [x] **T015** Mutation check — all seven defects SC-007 names were injected
  into `ml_signal.py` one at a time and `tests/test_ml_signal.py` re-run
  against each. Every one is caught; the file was restored from an in-memory
  copy and the restore verified by comparison, not by git (Rule 10).

  | injected defect | tests failed |
  |---|---|
  | boundary made inclusive (`>` → `>=`) | 2 |
  | slippage term dropped | 8 |
  | `1/(1-s)` divisor dropped | 8 |
  | `ln(1+g)` replaced by `g` | 3 |
  | null prediction treated as `0.0` | 2 |
  | hysteresis replaced by a per-bar gate | 5 |
  | shift applied before the comparison | 1 |

  The thinnest is the last, at one test — `OrderingTests`. It is the only
  mutant that has to be caught by construction rather than by arithmetic: no
  value is wrong, only the row it is paired with, so the test that catches it
  had to be built with a per-row hurdle that actually moves. That is recorded
  rather than smoothed over, because a one-test margin on the leak this spec
  calls "the single most likely bug in the phase" is the number a reviewer
  should see.
- [x] **T016** Full suite passes: 366 tests, no network, no new dependency.
  `matplotlib` and `statsmodels` were installed into the local virtualenv
  from the existing pinned `requirements.txt`; both were already declared and
  neither is new (Rule 6). Without them several existing test modules failed
  to *import*, so the suite silently ran 150 of its tests — worth flagging on
  its own, independent of this spec.

## Deferred to spec 013

End-to-end wiring (the `main()`-level three-way comparison, SC-006) belongs
with the multi-ticker runner, which already owns per-ticker composition and
both Rule 4 baselines. Building a single-ticker runner here and then
replacing it one spec later is duplicated work and a second reporting path to
keep honest. This spec ships the rule and its tests; spec 013 runs it.
