# Implementation Plan — 013 Multi-Ticker Comparison Table

**Spec**: `.specify/specs/013-multi-ticker-comparison/spec.md`

---

## Scope

- `scripts/multi_ticker_comparison.py` — **new**. `TICKER_UNIVERSE`,
  `ComparisonFailure`, `run_one_ticker`, `run_comparison`, `main` (FR-001 –
  FR-006)
- `tests/test_multi_ticker_comparison.py` — **new** (FR-009)

Explicitly **not** touched: `data.py`, `features.py`, `model_cv.py`,
`ml_signal.py`, `backtest_harness.py`, `metrics.py`, `signals.py`. This spec
calls each of those; it adds no logic to any of them (FR-007).
`ma_crossover_backtest.py` is called for one function only
(`mean_holding_bars`) and not modified — see **Design** below for why
`baseline_results` itself is not reused.

**No new dependency** (FR-008). Standard library, pandas, and the modules
above only.

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | Inherited, not re-established: this module builds no feature, label, or price column of its own. It calls `features.build_features` and reads back `model_cv.nested_walk_forward`'s predictions. |
| 2 — Purge/embargo | Inherited from `model_cv.nested_walk_forward` (spec 010/011), called once per ticker with the same `label_horizon`/`embargo_bars` for every ticker. FR-005 requires the fold count, purge length, and embargo length to appear as columns, not just be true internally. |
| 3 — Costs | `commission_per_trade` and `slippage_bps` are module-level constants passed identically into every ticker's `run_backtest`/`performance_summary`/`baseline_results` call — never per-ticker overrides — and both are carried into `results_frame` (FR-005, SC-003). |
| 4 — Baselines | The spec's central mechanism: every ticker's table rows include buy-and-hold and a seeded random baseline via `ma_crossover_backtest.baseline_results`, run over the identical bars and costs as the ML row (User Story 2). |
| 5 — Tests | This module indexes nothing on a timestamp itself (that work is inherited), but its own control flow — the per-ticker isolation loop and the aggregation into one frame — gets full coverage: isolated failure, all-succeed, all-fail, and cost-parameter consistency (T007–T011). |
| 6 — Dependencies | None added. |
| 7 — Execution | Not applicable; nothing here places an order or touches `exec/`. |
| 8 — Layer separation | This module is composition-only, sitting above every layer it calls. It does not reach into `backtest_harness` or `ml_signal` internals — it consumes their public functions in the order spec 012/010/011 already established. |
| 9 — The merge gate | The mechanism is a `try`/`except` around one ticker's pipeline call inside a loop, plus a `pd.concat` of the resulting rows — small enough to read in one pass, which is the point of pushing everything else into already-reviewed modules. |
| 10 — Version control | No `git` run outside the Actions lane. Camden commits. |

---

## Design

### `run_one_ticker` — the composition, in call order

```
prices          = data.download_market_data([ticker], period=...)
                   -> empty/short frame is a failure, not a crash (Edge Cases)
features, label_column, label_horizon = features.build_features(prices, ...)
predictions, _, fold_results = model_cv.nested_walk_forward(
    features, feature_columns=..., label_column=label_column, task="regression",
    name=ticker, label_horizon=label_horizon, embargo_bars=EMBARGO_BARS,
    random_state=RANDOM_STATE,
)
hurdle          = ml_signal.log_hurdle(features["Close"], commission_per_trade=..., slippage_bps=...)
desired_long    = ml_signal.positions_from_predicted_return(predictions, hurdle, exit_threshold=0.0)
buy, sell       = ml_signal.signal_from_positions(desired_long)
ml_prices       = features.assign(Buy_Next_Open=buy, Sell_Next_Open=sell)
ml_trades       = backtest_harness.run_backtest(ml_prices, commission_per_trade=..., slippage_bps=...)
ml_summary      = metrics.performance_summary(ml_prices, ml_trades, commission_per_trade=..., slippage_bps=..., starting_capital=CAPITAL_BASE)
baselines       = ma_crossover_backtest.baseline_results(
    ml_prices, n_trades=len(ml_trades), holding_bars=mean_holding_bars(ml_prices, ml_trades),
    commission_per_trade=..., slippage_bps=..., seed_count=SEED_COUNT,
)
```

`task="regression"` is fixed here — the estimator/target choice spec 010/011
default to, per the spec's own Assumptions. Nothing in this module selects a
model; it only calls the pipeline that already does.

The **model** row's dict is `ml_summary` plus:
`Ticker`, `Strategy="ml_cost_aware"`, `Median hurdle (bps)` (`hurdle.median() *
10_000`), `|pred| q90 (bps)` (`predictions.abs().quantile(0.9) * 10_000`),
`fold_count` (`len(fold_results)`), `purge_bars`/`embargo_bars`,
`commission_per_trade`, `slippage_bps`, `random_state`. The **baseline** rows
reuse `baseline_results`' own dicts, tagged with `Ticker` and their strategy
name and carrying the same cost columns so every row in the table — not just
the ML row — is self-describing (FR-005 applies to the table's own columns).

### Failure isolation — `ComparisonFailure`, and where the boundary sits

`run_one_ticker` wraps its entire body in one `try/except Exception`. On
failure it returns `ComparisonFailure(ticker=ticker, reason=str(exc))` instead
of a list of row-dicts — a *type* distinction (`dict`-producing success vs.
`ComparisonFailure`), not a sentinel value, so `run_comparison` cannot mistake
one for the other. This is the one place in the module allowed to catch a
bare `Exception`: everywhere else (inside the called modules) exceptions are
left to propagate, per CLAUDE.md's normal expectation — the isolation is
explicitly scoped to the per-ticker boundary FR-002 names, not a blanket
try/except sprinkled through the module.

`run_comparison` loops `for ticker in tickers`, appends each `run_one_ticker`
result to either `all_rows` or `failures` by its type, and never lets one
iteration's exception reach the loop — there is no shared mutable state
between tickers for a failure to corrupt. Concatenating `all_rows` with
`pd.concat(..., ignore_index=True)` on an empty list (the all-fail case)
returns the all-failures table SC-... / Edge Cases requires, with the
loop having still completed rather than raised.

### Output — namespaced filename via `data.cache_path`

`cache_path` only joins a name onto `data/cache/`; it does no namespacing
itself; that is this module's job (FR-006). The filename follows the same
sorted-deduped-tickers convention `download_market_data` already uses
internally (`data.py:253-259`), so the two artifacts a run produces —
the downloaded cache and this comparison table — are named consistently:
`"-".join(sorted(set(tickers))) + "_comparison.csv"`.

### Why the baselines do not reuse `ma_crossover_backtest.baseline_results`

**Revised during implementation.** The Design section as originally drafted
called `baseline_results` directly; reading its body showed it summarizes
each baseline's trade log with `backtest_harness.summarize_trades` — total
P&L and win rate only, no Sharpe or drawdown. User Story 2 requires every
row, baselines included, to compare on `performance_summary`'s risk-adjusted
fields, not raw P&L, so calling `baseline_results` verbatim would satisfy
`tasks.md`'s T006 literally while missing FR-005 and SC-... in substance.

`_baseline_rows` instead calls the same two signal functions
`baseline_results` calls — `signals.buy_and_hold_signal` and
`signals.random_signal` — directly against `ml_prices`, and summarizes each
resulting trade log with `metrics.performance_summary`.
`ma_crossover_backtest.mean_holding_bars` is still reused verbatim; only the
summarizer changes. `ml_prices` (the features frame with the ML strategy's
own `Buy_Next_Open`/`Sell_Next_Open` columns attached) is what both baselines
overwrite their own copy of, rather than the original `prices` frame — that
is what makes "identical bars and costs" true rather than merely intended
(Rule 4): a baseline run over a *different* row count than the ML backtest
would not share Rule 4's premise. `ma_crossover_backtest.py` is otherwise
untouched, and `baseline_results` itself is left in place for the script
that already depends on it.

### Empty/short-history tickers are a `run_one_ticker` failure, not a special case

`download_market_data` returning an empty frame, and `features.build_features`
raising because there is too little history for a single fold, both surface
as ordinary exceptions inside `run_one_ticker`'s try block. No separate
"is this ticker viable" pre-check is added — the spec's Edge Cases ask for
both cases (empty frame, too-short history) to be "treated the same way,"
and one catch-all boundary is how that sameness is guaranteed rather than
asserted by two similar-looking branches.

---

## Project structure

```text
scripts/
└── multi_ticker_comparison.py   # new — this spec's only production file

tests/
└── test_multi_ticker_comparison.py   # new — synthetic, network-free (Rule 5)
```

**Structure Decision**: single new runner module at the same level as
`ma_crossover_backtest.py` and `logistic_baseline.py` — this repo has no
`src/` layout; every runnable script lives directly under `scripts/`.

---

## Verification — as run

```
./venv/Scripts/python.exe -m unittest discover -s tests
```

**Result: 416 tests, OK.** Suite was 405 after spec 016; 11 added here.

### Mutation check (T012)

Two deliberate defects injected into `multi_ticker_comparison.py`, each run
against the full `test_multi_ticker_comparison.py`:

| Injected defect | Result |
|---|---|
| `run_one_ticker`'s isolation boundary narrowed from `except Exception` to `except KeyError` (lets a `RuntimeError` from an out-of-history ticker propagate) | **FAILED** (4 errors) |
| `run_one_ticker` returns only `[ml_row, *baseline_rows[:1]]` (silently drops the random baseline) | **FAILED** (3 failures) |

Both defects were reverted after confirming the failures; the file at HEAD is
the clean version.

### T014/T015 — left for Camden

Both remain unchecked in `tasks.md`. The real ten-year download and the
`docs/PROJECT_CONTEXT.md` rewrite both require live Yahoo Finance access,
which this lane does not have (specs 002, 006). `main()` fails fast with the
exact download command (T014's own text) rather than surfacing a network
error from inside the per-ticker loop.
