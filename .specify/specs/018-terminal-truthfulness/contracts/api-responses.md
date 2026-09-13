# Contract: Terminal API responses (Spec 018)

All routes are `GET`. Types are in [../data-model.md](../data-model.md). The
"Before" bodies are abridged from `docs/audit-2026-09-12/probe-results.json`.

---

## `GET /api/diagnostics/significance?ticker=`

**Before**: four entries with literal `p_value` (0.084/0.215/0.042/0.31),
`alpha` and `passed_screening`. The body is identical for AAPL and NVDA.

**After** (200, any ticker the loader can serve):

```json
{
  "ticker": "AAPL",
  "status": "not_computed",
  "reason": "No saved comparison run is wired to the terminal; run-store reading arrives in Stage 3.3."
}
```

| Case | Response |
|---|---|
| Ticker with no data | 404 `{"detail": "No cached data found for ticker X"}` (unchanged) |

---

## `GET /api/ml/rundown?ticker=`

**Before**:
- the literal `"P(Up) = 54.2% | Logit Score = +0.17 | Forward Horizon = 1 bar"`
  under category "ML Directional Forecast"
- five `MLInsightItem`s with trading advice
- `summary_verdict` saying "Model advises…"

**After** (200):

```json
{
  "ticker": "AAPL",
  "as_of_date": "2024-03-08",
  "model_forecast": {
    "status": "not_computed",
    "reason": "No fitted model's inference is wired to the terminal; this arrives in Stage 3.3."
  },
  "rule_summary": "Indicator rules only — not a model forecast.",
  "rule_readings": [
    {
      "rank": 1,
      "indicator": "Close / Short_SMA − 1",
      "value": 0.0123456,
      "rule": "above when value > 0",
      "classification": "above",
      "commentary": "Close is above its short moving average."
    }
  ]
}
```

**Rule readings.** There are four: `Close_To_Short`, `SMA_Spread`, annualized
`Rolling_Volatility`, and `Rel_Volume`.

**Commentary constraints.** Commentary MUST NOT contain:
- "model", "ML", "predict", "forecast" or "advise"
- "institutional", "flow" or "conviction"
- "theorem" or "standard-deviation"
- "win rate"
- any trading instruction
- any numeric figure (R3)

---

## `GET /api/capital_gate/status`

**Before**:
- Gate 1 `"status": "passed"`, with "All 301 unit tests passing" and "301
  passed in pytest suite"
- Gate 2 details with literal "36.17 to 2.15, VIF from 268 to 1.60"
- Gate 3 description "Deflated Sharpe ratio remains positive…"

**After** (200):

```json
{
  "overall_readiness": "Phase 3 — research; no gate has recorded evidence.",
  "test_run": {
    "status": "not_computed",
    "reason": "No recorded test run is read by the terminal; verification records arrive in Stage 3.3."
  },
  "gates": [
    {
      "gate_number": 1,
      "title": "Layer 3 Machine Gates",
      "description": "Requires a recorded automated verification run: lookahead, null-pipeline and cost-stress checks, with their results.",
      "status": "unknown",
      "reason": "No verification record is read by the terminal (Stage 3.3).",
      "evidence": null
    }
  ]
}
```

- **Gates 2–5**: same shape, all `unknown`, `evidence: null`.
- **Gate 3's reason**: names finding 30 / Stage 3.5 as where its criterion is
  predeclared.
- **Gates 4 and 5's reason**: name Phase 4 and Phase 5.

**Invariant.** A body with `status` in `{passed, failed, stale}` and empty
`evidence` fails response-model validation. The server cannot emit it.

---

## `GET /api/backtest/tearsheet`

### Request

| Param | Type | Default | Constraint | Error |
|---|---|---|---|---|
| `ticker` | str | `AAPL` | loader can serve it | 404 |
| `short_window` | int | 10 | `1 ≤ x ≤ 252` | 422 |
| `long_window` | int | 30 | `2 ≤ x ≤ 252`, `> short_window`, `< loaded sessions` | 422 |
| `commission` | float | 1.0 | finite, `≥ 0` (cost_domain) | 422 |
| `slippage_bps` | float | 5.0 | finite, `0 ≤ x < 10000` (cost_domain) | 422 |

### Error body

The standard 422 shape, used for built-in, cross-field and cost-domain errors
alike:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["query", "long_window"],
      "msg": "long_window must be greater than short_window",
      "input": 10
    }
  ]
}
```

**Never** returned for invalid input: 200, 500, or a tearsheet body.

**500** is reserved for server faults. Detail `"reconciliation failed"` is
emitted when `metrics.reconciliation_report(...).passed` is false on
validated input.

### Response (200) — changed fields only

```json
{
  "strategy_name": "SMA Crossover (10/30)",
  "strategy_family": "rule_based_sma_crossover",
  "costs": {
    "commission_total": 84.0,
    "slippage_total": 12.3456789,
    "spread_total": null,
    "spread_status": "not_modeled",
    "spread_reason": "The harness models commission and slippage only."
  },
  "reconciliation": {"passed": true, "abs_difference": 1.1e-13, "tolerance": 1e-9},
  "trade_log": [
    {
      "entry_date": "2024-01-03",
      "entry_price": 101.2345678,
      "exit_date": "2024-02-14",
      "exit_price": 104.9876543,
      "pnl": 1.7530865,
      "cumulative_pnl": 1.7530865,
      "holding_bars": 29
    }
  ]
}
```

- **Unrounded values**: every float in the body is unrounded.
- **Removed**: `reconciliation_passed`.

---

## `GET /api/diagnostics/collinearity?ticker=`

`condition_number` and `max_vif` become `DiagnosticValue`:

```json
{"value": 2.153, "status": "finite", "reason": null}
{"value": null, "status": "infinite", "reason": "exact linear dependence among columns"}
{"value": null, "status": "undefined", "reason": "zero-variance column"}
```

- **`max_vif_feature`**: `str | null`.
- **`correlation_matrix` values**: `float | null`.
- **Rounding**: none.

---

## CORS (all routes)

| Request `Origin` | `access-control-allow-origin` | `access-control-allow-credentials` |
|---|---|---|
| `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://127.0.0.1:3000` | echoed | absent |
| any other | absent | absent |

**Allowed methods**: `GET` only.

---

## Unchanged routes

These keep their shapes; they are covered by the L1 regression (their numbers
are computed):
- `/api/health`
- `/api/data/tickers`
- `/api/data/ohlcv`
- `/api/data/stats`
- `/api/data/gaps`

The fallback ticker list is finding 18, spec 027. It contains no numbers, and
is out of scope.

---

## Static frontend

`create_app(dist_dir=Path)` mounts `dist_dir` at `/` when it exists, and
`create_app(dist_dir=None)` mounts nothing. With no mount, `GET /` is 404; the
API routes are unaffected.
