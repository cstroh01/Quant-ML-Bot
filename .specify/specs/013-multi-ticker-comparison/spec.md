# Feature Specification: Multi-Ticker Comparison Table

**Feature Branch**: `013-multi-ticker-comparison`

**Created**: 2026-09-06

**Status**: Draft

**Input**: Every spec so far in this track (005, 009, 010, 011, 012) has run
on AAPL alone. Spec 008's own Background named the destination: *"Phase 3
needs them: a five-ticker comparison table."* Specs 010-012 supply, per
ticker, a tuned model, a cost-aware signal, and (spec 008) a risk-adjusted
`performance_summary`. Nothing yet runs that pipeline over more than one
name or assembles the results into one table. `docs/PROJECT_CONTEXT.md`'s
AAPL figures are also stale as of spec 006 (trained on a fixed 130 rows
instead of an expanding window) — this spec is what finally produces the
honest replacement.

**Owns / must not know about** (per CLAUDE.md's module table): a new
runner script, `scripts/multi_ticker_comparison.py`. It composes
`data.download_market_data`, `features.build_features`,
`estimator.fit_predict_walk_forward` (spec 010, tuned per spec 011),
`signals.cost_aware_entry_signal` (spec 012), `backtest_harness.run_backtest`,
and `metrics.performance_summary` (spec 008) — one ticker at a time. It adds
no new logic to any of those modules; it is composition and aggregation
only.

---

## Background

Every existing runnable script (`ma_crossover_backtest.py`,
`logistic_baseline.py`) hardcodes `TICKER = "AAPL"`. Generalizing to a
universe means:

1. **Isolating one ticker's failure from the rest.** A ticker with too
   little history for even one walk-forward fold, or a data gap large
   enough to break feature construction, should not take down a run that
   would otherwise produce four good rows.
2. **A shared reporting shape.** `metrics.performance_summary` (spec 008)
   already reports on one strategy's trade log; this spec's only new work is
   collecting one such summary per (ticker, strategy) pair into one table,
   with both baselines alongside the model for every ticker (Rule 4 applies
   per ticker, not once for the universe).
3. **An explicit, named universe.** Nothing in this repo names five tickers
   anywhere. `return_stats.py` uses three (AAPL, MSFT, GOOGL) for an
   unrelated purpose. This spec does not invent a five-name list — see
   *Assumptions*, which flags the actual universe as Camden's decision, not
   an assumed one.

### What the agent lane cannot do here

Same limitation spec 002 and spec 006 already recorded: the agent lane
cannot reach Yahoo Finance, so this spec's real multi-ticker run happens on
Camden's machine, not in CI or an agent session. This spec's own tests use a
small synthetic multi-ticker frame (2-3 tickers, one deliberately too short
to produce a fold) built in-repo, with no network access — matching Rule 5's
"a test that requires a download is not a test."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One ticker's failure does not sink the run (Priority: P1)

As the project owner, I need the multi-ticker runner to isolate each
ticker's pipeline, so a single bad name (too little history, a data gap)
produces a reported failure for that name and a complete table for the
rest.

**Independent Test**: Run the pipeline over a synthetic 3-ticker universe
where one ticker's frame is deliberately too short for a single walk-forward
fold; assert the other two tickers' rows are present and complete, and the
failing ticker is reported by name with a reason, not silently dropped or
allowed to raise past its own row.

**Acceptance Scenarios**:

1. **Given** a universe where one ticker cannot produce a single
   walk-forward fold, **When** the runner executes, **Then** the output
   table contains complete rows for every other ticker and a distinct
   "failed" entry naming the ticker and the reason.
2. **Given** a universe where every ticker succeeds, **When** the runner
   executes, **Then** the output table has one row per (ticker, strategy)
   for exactly three strategies per ticker: the cost-aware ML signal
   (spec 012), buy-and-hold, and the random baseline (Rule 4).

### User Story 2 - The table is risk-adjusted and cost-identical across tickers (Priority: P1)

As the project owner, I need every ticker's rows built from
`metrics.performance_summary` under the identical cost model, so ranking the
table by Sharpe (not raw P&L) is a comparison of alpha, not of share price.

**Acceptance Scenarios**:

1. **Given** the completed table, **When** any two tickers' rows are
   compared, **Then** both were produced with identical
   `commission_per_trade` and `slippage_bps`, and the comparison uses
   `performance_summary`'s Sharpe/max-drawdown fields, not raw total P&L.
2. **Given** the table, **When** it is written out, **Then** it is saved via
   `data.cache_path` (matching every other script's output convention) as a
   single CSV, one row per (ticker, strategy).

### Edge Cases

- **A ticker present in the universe list but returning an empty frame from
  `download_market_data`** (delisted, typo'd symbol): treated the same as
  the too-short-history case — reported as failed, by name, with the
  underlying reason surfaced rather than swallowed into a generic message.
- **All tickers fail**: the runner still completes and returns/prints an
  all-failures table rather than raising past the loop — a caller should be
  able to see *what* failed for every name, not just get an unhandled
  exception from whichever ticker happened to be first.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `TICKER_UNIVERSE` MUST be an explicit, named module-level
  constant (a plain list of ticker strings) — never inferred from another
  script or a config file this spec would have to invent. See Assumptions
  for what the actual list should be.
- **FR-002**: `run_one_ticker(ticker, ...) -> dict | ComparisonFailure` MUST
  run the full per-ticker pipeline (features -> tuned estimator -> cost-aware
  signal -> backtest -> performance summary, plus both Rule 4 baselines run
  through the identical cost model) and MUST catch and report — not
  propagate — any exception raised for that ticker alone, returning a
  structured failure (ticker name + reason) instead.
- **FR-003**: `run_comparison(tickers=TICKER_UNIVERSE) ->
  tuple[pd.DataFrame, list]` MUST call `run_one_ticker` for every ticker
  independently (one ticker's exception must not stop the loop) and return
  `(results_frame, failures)`.
- **FR-004**: `results_frame` MUST have one row per (ticker, strategy) for
  every ticker that succeeded, three strategies per ticker (cost-aware ML,
  buy-and-hold, random baseline), carrying every `performance_summary`
  field plus the cost parameters used (Rule 3/4 PR-description
  requirements apply to this table's own columns, not just the PR text).
- **FR-005**: Output MUST be written via `data.cache_path` as one CSV.
- **FR-006** *(Rule 8)*: This module composes existing modules; it adds no
  new feature, target, estimator, signal, or metrics logic of its own.
- **FR-007** *(Rule 6)*: No new dependency.
- **FR-008** *(Rule 5, tests)*: Coverage via a synthetic, network-free
  multi-ticker frame: the isolated-failure case, the all-succeed case, the
  all-fail case, and confirmation that every row's cost parameters match
  across tickers.

### Key Entities

- **Ticker universe**: the fixed list this spec runs over. Explicit, not
  inferred.
- **Comparison failure**: a (ticker, reason) pair reported instead of a row,
  for any ticker whose pipeline could not complete.

---

## Success Criteria *(mandatory)*

- **SC-001**: On a synthetic universe with one deliberately-too-short
  ticker, the output table is complete for the other tickers and the
  failing one is named with a reason, not silently absent.
- **SC-002**: On a synthetic all-succeed universe, the table has exactly
  one row per (ticker, strategy) across all three required strategies.
- **SC-003**: Every row in the table shares identical
  `commission_per_trade`/`slippage_bps` values.
- **SC-004**: The CSV round-trips through `data.cache_path` and reloads with
  the same shape it was written with.
- **SC-005**: A mutation check (one ticker's exception allowed to propagate
  and stop the loop; a baseline silently dropped for one ticker) fails the
  test suite for each injected defect.

---

## Assumptions

- **The five-ticker universe is not named anywhere in this repo and is
  flagged here as Camden's decision, not this spec's** — the constitution's
  "what to flag rather than fix" applies directly: naming a universe is a
  research/data choice (liquidity, sector spread, history length), not an
  engineering one. `TICKER_UNIVERSE`'s default should be treated as a
  placeholder (e.g. the three `return_stats.py` already uses, extended by
  two) until Camden confirms the real list.
- This spec's tests exercise the composition and failure-isolation logic
  only, against synthetic data. The real run — the one that finally
  supersedes `docs/PROJECT_CONTEXT.md`'s stale AAPL-only figures — happens
  on Camden's machine, matching the same limitation recorded for spec 002
  and spec 006.
- The estimator used per ticker is whatever spec 010/011 currently default
  to (tuned via `select_best_hyperparameters` if that path is wired in by
  the time this spec is implemented); this spec does not add model
  selection logic of its own.
