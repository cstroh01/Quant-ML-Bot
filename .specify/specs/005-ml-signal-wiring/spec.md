# Feature Specification: ML Signal Wiring

**Feature Branch**: `005-ml-signal-wiring`

**Created**: 2026-09-05

**Status**: Draft

**Input**: Wire `logistic_baseline.py`'s walk-forward model into an actual
tradeable signal, run it through `backtest_harness.py`, and report it beside
both Rule 4 baselines with identical costs — the way `ma_crossover_backtest.py`
already does for the rule-based strategy. Depends on spec 003 (purged &
embargoed CV): this is the first spec to actually trade on that CV's output,
so it is also the first real test that spec 003's fix works end to end.

**Owns / must not know about**: this spec's changes live entirely in
`scripts/logistic_baseline.py`. It does not modify `scripts/signals.py`,
`scripts/backtest_harness.py`, or `scripts/ma_crossover_backtest.py` — it only
*imports* two label-agnostic helpers from the latter (`baseline_results`,
`mean_holding_bars`) rather than duplicating that logic. Module boundaries
per CLAUDE.md stay exactly where they are: `backtest_harness.py` still knows
nothing about how a signal was produced, and this script still knows nothing
about fills or accounting beyond calling it.

---

## Background — what exists and what's missing

`evaluate_walk_forward` already fits one logistic model per walk-forward fold
and reports each fold's accuracy against a majority-class baseline. But it
throws every fold's predictions away once accuracy is computed — nothing in
the repo turns those predictions into a `Buy_Next_Open`/`Sell_Next_Open`
signal, so the model has never actually been backtested, only graded.

This spec closes that gap without changing how the model is evaluated:

| Behavior | Present today? |
|---|---|
| Walk-forward fold accuracy (informational only) | Yes |
| Out-of-sample predictions collected into one aligned series | **No** |
| Those predictions turned into a next-open trading signal | **No** |
| That signal run through `run_backtest` with real costs | **No** |
| Cost-adjusted comparison vs. buy-and-hold and random baselines | **No** |

## The lookahead constraint this spec exists to respect

A signal is only as trustworthy as the predictions behind it. If the model
were fit once on the whole dataset and then asked to "predict" every row,
every prediction before the fit's own end date would be lookahead — exactly
what spec 003's purge/embargo work was for. So the signal here is built
**fold-by-fold**, the same way `evaluate_walk_forward` already scores it: a
model trained only on data strictly before a fold's test window produces that
fold's predictions, and only those out-of-sample predictions ever become
part of the signal. Rows before the first fold's test window (the initial
training period) get no prediction and are treated as flat — there is no
model yet, so there is nothing to trade on, which is a true "not live yet"
state rather than a gap to paper over.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Turn predictions into a signal (Priority: P1)

As the project owner, I need the walk-forward model's out-of-sample
predictions collected into one series aligned to `features`' rows, so a
signal can be built from them without re-deriving the fold logic elsewhere.

**Acceptance Scenarios**:

1. **Given** `features` with several walk-forward folds, **when** predictions
   are collected, **then** every row inside any fold's test window has
   exactly one prediction (its own fold's), and no row is covered twice.
2. **Given** a row before the first fold's test window, **when** predictions
   are collected, **then** that row's prediction is missing (`<NA>`), not a
   guess.
3. **Given** the same `features` and the existing `evaluate_walk_forward`,
   **when** both are run, **then** the predictions collected here agree with
   `evaluate_walk_forward`'s per-fold predictions row for row (both fit the
   identical model on the identical training data per fold).

### User Story 2 - Predictions become a next-open signal (Priority: P1)

As the project owner, I need "predicted up" to become a real position, using
the same next-open discipline every other signal in the repo already uses —
a prediction known at a row's close is only actionable at the *next* row's
open.

**Acceptance Scenarios**:

1. **Given** a prediction of "up" following a period of "no position" or
   "down", **when** the signal is built, **then** `Buy_Next_Open` fires one
   row later, not on the same row the prediction became known.
2. **Given** a prediction of "down" following a held long position,
   **when** the signal is built, **then** `Sell_Next_Open` fires one row
   later.
3. **Given** consecutive "up" predictions, **when** the signal is built,
   **then** no repeated `Buy_Next_Open` fires while already long — only the
   transition into "up" trades, matching `sma_crossover_signal`'s
   crossing-detector pattern rather than firing every bar.
4. **Given** rows with no prediction yet (before the first fold), **when**
   the signal is built, **then** those rows are flat: no `Buy_Next_Open` or
   `Sell_Next_Open` fires on them.

### User Story 3 - Cost-adjusted comparison against both baselines (Priority: P1)

As the project owner, I need the ML signal's backtest reported beside
buy-and-hold and a random baseline, over the identical "live" period and
identical costs, per CLAUDE.md's PR requirements (Rule 4).

**Acceptance Scenarios**:

1. **Given** the ML signal only exists from the first fold's test window
   onward, **when** the comparison runs, **then** all three rows (ML
   strategy, buy-and-hold, random) are computed over that same live window —
   never over the pre-model warm-up period, which the strategy itself never
   had a chance to trade.
2. **Given** the same cost model `ma_crossover_backtest.py` uses
   ($1.00/fill commission, 5 bps slippage), **when** the comparison runs,
   **then** all three rows use those same costs, stated once above the
   table.

## Requirements *(mandatory)*

- **FR-001**: A new function collects one out-of-sample prediction per row
  covered by any walk-forward fold, using the same `label_horizon=1,
  embargo_bars=1` `evaluate_walk_forward` already uses.
- **FR-002**: Rows with no prediction (before the first fold) are represented
  as missing, not defaulted to a class.
- **FR-003**: A new function turns those predictions into `Buy_Next_Open` /
  `Sell_Next_Open` columns using next-open-shifted transition detection
  (enter on the transition into "predicted up", exit on the transition out
  of it) — not a same-bar fill, and not a repeated fire while already
  positioned.
- **FR-004**: `main()` runs this signal through `run_backtest` and reports it
  beside both Rule 4 baselines, computed over the same live (post-warm-up)
  window and the same costs as `ma_crossover_backtest.py`.
- **FR-005**: No change to `scripts/signals.py`, `scripts/backtest_harness.py`,
  or the *behavior* of `scripts/ma_crossover_backtest.py` — only importing
  two existing, label-agnostic helpers from it (`baseline_results`,
  `mean_holding_bars`). Report formatting is written locally rather than
  reusing `ma_crossover_backtest.format_comparison`, because that function
  hardcodes the SMA strategy's own label — reusing it here would mislabel
  the ML result as "SMA crossover."
- **FR-006**: `evaluate_walk_forward`'s existing signature and behavior are
  unchanged; this spec adds new functions alongside it rather than
  refactoring it, keeping this diff small enough to review against spec
  003's already-passing tests.

## Success Criteria

- **SC-001**: Every row in any fold's test window has exactly one
  prediction; no row is covered by two folds or zero folds within the
  covered range.
- **SC-002**: The resulting trade log, run through the existing cost model,
  never opens a position without a preceding "predicted up" transition and
  never closes one without a preceding "predicted down" transition (or
  end-of-data).
- **SC-003**: The printed comparison shows the ML strategy, buy-and-hold, and
  the random baseline computed over the identical live window with
  identical stated costs.
- **SC-004** (expectation, not a test): the ML strategy's edge over the
  random baseline, if any, should be modest — a large edge on a single-stock
  next-day-direction task is a result to distrust first and celebrate
  second, per CLAUDE.md's "too good" flag.

## Out of scope

`scripts/data.py`, `scripts/signals.py`, `scripts/backtest_harness.py`,
`scripts/plotting.py`, `scripts/walk_forward_cv.py`. No new dependency. No
change to the model itself (still `LogisticRegression`, same features, same
`random_state=42`) — this spec wires up what already exists, it does not
improve the model. No probability threshold tuning beyond the existing
`.predict()` class output.
