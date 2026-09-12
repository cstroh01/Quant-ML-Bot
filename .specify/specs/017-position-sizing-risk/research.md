# Research — 017 Position Sizing and Portfolio Risk Layer

Phase 0 output. Each decision: what was chosen, why, what else was
considered. The five clarifications in `spec.md` are the source of R1, R2,
R4, R5 and R6; this file adds the alternatives that were rejected, which the
spec only summarizes.

---

## R1 — Sizing rule: volatility targeting, not Kelly

**Decision.** `standalone = confidence × target_volatility / volatility`.
No Kelly path.

**Rationale.** Both rules have the same *shape* — size proportional to edge,
inversely proportional to risk. They differ in what they need from the
signal:

| | Needs | This repo has it? |
|---|---|---|
| Volatility targeting | `σ` | Yes — clusters, estimable point-in-time |
| Kelly | `μ` (expected return) *and* `σ` | No validated `μ` anywhere |

The size of a Kelly bet moves one-for-one with the error in `μ`. Worked on
this repo's numbers (binary Kelly, `f* = (2p − 1)/σ_daily`):

| Input | Value | Source |
|---|---|---|
| `p` | 0.5299 | spec 014, `logistic`/classification on AAPL |
| `σ_daily` | 0.0181 | spec 012 Background |
| full Kelly | **3.30×** the book | |
| half Kelly | 1.65× | |
| quarter Kelly | 0.83× | |

A one-ticker screening result that spec 005 showed does not beat a
majority-class baseline would set 165% leverage at half Kelly. That is the
"too good" failure CLAUDE.md tells agents to distrust, relocated from the
Sharpe ratio into the position size.

The continuous (Merton) form is worse for the regression path. With a
log-return forecast `m`, the arithmetic drift is `m + σ²/2`, so
`f* = (m − r)/σ² + 1/2`: at zero predicted edge Kelly still holds half the
book. "Sized off confidence" and "long 50% with no signal" cannot both hold.

**Alternatives considered.**

- *Fractional Kelly with a hard ceiling (e.g. `k ≤ 0.5`).* Rejected for now,
  not forever. The ceiling would make "never full Kelly" enforceable, but a
  ceiling on a multiplier of an uncalibrated `μ` bounds nothing real. Revisit
  in a spec that follows 013's calibrated evidence.
- *Kelly as a cap on the vol-target weight.* Needs `μ`; same objection.

---

## R2 — Volatility estimator and window

**Decision.** Realized volatility: sample standard deviation (`ddof=1`) of
the last 63 daily log returns ending at `t`, times `sqrt(252)`. Missing
unless all 63 returns exist. Correlation over the same trailing 63 returns.
Both windows are required parameters.

**Rationale.**

- Log returns, because `return_stats.daily_log_returns` and
  `features.Rolling_Volatility` already use them; two volatility conventions
  in one repo would make two numbers silently incomparable (the argument
  `constants.py` makes for sharing `TRADING_DAYS_PER_YEAR`).
- `sqrt(252)` via `constants.TRADING_DAYS_PER_YEAR`, imported, not restated.
- 63 sessions (one quarter). Shorter reacts faster but re-sizes on noise, and
  every re-size is turnover Rule 3 charges for. `docs/PROJECT_CONTEXT.md`
  shows MSFT's 21-day vol ranging 10%–58% — a 21-day window would move a
  position size by more than 5× on estimation alone.
- Correlation sampling error at `n = 63`, `ρ = 0.6`: `(1 − ρ²)/sqrt(n) ≈
  0.08`. A 252-day window would halve that but average away the sell-off
  correlation spike this adjustment exists for.
- "All returns exist, or missing" — no partial windows. A window with a hole
  is a smaller sample pretending to be a full one.

**Alternatives considered.**

- *EWMA (RiskMetrics, `λ = 0.94`).* A reasonable forecast. Not needed to meet
  the spec, and sizing takes volatility as an input, so it drops in later
  without touching sizing.
- *Stitching the return across a missing bar.* Rejected: a two-day return
  labelled as one day inflates variance and is a Rule 5 gap-case bug.

---

## R3 — Correlation-aware allocation: divide by overlap

**Decision.** For each active position `i`:

```
overlap_i  = Σ_{j active} max(ρ_ij, 0)      (ρ_ii ≡ 1, so overlap_i ≥ 1)
adjusted_i = capped_i / overlap_i
```

**Rationale.** It encodes the requirement's own wording — "correlated names
don't act as one concentrated bet" — in closed form:

| Case | Overlap | Effect |
|---|---|---|
| `k` names, `ρ = 1` | `k` | each `1/k` — the cluster is one bet |
| `k` names, `ρ = 0` | `1` | unchanged |
| `ρ < 0` | clipped to 0 | unchanged — no extra size for a hedge |
| a flat name | not counted | cannot shrink anyone |

For `k` equal positions (size `x`, vol `σ`) at common `ρ ≥ 0`:

```
book variance = (x/n)² σ² [k + k(k−1)ρ]      with n = 1 + (k−1)ρ
              = x² σ² k / n
book vol      = xσ · sqrt(k / (1 + (k−1)ρ))
```

`k/(1 + (k−1)ρ)` is the standard *effective number of independent bets* for
an equicorrelated set. So the book carries exactly one bet's volatility per
effective independent bet — which is a checkable number (SC-005), not a
slogan.

**Alternatives considered.**

| Method | Why not |
|---|---|
| Scale the whole book to a portfolio vol target using `Σ` | One scalar for every name: an uncorrelated name is shrunk as hard as the cluster, and the cluster keeps its share of the risk. |
| Mean-variance, `w ∝ Σ⁻¹μ` | Needs `μ` (R1's objection), and `Σ⁻¹` at `ρ ≈ 0.7` among five names amplifies estimation error; long-only clipping then discards the optimality it was chosen for. |
| Equal risk contribution | No closed form beyond two assets; needs an iterative solver. Correct, but Rule 9 asks Camden to explain the mechanism, and "the optimizer converged" is not an explanation. |
| Hierarchical risk parity | Designed for large universes; five names do not need a dendrogram. |

---

## R4 — Order of steps

**Decision.** standalone → per-name cap → overlap division → gross cap →
halt.

**Rationale.** Cap before overlap, or the cap undoes the correlation step.
Three perfectly correlated names at standalone 1.0 with a 0.25 cap:

| Order | Per name | Combined |
|---|---|---|
| cap, then divide by 3 | 0.083 | **0.25 — one bet** |
| divide by 3, then cap | 0.25 | 0.75 — three bets |

Overlap division can only shrink a weight (`overlap ≥ 1`), so the per-name
cap still holds after it. Gross cap after overlap, so diversification credit
is granted before the book-level limit is checked. Halt last, because it is
the only step allowed the final word on added risk.

---

## R5 — Loss caps: calendar week, latched, inclusive

**Decision.**

- Daily return against the previous observed close; weekly return against
  the last close of the previous ISO week; weekly drawdown against the week's
  running high (anchor included).
- Breach when the return is `≤ −limit`.
- Daily breach halts that session's decision. Weekly breach latches through
  the last session of that ISO week.

**Rationale.** See spec Clarifications Q2 and Q5. Two further points:

- **ISO week, not `(year, weekofyear)` naively.** `2025-12-29` (Mon) through
  `2026-01-02` (Fri) is ISO week `(2026, 1)`. Grouping by calendar year would
  split that week in two and reset the anchor on 1 January.
- **Anchor on the prior week's last close, not this week's first close.** A
  Monday gap-down happens between those two numbers. Anchoring on Monday's
  close would put the gap in neither week.

**Alternatives considered.** A rolling 5-session window (never resets; no
fixed resume point). An un-latched weekly halt (switches off on a one-day
bounce). A strict boundary (a book can sit exactly at its cap and keep
adding).

---

## R6 — What a halt blocks

**Decision.** `target = min(target, current)` per ticker, with `current` the
holding accounting reports at that close.

**Rationale.** Spec Clarifications Q3. Blocks opening and adding; allows
reducing and exiting.

**Alternatives considered.**

- *Block only opens from flat.* Leaves the "scale a 0.1% stub to the cap"
  loophole.
- *Freeze all positions.* A halt that traps the book in its losers adds risk.
- *Compare against the previous target instead of the drifted holding.*
  After a price drop, returning to the old target is buying.
- *Force-liquidate on breach.* Not requested, and it converts a risk control
  into a trading decision with its own costs. Recorded as an open question.

---

## R7 — API shape: a streaming guard, and a whole-series view built from it

**Decision.** `LossCapGuard.observe(session, equity)` holds the state;
`loss_cap_history(equity, …)` runs that same guard over a series.

**Rationale.** The halt at `t` feeds the positions that produce equity at
`t+1`, so any real use — a weight-based backtest, paper trading, a broker
loop — is a loop, and a loop needs a streaming object. A separate vectorized
implementation would be a second copy of the latch logic that could drift
from the first. Building the whole-series view by running the guard makes
"streaming and batch agree" true by construction, and the test only has to
pin it.

**Alternatives considered.** A pure vectorized function over the full equity
series. It is the natural pandas shape, but it cannot be used inside the
feedback loop without recomputing the whole history each bar, and it would
be the second implementation R7 exists to avoid.

---

## R8 — No harness wiring in this spec

**Decision.** No change to `backtest_harness.py`, `metrics.py`, or any
runner.

**Rationale.** `run_backtest` is one share, one instrument, and has no
weights. Making it multi-asset and weight-based is an execution-layer change
(Rule 8), and it would bring Rule 3/4 obligations for any number it
produced. Spec 012 set the precedent: ship the rule and its tests, wire it
in the spec that owns the runner.
