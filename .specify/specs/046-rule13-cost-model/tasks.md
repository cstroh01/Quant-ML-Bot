# Tasks: Rule 13 cost model

**Input**: [spec.md](spec.md), [plan.md](plan.md).
**Status**: All tasks are future work and unchecked. This docs-only request
creates no implementation, tests, research file or evidence artifact.
**Order**: Single-threaded, dependencies below; no task authorizes Git, network,
production ledger/cache writes or changes to existing human gates.

## Standing rules

- D-1–D-3 and S3b placement are fixed. Published-source verification is not
  a tuning task. Every item explicitly marked **HUMAN GATE** requires its
  stated approval/evidence; other tasks do not become human gates by wording.
- `research.md` and `artifacts/` below mean future files inside this 046 folder.
  Files listed elsewhere are future implementation targets, not edits now.
- Tests go under `tests/`, use labelled synthetic fixtures/temporary ledgers,
  and never inspect real strategy results. Do not weaken existing assertions.
- M1–M10 refer to spec §5. Record initial contract red, unmutated green and
  mutation kill separately. A killed mutant must fail the named assertion or
  reason; an import error, unrelated exception or zero-test run is not evidence.
- Each U1/U2/U3 diff is ≤300 added-plus-removed lines including tests and
  evidence/status edits. Measure against pre-unit copies without Git. If a cap
  cannot cover the required scope, stop for a plan revision before exceeding
  it. Review never authorizes omitted checks or a silent fourth unit.

## Prerequisites — human verification, no implementation

- [ ] T001 **HUMAN GATE — published-source verification.** Files: future
  `research.md`, source fixture specification for `tests/test_046_cost_model.py`.
  **Task:** implement from the published paper; record the equation and page
  reference in research.md before coding. Verify estimator/version, half-spread
  conversion, negative/undefined policy, lags, oracle/tolerance, 21-session
  compatibility, daily sigma/return/split convention and square-root-law citation.
  **Acceptance:** a human reviewer checks each against the published source and
  independently checks the numerical oracle; missing evidence keeps the gate
  closed. **Rule 12 planted defect:** a review copy with the equation/page
  omitted or full spread substituted for half-spread must be rejected; the
  source-complete correct copy passes. **Depends on:** none.

- [ ] T002 **HUMAN GATE — upstream evidence and edit boundaries.** Files:
  `research.md` (future evidence record); read-only `docs/V1-FINISH-PLAN.md`,
  `docs/STATE.md`, 044 `spec.md`, 033 runner inventory
  `tests/fixtures/spec_033/runner_inventory.json`, and the plan's target files.
  **Acceptance:** record S1/035, S2 and 044 implementation prerequisites as
  complete before U1; otherwise keep U1 blocked. Explicitly keep
  real-data acceptance closed for `provider_unverified`; identify any pinned
  caller requiring human authorization and confirm a ≤300-line budget for each
  complete unit. No production bundle or permission is invented. **Rule 12
  planted defect:** an evidence checklist treating 044 completion or an
  unverified-volume manifest as sufficient must be refused; an explicitly
  qualified synthetic-only readiness record is the control. **Depends on:** T001.

## U1 — cost model and tests (≤300 changed lines)

- [ ] T003 Write source-backed contracts first. Files:
  `tests/test_046_cost_model.py`, future `research.md` oracle reference.
  **Acceptance:** independent spread/handling expected values, 4× Q → 2×
  impact with unchanged half-spread, all permitted/refused volume bases, and
  incomplete versus first-complete history cases fail for the intended missing
  behavior. **Rule 12 planted defects:** M2, M3, M4 and M7; register each exact
  failing assertion before implementation. **Depends on:** T002.

- [ ] T004 Add time and config contracts. Files:
  `tests/test_046_cost_model.py`. **Acceptance:** independently perturb future
  O/H/L/C/Volume at and after t+1 with fixed Q; include first/last/fold boundary,
  holiday versus missing-session, split-basis, malformed data and extra-return-lag
  cases. Assert primary Y=1.0, fixed windows, labelled robustness-only 0.5/2.0
  and config identity changes for altered conventions. **Rule 12 planted
  defects:** M1 and M10, plus treating missing bars as valid warm-up (M4).
  **Depends on:** T003.

- [ ] T005 Implement only the pure estimator and cost-domain types. Files:
  `scripts/cost_model.py`; contracts in `tests/test_046_cost_model.py`.
  **Acceptance:** T003/T004 pass with verified-source arithmetic, explicit
  unavailable reasons and per-fill breakdown/cutoff; no signals, sizing, P&L,
  download or ledger coupling. **Rule 12 planted defects:** execute M1–M4,
  M7/M10 against isolated implementations and require their named failures.
  **Depends on:** T004 and recorded T001 verification.

- [ ] T006 Close U1 evidence. Files: `tests/test_046_cost_model.py`, future
  `artifacts/u1.txt`, `tasks.md`. **Acceptance:** record collected count, named
  reds, green controls, all U1 kills and ≤300 changed lines including evidence.
  **Rule 12 planted defect:** a harness for mutation evidence that accepts a
  surviving centered-window M1 must fail the evidence check; clean evidence
  has a real assertion failure and a passing control. **Depends on:** T005.

## U2 — harness, reconciliation and recorder (≤300 changed lines)

- [ ] T007 Write execution contracts before wiring. Files:
  `tests/test_046_cost_wiring.py`, read-only `scripts/backtest_harness.py` and
  `scripts/metrics.py`. **Acceptance:** hand-enumerated buys/sells, actual exit
  Q after splits, terminal close cutoff, unaffordable entry, no-cost-unavailable
  fill, and strategy/baseline identical-config cases fail at the intended seam.
  Use the real estimator for the model-backed integration case. **Rule 12
  planted defects:** M5 and M8; a correct label with flat arithmetic must fail.
  **Depends on:** T006.

- [ ] T008 Inject cost estimation and reconcile actual fills. Files:
  `scripts/backtest_harness.py`, `scripts/metrics.py`,
  `tests/test_046_cost_wiring.py`; narrow adaptations in
  `tests/test_backtest_harness.py`, `tests/test_019_ledger.py`,
  `tests/test_019_metrics.py`, `tests/test_metrics.py` only where the cost
  interface changes. **Acceptance:** T007 passes; cash, fees, marks, quantities,
  receivables and reconciliation tolerance retain their contracts. Explicit
  flat diagnostics carry `not reportable (Rule 13)` and cannot be fallback.
  **Rule 12 planted defects:** M5/M8, including flat replay in metrics after a
  correctly modeled fill. **Depends on:** T007.

- [ ] T009 Bind real cost config through caller and recorder. Files:
  `scripts/trial_runner.py`, `scripts/ma_crossover_backtest.py`,
  `tests/test_046_cost_wiring.py`; read-only `scripts/selection_bias.py` and
  `tests/spec033_support.py`. **Acceptance:** preregister exact slippage via
  config defaults, retain executed config, and copy it unchanged into synthetic
  sidecars for strategy and both baselines. An otherwise eligible fixture is
  included by `build_matrix`; changing only a sidecar cost operand yields
  `cost_mismatch`. In-sample runs remain `oos=False`. **Rule 12 planted
  defects:** M6, omitted canonical policy M10, and M5's forged label.
  **Depends on:** T008.

- [ ] T010 Close U2 and inventory legacy paths. Files:
  `tests/test_046_cost_wiring.py`, future `artifacts/u2.txt`, `tasks.md`;
  read-only `tests/fixtures/spec_033/runner_inventory.json` and its named
  callers. **Acceptance:** actual accounting/config evidence and M5/M6/M8
  controls pass, ≤300 changed lines, and every remaining reported path has an
  explicit U3 migration/refusal owner; additional pinned edits wait on T002's
  human authorization and a budgeted plan revision. **Rule 12 planted defect:**
  an inventory copy omitting a known flat-cost reported entry point must fail
  the coverage check; full inventory is the control. **Depends on:** T009.

## U3 — API and report disclosure (≤300 changed lines)

- [ ] T011 Write report-boundary contracts first. Files:
  `tests/test_046_cost_reporting.py`, narrowly scoped
  `tests/test_reports_api.py` and `tests/test_no_fabricated_values.py` cases.
  **Acceptance:** assert actual model config and limitation on strategy and
  baseline output, legacy flat query refusal, missing-volume/history unavailable
  state, and no successful numeric result from diagnostic mode. **Rule 12
  planted defects:** M9 and M5; changing only a truthful label cannot rescue
  a flat-cost result. **Depends on:** T010.

- [ ] T012 Wire API/schema and CLI output. Files:
  `reports/api/routes/backtest.py`, `reports/api/schemas.py`,
  `scripts/ma_crossover_backtest.py`, `tests/test_046_cost_reporting.py`.
  **Acceptance:** T011 passes with explicit Rule 13 config, recorded breakdown,
  provenance and “costs modeled, not calibrated against real fills”; baseline
  and candidate share config/history policy. Unmigrated reported paths refuse.
  **Rule 12 planted defects:** remove disclosure, restore the flat query/default
  or bypass unavailable handling (M9); each goes red. **Depends on:** T011.

- [ ] T013 Update frontend cost contract and rendering. Files:
  `reports/web/src/types/api.ts`, `reports/web/src/services/api.ts`,
  `reports/web/src/App.tsx`,
  `reports/web/src/components/views/BacktestTearsheetView.tsx`,
  `tests/test_046_cost_reporting.py`. **Acceptance:** no flat-bps selector,
  request parameter or fixed-5-bps cost claim remains on reported surfaces;
  actual config/breakdown and limitations render with API fixtures, and the
  existing lint/build pass. Keep the same fixture for a rendered inspection
  without market access; compilation alone is insufficient. **Rule 12 planted
  defect:** restore the old flat-bps field/text or drop the displayed limitation
  (M9); the consuming contract/render assertion must fail. **Depends on:** T012.

- [ ] T014 Close U3 and offline acceptance. Files:
  `tests/test_046_cost_model.py`, `tests/test_046_cost_wiring.py`,
  `tests/test_046_cost_reporting.py`, future `artifacts/u3.txt`, `tasks.md`.
  **Acceptance:** record M1–M10 controls/kills, full offline suite counts and
  exit status, frontend checks, complete reported-path coverage and each unit's
  ≤300-line total. Original production-ledger bytes remain unchanged.
  **Rule 12 planted defect:** a completion report lacking one mutant's named
  failure/control or hiding a still-reportable flat path must fail acceptance;
  the complete evidenced report passes. **Depends on:** T013.

## Release evidence — separate human gate

- [ ] T015 **HUMAN GATE — real-data acceptance and review.** Files: future
  `artifacts/real-data-readiness.md`, `tasks.md`; read-only upstream bundle and
  approved run evidence. **Acceptance:** only after S1/S2/044 and verified-volume
  evidence, ledger permission and applicable review gates, check a separately
  authorized run's fill/config/source/disclosure evidence. If prerequisites are
  absent, record blocked real-data acceptance, not success. Do not edit upstream
  governance or fetch/write production data under this task. **Rule 12 planted
  defect:** a copied report with `provider_unverified` volume or mismatched
  costs must be refused even if labelled Rule 13; a verified consistent report
  is the control. **Depends on:** T014 and actual upstream evidence. This gate
  does not approve 033 thresholds, capital readiness, a merge or publication.

## Dependency summary

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 →
T011 → T012 → T013 → T014 → T015. Real-data evidence can remain blocked after
offline work; no task changes the decided coefficient, windows or S3b placement.
