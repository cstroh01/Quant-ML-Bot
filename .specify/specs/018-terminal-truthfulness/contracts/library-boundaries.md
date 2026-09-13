# Contract: Library boundaries (Spec 018)

Each function lists its guarantee and what it raises. "Unchanged" means the
existing public signature and successful-path output are bit-identical.

---

## `scripts/cost_domain.py` (new)

Imports: `math` only (asserted by AST import-set test).

```python
MAX_SLIPPAGE_BPS: int = 10_000   # exclusive upper bound

def validate_costs(commission_per_trade: float, slippage_bps: float) -> None:
    """Guarantee: returns only if both costs are in the one domain every entry
    point shares (spec 018 FR-022)."""
```

| Input | Raises |
|---|---|
| `bool`, `str`, `None` or other non-real, for either value | `TypeError` naming the parameter |
| Commission: `nan`, `+inf`, `-inf`, `< 0` | `ValueError` naming `commission_per_trade` and the value |
| Slippage: `nan`, `+inf`, `-inf`, `< 0`, `≥ 10000` | `ValueError` naming `slippage_bps` and the value |
| `0`, `0.0` (explicit zero cost) | nothing |

Callers:
- `backtest_harness.run_backtest`
- `backtest_harness.trade_cost_breakdown`
- `metrics.equity_curve` (and so `performance_summary`)
- `metrics.reconciliation_report`
- `ml_signal._validate_costs` (the cost part)
- the tearsheet request dependency

---

## `scripts/backtest_harness.py`

### `run_backtest(prices, *, commission_per_trade=0.0, slippage_bps=0.0)` — hardened

The existing missing-column check still applies. New checks run before any row
is read by the loop:

| Condition | Raises |
|---|---|
| Cost outside domain | via `cost_domain.validate_costs` |
| `Open` or `Close` non-numeric, non-finite, or `≤ 0` in any row | `ValueError` naming the column and the first offending row position |
| `Buy_Next_Open` or `Sell_Next_Open` dtype is not numpy `bool` (includes nullable `boolean`, object, int, float) | `TypeError` naming the column and its dtype |

On valid input the output is unchanged.

### `summarize_trades(trade_log, *, commission_per_trade=0.0, slippage_bps=0.0)` — hardened

| Condition | Raises |
|---|---|
| Any `P&L` non-finite | `ValueError` ("non-finite trade P&L cannot be summarized") |

Otherwise unchanged.

### `trade_cost_breakdown(trade_log, *, commission_per_trade, slippage_bps) -> dict` (new)

**Guarantee**: splits the costs actually charged to `trade_log`'s fills into
commission and slippage, and reports spread as not modeled.

```text
commission_total = 2 · c · len(trade_log)
slippage_total   = Σ_trades [ EntryPrice · s/(1+s)  +  ExitPrice · s/(1−s) ]    s = slippage_bps/10_000
spread_total     = None
spread_status    = "not_modeled"
```

**Identity pinned by the oracle.** For the same signals:
`Σ P&L(run at zero cost) − Σ P&L(run at c, s) == commission_total + slippage_total`
within `1e-9`.

---

## `scripts/metrics.py`

### `equity_curve(...)` — hardened

The cost domain is checked via `cost_domain`, replacing `:95-100`. A
reconciliation failure is now also raised when `actual` or `expected` is
non-finite. It raises `ValueError`, as before.

### `reconciliation_report(prices, trade_log, *, commission_per_trade, slippage_bps) -> dict` (new)

**Guarantee**: the same comparison `equity_curve` enforces, returned instead
of raised.

```text
{"passed": bool, "abs_difference": float | None, "tolerance": RECONCILIATION_TOLERANCE}
```

- `passed` is false whenever either side is non-finite, and then
  `abs_difference` is `None`.
- It never raises on mismatch; it raises only on malformed input, the same
  checks as `equity_curve`.

---

## `scripts/ml_signal.py`

### `_validate_costs(commission_per_trade, slippage_bps, shares)` — delegates

It calls `cost_domain.validate_costs` for the two costs, then keeps its
`shares` checks (`:69-72`).

- **Messages**: follow `cost_domain`'s wording.
- **Existing assertions**: tests that assert `ValueError` for negative or
  ≥ 10000 still pass.
- **Import set**: becomes `{"__future__", "numpy", "pandas", "cost_domain"}`;
  the forbidden set is unchanged.

---

## `scripts/ma_crossover_backtest.py`

### `holding_bars_per_trade(prices, trade_log) -> pd.Series` (new)

**Guarantee**: for each trade, the number of rows between its `Entry Date` row
and its `Exit Date` row in `prices`, as integer dtype on `trade_log`'s index.

| Case | Result |
|---|---|
| Adjacent sessions | 1 |
| Same session | 0 |
| Across an exchange holiday | counts sessions, not calendar days |
| Forced final exit | counts to the last row |
| Empty `trade_log` | empty integer series |
| A trade date absent from `prices` | `KeyError` (the same `.loc` behaviour as today) |

### `mean_holding_bars(prices, trade_log) -> int` — unchanged output

Now `max(1, int(round(float(holding_bars_per_trade(...).mean()))))`, or 1 for
an empty log. Bit-identical to today on every existing test.

---

## `scripts/feature_set_comparison.py`

### `compare_classification(labels, predicted_a, predicted_b) -> dict` — corrected

- `p_one_sided = binomtest(b_wins, a_wins + b_wins, 0.5, alternative="greater").pvalue`
  when `a_wins + b_wins > 0`.
- `p_two_sided`, `statistic`, `favours_b`, the zero-discordant branch and all
  other keys are unchanged.
- Favoured-direction values are unchanged, to float equality with the
  previous formula.

---

## `scripts/feature_diagnostics.py`

### `variance_inflation_factors(frame, columns) -> pd.Series` — corrected

| Column condition | Value |
|---|---|
| Zero variance | `NaN` |
| Exactly linearly dependent on the other non-constant columns (`SSR ≤ 1e-10·SST`) | `+inf` |
| Otherwise | `1/(1 − R²)`, `≥ 1` |

It never raises for constant columns.

### `diagnose(frame, feature_set) -> dict`

Adds `vif_status: dict[str, "finite"|"infinite"|"undefined"]`. When no column
is finite, `max_vif` is `+inf` if any column is infinite; otherwise it is
`NaN` and `max_vif_feature` is `None`.

---

## `scripts/scratch_multiticker_collinearity.py`

Its local `variance_inflation_factors` (`:112-120`) is deleted, and the
function is imported from `feature_diagnostics`.
