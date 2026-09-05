# CLAUDE.md

Operating instructions for any agent working in this repository.

## Read this first

`.specify/memory/constitution.md` holds the non-negotiable rules. Read it before
writing code. It governs correctness (lookahead, cross-validation, costs,
baselines), process (tests, dependencies, merge gate), and boundaries
(execution code, version control). Nothing in this file overrides it.

The two rules most often violated by accident:

- **Point-in-time correctness.** For every row timestamped `t`, every value in
  that row must be computable using only data that existed at or before `t`.
  Judged per row, against that row's own timestamp.
- **Version control is human-owned.** Never run `git`. Write files, explain
  changes. Camden commits.

## What this project is

An ML-driven trading system built in dependency order: backtest → paper trading
→ small live capital. No phase is skipped because a backtest looked good.

The build order is deliberate. Mechanics are proven with a simple baseline
before a model is introduced, because a model on a broken pipeline disguises
bugs as bad predictions.

## Layout

```
.specify/memory/constitution.md   Non-negotiable rules
.specify/specs/                   Numbered specs — the unit of work
docs/PROJECT_CONTEXT.md           Roadmap and current state
scripts/                          Modules and runnable entry points
tests/                            Regression tests
data/cache/                       Generated output (gitignored)
```

### Module responsibilities

| Module | Owns | Must not know about |
|---|---|---|
| `scripts/data.py` | Download, cache, adjust OHLCV | Signals, positions, P&L |
| `scripts/signals.py` | When to trade, and nothing else | Fills, sizing, accounting |
| `scripts/backtest_harness.py` | Fills, trades, P&L | How a signal was produced |
| `scripts/plotting.py` | Headless figures | Everything else |

These boundaries are load-bearing. They are what let a model replace a rule
later without touching execution.

## How work arrives

Work is defined by a **numbered spec committed to the repo**, not by a prompt in
a chat window. Specs live in `.specify/specs/NNN-short-name/`.

An agent picks up a spec, implements it, and opens a PR that references it. If a
task cannot be written as a spec, it is not ready to be delegated.

Do not ask for clarification in a chat and proceed on the answer — the answer
belongs in the spec, where the next agent can also read it.

## Conventions

**Python.** Standard library first. Type hints on public functions. Docstrings
that state what a function guarantees, not what its lines do.

**Determinism.** Every stochastic operation takes an explicit seed parameter.
No implicit global random state. A result that cannot be reproduced is not a
result.

**Timestamps.** Timezone-aware throughout. Never compare a naive to an aware
timestamp. Resampling and joins state their alignment convention explicitly.

**Data.** Everything under `data/cache/` is regenerable output and gitignored.
Never commit market data. Never read from a path outside the repo root.

**Tests.** `python -m unittest discover -s tests`. No network access, no test
dependencies. A test that requires a download is not a test.

**Secrets.** Gitignored `.env` only. Never in code, never in a spec, never in a
log line, never echoed into agent context.

## Pull request requirements

Every PR description states:

1. Which spec it implements.
2. What changed and why it is correct.
3. For any reported metric: fold count, purge length, embargo length,
   commission, and slippage. A metric without these is not reportable.
4. For any strategy change: results beside a buy-and-hold baseline and a
   random-signal baseline over the identical period with identical costs.
5. For any new dependency: one line on what it does that existing dependencies
   cannot.

## What to flag rather than fix

Raise these; do not resolve them unilaterally:

- A spec whose requirements conflict with the constitution.
- A result that looks too good — an unusually high Sharpe is a bug report until
  proven otherwise.
- A change that would cross the module boundaries above.
- Anything touching `exec/` or broker credentials.
- A PR growing large enough that reviewing it line by line is impractical. Split
  it. Reviewability is a hard constraint, not a preference.
