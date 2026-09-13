# Feature Specification: Terminal Truthfulness (Audit Work Order 1)

**Feature Branch**: `018-terminal-truthfulness`

**Created**: 2026-09-12. **Re-scoped**: 2026-09-12.

**Status**: PRs A–C implemented in the working tree, uncommitted, awaiting
Camden's review. PRs D–E not started.

**Input**: Work order 1 of `docs/audit-2026-09-12/AUDIT.md` (line 229),
*Honest dashboard and adversarial regressions*.

## Re-scope

The first draft took its scope from `REMEDIATION_PLAN.md` Stage 3.1 (15
findings), a document derived from the audit, while the audit's own work
order 1 lists 10. The audit is the source, so it wins. Five findings moved to
later specs (below), and this file went from 49.6 KB to under 15 KB.
`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` and
`checklists/` predate the re-scope; where they conflict with this file or
`tasks.md`, they are superseded.

## Scope: exactly work order 1 (03–04, 45–50, 57–58)

Line numbers refer to commit `555343e`.

| ID | P | Defect | Where | PR |
|---|---|---|---|---|
| 45 | P0 D | Significance endpoint returns four literal p-values, identical for every ticker | `reports/api/routes/diagnostics.py:81-126`; `FeatureDiagnosticsView.tsx:141-194` | B |
| 46 | P0 D | `P(Up) = 54.2%` and `Logit Score = +0.17` literals; indicator sign tests presented as a model's prediction | `reports/api/routes/ml_rundown.py:52-93`, `:170-229`; `MLRundownPane.tsx`; `Header.tsx:90-102` | B, C |
| 47 | P0 D | Gate 1 hardcoded `passed` with "301 passed"; header "311/311 PASS"; no distinct unknown/failed/stale states | `reports/api/routes/capital_gate.py:15-22`; `schemas.py:114-120`; `Header.tsx:104-108`; `CapitalGateView.tsx:27`, `:41`, `:74-151` | B, C |
| 03 | P0 D | NaN fills and signals yield a normal tearsheet; `reconciliation_passed=True` literal | `scripts/backtest_harness.py:13`, `:108`; `reports/api/routes/backtest.py:168` | D |
| 04 | P0 D | Cost checks accept NaN and infinity; `slippage_bps=10000` accepted | `scripts/ml_signal.py:47`; `backtest_harness.py`; `routes/backtest.py:39-40` | D |
| 50 | P1 D | Invalid windows and costs return 500 or 200 | `reports/api/routes/backtest.py:34-41` | D |
| 48 | P1 D | `holding_bars=1` literal; commission-only "friction"; rounded export | `routes/backtest.py:101-167`; `schemas.py:77`; `BacktestTearsheetView.tsx:92-93`, `:158-159` | E |
| 49 | P1 D | Gate decoder mismatch; p-value as "chance of luck"; Kelly teaching; unknown correlation shown as 0.00; volume as institutional flow | `CapitalGateView.tsx:60-69`; `FeatureDiagnosticsView.tsx:47-61`, `:203`, `:226`; `MarketDataView.tsx:56`, `:86`; `ml_rundown.py:145-168` | B (rundown), E (rest) |
| 57 | P1 D | CI cannot import the API tests; 7 of 11 fail on a clean checkout | `.github/workflows/test.yml:16`; `tests/test_reports_api.py`; `routes/data.py:26-57`; `main.py:53-56` | A |
| 58 | P1 G | Tests assert response shape, not truth; mutation evidence lives outside the repository | `tests/` | C (regression, runner); D (all-NaN oracle) |

### Moved to later specs

Names and numbers are `REMEDIATION_PLAN.md`'s proposals (its line 9), not
assigned numbers. Camden assigns them.

| ID | Moves to | Reason |
|---|---|---|
| 29 | Inference and multiple testing (proposed 035) | Audit work order 5. A statistics fix to the research comparison; no terminal value depends on it, and all four saved entries lie in the direction the old formula gets right. |
| 35 | Diagnostics correctness (proposed 020) | In no audit work order. A library VIF defect that fabricates no terminal value. |
| 36 | Diagnostics correctness (proposed 020) | In no audit work order. What conditioning proves is best restated alongside the VIF fix that changes those numbers. |
| 51 | Terminal reliability (proposed 038) | Audit work order 6. The API already binds loopback (`main.py:62`) and serves read-only routes. |
| 54 | Terminal reliability (proposed 038) | Audit work order 6. Honest fold and run labels need the run identity finding 53 introduces there. |

### Lane boundary during the parallel run

A second agent is rewriting the core modules (`data.py`, `features.py`,
`targets.py`, `metrics.py`, `backtest_harness.py`, `ml_signal.py`,
`estimators.py`, `model_cv.py`) under spec 019. Spec 018 does not edit them,
or `requirements.txt`. Two consequences:

- The library halves of 03 and 04 live in those modules. Spec 018 owns only
  their HTTP halves (PR D). Whether spec 019 absorbs the library halves, or
  spec 018 takes them after 019 merges, is Camden's decision.
- Test-only dependencies go in a new `requirements-dev.txt`.

### Explicitly excluded

- **Computing real values.** Every fabricated value becomes an explicit *not
  computed* response and screen state. Wiring saved runs, fitted-model
  inference or verification artifacts is audit work order 3. No gate can
  report `passed` until then.
- The gate rule texts "Sharpe <= 0.3" and "remains positive" are finding 30's.
  They stay as descriptions of what a gate would require; no gate claims them.
- Everything else in these files: the stale as-of date (23), the fallback
  ticker list (18), the risk-free label (12), request races and error states
  (52, 53), the `parents[2]` import path (56), and CI permissions (63).
- No experiment is rerun and no metric is reported.

## Acceptance: the audit's pass condition, verbatim

> No fabricated forecast/p-value/pass badge; malformed inputs cannot yield a successful result; clean API fixtures

Clause 1 maps to SC-001 and SC-002, clause 2 to SC-003, clause 3 to SC-004 and
SC-005.

## User Stories

### US1: No fabricated evidence reaches the terminal (P1; 45, 46, 47, 58)

Every forecast, p-value, gate state and test count on the terminal comes from
a computation, or says plainly that none exists.

**Independent test**: serve the API from two generated panels. No response or
component states a p-value, forecast probability, model score, test count or
evidence-free gate state. The same tests fail against the pre-018 code,
naming each literal.

### US2: Malformed input cannot yield a successful result (P1; 03, 04, 50)

**Independent test**: a table of malformed prices, signals, costs and
requests. Every library row raises before simulating; every HTTP row returns
a documented 4xx.

### US3: API tests pass on a clean checkout (P1; 57)

**Independent test**: in a copy with no `data/cache/`, no
`reports/web/dist/`, no network and the declared dependencies installed, the
API tests pass and none is skipped.

### US4: Derived numbers and explanations say what is shown (P2; 48, 49)

**Independent test**: hand-counted holding bars and cost breakdown on a
fixture. The capital gate decoder names the API's gates in order. No screen
teaches p-value-as-luck or Kelly, or shows an unknown correlation as 0.00.

## Requirements

### Fabricated evidence (45, 46, 47: PR B for the API and header, PR C for the other screens)

- **FR-001** *(45)*: The significance endpoint returns, for every ticker,
  `status: "not_computed"` and a non-empty `reason`, with no p-value, alpha,
  pass flag or entry list. The screen shows a *not computed* notice in place
  of the table.
- **FR-002** *(46)*: The rundown returns `model_forecast: {status:
  "not_computed", reason}` and no probability, logit or score. Its five items
  are indicator rule readings.
  - No text says a model predicts, detects, advises or flags.
  - No pane, tab or header label calls the readings ML or model output.
  - Unmeasured claims in the same text are deleted: "2-standard-deviation
    stretch", "significantly higher win rates", a named "theorem", "30-50%",
    "$2.00 + 10 bps", "probability > 55%".
- **FR-003** *(47)*: A gate's status is exactly one of `passed`, `failed`,
  `stale` or `unknown`, in the API schema and the UI type. The schema rejects
  every state except `unknown` without an evidence reference. With no
  artifact reader, every gate is `unknown` with no evidence, and its details
  carry no test count or unsourced figure.
- **FR-004** *(47)*: The gate status response carries `test_run: {status:
  "not_computed", reason}`. The header shows tests *not reported*, with no
  count, success colour or pulse. The gate summary counts against the number
  of gates returned, not a literal.
- **FR-005**: A *not computed* notice looks different from loading, passed and
  failed: neutral grey, no spinner, no pulse.

### Malformed input (PR D: 03, 04, 50)

- **FR-006** *(03)*: Before simulating, the harness rejects non-finite or
  non-positive fill prices and any signal column that is not exactly boolean.
  A non-finite trade P&L or total fails. A reconciliation comparison fails
  when either side is non-finite. *Library half: see Lane boundary.*
- **FR-007** *(03)*: The tearsheet's reconciliation flag reflects that
  request's reconciliation, never a literal. The screen shows *reconciled*
  only when it is true.
- **FR-008** *(04)*: One cost domain at every public entry point: commission
  finite and ≥ 0; slippage finite and in [0, 10000) bps. Zero stays valid. One
  out-of-domain table (NaN, ±inf, negative, 10000, and a non-numeric string
  over HTTP) runs at both the library and HTTP boundaries.
- **FR-009** *(50)*: The tearsheet request enforces integer windows,
  `short_window ≥ 1`, `long_window > short_window`, a documented upper bound,
  costs per FR-008, and a servable ticker. An invalid request returns a
  documented 4xx naming the parameter, never 500 and never a tearsheet body.

### Derived values and explanations (PR E: 48, 49)

- **FR-010** *(48)*: A trade's holding period is the number of sessions
  between entry and exit in the simulated frame, and the field has no default.
  Commission and slippage are separate totals from that request's fills.
  Spread is *not modeled*, never zero. Responses carry unrounded values; the
  UI rounds for display.
- **FR-011** *(49)*: The capital gate decoder describes the gates the API
  returns, in order. No screen describes a p-value as the chance a result is
  luck, prescribes discarding a model by p-value, teaches Kelly sizing, shows
  a missing correlation as 0.00, or describes relative volume as
  institutional flow. The rundown's volume narrative went in PR B.

### Clean CI (PR A: 57)

- **FR-012**: CI installs every dependency the suite imports: `requirements.txt`
  plus a new `requirements-dev.txt` holding test-only packages, pinned to
  their existing declarations in `reports/requirements-ui.txt`. A test fails
  if the pins drift. `requirements.txt` is not edited.
- **FR-013**: Routes read market data through an injectable dependency,
  `get_cache_dir`. API tests serve seeded synthetic panels written to a
  temporary directory, and never read `data/cache/` or the network. A test
  fails if a route bypasses the dependency.
- **FR-014**: An app factory takes the static-asset directory, and the static
  test serves a directory it creates. A separate CI job installs the locked
  web dependencies, then lints and builds the terminal.
- **FR-015**: Tests that passed only by asserting fabricated values are
  rewritten to assert the *not computed* contract, not deleted.

### Regressions (PR C, D: 58)

- **FR-016**: A fabricated-value regression fails against the pre-018 code
  and passes after, in three layers:
  1. **Responses** from two generated panels that differ in every price and
     in length. No text states a fabricated value, and no number is identical
     across both panels unless allowlisted with its reason.
  2. **Route source**, by AST, covering branches no fixture reaches.
  3. **Terminal component source.**
- **FR-017**: A mutation runner lives in the repository (finding 58). It
  restores each deleted literal in a copy, runs an unmutated control first,
  hashes the sources before and after, and its table is recorded in
  `tasks.md`. A mutant is caught only if it fails a test the control does
  not.
- **FR-018**: PR D adds the all-NaN-price oracle at the library and HTTP
  boundaries. The funded-ledger, overnight-timing, planted-signal and
  whole-pipeline-perturbation oracles belong to the specs that build their
  subjects.

### Process

- **FR-019**: Delivered as separately reviewable PRs referencing spec 018,
  each at most about 400 diff lines including tests:
  - **A**: clean CI (57).
  - **B**: the API for 45, 46 and 47, plus the header and the one screen the
    new responses would otherwise break.
  - **C**: the remaining screens, the regression and the mutation runner.
  - **D**: malformed input (03, 04, 50).
  - **E**: derived values and explanations (48, 49).

  This run delivers A–C.
- **FR-020**: No new runtime dependency (Rule 6). No `git` (Rule 10).

## Success Criteria

- **SC-001** *(clause 1)*: The regression passes on the post-018 code and fails
  on the pre-018 code for: the significance p-values and alpha; the
  `P(Up)`/`P(Down)`/logit literals; model attribution; Gate 1 `passed` and
  "301"; the header's "311/311 PASS"; the literal gate total.
- **SC-002** *(clause 1)*: The mutation check catches every mutant, and the
  source hashes are identical before and after.
- **SC-003** *(clause 2)*: Every malformed row fails explicitly. Malformed
  library input produces 0 trade logs. Malformed HTTP requests get a
  documented 4xx 100% of the time, and 0 of them return 200 or 5xx.
- **SC-004** *(clause 3)*: The API test modules pass in a copy with no
  `data/cache/` and no `reports/web/dist/`, with none skipped. They cover at
  least the 11 behaviours covered before.
- **SC-005** *(clause 3)*: CI's Python job installs only declared files, and
  the web job lints and builds.
- **SC-006** *(48, 49)*: Holding bars equal hand-counted sessions. Commission
  plus slippage equals costless minus net P&L within 1e-9. Spread is reported
  as not modeled. The decoder matches the API's gate titles and order.

## Assumptions and Flags

- Fixtures are generated inside tests. A committed CSV would be ignored by
  `.gitignore` (`*.csv`), and CLAUDE.md forbids committing market data.
  Fixture sessions are weekdays; nothing the API tests assert depends on the
  exchange calendar.
- `httpx` is a test-only dependency, which is in tension with CLAUDE.md's "no
  test dependencies". Camden directed `requirements-dev.txt`; the tension is
  recorded, not resolved.
- `/api/ml/rundown` keeps its URL, and `MLInsightItem` its name, so no
  contract is renamed that no finding requires.
- **Mid-run, the core lane changed two contracts the routes consume.**
  - `build_features` now keeps warm-up rows. The collinearity route therefore
    diagnoses complete rows only, which is a no-op under the old contract.
  - `run_backtest` now requires prices declared as unadjusted dollars. The
    tearsheet route reads the adjusted cache and cannot honestly declare
    that, so its API test fails against the in-flight harness. This is
    flagged for the lanes to reconcile (tasks T024), not patched.
