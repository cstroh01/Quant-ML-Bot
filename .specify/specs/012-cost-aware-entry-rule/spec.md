# Feature Specification: Cost-Aware Entry Rule

**Feature Branch**: `012-cost-aware-entry-rule`

**Created**: 2026-09-06

**Status**: Draft

**Input**: Spec 009's Background named the reason a continuous target
exists at all: *"'up' is not actionable; 'up by 15 bps' is, and it says
don't."* Specs 010 and 011 now produce a tuned, out-of-sample continuous
return prediction per row. Nothing yet turns that prediction into a trade
decision — `logistic_baseline._signal_from_predictions` only knows how to
threshold a binary class prediction at 0.5-vs-not. A regression prediction
needs a different rule: go long only when the predicted return clears what
the round trip will actually cost, else stay flat. `tests/test_metrics.py`
already names the expected outcome of building this correctly: *"Phase 3's
cost-aware entry rule is expected to decline nearly every trade."*

**Owns / must not know about** (per CLAUDE.md's module table): lives in
`scripts/signals.py` (signal layer). It computes a cost **hurdle** — a
return-fraction threshold derived from the same cost parameters
`backtest_harness.run_backtest` accepts — and compares a predicted return
against it. It does not import `backtest_harness.py`; it does not fit a
model or know what a fold is. See *Assumptions* below for a boundary
question this spec surfaces rather than resolves.

---

## Background

`backtest_harness.run_backtest(prices, commission_per_trade, slippage_bps)`
charges commission per fill (twice per round trip) and slippage against the
trade direction. For a one-share position at price `P`, the round trip's
total cost in dollars is approximately
`2 * commission_per_trade + 2 * (slippage_bps / 10_000) * P`. Expressed as a
fraction of `P` (the same units a forward log return is in), that is the
**hurdle**: the minimum predicted return an entry must clear before the trade
is worth taking at all, before even asking whether the direction call is
right.

This is a per-row number, not a constant, because `P` moves — Rule 1 applies
here exactly as it does to any other feature: the hurdle at row `t` uses only
`Close[t]`, never a full-sample average price.

A model's own predicted return is small on a daily-bar single-stock signal —
spec 009's own numbers put AAPL direction accuracy barely above a coin flip.
A ~90 bps round-trip hurdle against predictions that size is expected to
clear on very few rows. `tests/test_metrics.py`'s `TestEmptyTradeLog` already
treats a near-empty trade log as the expected, honest shape of this result,
not a bug to chase.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A prediction becomes a trade only past the cost hurdle (Priority: P1)

As the project owner, I need a continuous return prediction converted into a
Buy/Sell signal that only fires when the predicted move is worth its own
cost, so the strategy is graded on decisions it could actually profit from
taking, not on direction alone.

**Independent Test**: Feed a hand-built predicted-return series and price
series with known costs; assert the desired-long mask is `True` exactly on
rows where the prediction exceeds that row's own hurdle, computed from that
row's own price.

**Acceptance Scenarios**:

1. **Given** a predicted return exactly equal to the hurdle, **When** the
   entry rule evaluates that row, **Then** it does **not** enter (the
   boundary is exclusive — a trade that exactly breaks even on costs is not
   a reason to take on execution risk for nothing).
2. **Given** a predicted return one unit above the hurdle, **When** the
   entry rule evaluates that row, **Then** it desires long.
3. **Given** `predicted_return` is null (no out-of-sample prediction yet —
   the pre-first-fold window), **When** the entry rule evaluates that row,
   **Then** it desires flat, matching spec 005's existing "no model yet"
   semantics.

### User Story 2 - The hurdle matches the harness's own cost model exactly (Priority: P1)

As the project owner, I need the hurdle computed from the identical cost
parameters the harness will actually charge, so a strategy that "clears the
hurdle" and then loses money after real costs is a contradiction that gets
caught by a test, not discovered in a live account.

**Acceptance Scenarios**:

1. **Given** `commission_per_trade` and `slippage_bps` values, **When**
   `round_trip_cost_hurdle` computes a threshold for a known price,
   **Then** entering and exiting a one-share position through
   `backtest_harness.run_backtest` at that exact predicted return produces a
   net P&L within floating-point tolerance of zero — the two modules'
   arithmetic reconciles.

### Edge Cases

- **Zero commission and zero slippage**: hurdle is exactly `0.0`; any
  strictly positive predicted return enters. Confirms the rule degrades to
  "trade on any positive prediction" when costs are turned off, which is
  the expected limit.
- **A near-empty resulting trade log**: not an error. `main()`'s reporting
  path must handle zero trades the same way `_format_ml_comparison` already
  does for the existing baseline comparison (spec 005) — print the cost
  model and the (possibly empty) trade table without raising.
- **Very large predicted returns from a fold with too little training data**
  (an unstable early fit): not specifically guarded against here — the
  hurdle comparison is unconditional regardless of prediction size. Flagged
  in Assumptions rather than solved, since bounding early-fold predictions
  is a estimator-stability concern (spec 010/011), not an entry-rule one.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `round_trip_cost_hurdle(price, *, commission_per_trade,
  slippage_bps, shares=1)` MUST return
  `2 * commission_per_trade / (shares * price) + 2 * slippage_bps / 10_000`
  as a return fraction, computed from `price` alone (Rule 1).
- **FR-002**: `cost_aware_entry_signal(predicted_return, prices, *,
  commission_per_trade, slippage_bps) -> (buy_next_open, sell_next_open)`
  MUST desire long strictly where `predicted_return > hurdle` for that row's
  own price, flat elsewhere, and MUST treat a null `predicted_return` as
  flat.
- **FR-003**: The exit side (`sell_next_open`) MUST use the same
  transition-detector-then-shift pattern as
  `logistic_baseline._signal_from_predictions` (spec 005): a position closes
  when the desired-long mask turns off, shifted to the next bar's open —
  not re-derived independently, so both entry rules share one proven
  shift discipline.
- **FR-004** *(reconciliation)*: A synthetic one-trade scenario where the
  predicted return equals the hurdle exactly plus one basis point MUST
  produce, through `backtest_harness.run_backtest` with the identical cost
  parameters, a net P&L consistent with "barely profitable" — never a loss
  larger than the stated costs, which would mean the two modules disagree
  about what the costs are.
- **FR-005** *(Rule 8 boundary — see Assumptions)*: `signals.py` accepts
  cost *parameters* as plain numbers to size the hurdle; it MUST NOT import
  `backtest_harness.py`. The harness remains the only module that *applies*
  costs to a fill.
- **FR-006**: End-to-end wiring (a `main()`-level script, following
  `logistic_baseline.py`'s own pattern) MUST report the cost-aware ML
  strategy beside both Rule 4 baselines, with a trade log that may
  legitimately be empty — `_format_ml_comparison`'s existing empty-trade-log
  path (spec 005) is reused or matched.
- **FR-007** *(Rule 6)*: No new dependency.
- **FR-008** *(Rule 5, tests)*: Coverage for the hurdle arithmetic at known
  prices/costs, the boundary-exclusive case, the null-prediction-is-flat
  case, the zero-cost limit, and the harness reconciliation case (FR-004).

### Key Entities

- **Hurdle**: a per-row return-fraction threshold, derived from that row's
  own price and the stated cost model — never a full-sample statistic.
- **Predicted return**: the continuous, out-of-sample output of spec
  010/011's regression path — an input to this spec, not produced by it.

---

## Success Criteria *(mandatory)*

- **SC-001**: The entry mask is `True` exactly where `predicted_return` is
  non-null and strictly exceeds that row's own hurdle; `False` (including
  the boundary-equal case) everywhere else.
- **SC-002**: At zero commission and zero slippage, the entry mask matches
  "predicted return strictly positive."
- **SC-003**: `round_trip_cost_hurdle` and `backtest_harness.run_backtest`
  reconcile on a synthetic one-trade scenario within floating-point
  tolerance (FR-004).
- **SC-004**: An end-to-end run against real or realistic synthetic data
  produces a near-empty or empty trade log without raising, and the
  reporting path prints the cost model and an honest "no completed trades"
  line rather than crashing on empty aggregation — matching
  `TestEmptyTradeLog`'s existing expectation in `test_metrics.py`.
- **SC-005**: A mutation check (hurdle boundary made inclusive, slippage
  term dropped from the hurdle, null prediction treated as a False `0.0`
  rather than flat) fails the test suite for each injected defect.

---

## Assumptions

- **Rule 8 boundary, flagged rather than resolved**: `signals.py` reasoning
  about the *size* of a cost (to build a threshold) while
  `backtest_harness.py` reasons about *applying* that same cost to a fill is
  a real coupling — both modules now need to agree on the cost model's
  shape. This spec keeps the coupling at "shared parameters, not shared
  code" (no import either direction) and adds the reconciliation test
  (FR-004) as the safety net, but whether that boundary is the right one
  long-term is raised here per CLAUDE.md's "what to flag rather than fix" —
  not decided unilaterally.
- The hurdle formula assumes a one-share position, matching every existing
  script in this repo (`ma_crossover_backtest.py`, `logistic_baseline.py`).
  Position sizing beyond one share is out of scope.
- No stabilization of early-fold predictions (edge case above) is added
  here; if it proves necessary it belongs in spec 010/011's estimator layer,
  not the entry rule.
