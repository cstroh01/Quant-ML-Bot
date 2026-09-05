# Feature Specification: Backtest Costs & Baselines

**Feature Branch**: `002-backtest-costs-baselines`

**Created**: 2026-09-05

**Status**: Draft

**Input**: Close the Rule 3 (costs) and Rule 4 (baselines) gaps flagged in
`docs/PROJECT_CONTEXT.md` as "the largest outstanding correctness gap in the
repo — upstream of any reportable metric," before any ML model is
introduced.

**Owns / must not know about** (per CLAUDE.md's module table): this spec's
cost changes live in `scripts/backtest_harness.py` (fills, trades, P&L —
costs are an execution-layer concept) and its baseline-signal changes live in
`scripts/signals.py` (when to trade, and nothing else). Neither gains
knowledge of how the other's counterpart signal was produced;
`backtest_harness.py` still must not know whether a signal came from SMA
crossover, buy-and-hold, a random baseline, or (later) an ML model.

---

## Background — what already exists

| Behavior | Present today? |
|---|---|
| Long-only, one-share execution, entry/exit accounting | Yes (`run_backtest`) |
| Trade log with per-trade and cumulative P&L | Yes |
| Summary stats (trade count, total P&L, win rate) | Yes (`summarize_trades`) |
| Commission per trade | **No** |
| Slippage | **No** |
| Buy-and-hold baseline | **No** |
| Random-signal baseline | **No** |
| Reporting a strategy's metrics beside both baselines | **No** |

`scripts/ma_crossover_backtest.py` already prints "fees and slippage: none" as
an honest disclaimer. This spec is what turns that disclaimer into a closed
gap.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cost-adjusted P&L (Priority: P1)

As the project owner, I need every backtest's P&L to reflect commission and
slippage, so that a Sharpe ratio or win rate I look at is a number the
constitution actually allows me to report — not a gross figure I'd have to
redo later.

**Why this priority**: Rule 3 blocks every other reportable metric. Nothing
downstream (baselines, ML evaluation) produces a number worth trusting until
this exists.

**Independent Test**: Run the existing SMA crossover strategy with
`commission_per_trade=1.00`, `slippage_bps=5` against a known trade log; the
reported net P&L must equal the hand-computed gross P&L minus
(2 × commission_per_trade × total_trades) minus the hand-computed slippage
cost, per trade.

**Acceptance Scenarios**:

1. **Given** a trade log with entry and exit fills, **When** `run_backtest`
   is called with non-zero `commission_per_trade` and `slippage_bps`,
   **Then** each trade's `P&L` reflects both costs applied against the
   trade's direction (slippage raises the buy fill price, lowers the sell
   fill price).
2. **Given** `commission_per_trade=0.0` and `slippage_bps=0.0` (the
   defaults), **When** `run_backtest` is called, **Then** the output is
   byte-identical to the current zero-cost behavior — this spec must not
   change any existing test's expected numbers.
3. **Given** any run, **When** `summarize_trades` is called, **Then** the
   returned summary includes the commission and slippage parameters that
   produced it, alongside total P&L — so a results artifact never reports a
   number without the cost assumptions behind it.

---

### User Story 2 - Buy-and-hold baseline (Priority: P2)

As the project owner, I need a buy-and-hold signal generator so any strategy
can be compared against "did nothing beat doing nothing."

**Why this priority**: Rule 4's first baseline; simpler than the random
baseline and useful as a reference implementation before it.

**Independent Test**: Call `buy_and_hold_signal(prices)` and run it through
`run_backtest`; the trade log has exactly one trade, entered near the first
available bar and exited at the last available bar's close (via the
harness's existing end-of-data exit).

**Acceptance Scenarios**:

1. **Given** a price frame, **When** `buy_and_hold_signal` is applied,
   **Then** exactly one `Buy_Next_Open=True` appears (shifted forward one
   bar from the first row, consistent with the project's existing
   signal-shift convention) and no `Sell_Next_Open` is ever `True`.
2. **Given** the resulting frame, **When** `run_backtest` is called,
   **Then** the harness's existing "still open at end" branch closes the
   position at the final row's close — no new exit logic is added to
   `backtest_harness.py`.

---

### User Story 3 - Random-signal baseline (Priority: P3)

As the project owner, I need a random-signal baseline with the same trade
count as a real strategy, averaged over multiple seeds, so I can tell a real
edge from noise the strategy would have produced by chance.

**Why this priority**: Rule 4's second baseline. Depends on User Story 1
(costs must apply identically to the baseline and the strategy, or the
comparison is meaningless) and benefits from User Story 2 existing first as
a simpler reference implementation.

**Independent Test**: Call
`random_signal(prices, n_trades=8, avg_holding_days=12, seed=0)` twice with
the same seed; results are byte-identical. Call it with 20 different seeds;
the mean and standard deviation of the resulting net P&L (after identical
costs) can be computed and reported beside the real strategy's single
result.

**Acceptance Scenarios**:

1. **Given** `n_trades`, `avg_holding_days`, and `seed`, **When**
   `random_signal` is called, **Then** it produces exactly `n_trades`
   non-overlapping round trips (never enters a new position while one is
   open), each held for `avg_holding_days` trading days, using the same
   `Buy_Next_Open`/`Sell_Next_Open` contract `run_backtest` already expects.
2. **Given** the same arguments and seed, **When** called twice, **Then**
   the output is identical (determinism convention — explicit seed, no
   implicit global random state).
3. **Given** `ma_crossover_backtest.py` run end-to-end, **When** it reports
   the SMA strategy's metrics, **Then** it also reports buy-and-hold's
   metrics and the random baseline's mean ± standard deviation across at
   least 20 seeds, all computed over the identical period with identical
   `commission_per_trade`/`slippage_bps`.

---

### Edge Cases

- Fewer tradeable bars than `avg_holding_days` needs for even one round trip
  — `random_signal` must not silently produce fewer than `n_trades` trades
  without saying so.
- A strategy with `n_trades=0` (no crossovers in the window) — the random
  baseline and buy-and-hold must still run without dividing by zero in any
  frequency-matching step.
- `slippage_bps` large enough to flip a winning trade into a loser — this is
  expected behavior, not a bug, and should be exercised by a test rather
  than assumed away.
- Buy-and-hold on a single-row price frame (no next bar to shift the entry
  onto).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** *(Rule 3)*: `run_backtest` MUST accept `commission_per_trade`
  (dollars, applied once per fill — both the entry and the exit each incur
  it) and `slippage_bps` (basis points of notional, applied against the
  trade's direction) parameters, both defaulting to `0.0` so existing
  callers and tests are unaffected.
- **FR-002** *(Rule 3)*: Slippage MUST worsen every fill in the direction
  that hurts the trade — raise the effective entry (buy) price, lower the
  effective exit (sell) price — never improve a fill.
- **FR-003** *(Rule 3)*: `summarize_trades` MUST return the
  `commission_per_trade` and `slippage_bps` values used, alongside
  `total_pnl`, so a printed or saved summary is never missing the cost
  assumptions behind its own numbers.
- **FR-004** *(Rule 4, baseline 1)*: `scripts/signals.py` MUST provide
  `buy_and_hold_signal(prices)`, producing exactly one shifted entry at the
  first tradeable bar and no exit signal, relying on the harness's existing
  end-of-data close.
- **FR-005** *(Rule 4, baseline 2)*: `scripts/signals.py` MUST provide
  `random_signal(prices, n_trades, avg_holding_days, seed)`, producing
  `n_trades` non-overlapping round trips of `avg_holding_days` length each,
  using an explicit seed (project determinism convention) via
  `numpy.random.default_rng(seed)` — no implicit global random state.
- **FR-006** *(Rule 4)*: `scripts/ma_crossover_backtest.py` MUST report the
  SMA strategy's cost-adjusted metrics beside buy-and-hold's cost-adjusted
  metrics and the random baseline's mean/standard-deviation across at least
  20 seeds, all over the identical ticker/period with identical cost
  parameters.
- **FR-007** *(Rule 8, layer separation)*: Neither new signal function may
  read or produce anything execution-layer (fills, P&L) — they only ever
  emit `Buy_Next_Open`/`Sell_Next_Open` columns, same as
  `sma_crossover_signal` today.
- **FR-008** *(Rule 5, tests)*: Cost math, `buy_and_hold_signal`, and
  `random_signal` each ship with tests before merge — a cost formula is
  exactly the kind of code this rule exists for (silent wrong-number
  failure, not a crash).
- **FR-009** *(Rule 6, dependencies)*: No new dependency. `numpy` is already
  in `requirements.txt`.

### Key Entities

- **Cost parameters**: `commission_per_trade` (USD, per fill) and
  `slippage_bps` (basis points of notional, applied against trade
  direction) — inputs to `run_backtest`, echoed back by `summarize_trades`.
- **Baseline signal**: a `Buy_Next_Open`/`Sell_Next_Open`-shaped DataFrame
  produced without reference to price trend (buy-and-hold) or with
  randomized timing (random signal) — structurally identical to a real
  strategy's signal from the harness's point of view.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero-cost defaults reproduce today's exact SMA crossover
  numbers (8 trades, 50% win rate, ~$33 total P&L) — a regression test pins
  this so the cost change cannot silently alter existing behavior.
- **SC-002**: A hand-computed cost example (fixed commission + slippage on a
  2-trade log) matches `run_backtest`'s output exactly.
- **SC-003**: `random_signal(seed=0)` called twice produces identical trade
  logs; called across 20 seeds produces 20 different, individually valid
  (non-overlapping, correct count) trade logs.
- **SC-004**: `ma_crossover_backtest.py`'s printed output shows three sets
  of cost-adjusted numbers side by side (SMA crossover, buy-and-hold,
  random-baseline mean±std) with the cost parameters used printed once, not
  per-baseline.

---

## Assumptions

- Commission is charged **per fill** (entry and exit each incur
  `commission_per_trade` once), not per round trip. This is the
  conservative reading and matches how a real broker bills.
- `slippage_bps` is a flat basis-points-of-notional model (Rule 3's minimum
  acceptable model); a bid-ask-spread-based model is deferred until real
  spread data is available.
- `avg_holding_days` for the random baseline is computed by the **caller**
  (`ma_crossover_backtest.py`, from the SMA strategy's own trade log) and
  passed in — `signals.py` does not reach into another strategy's results to
  compute it, preserving the module boundary.
- 20 seeds is the minimum for the random baseline's mean/std to be worth
  reporting; this is a default, not a hard requirement — a future spec
  could raise it if the variance looks unstable.
- This spec does not touch `scripts/data.py`, `scripts/plotting.py`, or
  `scripts/return_stats.py`.
