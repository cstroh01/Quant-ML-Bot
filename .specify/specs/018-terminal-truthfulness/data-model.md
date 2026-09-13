# Data Model: Terminal Truthfulness (Spec 018)

This spec persists nothing; every entity is in-memory or a response body. Field
types use Python/pydantic notation, and `types/api.ts` mirrors each entity.

---

## ComputationStatus

The status of a quantity the terminal may display.

| Value | Meaning | Carries |
|---|---|---|
| `computed` | Produced by a computation in this request | the value |
| `not_computed` | No computation is wired to produce it | `reason: str`, naming the stage that will (e.g. "Stage 3.3") |
| `unavailable` | Its input data does not exist | Expressed as the loader's HTTP 404, not as a 200 body (R1) |

**Validation.**
- A `not_computed` object MUST have a non-empty `reason`.
- It MUST NOT carry a numeric value field.

---

## NotComputed

The object that stands in for a quantity that was never computed.

```text
NotComputed
  status: Literal["not_computed"]
  reason: str        # non-empty; may contain only roadmap references as figures (R3)
```

Used by:
- `SignificanceResponse`: the whole body is a ticker plus a `NotComputed`.
- `MLRundownResponse.model_forecast`
- `CapitalGateStatusResponse.test_run`

---

## GateEvidenceStatus and CapitalGateItem

```text
CapitalGateItem
  gate_number: int                                   # structural ordinal (allowlisted)
  title: str
  description: str                                   # evidence required; no pass rule, no figures
  status: Literal["passed", "failed", "stale", "unknown"]
  reason: str                                        # why this status (roadmap reference allowed)
  evidence: str | None                               # reference to a verification record
```

**Validation.**
- If `status != "unknown"`, `evidence` MUST be a non-empty string; otherwise
  the model rejects it (FR-007).

**State transitions** (future; only `unknown` is reachable in spec 018):

```text
unknown ──(verification record read, criteria met)──────► passed
unknown ──(verification record read, criteria not met)──► failed
passed/failed ──(data, source, costs or policy changed after record)──► stale
stale ──(new record read)──► passed | failed
```

Spec 018 implements none of these transitions. Spec 028 (run store) supplies
the reader, and spec 035 the gate-3 criterion.

```text
CapitalGateStatusResponse
  overall_readiness: str
  test_run: NotComputed                  # header badge source (FR-008)
  gates: list[CapitalGateItem]
```

---

## Rundown

```text
MLRundownResponse                        # path /api/ml/rundown kept
  ticker: str
  as_of_date: str                        # unchanged; one session stale (finding 23, out of scope)
  model_forecast: NotComputed
  rule_summary: str                      # describes which rules fired; no model/advice wording
  rule_readings: list[RuleReading]

RuleReading
  rank: int                              # structural ordinal
  indicator: str                         # e.g. "Close / Short_SMA − 1"
  value: float                           # computed this request
  rule: str                              # the threshold test applied, stated plainly
  classification: Literal["above", "below", "within"]
  commentary: str                        # descriptive only; no unmeasured claims (FR-005, FR-015)
```

**Removed**: `MLInsightItem` (`category`, `headline`, `technical_reading`,
`plain_english`, `how_to_plan`, `status`, `importance`), `summary_verdict` and
`verdict_status`.

**Why rename `how_to_plan` rather than keep it**: every value in it is trading
advice presented as a model playbook, which FR-004 forbids.

---

## Significance

```text
SignificanceResponse
  ticker: str
  status: Literal["not_computed"]
  reason: str
```

**Removed**: `screening_alpha`, `entries`, and the `SignificanceEntry` schema.

---

## FiniteOrSpecial (VIF, condition number)

```text
DiagnosticValue
  value: float | None
  status: Literal["finite", "infinite", "undefined"]
  reason: str | None                     # required when status != "finite"
```

**Validation.**
- `finite` ⇒ `value` is a finite float, and for VIF `value ≥ 1`.
- `infinite` or `undefined` ⇒ `value is None` and `reason` is non-empty.

`CollinearityEntry.condition_number` and `CollinearityEntry.max_vif` become
`DiagnosticValue`. `correlation_matrix` values become `float | None`, where
`None` means undefined (for example, a constant column); the UI renders it as
unavailable (FR-015).

---

## Tearsheet

```text
TradeRecord
  entry_date, exit_date: str
  entry_price, exit_price, pnl, cumulative_pnl: float    # unrounded (FR-011)
  holding_bars: int                                       # no default; ≥ 0 (FR-009)

CostBreakdown
  commission_total: float
  slippage_total: float
  spread_total: None
  spread_status: Literal["not_modeled"]
  spread_reason: str

ReconciliationReport
  passed: bool                                            # computed, never literal
  abs_difference: float | None                            # None only if a side was non-finite
  tolerance: float                                        # configuration (metrics.RECONCILIATION_TOLERANCE)

BacktestTearsheetResponse
  ticker: str
  strategy_name: str
  strategy_family: Literal["rule_based_sma_crossover"]    # FR-018
  commission_per_trade, slippage_bps: float               # request echo
  capital_base, total_return, total_pnl: float            # unrounded
  sharpe_ratio, max_drawdown: float | None
  costs: CostBreakdown
  reconciliation: ReconciliationReport
  equity_curve: list[EquityPoint]                         # unrounded
  trade_log: list[TradeRecord]
  comparison_table: list[BaselineComparisonRow]           # unrounded
```

**Removed**: `reconciliation_passed: bool`.

---

## Cost domain (library)

```text
commission_per_trade : real, finite, ≥ 0
slippage_bps         : real, finite, 0 ≤ x < 10000 (MAX_SLIPPAGE_BPS, exclusive)
bool is rejected as a type, even though bool ⊂ int in Python
```

---

## Harness inputs (library)

```text
prices["Open"], prices["Close"]                  : numeric, all finite, all > 0
prices["Buy_Next_Open"], prices["Sell_Next_Open"] : dtype exactly numpy bool
```

---

## Regression entities (test-only)

```text
FixturePanel
  seed: int
  sessions: int          # A ≈ 300, B ≈ 347; real exchange sessions from data.trading_days
  drift: float           # A > 0, B < 0
  tickers: ("AAPL", "NVDA")   # synthetic values under real symbols (loader requires a symbol)

AllowlistEntry
  endpoint: str | None             # L1 entries
  target: str                      # JSON path with [] for list items, or Schema.field for L2
  category: Literal["request_echo", "configuration", "structural_ordinal",
                    "structurally_constant", "roadmap_reference"]
  reason: str
  permitted_figures: str | None    # regex; required for roadmap_reference

PendingCoverage
  endpoint_or_field: str
  owner_pr: str                    # e.g. "PR D (FR-009)"; table must be empty after PR G

Mutant
  id: int                          # SC-002 numbering
  file: str                        # repository-relative
  find: str                        # must match exactly once
  replace: str
  expected: "fails at least one test"
```
