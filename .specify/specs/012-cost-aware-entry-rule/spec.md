# Feature Specification: Cost-Aware Entry Rule

**Feature Branch**: `012-cost-aware-entry-rule`

**Created**: 2026-09-06

**Revised**: 2026-09-06 — see *Revision note* below.

**Status**: Draft

**Input**: Spec 009's Background named the reason a continuous target exists
at all: *"'up' is not actionable; 'up by 15 bps' is, and it says don't."*
Specs 010 and 011 now produce a tuned, out-of-sample continuous return
prediction per row. Nothing yet turns that prediction into a trade decision —
`logistic_baseline._signal_from_predictions` only knows how to threshold a
binary class prediction. A regression prediction needs a different rule: go
long only when the predicted return clears what the round trip will actually
cost, else stay flat. `tests/test_metrics.py` already names the expected
outcome of building this correctly: *"Phase 3's cost-aware entry rule is
expected to decline nearly every trade."*

**Owns / must not know about** (per CLAUDE.md's module table): a new
`scripts/ml_signal.py`, in the signal layer. It computes a cost **hurdle** —
a return threshold derived from the same cost parameters
`backtest_harness.run_backtest` accepts — and compares a predicted return
against it. It does not import `backtest_harness.py`; it does not fit a model
or know what a fold is.

### Revision note

The first draft had two arithmetic defects and one boundary defect. All three
are corrected here; the first would have made this spec's own success
criterion unreachable.

**1. The hurdle formula was the first-order approximation, not the
break-even.** It stated `2c/(shares·P) + 2s`. Derived against the harness's
actual fills (`backtest_harness.py:67`, `:73`, `:75`):

```
entry fill  E = O_e · (1 + s)
exit  fill  X = O_x · (1 - s)
P&L = X - E - 2c = O_x(1-s) - O_e(1+s) - 2c
```

Setting P&L to zero and solving for the open-to-open simple return
`g = O_x/O_e - 1`:

```
O_x(1-s) = O_e(1+s) + 2c
O_x/O_e  = [(1+s) + 2c/O_e] / (1-s)
g*       = (2s + 2c/P) / (1 - s)
```

The draft dropped the `1/(1-s)` divisor. It is a small term — about 0.05% of
the hurdle at `s = 5 bps` — but SC-003 requires reconciliation with
`run_backtest` *within floating-point tolerance*, and the approximation
cannot meet a 1e-9 bar. Either the formula or the criterion had to give, and
the formula is the one that is simply wrong.

**2. The hurdle is a simple return; the prediction is a log return.**
`targets.forward_log_return_label` (spec 009 FR-002) produces `log(P_{t+h} /
P_t)`. Comparing it directly against `g*` compares two different units. The
conversion is `r* = ln(1 + g*)` and it is not optional — this repo's whole
argument for log returns is that they are a different quantity that happens
to be close for small moves.

**3. It placed the code in `signals.py` and had the exit side import
`logistic_baseline._signal_from_predictions`.** That is a private function in
a module that imports scikit-learn, `backtest_harness`, and
`ma_crossover_backtest`; importing it into `signals.py` would invert the
layering and make the repo's lowest-level signal module depend on its
highest-level ML script. The shift discipline is **copied** into
`ml_signal.py` instead — the same call spec 005 made, with spec 011's
equivalence test pinning the copy to the original.

A fourth change is an addition rather than a correction: **hysteresis**, per
*Design constraint* below.

---

## Background

For a one-share position at price `P`, the round trip's break-even simple
return is `g* = (2s + 2c/P)/(1-s)`, derived above. This is a per-row number,
not a constant, because `P` moves — Rule 1 applies here exactly as it does to
any other feature: the hurdle at row `t` uses only `Close[t]`, never a
full-sample average price.

The commission term dominates. At `P = $250`, `c = $1.00`, `s = 5 bps`, the
hurdle is about **90 bps**, of which the commission contributes 80 and
slippage 10 — a 9:1 ratio. Daily σ for AAPL is around 181 bps. A model's
predicted daily return is very much smaller than its σ, so a 90 bps hurdle
against predictions of that size is expected to clear on very few rows, or
none.

**That is the finding, not a failure.** It is the "transaction-cost story,
not an edge" outcome Rule 4 exists to expose, and it is why
`tests/test_metrics.py`'s `TestEmptyTradeLog` is the best-tested path in the
metrics module. The one-share position size is the root cause — a $1
commission is 40 bps on a $250 share — and fixing *that* is an execution-layer
change under Rule 8, recorded as the natural follow-up and deliberately not
smuggled in here.

---

## Design constraint — three things this must get right

**1. `reference_price` is `Close[t]`, never `Open[t+1]`.** The true entry
price is next bar's open, which is unknowable at `t`. `Close[t]` is a
documented approximation — the overnight gap moves the hurdle by well under a
basis point at $250 — not lookahead. The docstring says so explicitly, or a
reviewer will flag it and be wrong.

**2. The hurdle is compared against the prediction on row `t`, producing
`desired_long[t]`, and only then shifted.** Computing it after building
`Buy_Next_Open` pairs row `t+1`'s Close with row `t`'s decision — a one-row
leak that raises nothing. This is the single most likely bug in the phase and
gets its own test.

**3. Hysteresis, not a per-bar gate.** Holding costs nothing; the hurdle is a
*round-trip* cost. Re-testing a round-trip hurdle every bar would exit and
re-enter repeatedly, paying that round trip each time — the exact opposite of
the rule's purpose. So: enter when the prediction exceeds the entry hurdle,
and stay long until it falls below `exit_threshold` (default `0.0`). This is
a stateful forward scan, which makes it a prime Rule 5 target.

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
row's own close.

**Acceptance Scenarios**:

1. **Given** a predicted return exactly equal to the hurdle, **When** the
   entry rule evaluates that row, **Then** it does **not** enter — the
   boundary is exclusive, because a trade that exactly breaks even is not a
   reason to take on execution risk for nothing.
2. **Given** a predicted return above the hurdle, **When** the rule
   evaluates that row, **Then** it desires long.
3. **Given** `predicted_return` is null (the pre-first-fold window),
   **When** the rule evaluates that row, **Then** it desires flat — matching
   spec 005's existing "no model yet" semantics, and distinct from a
   prediction of `0.0`.
4. **Given** the sequence `[+2h, +0.5h, +0.5h, -h]` where `h` is the hurdle,
   **When** the rule runs, **Then** it produces exactly one entry and one
   exit — not two round trips.

### User Story 2 - The hurdle matches the harness's own cost model exactly (Priority: P1)

As the project owner, I need the hurdle computed from the identical cost
parameters the harness will actually charge, so a strategy that "clears the
hurdle" and then loses money after real costs is a contradiction caught by a
test, not discovered in a live account.

**Acceptance Scenarios**:

1. **Given** a hand-picked pair of opens whose simple return is exactly
   `g*`, **When** a one-share round trip is run through the **real**
   `backtest_harness.run_backtest` with the same `commission_per_trade` and
   `slippage_bps`, **Then** the net P&L is within `1e-9` of zero.

### Edge Cases

- **Zero commission and zero slippage**: hurdle is exactly `0.0`, and
  `ln(1+0) == 0.0` exactly, so any strictly positive predicted return
  enters. This preserves the harness's bit-for-bit uncosted property and
  confirms the rule degrades to "trade on any positive prediction."
- **A near-empty or empty resulting trade log**: not an error, and the
  expected outcome. The reporting path prints the cost model and an honest
  "no completed trades" line, matching `TestEmptyTradeLog`.
- **A non-positive `reference_price`**: the `2c/P` term is undefined. Raise
  rather than emit an `inf` hurdle that silently blocks every trade and looks
  like a finding.
- **Very large predicted returns from an unstable early fold**: not guarded
  here. The comparison is unconditional regardless of prediction size;
  bounding early-fold predictions is an estimator-stability concern (spec
  010/011), flagged rather than solved.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `cost_hurdle(reference_price, *, commission_per_trade,
  slippage_bps, shares=1) -> pd.Series` MUST return the **simple** return
  break-even `(2s + 2c/(shares·P)) / (1 - s)` with `s = slippage_bps/10_000`,
  computed from `reference_price` alone (Rule 1). It MUST raise on a
  non-positive price.
- **FR-002**: `log_hurdle(...)` MUST return `ln(1 + g*)`, and the comparison
  against a `forward_log_return_label` prediction MUST use it. Comparing a
  log-return prediction against a simple-return hurdle is a unit error and
  MUST NOT appear in the code path.
- **FR-003**: `positions_from_predicted_return(predicted_return,
  entry_hurdle, *, exit_threshold) -> pd.Series` MUST implement the
  hysteresis of *Design constraint* 3: enter on `prediction > entry_hurdle`
  (strict), remain long until `prediction < exit_threshold`, treat null as
  flat, and force flat at the final bar's decision if still long.
  `exit_threshold` is keyword-only with no default at the call site.
- **FR-004**: `positions_from_direction(predicted_direction) -> pd.Series`
  MUST provide the classification counterpart, so both targets reach the
  harness through one shift discipline.
- **FR-005**: `signal_from_positions(desired_long) -> (buy_next_open,
  sell_next_open)` MUST use the transition-detector-then-shift pattern —
  a deliberate copy of `logistic_baseline._signal_from_predictions`
  (spec 005), not an import. The docstring MUST say it is a copy and name
  spec 011's equivalence test as what pins it.
- **FR-006** *(Rule 1)*: The hurdle at row `t` MUST depend only on
  `Close[t]`. Perturbing `Close[t+1]` by any factor MUST leave `hurdle[t]`
  bit-identical.
- **FR-007** *(ordering)*: The hurdle comparison MUST be applied to the
  prediction at row `t` to produce `desired_long[t]`, and the shift to
  next-bar-open MUST happen only afterward.
- **FR-008** *(reconciliation)*: A pair of opens at exactly `g*` MUST produce
  a net P&L within `1e-9` of zero through the real `run_backtest`.
- **FR-009** *(Rule 8)*: `ml_signal.py` MUST NOT import
  `backtest_harness.py` or `logistic_baseline.py`. The harness remains the
  only module that *applies* costs to a fill; this module only reasons about
  their size.
- **FR-010** *(Rule 6)*: No new dependency.
- **FR-011** *(Rule 5, tests)*: Coverage for the hurdle arithmetic at known
  prices/costs, the boundary-exclusive case, the null-is-flat case, the
  zero-cost limit, the Rule 1 perturbation test, the hysteresis sequence,
  the harness reconciliation, and the module import set.

### Key Entities

- **Hurdle**: a per-row return threshold derived from that row's own price
  and the stated cost model — never a full-sample statistic. Exists in two
  units, simple and log; the log one is what a spec 009 prediction is
  compared against.
- **Predicted return**: the continuous, out-of-sample output of spec
  010/011's regression path — an input here, not produced here.

---

## Success Criteria *(mandatory)*

- **SC-001**: The entry mask is `True` exactly where `predicted_return` is
  non-null and strictly exceeds that row's own log hurdle; `False`
  (including the boundary-equal case) everywhere else.
- **SC-002**: At zero commission and zero slippage the hurdle is exactly
  `0.0` and the entry mask matches "predicted return strictly positive."
- **SC-003**: A pair of opens at exactly `g*` reconciles to a net P&L within
  `1e-9` of zero through the real `run_backtest`.
- **SC-004**: `[+2h, +0.5h, +0.5h, -h]` produces exactly one entry and one
  exit.
- **SC-005**: Perturbing `Close[t+1]` leaves `hurdle[t]` bit-identical.
- **SC-006**: An end-to-end run on realistic synthetic data produces a
  near-empty or empty trade log without raising, and the reporting path
  prints the cost model and an honest "no completed trades" line.
- **SC-007**: A mutation check (boundary made inclusive; slippage term
  dropped; the `1/(1-s)` divisor dropped; `ln(1+g)` replaced by `g`; null
  prediction treated as `0.0`; hysteresis replaced by a per-bar gate; the
  shift applied before the comparison) fails the test suite for each
  injected defect.

---

## Assumptions

- **Rule 8 boundary, recorded rather than re-litigated.** `ml_signal.py`
  reasoning about the *size* of a cost while `backtest_harness.py` reasons
  about *applying* it is a real coupling: both modules must agree on the cost
  model's shape. The coupling is kept at "shared parameters, not shared
  code" — no import in either direction — with FR-008's reconciliation test
  as the safety net. That is the same shape of guarantee spec 008's
  `equity_curve` reconciliation already provides, so the pattern is
  established rather than novel.
- The hurdle assumes a one-share position, matching every existing script.
  Position sizing is out of scope and is the recorded follow-up.
- `exit_threshold` defaults to `0.0` conceptually — exit when the model stops
  predicting a gain — but is passed explicitly at every call site, per the
  plan's keyword-only-no-default convention for decision parameters.
