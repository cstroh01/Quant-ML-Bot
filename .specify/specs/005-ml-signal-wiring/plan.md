# Implementation Plan — 005 ML Signal Wiring

## Where the code goes

Everything lives in `scripts/logistic_baseline.py`, added alongside the
existing `build_features` / `evaluate_walk_forward`. Two new functions,
one new set of `main()` steps.

### `walk_forward_predictions(features) -> pd.Series`

Re-runs the same fold loop `evaluate_walk_forward` uses
(`walk_forward_splits(features, label_horizon=1, embargo_bars=1)`), fitting
one `LogisticRegression(max_iter=1000, random_state=42)` per fold on that
fold's training rows and predicting its test rows. Results are written into
a `pd.Series(pd.NA, index=features.index, dtype="Int64")` at each fold's
`test_indices` positions.

This *duplicates* the fit/predict loop that already lives in
`evaluate_walk_forward` rather than sharing it. That's a deliberate,
disclosed tradeoff (FR-006): refactoring both functions to share one
generator would touch `evaluate_walk_forward`, which spec 003's tests
already cover and pass against today. A few extra `LogisticRegression` fits
on a handful of years of daily bars cost milliseconds — not worth the risk
to an already-correct, already-tested function for this spec's scope. If a
future spec needs the folds computed once and reused, that refactor can
happen then, on its own diff.

### `build_ml_signal(features) -> tuple[pd.DataFrame, int]`

```
predictions = walk_forward_predictions(features)
desired_long = (predictions == 1).fillna(False).astype(bool)

enters_long = desired_long & ~desired_long.shift(1, fill_value=False)
exits_long = ~desired_long & desired_long.shift(1, fill_value=False)

features = features.copy()
features["Buy_Next_Open"] = enters_long.shift(1, fill_value=False)
features["Sell_Next_Open"] = exits_long.shift(1, fill_value=False)

first_covered_pos = int(predictions.first_valid_index())
return features, first_covered_pos
```

This mirrors `sma_crossover_signal`'s own pattern exactly: compute a
same-bar transition (`enters_long`/`exits_long`, analogous to
`Crosses_Above`/`Crosses_Below`), then shift the whole thing forward one bar
so the fill lands on the next bar's open. `desired_long` before the first
fold is `False` (from `fillna(False)`) — a row nothing is known about yet is
a flat row, not a random guess.

`first_covered_pos` is returned rather than recomputed by the caller,
because it is the position `predictions.first_valid_index()` already
determines internally — recomputing it in `main()` would mean either
running `walk_forward_predictions` a second time or duplicating
`first_valid_index()` logic against a series `main()` does not otherwise
need.

### `main()` changes

After `evaluate_walk_forward(features)` runs and saves its CSV as it does
today, add:

```
signalled, first_covered_pos = build_ml_signal(features)
live = signalled.iloc[first_covered_pos:].reset_index(drop=True)

costs = {"commission_per_trade": COMMISSION_PER_TRADE, "slippage_bps": SLIPPAGE_BPS}
trade_log = run_backtest(live, **costs)
summary = summarize_trades(trade_log, **costs)
baselines = baseline_results(
    live,
    n_trades=summary["total_trades"],
    holding_bars=mean_holding_bars(live, trade_log),
    seed_count=RANDOM_BASELINE_SEEDS,
    **costs,
)
print(_format_ml_comparison(summary, baselines, seed_count=RANDOM_BASELINE_SEEDS))
```

`COMMISSION_PER_TRADE = 1.00`, `SLIPPAGE_BPS = 5.0`, `RANDOM_BASELINE_SEEDS
= 20` are new module-level constants in `logistic_baseline.py`, matching
`ma_crossover_backtest.py`'s values so the two strategies' reports are
directly comparable — restating the same illustrative retail-broker cost
model, not importing it (importing a *value* across scripts for no reason
beyond "keep them equal" adds a coupling this repo doesn't otherwise have;
restating a constant is the smaller, more legible dependency here).

`baseline_results` and `mean_holding_bars` ARE imported from
`ma_crossover_backtest` — those two are already label-agnostic (they take
`prices`/`trade_log`/cost values, never a strategy name), so importing them
is reuse, not coupling to that script's SMA-specific behavior.

`_format_ml_comparison` is a new, local, small function — a straight copy
of `ma_crossover_backtest.format_comparison`'s layout and precision, with
the row label changed to `"Logistic regression (walk-forward)"` and the
cost-model header text reused verbatim. Not imported, per FR-005: the
original hardcodes `SHORT_WINDOW`/`LONG_WINDOW` into its own label, so
calling it here would print a wrong strategy name in a machine-readable-ish
report — worth a few duplicate lines of formatting code to avoid a report
that lies about what it's reporting.

## Test plan

New file `tests/test_logistic_baseline.py`, following the `context.py`
sys.path convention the other test files already use (spec 003's test file
did its own `sys.path.insert` instead — this spec's new file corrects that
locally without touching the passing spec-003 file).

| Case | Tests |
|---|---|
| Coverage, no gaps/overlap | Every position in `pd.concat` of all folds' `test_indices` gets exactly one prediction; positions before the first fold's test start are `<NA>`. (SC-001) |
| Agreement with `evaluate_walk_forward` | Same synthetic features run through both `walk_forward_predictions` and the fold loop inside `evaluate_walk_forward`; per-fold predictions match array-for-array (same fit, same data). |
| Enter/exit is next-open shifted | Hand-built `predictions` Series (bypassing the walk-forward fit) fed through the position logic; assert a `Buy_Next_Open`/`Sell_Next_Open` never fires on the same row a prediction changed, always one row later. |
| No repeated fire while positioned | Multiple consecutive "up" predictions produce exactly one `Buy_Next_Open`, not one per row. |
| Pre-coverage rows are flat | Rows before `first_covered_pos` have `Buy_Next_Open == Sell_Next_Open == False`. |
| End-to-end smoke test | `build_ml_signal` + `run_backtest` on synthetic features runs without error and produces a `Cumulative P&L` column that is finite throughout. |

## Risks

| Risk | Mitigation |
|---|---|
| Duplicating the fold loop between `evaluate_walk_forward` and `walk_forward_predictions` could silently drift if one is edited later | Both call `walk_forward_splits` with the same literal `label_horizon=1, embargo_bars=1` and the same model constructor; the agreement test (above) catches drift immediately if either changes. |
| A single-stock, next-day-direction logistic model on 5 weak features very likely has ~no real edge | Expected, and explicitly named in the spec (SC-004) — the point of this spec is wiring, not alpha. Report it honestly against the random baseline either way. |
| Reusing `ma_crossover_backtest.baseline_results`/`mean_holding_bars` couples this script to that one's continued existence | Both are already the generic, label-agnostic layer that script itself uses for its own baselines — this is the intended reuse point, not an accidental one. |
