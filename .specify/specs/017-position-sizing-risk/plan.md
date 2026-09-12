# Implementation Plan: Position Sizing and Portfolio Risk Layer

**Branch**: `017-position-sizing-risk` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `.specify/specs/017-position-sizing-risk/spec.md`

## Summary

A new risk layer, `scripts/portfolio_risk.py`, between signal and execution.

- **Sizing (US1):** volatility targeting only —
  `confidence × target_volatility / realized_volatility`, capped per name.
  No Kelly path (research R1).
- **Correlation (US2):** each active weight divided by its *overlap*, the sum
  of its non-negative correlations with every active name. A perfectly
  correlated cluster becomes one bet; uncorrelated names are untouched
  (research R3).
- **Loss caps (US3):** a streaming `LossCapGuard` consumes equity at each
  close; a daily breach halts that session's decision, a weekly loss or
  drawdown breach latches through the ISO week (research R5). A halt clamps
  each target to `min(target, current)` (research R6).

One composing function, `target_weights`, runs the steps in a fixed order
and returns every intermediate step as a column. No harness wiring, no P&L.

## Technical Context

**Language/Version**: Python 3.13 locally (`venv`), 3.12 in CI (`test.yml`).
No syntax newer than 3.10; `from __future__ import annotations` as in
`ml_signal.py`.

**Primary Dependencies**: numpy, pandas (existing). Standard library
`dataclasses`. Project module `constants` (importless by design).

**Storage**: N/A — in-memory only.

**Testing**: `unittest` via `python -m unittest discover -s tests`. No
network, no test dependencies.

**Target Platform**: Local research workstation and GitHub Actions
(`ubuntu-latest`).

**Project Type**: Library module inside a research scripts directory.

**Performance Goals**: One `target_weights` call on a 2,500-session,
5-ticker panel well under 50 ms (it truncates to the trailing window before
estimating). A full-history loop is seconds, not minutes.

**Constraints**: Point-in-time at every row (Rule 1); session labels naive
and midnight-normalized (CLAUDE.md); no forbidden imports (FR-013).

**Scale/Scope**: 5 tickers in practice, any `N` supported; ~2,500 sessions
per ticker in the ten-year cache.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | Bearing on this plan | Status |
|---|---|---|
| 1 — Point-in-time | Volatility, correlation, and the halt state at `t` read only data at or before `t`. `target_weights` and `trailing_correlation` truncate at the session *before* computing, so a leak would need code that re-reads the untruncated frame. Each ships with a perturb-the-future, bit-identical test plus a control that perturbing `t` itself does change the result. | PASS |
| 2 — Purged walk-forward CV | No model is fit and nothing is cross-validated. | N/A |
| 3 — Costs | No return, Sharpe, or P&L is computed or reported. The turnover consequence of the window choice is recorded (research R2) for the spec that does run costs. | N/A |
| 4 — Baselines | No strategy is proposed or modified. The first spec to run this layer through a costed backtest owes both baselines. | N/A |
| 5 — Time tests | Every time-indexed function gets off-by-one, boundary (first row, window edge, week edge, ISO year boundary), and gap (missing bar, holiday week, missing week) tests. | PASS |
| 6 — Dependencies | None added. | PASS |
| 7 — Execution | Nothing places an order; no `exec/`, no credentials. | PASS |
| 8 — Layer separation | New layer between signal and execution. Consumes the *shape* of two accounting outputs (equity, holdings) and one signal output (confidence); imports none of those modules. Enforced by an AST import-set test. The spec's Background states why the layer reads accounting outputs, as Rule 8 requires. | PASS — boundary statement in spec |
| 9 — Merge gate | Each step is a closed-form line: a ratio, a `min`, a division by a sum, a scale, a `min`. The guard is a six-field state machine written out in `data-model.md`. | PASS |
| 10 — Version control | No `git`. Camden commits. | PASS |

**Post-design re-check (after Phase 1):** unchanged. The contract adds no
import beyond `dataclasses` and `constants`, and no function returns a
trade, a fill, or P&L.

**One flag, raised rather than resolved.** The run request cites "the
constitution's Rule on adversarial coverage." The constitution has no rule by
that name. The nearest are Rule 1's enforcement clause ("ships with a test
that would fail if the computation could see past `t`") and Rule 5. The
mutation check here follows the precedent of specs 012 and 013, which made it
a success criterion. Recorded for Camden; the constitution is not edited.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/017-position-sizing-risk/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R8
├── data-model.md
├── quickstart.md
├── contracts/
│   └── portfolio-risk-module.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
scripts/
└── portfolio_risk.py        # new — this spec's only production file

tests/
└── test_portfolio_risk.py   # new — synthetic, network-free
```

**Structure Decision**: One new module under `scripts/`, beside
`ml_signal.py` and `metrics.py`, matching the repo's flat layout. Explicitly
**not** touched: `backtest_harness.py`, `metrics.py`, `signals.py`,
`ml_signal.py`, `data.py`, `multi_ticker_comparison.py`, `constants.py`.

## Design

### Module layout, top to bottom

```
RiskConfig, RECOMMENDED_CONFIG          validation (FR-016)
_validate_sessions, _aligned            shared guards (FR-015, label alignment)
log_returns, realized_volatility,       estimation (FR-003, FR-004)
  trailing_correlation
volatility_target_weights               US1 (FR-001)
position_overlap,                       US2 (FR-005)
  correlation_adjusted_weights
apply_gross_cap                         FR-007
apply_entry_halt                        FR-010
target_weights                          composition (FR-006, FR-012)
LossCapStatus, LossCapGuard,            US3 (FR-008, FR-009, FR-011)
  loss_cap_history
```

### `target_weights`, in call order

```
history     = closes.loc[:session]                       # truncate first
vol         = realized_volatility(history.iloc[-(vw+1):], window=vw).iloc[-1]
corr        = trailing_correlation(history, session, window=cw)
sizeable    = vol finite & vol > 0 & diag(corr) finite
standalone  = volatility_target_weights(confidence, vol.where(sizeable), ...)
capped      = min(standalone, max_weight)                 # BEFORE overlap
overlap     = position_overlap(capped, corr)
adjusted    = correlation_adjusted_weights(capped, corr)
scaled      = apply_gross_cap(adjusted, max_gross=...)
target      = apply_entry_halt(scaled, current, halted=entries_halted)
```

Why `diag(corr)` is part of "sizeable": when `correlation_window >
volatility_window`, a name can have a volatility before it has a full
correlation window. Leaving it active would make `position_overlap` see an
undefined correlation and raise mid-history. Treating it as unsizeable is
the same rule as warm-up: no full window, no position.

### Overlap arithmetic

`ρ_ii` is taken as exactly `1.0`, and off-diagonal values are clipped to
`[0, 1]`, before summing. Two reasons: a pandas correlation diagonal can come
back as `0.9999999999999998`, which would make an isolated name's overlap
fall below 1 and *increase* its weight by one ulp — breaking FR-005's "never
increases" on a technicality; and self-overlap is 1 by definition, not by
estimate.

### Guard

Exactly the transition in `data-model.md`. `observe` validates everything
before mutating any state, so a rejected observation leaves the guard as it
was. `loss_cap_history` constructs one fresh guard and calls `observe` per
row — no second implementation (research R7).

### Tests — what each class pins

| Class | Pins |
|---|---|
| `SessionIndexValidationTests` | FR-015: aware, non-midnight, repeated, decreasing, non-datetime index all raise |
| `LogReturnTests` | row 0, gap rows, non-positive close |
| `RealizedVolatilityTests` | independent recomputation; first valid row is exactly `window`; gap re-warm; future perturbation bit-identical + control |
| `TrailingCorrelationTests` | vs `numpy.corrcoef` on the slice; short history; gap; future perturbation |
| `VolatilityTargetSizingTests` | formula, halving, zero/missing confidence and volatility, range checks, label alignment |
| `CorrelationAdjustmentTests` | `ρ = 1` halves, `ρ = 0` unchanged, `ρ < 0` unchanged, inactive not counted, never increases (seeded random matrices), diagonal rounding |
| `ExAnteVolatilityTests` | SC-005 formula at `ρ ∈ {0, 0.3, 0.6, 1}` |
| `CapOrderingTests` | US2 #6: three correlated names above the cap combine to one cap |
| `GrossCapTests` | untouched below cap; proportional above; sum equals cap |
| `EntryHaltTests` | open blocked, add blocked, reduce and exit allowed |
| `LossCapGuardTests` | daily one-session halt; inclusive boundary at an exactly representable value, and one ulp inside; weekly latch; weekly drawdown; Monday gap anchor; first session; holiday week; ISO year boundary; missing week; ordering and equity validation |
| `LossCapHistoryTests` | streaming == history; future perturbation; control |
| `RiskConfigValidationTests` | FR-016 domain edges; recommended values equal the spec's table |
| `TargetWeightsCompositionTests` | per-step columns; future perturbation bit-identical; warm-up flat; all flat; label order |
| `FiveTickerUniverseTests` | SC-004 on `multi_ticker_comparison.TICKER_UNIVERSE`, built from orthogonal return patterns so the correlations are exact |
| `AutomaticHaltIntegrationTests` | a crash in a synthetic loop halts entries with no manual flag; no target exceeds current while halted; entries resume the next week |
| `ModuleBoundaryTests`, `NoKellyPathTests` | FR-013 import set by AST; FR-002 no Kelly identifier |

### Mutation check (SC-008)

Twenty-one mutants — the twelve SC-008 defects (fourteen mutants, because
the strict-boundary defect is run once per cap) plus seven extras — each a
textual replacement applied to a **copy** of the module in the scratchpad. Each runs
`tests/test_portfolio_risk.py` in a fresh interpreter with the mutant's
directory ahead of `scripts/` on `sys.path`. An unmutated copy runs first as
the control and must pass. The repo file is hashed before and after; the
hashes must match. No `git` (Rule 10).

## Complexity Tracking

No constitution violation to justify.

**Size, flagged per CLAUDE.md — revised after implementation.** This section
first estimated ~450 module lines and ~900 test lines, "comparable to spec
012." That estimate was wrong. Actual: **745 module lines, 1,391 test
lines** — about 2.6× spec 012's module (287) and 1.7× its tests (802). Much
of the module is docstrings stating guarantees, but it is still more than one
sitting of line-by-line review.

Not split unilaterally (CLAUDE.md: raise, don't resolve). If Camden wants a
split, the seams already exist, one per story:

1. Configuration, validation, estimation, sizing, correlation, gross cap.
2. `apply_entry_halt`, `LossCapGuard`, `loss_cap_history`.
3. `target_weights`, with the composition and integration tests.

Otherwise, read it in that same order, one pass per group.
