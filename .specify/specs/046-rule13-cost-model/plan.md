# Implementation Plan: Rule 13 cost model

**Branch**: `046-rule13-cost-model` (human-owned) | **Date**: 2026-10-03
**Spec**: [spec.md](spec.md) | **Tasks**: [tasks.md](tasks.md)
**Status**: Design only; no implementation is authorized by this drafting task.
**Placement**: S3b after S2 and before S4, dependent on 044 and S1/035.

## Summary

Introduce one pure per-fill estimator, inject it into execution, reconcile its
actual costs, and carry one canonical configuration into reporting and 033.
Model implementation starts only after the published-paper human gate. The
fixed primary coefficient and windows are already decided. No new dependency,
network test, data download, strategy change or production ledger write is part
of implementation validation.

## Technical context and constitution check

Python 3.12, existing NumPy/pandas and standard-library facilities suffice.
Existing React/TypeScript reporting contracts need corresponding type/render
updates; no additional frontend package is proposed. Tests belong in `tests/`;
temporary ledgers use the existing synthetic context. Source verification is a
human task, not an implied network permission for an agent.

| Rule | Design obligation |
|---|---|
| 1 / 5 | All cost windows trailing through t, fill at t+1, future-field perturbations plus first/last/fold/gap boundaries. |
| 3 / 13 | Half-spread plus square-root impact per fill, separate commission, no reportable flat-cost fallback. |
| 4 | Identical config, usable-history policy and evaluation span for strategy and both baselines. |
| 6 / 8 | Existing dependencies; estimator owns neither signals nor sizing, accounting, downloading or recording. |
| 11 / 16 | Config/source/run/date plus per-fill evidence and the exact modeled-cost limitation. |
| 12 | Independent paper oracle, isolated M1–M10, specific failures and clean controls. |
| 9 / 10 | Human review/merge and existing pins respected; no Git commands. |

## 1. Module contract: `scripts/cost_model.py`

Proposed interfaces (design names, not an implementation):

- `CostConfig`: immutable, serializable, validated model parameters/policies.
- `estimate_fill_cost(history, *, as_of, quantity, config) -> CostEstimate`:
  pure computation over a single instrument's validated nominal OHLCV history
  ending at `as_of`. History includes Date and permitted provenance attrs, not
  signal columns or portfolio state. The caller supplies absolute Q; this
  function never chooses Q. Reject rows later than the explicit cutoff.
- `CostEstimate`: half-spread fraction, impact fraction, total adverse fraction,
  daily sigma, ADV, Q, as-of session, actual window bounds/counts, volume basis,
  and paper-rule handling/status. Missing prerequisites raise an explicit
  cost-unavailable exception/reason, never a valid-looking zero estimate.

Validate positive finite OHLC, ordered naive session labels, valid volume and
quantity domains, permitted volume basis, complete trading-session coverage,
and all conventions required by the verified paper. No mutable global cache,
file writes or network. The model does not receive the t+1 quote; execution
converts the estimated fraction into dollars at the actual fill quote.

**HUMAN-VERIFICATION GATE:** implement from the published paper; record the
equation and page reference in research.md before coding. Record full/half
spread units, negative/undefined policy, lags and sample count, oracle/tolerance,
sigma return basis/ddof, split handling and source for the impact assumption.
Verify these against the fixed 21-trading-day windows. If forming 21 returns
requires an extra prior close, enumerate it explicitly; no future observation
may provide that lag. A conflict blocks implementation and is not resolved by
guessing or parameter tuning. `research.md` is a future task output, not a
fourth file created by this docs-only request.

## 2. Injection into execution and accounting

The harness accepts an explicit cost-function dependency with its resolved cost
config and an explicit reportable/diagnostic mode. The callable and config are
bound together before execution; output records the same immutable config.
The harness receives only cost-domain config, never the full research config.
The recorder remains outside the harness, as 033's layer boundary requires.

At each order, slice cost inputs strictly before the fill session (cutoff t for
t+1). Buy Q comes from externally supplied shares; exit Q is the actual held
quantity, including splits. Require Q and ADV to share units. A split whose
unit/return treatment is not yet verified causes explicit refusal, not an
adjustment invented to make a fixture pass. Retain existing account/split and
receivable semantics. Terminal-close liquidation uses that session's preceding
cost cutoff and its actual held Q; mark-only events have no fill cost.

For valid total fraction c, buy fill is quote × (1+c), sell fill is quote ×
(1−c); commission is applied separately once per fill. The harness owns the
affordability decision and never resizes an unaffordable entry. An unavailable
estimate fails before the order mutates account state; it does not create a
free trade. Flat diagnostics require an explicit mode and the D-3 label.

Extend funded fill-event evidence with quote, actual fill price, fill quantity,
cost breakdown, cutoff and config identity. Preserve existing mark-price and
equity meanings. `metrics.equity_curve` must verify and replay those recorded
fills/costs, not reconstruct them from one bps rate. Check component sum,
adverse sign, fee/cash transitions and agreement with trade records; a price or
breakdown mutation must fail even when the model string remains valid.
`performance_summary` and `summarize_trades` propagate actual cost evidence
and reject conflicting cost declarations. Preserve reconciliation tolerances;
do not weaken existing funded-account tests to accommodate the new model.

## 3. Canonical configuration and 033 binding

The following is a schema description, not a fabricated result. Unknown source
details must be filled from the human-verified evidence before use, never
serialized as plausible citations.

| Slippage field | Required meaning |
|---|---|
| `model` | Exactly `spread_plus_sqrt_impact`. |
| `spread_window`, `sigma_window`, `adv_window` | Each 21 trading sessions, trailing through the explicit cutoff. |
| `impact_coef` | 1.0 primary; 0.5/2.0 only in separately labelled robustness runs. |
| `source` | Published spread/impact references, equation/page and verified oracle reference; no invented locator. |
| `estimator_version` | Version of the verified algorithm/conventions. |
| `sigma_convention` | Explicit daily-return basis, dispersion definition/ddof and lag requirement. |
| `volume_convention` | Share units and the verified split-comparability policy; not a claim that all input volume is verified. |
| `window_policy` | Trading-session count, cutoff, missing-session policy and minimum observations. |
| `spread_handling` | Paper-backed negative/undefined handling and half-spread conversion. |
| `warmup_policy`, `liquidation_cost_policy` | Explicit refusal until ready; preceding-session estimate for terminal close. |

Use `trial_registry`'s existing canonical serialization/hash. No parallel hash
format, dataframe, callable or nonfinite value belongs in this mapping. Source
manifest/hash and actual `volume_basis` belong to data provenance; per-fill
values/cutoffs belong to execution evidence, not a changing shared cost config.
Run identity, date and evidence digest link that execution evidence to the
trial. Every policy that changes a cost is part of the canonical configuration.

The caller resolves the model before `research_attempt`/`run_trial` records a
start. Supply commission and slippage via the existing `research_config`
defaults seam, not by hoping that a callable in `locals()` is a complete config.
The harness result retains `commission_per_trade` and the canonical `slippage`.
`Attempt.account` copies those actual costs to the sidecar without replacing
them with flat bps; compare against the started config and refuse divergence.

The binding is exact:

```
trial.config.slippage == executed_log.attrs.slippage
sidecar.metadata.costs == {
    "commission": trial.config.commission,
    "slippage": trial.config.slippage
}
```

Keep `selection_bias.py`'s `cost_mismatch`, `realistic_costs_missing` and
`matrix_cost_mismatch` checks intact. An acceptance fixture must satisfy all
earlier eligibility checks so a changed cost field reaches `cost_mismatch`;
use the public `build_matrix` outcome with the specific excluded-trial reason.
Separately prove actual fill arithmetic: identical false labels on config and
sidecar otherwise pass the equality check. Never promote `Attempt.account`'s
in-sample returns to `oos=True` or invent CV/action verification. Synthetic
eligibility fixtures do not authorize production Gate 3 admission.

Different robustness coefficients have different configs and remain outside
one same-cost selection matrix. Primary Y stays 1.0 regardless of robustness
results. Real inspected attempts retain 033 recording/counting obligations;
this design adds no silent recorder bypass.

## 4. Callers and reported surfaces

Wire the SMA caller and its buy-and-hold/random helpers with the same cost
dependency, warm-up history, comparison period and config. All other reportable
entry points must either use the same model or refuse result production; label
only explicitly unreported diagnostics. Inspect the existing 033 runner
inventory when implementing so a legacy CLI cannot quietly remain reportable.
Pinned 019 callers require the existing human gate before an edit, never an
automatic fingerprint update.

The tearsheet route removes the flat-bps query/default and returns actual model
config, breakdown/provenance and limitations through `BacktestTearsheetResponse`.
Update TypeScript contracts, API request builder, App parameter state and the
tearsheet controls/text together. Reject legacy flat-bps result requests rather
than silently accept and ignore them. Missing cost history/basis returns a
specific unavailable state without a successful numeric tearsheet.

Each result includes “costs modeled, not calibrated against real fills” beside
its costs and the existing data limitations. CLI output, baseline comparison,
API and rendered UI must agree. Remove fixed-5-bps friction claims and compute
any displayed cost total from recorded evidence. Existing historical results
are not relabelled as compliant. No global governance/disclosure rewrite is
authorized; independent S7 work remains separate.

## 5. Three implementation units — hard cap ≤300 lines each

The budget is added plus removed lines across the entire unit, including tests,
evidence and task-status changes, measured against pre-unit copies without Git.
These are three planned implementation units, not claims that their future
diffs are already known. Do not compress unreadable code, weaken tests or omit
a caller to fit. If complete scope exceeds a cap, stop for an explicit plan
revision before coding beyond it; this plan grants no automatic extra unit.
Human source/upstream gates precede these units and are not implementation.

| Unit | Files / responsibility | Acceptance and red proof |
|---|---|---|
| U1 — model + tests | New `scripts/cost_model.py`, `tests/test_046_cost_model.py`; verified source/oracle evidence in future `research.md`. | Paper oracle, trailing windows, boundaries, volume refusal, impact scaling, warm-up and primary/robustness config; M1–M4, M7, M10. |
| U2 — harness wiring | `scripts/backtest_harness.py`, `scripts/metrics.py`, `scripts/trial_runner.py`, `scripts/ma_crossover_backtest.py`; new `tests/test_046_cost_wiring.py`, narrowly scoped adaptations to existing accounting/caller tests. | Actual buy/sell/liquidation costs and affordability, reconciled funded returns, strategy/baseline parity, exact sidecar binding with unchanged 033 checks; M5, M6, M8. |
| U3 — API/report disclosure | `reports/api/routes/backtest.py`, `reports/api/schemas.py`, `reports/web/src/types/api.ts`, `reports/web/src/services/api.ts`, `reports/web/src/App.tsx`, `reports/web/src/components/views/BacktestTearsheetView.tsx`, CLI formatting in `scripts/ma_crossover_backtest.py`; new `tests/test_046_cost_reporting.py`, narrow `tests/test_reports_api.py`/`tests/test_no_fabricated_values.py` adaptations. | No flat result route/control, explicit unavailable states, exact config/limitation rendered on all affected surfaces and baseline rows; M9 plus M5 boundary regression. |

U2 and U3 share one caller file and execute sequentially. Any additional legacy
runner changes found by inventory must be explicitly budgeted/authorized before
editing; unmigrated paths cannot be declared complete. Existing tests migrate
to explicit diagnostic mode only where their purpose is synthetic accounting;
the new Rule 13 integration tests use the real estimator, not a flat stub.

## 6. Validation and remaining risks

Within future implementation, record each contract's intended red assertion,
then its green result, mutant kill and clean control. Run the repository suite
offline; run the existing frontend lint/build for U3, plus rendered-surface
checks (a type check alone does not prove disclosure). Never write production
ledger/caches or fetch market data as test setup.

Readiness is layered: source verified; offline model/accounting/report contracts
verified; upstream nominal-volume bundle available; separately authorized real
evidence produced; 033's independent gates satisfied. These are not synonyms.
The current 044 Q-P4 policy and 043 ledger guards can leave real-data acceptance
blocked even when the offline implementation passes. A paper mismatch or a
≤300-line budget overrun is reported, not hidden by changing D-1/D-2 or scope.
