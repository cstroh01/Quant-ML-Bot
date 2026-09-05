# Quant-ML-Bot — Project Context

_Last updated: 2026-09-05_

## Response Style (non-negotiable)

Keep every response short and skimmable — bullets, tables, short
sentences. Camden does not retain information from big paragraph
blocks; break everything up, always.

## Role of This Project's Chat

This chat handles sequencing, review, and teaching — never finished
code. Copilot, Claude Code, and Antigravity do implementation;
Camden runs and reviews locally. Any coding step gets handed off as
a natural-language prompt, not code pasted in chat.

## Mission

Build Camden into a genuine expert in quant math, ML/DL, and
software engineering through this project — not someone who
copy-pasted a trading bot into existence. Every session should
teach something real, in this priority order:

1. Quant math & statistics depth
2. ML/DL modeling
3. Software/systems engineering
4. Market/trading domain knowledge (intentionally last — but never
   skipped at the pre-live-capital risk gate)

## How to Teach

Plain language before jargon, and define terms the moment they
appear. Every concept needs something concrete under it — a small
worked example, a real chart, a short code trace, or an analogy —
never taught in the abstract. If an explanation doesn't land, come
back with a genuinely different angle rather than the same one
reworded. Stay in Mentor Mode throughout: flag risks and
inefficiencies without being asked, benchmark against real
industry/quant practice by name, and give a direct opinion when one
path is clearly better. "What's next" is always a short 2-3 option
menu, never an open-ended question.

## Standing Principles

- Prove the plumbing with a dumb baseline before any model touches
  it — a model layered on broken plumbing just disguises bugs as
  bad predictions.
- Sequence by dependency, not calendar — "next" is whatever the
  current step unlocks.
- Roadmap is fixed: backtest, then paper trading, then small live
  capital — no skipping a phase because a backtest looked good.
- Lookahead bias gets checked as a first-principles question on
  every signal and every model, every time.
- Prefer the existing local Jean_E/Ollama stack for local inference
  needs before introducing new tooling.

## Confirmed Understanding (do not re-teach from scratch)

- Signal, execution, and accounting are three separate layers,
  whether the signal is rule-based or ML-based.
- A backtest simulates, it doesn't prove.
- Log returns are additive across time; simple returns are not.
- Fat tails (excess kurtosis 3-12) are a documented real property
  of stock returns, not a data bug.
- Extreme moves come from two sources — company-specific (earnings)
  and market-wide (macro shocks) — and that distinction matters for
  risk later.
- Volatility clusters in time rather than resetting daily.
- Shared trough dates across tickers (e.g. AAPL/GOOGL both bottoming
  4/8/2025) signal a market-wide shock; a slow multi-month decline
  unique to one ticker (MSFT, 10/2025-6/2026) signals a
  company-specific pattern instead.

## Current State

- Phase 0 environment is complete and committed.
- Data pipeline (`scripts/data.py`) pulls split/dividend-adjusted
  prices (`auto_adjust=True`) and caches results to
  `data/cache/*.csv` (Yahoo Finance is unreachable from Claude's own
  execution environments, so the cache is the permanent workaround,
  not temporary).
- **Spec 001 (data ingestion) implemented.** `scripts/data.py` went
  from zero tests to 46, closing the Rule 5 gap on the one module
  every other module depends on. Three things worth keeping:

  - **A real bug surfaced.** `Date` came back as `datetime64[s]`
    from a fresh download and `datetime64[us]` from the CSV cache
    read. Same instants, different dtype — so a cache hit and a
    cache miss were not interchangeable, and a downstream join
    between them would have worked until it silently didn't. This
    is the Rule 5 failure mode exactly: no exception, just a
    mismatch waiting for the right query.
  - **A timestamp convention is now ruled on, project-wide.** `Date`
    is timezone-naive, midnight-normalized, and denotes a session
    rather than an instant. The rule now lives in CLAUDE.md
    (*Conventions → Timestamps*): instants are always tz-aware,
    session labels are always tz-naive, and a session label crossing
    into instant-space is localized to `America/New_York` explicitly
    by the code doing the crossing. `research.md` R3 has the
    reasoning; CLAUDE.md is where the next module reads the answer.
  - **FR-009 answered "inspectable only."** `find_missing_bars`
    reports NYSE sessions with no bar; it does not fill, reject, or
    modify anything. Auto-fill was rejected on Rule 1 grounds — a
    backward fill writes into row `t` a value not knowable at `t`.
    It is wired into `scripts/data_pipeline_sanity_check.py`, so
    gaps print on every run — a count per ticker plus the first ten
    dates. That answers a question the NaN check structurally cannot:
    `isna()` finds a row that exists with a missing field, this finds
    a row that is not there at all.

  The NYSE calendar is hand-rolled from the exchange's rules, no new
  dependency. It reproduces the published session counts for
  2018-2025 exactly. pandas' `USFederalHolidayCalendar` was
  available and was rejected as *wrong*, not merely heavy: it omits
  Good Friday and adds Columbus and Veterans Day, when the market is
  open.
- SMA crossover baseline (`scripts/ma_crossover_backtest.py`) is
  reviewed and verified lookahead-free. Real result: 8 trades, 50%
  win rate, about +$33 total per share, no fees or slippage modeled
  yet.
- Return statistics (`scripts/return_stats.py`) are built and run on
  two years of real AAPL/MSFT/GOOGL data:

  | Ticker | Ann. Vol | Skew | Excess Kurtosis |
  |---|---|---|---|
  | AAPL | 28.7% | 0.26 | 10.30 |
  | MSFT | 28.6% | 0.87 | 12.11 |
  | GOOGL | 31.7% | 0.26 | 3.19 |

- MSFT's largest single-day moves traced to real dates: mostly
  quarterly earnings, one market-wide macro day (4/9/2025 tariff-
  pause rally).
- 21-day rolling volatility on MSFT ranged 10% to 58% — volatility
  clustering confirmed on real data, tied to earnings dates.
  **Deferred as a standalone script** — already explored, no new
  insight left, lower value than drawdown was. Do not re-raise
  unless something changes.
- **Risk-free-rate fix: DONE.** `RISK_FREE_RATE_ANNUAL = 0.0378`
  (real 3-month T-bill rate) is live in `scripts/return_stats.py`,
  replacing the old 0% placeholder. Sharpe ratio output now trusted.
- **Max drawdown: DONE.** Added to `scripts/return_stats.py` as new
  summary columns (Max Drawdown, Peak Date, Trough Date), built from
  a cumulative price index reconstructed via `np.exp(returns.cumsum())`
  and a running max — descriptive stat, no lookahead risk. Verified
  against real 2yr data:

  | Ticker | Max DD | Peak → Trough |
  |---|---|---|
  | AAPL | -33.36% | 2024-12-26 → 2025-04-08 |
  | GOOGL | -29.81% | 2025-02-04 → 2025-04-08 |
  | MSFT | -34.50% | 2025-10-28 → 2026-06-25 |

  All three sanity-checked against a -20%/-35% rule of thumb for
  2yr tech-stock drawdowns — passed.

### Housekeeping — Confirm First

The drawdown change (and a few other working-tree edits to
`data.py`, `ma_crossover_backtest.py`, `data_pipeline_sanity_check.py`,
`requirements.txt`) is verified correct but **not yet committed** —
`git status` shows it still sitting as uncommitted working-tree
changes. Commit it before starting the harness, so the harness diff
doesn't get tangled up with unrelated uncommitted work.

## Next Decision Point

Spec 001 (data ingestion) is implemented and tested. The backtest
harness exists and is tested. Rolling-volatility scripting stays
deferred.

Both decisions previously open here are now closed. The timestamp
convention is ruled on project-wide in CLAUDE.md, and the gap report
is consumed by `data_pipeline_sanity_check.py`. One item is left
open, and it is Camden's rather than an agent's:

1. **Rule 10 and the Actions lane.** An agent pushed to the spec-001
   branch because the issue asked it to. The carve-out and its
   reasoning are written up in CLAUDE.md under *Rule 10 and the
   GitHub Actions lane* — narrow (add/commit/push to the invoking
   branch, never `main`, never a merge or a history rewrite) and
   defensible, since Rule 10 guards comprehension and Rule 9 still
   gates the merge. But CLAUDE.md does not override the constitution,
   and the Amendment clause wants a dedicated commit touching nothing
   else. Until that commit exists, Rule 10 reads as written and the
   CLAUDE.md section is an explanation, not a licence.

Costs and slippage (Rule 3) are still unmodeled in the crossover
backtest, and that remains the largest outstanding correctness gap
in the repo — it is upstream of any reportable metric.
