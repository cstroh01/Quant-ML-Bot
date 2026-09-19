# Contracts: Interfaces 021 Changes

021 changes four production interfaces that code outside its own lanes
imports:

- spec 018 T024's route;
- the frozen `multi_ticker_comparison.py`;
- the API diagnostics route.

This file fixes their shape, so those consumers can adopt it without reading
021's diffs. Nothing here is a library module.

---

## 1. `ma_crossover_backtest.baseline_results`

**Before (current):**

```text
baseline_results(prices, n_trades, holding_bars, *,
                 commission_per_trade, slippage_bps, seed_count) -> dict
```

**After:**

```text
baseline_results(prices, n_trades, holding_bars, *,
                 commission_per_trade, slippage_bps, seed_count,
                 starting_capital, liquidate) -> dict
```

- `starting_capital` and `liquidate` are **keyword-only and required**, with
  no default. A default would be the implicit funding 019 forbids, or an
  implicit end-of-data policy.
- Both values are passed unchanged to every `run_backtest` call inside:
  buy-and-hold, and each random seed.
- **Return shape.** The keys are unchanged: `buy_and_hold`,
  `random_summaries` and `random_error`. Each summary is still
  `summarize_trades` output.
- **Guarantee.** With a feasible `(n_trades, holding_bars)`, `random_error` is
  `None` and `len(random_summaries) == seed_count`. `random_signal` no longer
  emits a same-row sell and buy; see §3.

**Consumers that must adopt it:**

| Consumer | Owner | Adopts in |
|---|---|---|
| `scripts/ma_crossover_backtest.main` | 021 lane B | 021 |
| `scripts/logistic_baseline.main` | 021 lane B | 021 |
| `tests/test_ma_crossover_backtest.py` | 021 lane B | 021 |
| `reports/api/routes/backtest.py:75-82` | **018 T024** | T024. The route already fails earlier, on `price_basis`, so this adds no new breakage before T024 lands. |

## 2. `ma_crossover_backtest.format_comparison`

The signature is unchanged. **Output contract, added:**

- The cost-model block states starting capital once and the end-of-data policy
  once, beside commission and slippage.
- Each of the four appears exactly once in the rendered text.

`summary` dicts do not carry capital, so `format_comparison` takes both new
values from module constants that `main()` also passes to the harness. That
way the printed value and the used value cannot differ.

## 3. `signals.random_signal`

The signature is unchanged:

```text
random_signal(prices, n_trades, avg_holding_days, seed) -> DataFrame
```

**Guarantees:**

| # | Guarantee | Before 021 |
|---|---|---|
| G1 | Exactly `n_trades` `True` values in each of `Buy_Next_Open` and `Sell_Next_Open` | same |
| G2 | Every trip is held exactly `avg_holding_days` rows | same |
| G3 | Trips never overlap | same |
| **G4** | **No row has both flags. Entry *i+1* is at least one row after exit *i*.** | **new**. The old version could put exit *i* and entry *i+1* on one row. |
| G5 | Same arguments give the same frame; no global RNG state is touched | same |
| G6 | `n_trades == 0` gives all-`False` columns, not an error | same |
| **G7** | Raises `ValueError` when `len(prices) < n_trades·(avg_holding_days+1) + 1`, and the message names that bound | **changed**. The old bound was `n_trades·avg_holding_days + 2`. |
| G8 | Both columns are exact `bool` dtype, as the 019 harness requires | same |

**Consumers:** `ma_crossover_backtest.baseline_results` (021), and
`multi_ticker_comparison._baseline_rows` (frozen). The frozen consumer gains
G4 by import alone, and its source does not change.

## 4. `feature_diagnostics`

**`standardized_matrix(frame, columns)`, and the measures built on it**
(`condition_number`, `variance_inflation_factors`, `correlation_frame`,
`max_abs_offdiagonal_correlation`):

- **New precondition.** Every value in `frame[columns]` is finite.
- **On violation.** It raises `ValueError`, naming the columns and the number
  of non-finite rows, and telling the caller to pass the set's complete rows.
  It no longer fails as `LinAlgError: SVD did not converge`, and no longer
  returns `nan`.

**`diagnose(frame, feature_set) -> dict`:**

- It accepts a full-calendar `build_features` frame.
- It measures only rows where every column of `feature_columns(feature_set)`
  is finite.
- **Keys.** It keeps every existing key. `rows` now means *rows measured*, and
  a new key `rows_excluded` counts the rows it left out.
- `format_report` prints both.

**Consumers:**

- `feature_diagnostics.main` (021 lane D).
- `reports/api/routes/diagnostics.py:50-51`. Not edited. It already filters
  complete rows before calling `diagnose`, so `rows_excluded == 0` there and
  its response is unchanged. The response schema does not expose `rows`.
- `tests/test_feature_scaling.py` (021 lane D), which calls the primitives
  with complete rows.
