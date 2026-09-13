# Implementation Plan: Terminal Truthfulness (Audit Stage 3.1)

**Branch**: `018-terminal-truthfulness` | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `.specify/specs/018-terminal-truthfulness/spec.md`

**Note**: This plan changes no production code. It is written for Camden's
review before `/speckit.implement` is run.

## Summary

The work splits along three independent axes; the details are in
[research.md](research.md).

**1. Truthfulness (findings 45, 46, 47, 48, 49, 36, 54).**
- Delete every fabricated figure from the API and the terminal.
- Replace each with an explicit status (R1, R2):
  - `not_computed` or `unavailable` for a computed quantity
  - `unknown` for a gate
- Fix the three derived values that were constants or wrong: holding bars,
  cost breakdown, unrounded export (R8, R9).
- Rewrite explanatory text so it describes what is displayed.

**2. Boundary validation (findings 03, 04, 50, 51).**
- Add one cost-domain rule, shared by the harness, accounting, the signal
  layer and HTTP (R6).
- Validate fill inputs before simulation (R7).
- Replace the literal reconciliation flag with a computed reconciliation
  result (R7).
- Add constrained HTTP requests with documented 4xx responses (R10).
- Restrict CORS (R11).

**3. Evidence the suite can be trusted (findings 57, 58, 29, 35).**
- Add a data and static-asset seam, so the API tests run on generated
  fixtures (R4).
- Make CI install the declared API dependencies, and build/lint the web
  terminal in its own job (R5).
- Fix exact McNemar (R12) and singular VIF (R13), each checked against an
  independent oracle.
- Add the three-layer fabricated-literal regression and an in-repository
  mutation runner (R3).

Delivery is one foundation PR, then one PR per user story, then a closing PR
for the mutation table (R15). None of them changes a research result or
reports a metric.

## Technical Context

**Language/Version**:
- Python 3.13 locally (`venv`) and 3.12 in CI (`.github/workflows/test.yml:15`).
  No syntax newer than 3.10.
- TypeScript ~6.0 for the web terminal (`reports/web/package.json`).

**Primary Dependencies** (all existing, none added):
- Python, from `requirements.txt`: numpy 2.5.2, pandas 3.0.5, scipy 1.16.2
  (`binomtest`), statsmodels 0.14.6 (existing McNemar; VIF oracle).
- Python, from `reports/requirements-ui.txt`: fastapi 0.141.1 (with its
  bundled pydantic v2), uvicorn 0.52.4, httpx 0.28.1.
- Web: React 19, Vite 8, oxlint (`reports/web/package.json`, locked by
  `package-lock.json`).

**Storage**: N/A. Test fixtures are written to per-test temporary directories.
No market data or artifacts are persisted.

**Testing**:
- `python -m unittest discover -s tests`: no network, fixtures generated in
  the tests.
- Web: `npm run lint`, and `npm run build` (the `tsc -b` type-check).
- There is no browser test suite; that is finding 55 (spec 038). UI text is
  checked by source scan (L3) plus type-check.

**Target Platform**: A local research workstation (Windows), and GitHub
Actions `ubuntu-latest`.

**Project Type**: A research library (`scripts/`), plus a read-only local
reporting API (`reports/api/`) and a web terminal (`reports/web/`).

**Performance Goals**:
- The new API fixture tests add under about 15 s to the suite; two
  ~300-session synthetic panels.
- The tearsheet's 20-seed random baseline runs on fixture-sized data only.
- The mutation runner is not part of the suite. It takes minutes and runs on
  demand.

**Constraints**:
- No network and no `data/cache/` reads in tests.
- No new dependency (Rule 6).
- No `git` (Rule 10).
- Session labels are naive and midnight-normalized (CLAUDE.md).
- Module boundaries, per CLAUDE.md and Complexity Tracking below.

**Scale/Scope**:
- **Findings**: 15.
- **Endpoints touched**: 5 of 9 (`/api/diagnostics/significance`,
  `/api/diagnostics/collinearity`, `/api/ml/rundown`,
  `/api/capital_gate/status`, `/api/backtest/tearsheet`), plus the app
  factory and CORS.
- **Web components touched**: 8 (Header, MLRundownPane, TabNavigation,
  CapitalGateView, FeatureDiagnosticsView, MarketDataView, CrossValidationView,
  BacktestTearsheetView), plus one new common component.
- **Library modules touched**: 6 (`backtest_harness`, `metrics`, `ml_signal`,
  `ma_crossover_backtest`, `feature_set_comparison`, `feature_diagnostics`),
  plus one new module (`cost_domain`) and one scratch script.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | Bearing on this plan | Status |
|---|---|---|
| 1 — Point-in-time | No feature, label or signal computation changes. `holding_bars_per_trade` counts positions between a completed trade's own recorded entry and exit sessions, which is after-the-fact accounting and not an input to any decision. The rundown still reads the last feature row, and its one-session staleness (finding 23) is untouched and recorded. | PASS |
| 2 — Purged walk-forward CV | No CV metric is produced or reported. The CV screen is relabelled as an illustration (FR-017), so it can no longer be read as a reported fold structure. | N/A |
| 3 — Costs | The tearsheet keeps its costs, and now shows commission and slippage separately, with spread marked not modeled (FR-010). The cost domain tightens (NaN, inf and ≥ 10000 bps rejected) without adding a costless mode. Zero cost stays an explicit parameter value, as specs 012 and 014 already use it. | PASS |
| 4 — Baselines | No strategy is proposed or modified. The tearsheet's existing buy-and-hold and 20-seed random rows are unchanged, apart from unrounded export. | N/A |
| 5 — Time tests | `holding_bars_per_trade` aligns trades to sessions, and ships with off-by-one, boundary (first row, same session, forced final exit) and gap (holiday) tests in the same PR (FR-038). Fixtures are built on `data.trading_days` sessions, so holiday gaps are real. | PASS |
| 6 — Dependencies | None added. CI starts installing the already-declared `reports/requirements-ui.txt`, whose Rule 6 justifications are in the file. **Flagged** in Complexity Tracking: `httpx` serves only the test client, against CLAUDE.md's "no test dependencies". | PASS — flag recorded |
| 7 — Execution | Nothing places an order; no `exec/`, no credentials. CORS is narrowed, not widened. | PASS |
| 8 — Layer separation | A new shared `scripts/cost_domain.py` is imported by the signal, execution and accounting layers and by the API. It carries no knowledge of any of them, but it is a new module outside the CLAUDE.md table and changes asserted import sets. Cost breakdown stays in the harness (its owner). Holding bars stay in `ma_crossover_backtest.py`, the one script that already sees both prices and trades. | PASS — Complexity Tracking entries 1–3 |
| 9 — Merge gate | Split into eight PRs (R15). Each is small enough to explain, and each states which findings it closes. | PASS — size flag recorded |
| 10 — Version control | No `git` in this run or in the plan. Workflow file edits are file edits; CI runs them. | PASS |

**Post-design re-check (after Phase 1):** unchanged.
- **Contracts**:
  - no new layer dependency beyond `cost_domain`
  - no response gains a figure without a computation behind it
  - no library function starts returning P&L it did not already return
- **Rule gap (reported, constitution not edited)**: no rule forbids an
  unsourced or fabricated number in a report or UI. Rule 3 covers only
  costless figures. FR-037 enforces a project convention the constitution
  does not state. Recorded in the handoff for Camden.

## Project Structure

### Documentation (this feature)

```text
.specify/specs/018-terminal-truthfulness/
├── spec.md
├── plan.md                         # this file
├── research.md                     # R1–R15
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api-responses.md            # endpoint bodies before/after, error body
│   ├── library-boundaries.md       # cost_domain, harness, metrics, stats
│   └── regression-and-mutation.md  # L1/L2/L3 rules, allowlist, mutant list
├── checklists/
│   └── requirements.md
└── tasks.md                        # /speckit.tasks
```

### Source Code (repository root)

```text
.github/workflows/
└── test.yml                              # + UI deps install; + separate `web` job

scripts/
├── cost_domain.py                        # NEW — one cost-domain rule (FR-022)
├── backtest_harness.py                   # input validation; non-finite summary; trade_cost_breakdown
├── metrics.py                            # cost_domain; finite reconciliation; reconciliation_report
├── ml_signal.py                          # _validate_costs delegates cost domain to cost_domain
├── ma_crossover_backtest.py              # holding_bars_per_trade (mean_holding_bars reuses it)
├── feature_set_comparison.py             # exact one-sided McNemar (FR-028)
├── feature_diagnostics.py                # regression VIF with inf/undefined (FR-029)
├── features.py                           # comment at :39-42 only (FR-016)
└── scratch_multiticker_collinearity.py   # imports the one VIF implementation

reports/api/
├── main.py                               # create_app(cache_dir?, dist_dir?); CORS; start() loopback
├── schemas.py                            # status types; gate evidence; cost breakdown; VIF value
└── routes/
    ├── data.py                           # get_cache_dir dependency (seam)
    ├── diagnostics.py                    # significance not_computed; VIF serialization; unrounded
    ├── ml_rundown.py                     # forecast not_computed; rule readings only
    ├── capital_gate.py                   # all gates unknown; no pass rules; test-run status
    └── backtest.py                       # validated request; holding bars; costs; reconciliation

reports/web/src/
├── types/api.ts                          # mirror schema changes
├── App.tsx                               # pass test-run status to Header
└── components/
    ├── common/NotComputedNotice.tsx      # NEW — the one "not computed" UI state
    ├── layout/{Header,MLRundownPane,TabNavigation}.tsx
    └── views/{CapitalGate,FeatureDiagnostics,MarketData,CrossValidation,BacktestTearsheet}View.tsx

tests/
├── api_fixtures.py                       # NEW helper (not collected): seeded synthetic panels
├── test_reports_api.py                   # rewritten on fixtures; asserts honest states
├── test_terminal_truthfulness.py         # NEW — L1 differential, L2 static, L3 UI scan
├── test_cost_domain.py                   # NEW — domain table, library + HTTP boundary
├── test_backtest_harness.py              # + input validation, cost breakdown oracle
├── test_metrics.py                       # + non-finite reconciliation
├── test_ml_signal.py                     # import-set assertion updated (:671-675)
├── test_ma_crossover_backtest.py         # + holding_bars_per_trade Rule 5 tests
├── test_feature_scaling.py               # + McNemar and VIF oracles
└── mutation/
    └── run_spec_018_mutants.py           # NEW — not collected; copies tree, runs mutants

.specify/specs/014-scale-free-features/spec.md   # appended dated audit note (FR-016)
```

**Structure Decision**:
- **Existing layout kept**: library changes stay in their owning modules
  under `scripts/`, API changes stay in `reports/api/`, UI changes in
  `reports/web/src/`.
- **New files, four**:
  - `scripts/cost_domain.py`: the shared rule.
  - `NotComputedNotice.tsx`: the single UI state.
  - `tests/api_fixtures.py`: a helper module, named so discovery skips it,
    like `tests/context.py`.
  - `tests/mutation/`: not a package and not `test*.py`, so discovery skips it.
- **Not touched**: `scripts/signals.py`, `scripts/data.py`,
  `scripts/targets.py`, `scripts/portfolio_risk.py`, `.specify/specs/017-*`,
  `.specify/memory/constitution.md`, `CLAUDE.md`.

## Design

### Order of work and PR split (R15)

| PR | Content | Findings closed | Depends on |
|---|---|---|---|
| **A — Foundation** | App factory and cache seam; fixture helper; `test_reports_api.py` rebuilt on fixtures with the two defect-asserting checks removed; CI UI-deps install; `web` job; mutation runner skeleton with control run | 57 | — |
| **B — US1** | Significance, rundown and gate truthfulness; header badge; `NotComputedNotice`; L1/L2/L3 regression over the endpoints B covers, with explicit pending-coverage entries for tearsheet fields owned by D | 45, 46, 47 (and FR-015's rundown-volume part of 49, FR-016's `capital_gate.py:28` part of 36) | A |
| **C — US2** | `cost_domain`; harness input validation; non-finite summary and reconciliation; computed reconciliation report; HTTP request validation; L2 rule for pass-flag literals | 03, 04, 50 | A, B (regression infra) |
| **D — US4** | Holding bars; cost breakdown; unrounded export; McNemar; VIF with serialization; tearsheet added to L1 coverage (pending list emptied for the tearsheet) | 48, 29, 35 | A, B, C (cost breakdown uses validated costs) |
| **E — US5** | Gate decoder, p-value, conditioning, Kelly and correlation text; CV illustration label; SMA label; features.py comment; spec 014 note | 49, 36, 54 | B (rundown and gate text already honest) |
| **F — US6** | CORS allowlist, no credentials, GET only; loopback bind test | 51 | A |
| **G — Oracles and mutation closure** | Coverage-completeness test (every `/api` GET route covered, pending list empty); full mutant run; result table recorded in tasks.md | 58 | B–F |

Why the regression grows per PR instead of landing whole in B: L1 would
immediately flag `holding_bars=1` (finding 48, PR D) and the reconciliation
literal (finding 03, PR C). Hiding them with a temporary allowlist would be
exactly the defect the regression exists to stop. Instead, each PR adds
coverage that fails on its own pre-fix code. An explicit
`PENDING_COVERAGE` table names each uncovered field and the PR that owns it,
and PR G asserts that table is empty.

### Key design points (details in research and contracts)

- **Status, not absence** (R1): `not_computed` is a 200 response carrying a
  reason. `unavailable` stays the loader's 404. An error status code would
  land in `App.tsx`'s `.catch(() => null)` and show an endless spinner (finding
  53), which is indistinguishable from loading.
- **Gate evidence** (R2): `status ∈ {passed, failed, stale, unknown}`. A
  response-model validator rejects any non-`unknown` status whose `evidence`
  is empty. PR B returns `unknown` for all five gates. The header reads a new
  `test_run` status from the same response.
- **Reconciliation** (R7): `metrics.reconciliation_report` returns
  `{passed, abs_difference, tolerance}`, with `passed` false for any
  non-finite side. `equity_curve` keeps raising on failure, as its existing
  contract and tests require. The route reports the computed object; a
  failure on validated input is a server fault (500 with explicit detail),
  never a normal tearsheet.
- **Cost breakdown** (R8): `backtest_harness.trade_cost_breakdown` inverts
  the recorded slipped fills (`raw = fill/(1+s)` on entry, `fill/(1−s)` on
  exit), because the harness owns the cost model. Its oracle reruns the
  harness at zero cost and checks `costless − net = commission + slippage`
  within 1e-9.
- **Regression** (R3, [contracts/regression-and-mutation.md](contracts/regression-and-mutation.md)):
  three layers — L1 differential over two fixtures with opposite drift; L2
  AST scan of routes and schemas; L3 UI source scan. Allowlist entries name a
  field, a category and a reason, and text entries carry a permitted-figure
  pattern.

## Complexity Tracking

> Each entry is a boundary crossing, a convention tension or a size concern.
> None is resolved silently; entries marked **FLAG** need Camden's call.

| # | Crossing / tension | Why needed | Simpler alternative rejected because |
|---|---|---|---|
| 1 | **New module `scripts/cost_domain.py` outside the CLAUDE.md module table** (FLAG). Imported by `ml_signal.py` (signal), `backtest_harness.py` (execution), `metrics.py` (accounting) and `reports/api/routes/backtest.py`. | Finding 04 is three independently written copies of one domain rule, `x < 0`, each accepting NaN. The plan asks for one validator. The module imports only `math` and knows nothing of signals, fills or P&L. | *Copy plus equivalence test* (the spec 012 `signal_from_positions` precedent): keeps three copies of a rule whose drift is the defect. *Put it in `constants.py`*: that module is importless by design, and a validator is behaviour, not a constant. *Import it from the harness in `ml_signal`*: forbidden by spec 012 FR-009. The CLAUDE.md table needs a row; CLAUDE.md is not edited this run. |
| 2 | **Asserted import sets change.** `tests/test_ml_signal.py:671-675` pins `ml_signal`'s imports to exactly `{"__future__", "numpy", "pandas"}`; `cost_domain` must be added. `backtest_harness.py` gains its first project import. | Direct consequence of entry 1. The forbidden-import assertion (`:677-691`, spec 012 FR-009) is unchanged and still passes. | Leaving the exact set unchanged forces the copy approach rejected in entry 1. The assertion is widened by exactly one name, with a docstring citing this spec. |
| 3 | **`backtest_harness.py` gains `trade_cost_breakdown`, and `metrics.py` gains `reconciliation_report`** (report-facing helpers). | The harness owns costs, so decomposing costs belongs where the cost model is defined; accounting owns reconciliation. Putting either computation in the API route would re-implement execution arithmetic in the reporting layer. | Computing in the route: crosses into the harness's ownership. Adding columns to `TRADE_LOG_COLUMNS`: changes a frame schema that `metrics.py`, `ma_crossover_backtest.py`, `multi_ticker_comparison.py` and their tests depend on, for a reporting need. |
| 4 | **CI installs `reports/requirements-ui.txt`, whose `httpx` is used only by the FastAPI test client** (FLAG). CLAUDE.md: "No network access, no test dependencies." | The API tests import `fastapi.testclient`, and FR-025 requires the HTTP boundary itself to be tested. The dependency is already declared, with a Rule 6 justification naming this exact use. | `unittest.skipUnless(fastapi)`: CI would silently skip the very tests finding 57 is about. Calling route functions directly: never exercises query parsing, validation errors or CORS. Removing the API tests: removes the pass condition's third clause. |
| 5 | **Mutation runner under `tests/mutation/`** (FLAG). A new directory holding tooling, not tests. | Finding 58 requires mutation scripts in the repository; spec 017's runner lived in a lost scratchpad. Placing it beside the tests it mutates keeps it discoverable to reviewers while unittest skips it (not a package, not `test*.py`). | `scripts/`: that directory is on the tests' `sys.path` and holds research modules and entry points; a runner that rewrites copies of `scripts/` does not belong among them. |
| 6 | **Appending to merged spec 014's `spec.md`** (FLAG). | Finding 36 names spec 014 as a place that presents conditioning as the fix. FR-016 appends a dated audit note and preserves the original text, per finding 67's "keep history". | Rewriting the spec: erases the record of what was believed. Leaving it unchanged: leaves the uncorrected claim where the next agent reads it. |
| 7 | **Editing `scripts/scratch_multiticker_collinearity.py`** (FLAG). | Finding 35 names its duplicate VIF. It is replaced by an import of the fixed implementation. | Deleting the scratch script is plausibly right, but deleting files is Camden's call. |
| 8 | **Stories share files.** `ml_rundown.py` serves 46 (US1) and 49's volume narrative (US5); `capital_gate.py` serves 47 (US1) and 36 (US5). | Splitting one file's rewrite across two PRs would leave the rundown half-honest between them. | PR B does both parts in those two files. PR E handles 49 and 36 everywhere else. Tasks mark the cross-story coverage explicitly. |
| 9 | **Size** (FLAG). Around 15 production files, 8 UI components and 9 test files. | Stage 3.1 is 15 findings by the plan's own grouping. The run request puts all of them in one spec. The plan's proposed 018–021 split is not used. | One PR: not reviewable line by line, which is a CLAUDE.md hard constraint. Hence the eight PRs above, each with a stated scope. |
| 10 | **Fixture file named with the loader's primary cache filename.** | It exercises the loader's primary branch rather than the arbitrary-CSV glob fallback that finding 18 (spec 027) deletes. | Relying on the glob fallback: couples the tests to code scheduled for removal. Spec 027 replaces the loader, and this fixture writer with it. |
