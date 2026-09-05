# Implementation Plan — 002 Backtest Costs & Baselines

**Spec**: `.specify/specs/002-backtest-costs-baselines/spec.md`

---

## Scope

Three modules touched, no new files beyond tests:

- `scripts/backtest_harness.py` — add commission/slippage params to
  `run_backtest`; extend `summarize_trades`'s return dict (FR-001–003)
- `scripts/signals.py` — add `buy_and_hold_signal`, `random_signal`
  (FR-004–005)
- `scripts/ma_crossover_backtest.py` — wire real cost params, run and print
  both baselines beside the SMA result (FR-006)
- `tests/test_backtest_harness.py`, `tests/test_signals.py` — extended, not
  replaced

Explicitly **not** touched: `scripts/data.py`, `scripts/plotting.py`,
`scripts/return_stats.py`, `scripts/logistic_baseline.py`,
`scripts/walk_forward_cv.py`. This spec is execution-layer and signal-layer
only.

**No new dependency.** `numpy` is already present for the random baseline's
`default_rng`.

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 3 — Costs mandatory | The entire point of this spec. Defaults are `0.0` so nothing existing regresses, but every call site in `ma_crossover_backtest.py` is updated to pass real values. |
| 4 — Two baselines | Buy-and-hold and random-signal both implemented as signal generators, run through the unmodified `run_backtest`, reported beside the real strategy with identical costs. |
| 5 — Tests | Cost math and both new signal generators ship with tests before merge — see Test plan below. |
| 6 — Dependencies | None added. |
| 8 — Layer separation | Costs live in the harness (execution), not in signals. Baselines live in signals (when to trade), and know nothing about fills or P&L — they emit the same `Buy_Next_Open`/`Sell_Next_Open` contract `sma_crossover_signal` already does, so `run_backtest` needs zero changes to accept them. |
| 10 — Version control | Same Actions-lane carve-out as spec 001: implementing agent pushes only to the branch it was invoked on. |

---

## Design

### Cost model, in `run_backtest`

Two new keyword-only parameters, both defaulting to `0.0`:

```
run_backtest(prices, *, commission_per_trade=0.0, slippage_bps=0.0)
```

Applied at the two points a fill already happens in the existing state
machine:

- **Entry fill**: `effective_price = raw_open_price * (1 + slippage_bps /
  10_000)` — buying gets worse, never better.
- **Exit fill**: `effective_price = raw_open_price * (1 - slippage_bps /
  10_000)` (or `raw_close_price` for the end-of-data exit) — selling gets
  worse, never better.
- **Commission**: subtracted once at entry, once at exit, from that
  trade's `P&L`.

No change to the state machine's control flow — only the two
price-assignment lines and one additional subtraction gain the cost terms.
This is why SC-001 (zero-cost defaults reproduce today's numbers exactly) is
a meaningful regression test rather than a formality: the change is additive
to the existing arithmetic, not a rewrite.

`summarize_trades` gains two more keys in its returned dict:
`commission_per_trade`, `slippage_bps` — the values it was given, not
recomputed, so the summary is self-describing wherever it's printed or
saved.

### Baseline signals, in `signals.py`

```
buy_and_hold_signal(prices) -> DataFrame
random_signal(prices, n_trades, avg_holding_days, seed) -> DataFrame
```

`buy_and_hold_signal` sets crossover-equivalent truth on row 0 only, then
applies the same `shift(1, fill_value=False)` convention
`sma_crossover_signal` already uses for `Buy_Next_Open` — so the entry lands
on row 1's open, and no `Sell_Next_Open` is ever set. The harness's existing
"still open at end" branch (already in `run_backtest`, untouched) closes it
at the last row's close. Zero new exit logic anywhere.

`random_signal` uses `numpy.random.default_rng(seed)` to choose `n_trades`
non-overlapping start indices from the valid entry range (`len(prices) -
avg_holding_days`, so every trade has room to complete), sets
`Buy_Next_Open=True` at each start and `Sell_Next_Open=True` exactly
`avg_holding_days` rows later. Chosen without replacement and sorted, so
trades never overlap by construction — no separate overlap check needed
downstream.

### Wiring, in `ma_crossover_backtest.py`

1. Run the SMA strategy as today, but with real `COMMISSION_PER_TRADE` /
   `SLIPPAGE_BPS` constants (module-level, matching the existing
   `SHORT_WINDOW`/`LONG_WINDOW` pattern).
2. Compute `avg_holding_days` from the SMA trade log (`(Exit Date - Entry
   Date).mean()` in trading days) and `n_trades` from its row count.
3. Run `buy_and_hold_signal` and 20 seeded calls to `random_signal` through
   the same `run_backtest` with the same cost constants.
4. Print all three summaries in one block, cost parameters printed once at
   the top.

### Not doing

- No bid-ask-spread-based slippage model (Assumptions — deferred, no real
  spread data yet).
- No change to `run_backtest`'s control flow or trade-log schema — only new
  optional parameters and two new summary keys.
- No new file for baselines — they are signal generators like any other,
  per the module table.

---

## Test plan (Rule 5)

| Case | Test |
|---|---|
| Zero-cost regression | `run_backtest` with defaults on the real SMA crossover data reproduces today's exact numbers (8 trades, 50% win rate, ~$33 P&L) — pins SC-001. |
| Cost math | A small hand-built 2-trade log, non-zero commission and slippage, output matches a hand-computed expected value exactly. |
| Slippage direction | A winning trade becomes a loss under high enough `slippage_bps` — proves slippage is applied against the trade, not with it. |
| Buy-and-hold | Exactly one trade, entered row 1, exited at the final row's close; single-row frame doesn't crash (edge case). |
| Random-signal determinism | Same seed twice -> identical output. Different seeds -> different but individually valid (correct count, non-overlapping) output. |
| Random-signal edge cases | `n_trades=0` doesn't divide by zero; insufficient bars for even one trade raises rather than silently returning fewer trades than asked. |
| End-to-end | `ma_crossover_backtest.py` prints three cost-adjusted summaries with matching cost parameters. |

---

## Risks

| Risk | Mitigation |
|---|---|
| Commission-per-fill vs per-round-trip is a real modeling choice, not obviously "the" right answer | Documented explicitly in spec Assumptions; flagged for Camden in the PR description rather than silently picked. |
| 20 seeds may be too few for a stable mean/std | Documented as a default, not a hard requirement (spec Assumptions) — cheap to raise later if the variance looks unstable. |
| Random baseline's fixed `avg_holding_days` doesn't reflect the real strategy's holding-period *variance*, only its mean | Accepted for this spec — matching the full distribution is more baseline than Rule 4 asks for; flagged here so it isn't mistaken for an oversight later. |
