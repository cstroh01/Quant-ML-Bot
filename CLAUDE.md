# CLAUDE.md

Operating instructions for any agent working in this repository.

## Read this first

`.specify/memory/constitution.md` holds the non-negotiable rules. Read it before
writing code. `docs/SCOPE-V1.md` holds the project's scope, hard constraints,
and definition of done — read it before proposing work, and treat it as
authoritative wherever an older roadmap, README line, or spec status contradicts
it. It governs correctness (lookahead, cross-validation, costs,
baselines), process (tests, dependencies, merge gate), and boundaries
(execution code, version control). Nothing in this file overrides it.

The two rules most often violated by accident:

- **Point-in-time correctness.** For every row timestamped `t`, every value in
  that row must be computable using only data that existed at or before `t`.
  Judged per row, against that row's own timestamp.
- **Version control is human-owned.** Local agents never run Git, including
  read-only commands. Camden performs version control in GitKraken.
  Constitution Rule 10 defines the two narrow exceptions: the GitHub Actions
  lane and the cloud scheduled-session lane. See
  [Rule 10 and the two commit lanes](#rule-10-and-the-two-commit-lanes).

## Rule 10 and the two commit lanes

_Formerly titled "Rule 10 and the GitHub Actions lane"; the constitution's
2026-09-06 amendment note cites this section by that name._

Rule 10 says agents do not run `git`. PR #5 (spec 001) was pushed by an agent
anyway. That is recorded here rather than left as a silent precedent. The
constitution now names two lanes: the GitHub Actions lane (history below) and
the cloud scheduled-session lane (added 2026-10-01). Its text is the authority
for both.

**The Actions carve-out.** An agent invoked from a GitHub issue or PR comment, running
in the repository's GitHub Actions workflow, may run `git add`, `git commit`,
and `git push` — and only those three — to the branch it was invoked on.

**Everything still forbidden.** `merge`, `rebase`, `reset`, `checkout` of
another branch, force-push, tag, any push to `main`, and any history rewrite.
Outside the two lanes named in constitution Rule 10, agents run no Git at
all. The cloud scheduled-session lane may clone, fetch, create one new
`claude/*` branch per session, and add explicit paths, commit and non-force
push to that session's branch only. Its protected paths and all remaining
prohibitions are exactly those in the constitution. A local session, worktree
or terminal never gains either exception by setting an environment variable.
The carve-out is the lane, not the agent.

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
record of why the Actions carve-out exists and what it does and does not
grant; the constitution's own text is the current authority on the rule,
including the cloud scheduled-session lane.

## What this project is

A **quantitative research framework** built to industry standards on **free data
only**, shipped publicly as a finished, reproducible artifact. The machinery is
the deliverable: anti-lookahead discipline, purged/embargoed cross-validation,
false-discovery correction, realistic cost modeling, and an execution safety
layer.

It is built in dependency order — backtest -> paper trading -> small live
capital — and no phase is skipped because a backtest looked good. Mechanics are
proven with a simple baseline before a model is introduced, because a model on a
broken pipeline disguises bugs as bad predictions.

**Scope is fixed by `docs/SCOPE-V1.md`.** The short version:

- **Free data only.** No paid vendor, no paid API tier. Norgate and Sharadar are
  out of scope, not pending purchases; WRDS/CRSP/Compustat/FactSet are closed.
- **Two releases.** v1.0 is the complete research framework, publicly tagged.
  v1.1 adds the paper-trading loop and starts the capital gate's paper clock.
- **The capital gate is retained and unreached.** No real capital until every
  step of it passes. A deadline never relaxes a gate.
- **Limitations are disclosed, not solved.** A static survivor basket, free-tier
  corporate actions, no point-in-time fundamentals, daily bars only, modeled
  rather than calibrated costs. Every surface reporting a result says so.

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
| `scripts/portfolio_risk.py` | Position sizing, correlation overlap, loss-cap halts | Raw data, fills, P&L, broker calls |
| `scripts/live_safety_gate.py` | Independent pre-order safety checks, durable halts, reservations, kill switch | Signal generation, sizing, fills, P&L, broker credentials or network |
| `scripts/metrics.py` | Performance and significance statistics, HAC standard errors | Data fetching, signals, fills, sizing |
| `scripts/selection_bias.py` | CSCV / PBO and deflated-Sharpe selection-bias math | Where a trial came from, execution, sizing |
| `scripts/trial_registry.py`, `scripts/trial_runner.py` | Append-only hash-chained trial ledger and instrumented run recording | Strategy logic, fills, P&L accounting |
| `scripts/order_gateway.py` | Submitting orders through the safety gate | Signal generation, model internals, broker credentials |
| `scripts/plotting.py` | Headless figures | Everything else |
| `scripts/mode_config.py` | Immutable PAPER/LIVE profiles, bot budget, namespaces, arming state (spec 051) | Signals, broker network, credential values |
| `scripts/asset_registry.py` | Dated instrument identity, research and executable eligibility with reasons (spec 052) | Signals, fills, credentials, network |
| `scripts/model_registry.py` | Model artifact manifests, champion/challenger records, promotion and rollback (spec 053) | Order placement, broker calls, statistics computation |
| `scripts/holdings_import.py` | Read-only external holdings normalization and staleness (spec 054) | Order intents, credentials, network |
| `scripts/ops_runtime.py` | Due-run calendar, intent leases, run summaries and alert payloads (spec 055) | Signals, sizing, broker credentials |
| `scripts/data_sources.py` | Free-source adapters' manifests and cross-source checks (spec 056) | Signals, fills, P&L |
| `scripts/cost_model.py` | Spread (EDGE) and square-root impact cost estimates per fill (spec 046) | Signals, sizing, P&L accounting, downloads, the ledger |
| `scripts/corporate_actions.py` | Cross-source corporate-action and close reconciliation for the unadjusted cache (spec 035) | Signals, fills, P&L, network |
| `scripts/portfolio_backtest.py` | Multi-asset weights → next-open fills → portfolio P&L (spec 058) | How weights or signals were produced, downloads |
| `scripts/disclosure.py` | Limitations register text, provenance/source stamps and Rule 11/15/16 labels with an injected UTC clock (spec 038) | Signals, fills, sizing, P&L, network |
| `exec/fidelity_live.py` | LIVE order adapter for Fidelity, preview-default, Rule 7 reviewed lane only (spec 057) | Signals, sizing, anything outside order I/O |

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

**Tests.** From the repository root, install with
`python -m pip install -r requirements.txt -r requirements-dev.txt`, then run
the entire Python suite with **`python -m pytest tests`**. Pytest is the single
runner for both unittest classes and parametrized function tests. No network
access. Test-only libraries belong in `requirements-dev.txt`, never runtime
`requirements.txt`. A test that requires a download is not a test.

Python test modules (`test*.py` or `*_test.py`) belong under `tests/`, including
spec acceptance tests. Helpers must not use test-module names; mutation drivers
belong under `tests/mutation/` and invoke pytest. The full-suite collection
guards reject misplaced test files and test modules with zero collected cases,
including files ignored by collection configuration. Dependency environments,
third-party packages, and tool caches are excluded from the repository scan.
Focused pytest selections are useful during development; the full command above
is the required verification gate. Older spec plans and audit logs record the
runner used at that time; this section defines the current command.

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
