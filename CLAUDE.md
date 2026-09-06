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
  changes. Camden commits. One narrow, recorded carve-out exists — see
  [Rule 10 and the GitHub Actions lane](#rule-10-and-the-github-actions-lane).

## Rule 10 and the GitHub Actions lane

Rule 10 says agents do not run `git`. PR #5 (spec 001) was pushed by an agent
anyway. That is recorded here rather than left as a silent precedent.

**The carve-out.** An agent invoked from a GitHub issue or PR comment, running
in the repository's GitHub Actions workflow, may run `git add`, `git commit`,
and `git push` — and only those three — to the branch it was invoked on.

**Everything still forbidden.** `merge`, `rebase`, `reset`, `checkout` of
another branch, force-push, tag, any push to `main`, and any history rewrite.
An agent working outside the Actions lane — a local session, a worktree, a
terminal — runs no `git` at all. The carve-out is the lane, not the agent.

**Why it does not defeat the rule.** Rule 10 is a comprehension rule, not a
safety rule: it exists so changes do not become permanent faster than Camden
can follow them. In this lane they do not. The agent's push lands on a feature
branch inside an open PR; it cannot merge, and Rule 9 still gates the merge on
Camden being able to explain the change. What the agent gains is the ability
to put a commit where the review already is. What it does not gain is the
ability to make anything permanent.

**Status.** Amended into the constitution directly, 2026-09-06, per
Camden's confirmation — Rule 10 now states this exception itself, in a
dedicated commit to `.specify/memory/constitution.md` that changes nothing
else, per that file's own Amendment clause. This section is kept as the
record of why the carve-out exists and what it does and does not grant; the
constitution's own text is the current authority on the rule.

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

**Timestamps.** Never compare a naive to an aware timestamp. Resampling and
joins state their alignment convention explicitly. Which of the two kinds a
value is decides its representation, and the split is project-wide:

- **An instant is timezone-aware.** Anything naming a moment — an intraday
  bar, an order timestamp, a fill, a log line — carries a zone. No exceptions.
- **A session label is timezone-naive, midnight-normalized.** A daily bar does
  not name a moment; it names a trading day. Attaching a zone forces a choice
  of *which* moment in the session the label means, and every choice puts the
  same bar on a different calendar day for some reader: `2024-03-08 00:00
  America/New_York` is `2024-03-08 05:00Z`, while `2024-03-08 00:00 UTC` read
  in Eastern is *March 7th*. That is a silent one-bar shift, which is the
  failure Rule 5 exists to catch.

A session label crossing into instant-space — feeding an order, a broker call,
or an intraday join — is localized to `America/New_York` explicitly at that
boundary, by the code doing the crossing. It is never localized implicitly,
and a session label is never localized to UTC.

This settles research R3 in `.specify/specs/001-data-ingestion/`, which raised
it as a module-local question. It is answered here because the answer is not
module-local: `scripts/data.py` applies it in `_normalize_dates`, and every
module downstream inherits it.

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
