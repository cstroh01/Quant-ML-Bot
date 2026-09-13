---
description: "Task list for spec 018 — Terminal Truthfulness (audit work order 1), re-scoped"
---

# Tasks: Terminal Truthfulness (Audit Work Order 1)

**Input**: `spec.md` in this directory, re-scoped on 2026-09-12 to
`AUDIT.md` work order 1.

**Tests**: Required. Each regression is shown failing against the pre-018
code before it is recorded as passing.

**Rules**: No `git` (Rule 10); Camden commits. While the parallel lane is
open, no edits to the core modules or to `requirements.txt`.

**Line counts** are changed lines (+ and −), measured with GNU `diff -u`
against a snapshot taken before any edit, not with git. Where one file spans
two PRs, the split is by hunk and is named in the task.

## PR A: Clean CI (57). 333 lines. Done, uncommitted.

- [x] T001 Create `requirements-dev.txt` with `fastapi==0.141.1` and `httpx==0.28.1`, the same pins as `reports/requirements-ui.txt`.
- [x] T002 In `.github/workflows/test.yml`:
  - The `test` job installs `requirements.txt` and `requirements-dev.txt`.
  - A new `web` job runs `npm ci`, `npm run lint` and `npm run build` in `reports/web` on Node 24.
- [x] T003 In `reports/api/routes/data.py`:
  - Add a `get_cache_dir()` dependency.
  - `get_cached_ticker_data(ticker, cache_dir)` takes the directory, with no default.
  - Every data route declares `cache_dir: Path = Depends(get_cache_dir)`.
- [x] T004 Thread `cache_dir` through `diagnostics.py` (collinearity), `ml_rundown.py` and `backtest.py`. These are the A hunks of those files.
- [x] T005 In `reports/api/main.py`, add `create_app(*, dist_dir=DIST_DIR)` and keep a module-level `app = create_app()`. CORS is unchanged, because finding 51 moved out.
- [x] T006 Create `tests/api_fixtures.py`. Test discovery does not collect it.
  - `synthetic_panel(seed, sessions, drift, tickers)`, plus `FIXTURE_A` (seed 1, 320 sessions) and `FIXTURE_B` (seed 2, 347 sessions).
  - `fixture_client(test, panel, dist_dir=)` overrides `get_cache_dir` with a temporary directory, and points the module-level cache path at a directory that does not exist.
- [x] T007 Move `tests/test_reports_api.py` onto the fixtures (its A hunks).
  - All 11 behaviours are kept.
  - `test_list_tickers` asserts the fixture's tickers instead of passing on the fallback list.
  - `test_static_frontend_root` serves a directory the test creates.
  - New class `TestCleanCheckoutSeams`: one test fails if a route bypasses the dependency, one if the dev pins drift.
- [x] T008 **Added mid-run.** The collinearity route in `diagnostics.py` now diagnoses complete rows only.
  - The core lane's in-flight `build_features` began keeping warm-up rows, and `diagnose` then raised `SVD did not converge`.
  - Under the old contract this change is a no-op.

## PR B: The API stops fabricating (45, 46, 47). 391 lines. Done, uncommitted.

- [x] T009 In `schemas.py`:
  - Add `NotComputed`.
  - `SignificanceResponse(NotComputed)` carries `ticker` and replaces `SignificanceEntry`.
  - `CapitalGateItem.status` becomes `Literal["passed","failed","stale","unknown"]`, and a validator requires evidence for every state except `unknown`.
  - Add `CapitalGateStatusResponse.test_run` and `MLRundownResponse.model_forecast`.
- [x] T010 In `diagnostics.py` (its B hunks), significance returns `not_computed` and a reason for every ticker. The four literal entries and `screening_alpha` are deleted.
- [x] T011 In `capital_gate.py`:
  - Every gate is `unknown`, with no evidence, and `test_run` is not computed.
  - The "301" texts and Gate 2's literal figures are deleted.
  - Gate descriptions are unchanged; their rule texts belong to finding 30.
- [x] T012 In `ml_rundown.py` (its B hunks), `model_forecast` is not computed, and item 1 becomes "SMA Rule Agreement". Deleted:
  - the three `P(...)`/logit literals
  - every "model predicts", "detects", "flags" or "advises"
  - the "$2.00 + 10 bps" and "probability > 55%" advice
  - "2-standard-deviation stretch", "significantly higher win rates", the named theorem and "30-50%"
  - the institutional-flow narrative (finding 49's rundown part)
- [x] T013 In `FeatureDiagnosticsView.tsx`, the significance table becomes a `NotComputedNotice`.
  - New component `components/common/NotComputedNotice.tsx`: neutral grey, no spinner, no pulse.
  - It ships in B because the old table would crash on the new response.
- [x] T014 In `Header.tsx` and `App.tsx`:
  - The badge reads "TESTS: NOT REPORTED", with the reason as its title, fed by `test_run`.
  - The pane toggle's title no longer says "ML Model".
- [x] T015 `types/api.ts` (its B hunks): `NotComputed`, `SignificanceResponse`, `CapitalGateStatusResponse.test_run` and `MLRundownResponse.model_forecast`.
- [x] T016 In `tests/test_reports_api.py` (its B hunks), three tests are rewritten, not deleted:
  - `test_significance_screening`: AAPL and NVDA are both not computed; the response keys are exactly ticker, status and reason.
  - `test_capital_gate_status`: all five gates are unknown, with no evidence, and the test run is not computed.
  - `test_ml_rundown`: the forecast is not computed.

## PR C: Screens, regression, mutation check (45, 46, 47, 58). 401 lines. Done, uncommitted.

- [x] T017 `types/api.ts` (its C hunks): `GateEvidenceStatus` and `CapitalGateItem.status`. These ship with `CapitalGateView.tsx`, because the old view's `'in_progress'` comparison does not type-check against the new union.
- [x] T018 In `CapitalGateView.tsx`, each evidence state gets its own chip, and the summary counts against `gates.length`.
- [x] T019 In `MLRundownPane.tsx`:
  - The forecast renders as a `NotComputedNotice`.
  - The pane, tab, loading, verdict and guide text are relabelled as indicator rule readings.
  - "How to Plan & Trade" becomes "Limits of This Reading".
- [x] T020 Create `tests/test_no_fabricated_values.py`, with four layers:
  - **Responses**: text patterns, and a number identical across `FIXTURE_A` and `FIXTURE_B` fails unless allowlisted. A stale allowlist entry also fails.
  - **Gate schema**.
  - **Route AST**.
  - **UI source**.

  It also self-tests its patterns against verbatim pre-018 literals.
- [x] T021 Create `tests/mutation/run_spec_018_mutants.py`, not collected by discovery. It follows spec 017's T030 shape, but lives in the repository.
- [x] T022 Record the evidence below.

## PR D: Malformed input (03, 04, 50, 58). Not started.

- [ ] T023 Camden decides whether spec 019 absorbs the library halves of 03 and 04 (`backtest_harness.py`, `metrics.py`, `ml_signal.py`), or 018 takes them after 019 merges. Read 019's final harness first: its in-flight `run_backtest` already validates costs, dates, prices and actions.
- [ ] T024 Reconcile the tearsheet route with the funded-ledger contract, `prices.attrs["price_basis"] == "unadjusted_dollars"`.
  - The route reads the adjusted cache (finding 13), so it must not declare otherwise.
  - The likely outcome is an explicit *unavailable* state until unadjusted prices exist.
  - This restores `test_backtest_tearsheet`.
- [ ] T025 In `routes/backtest.py`, add a constrained request (FR-009) and the cost domain (FR-008), both returning documented 4xx, and take the reconciliation flag from the request's own reconciliation (FR-007). Tests:
  - the audit probes: `short_window=30&long_window=10`, `commission=-1`, `commission=nan`, `slippage_bps=10000`, `short_window=0`
  - an unknown ticker
  - a non-numeric value
- [ ] T026 Add the all-NaN-price oracle (FR-018) at the HTTP boundary, and at the library boundary once T023 settles.
- [ ] T027 Add mutants for T024–T026 to the runner, and record their rows here.

## PR E: Derived values and explanations (48, 49). Not started.

- [ ] T028 Compute `holding_bars` from session positions, with no default. The hand-counted fixture includes a same-session round trip and a forced final exit, and the Rule 5 alignment tests ship in the same PR.
- [ ] T029 Report commission and slippage totals from the fills, spread as *not modeled*, and unrounded responses (FR-010). Depends on T024.
- [ ] T030 Explanations (FR-011):
  - Derive the `CapitalGateView.tsx` decoder from the API's gates.
  - Remove the p-value-as-luck, discard-by-p and Kelly text.
  - Render an unknown correlation as unavailable (the `?? 0` in `FeatureDiagnosticsView.tsx`).
  - Remove the kurtosis range and the Kelly advice from `MarketDataView.tsx`.
- [ ] T031 Add finding 49's patterns to the UI layer, drop its `p-value figure` exemption, and add mutants.

## Evidence (2026-09-12)

**How the tests were run.**
- Command: `venv/Scripts/python.exe -B -m unittest`, run on spec 018's test modules only.
- pytest is not installed, so `-p no:cacheprovider` could not apply. `-B` writes no bytecode, and unittest writes no cache.
- Python 3.13.14 locally. CI's 3.12 was not run.

**Against the pre-018 code.**
- **Response and schema layers**, run with PR A applied and PRs B and C not yet written: 7 run, 4 failures, 1 error. That version predates the `p-value figure` pattern. First failure per test:
  - `entries[].alpha is (0.1,) for both panels`
  - `gates[].details: test count in 'All 301 unit tests passing…'`
  - route scan: `capital_gate.py:19 literal status='passed'`, plus 25 more
  - UI scan: `Header.tsx:93 model attribution`, plus 11 more
  - gate schema test: error, because no validator existed
- **Final route and UI layers**, applied to the snapshot of the pre-018 sources: 25 route violations and 11 UI violations. Among them:
  - `diagnostics.py:92 literal p_value=0.084`
  - `capital_gate.py:20 test count`
  - `ml_rundown.py:61` and `:73` forecast probability (`:73` is the bearish branch)
  - `ml_rundown.py:228 model attribution`
  - `Header.tsx:107 test count`
  - `CapitalGateView.tsx:41 literal gate total`
  - `FeatureDiagnosticsView.tsx:175 p-value field`

**After.**

| Check | Result |
|---|---|
| `test_no_fabricated_values` | 7 run, OK |
| `test_reports_api` | 13 run, 12 pass, 1 error: `test_backtest_tearsheet` raises `ValueError: funded ledger requires declared unadjusted dollar prices` from the core lane's in-flight `scripts/backtest_harness.py:37-38` (T024) |
| `tsc -b --noEmit` | exit 0 |
| `oxlint` | exit 0; one warning, the pre-existing `App.tsx:93` |

**Mutation check** (`python tests/mutation/run_spec_018_mutants.py`):
- **Control**: 20 tests, 1 failing (the tearsheet error above).
- **Clean checkout**: the copy has no `data/cache/` and no `reports/web/dist/`, so the control doubles as the clean-checkout run. 19 of 20 pass, and the one failure is not a missing cache or build.
- **Hashes**: source SHA-256 `8714a3f5f8ff4838…` before and after, identical.
- **Exit code**: 1, because the control is not clean.

| # | Finding | File | Restored defect | Newly failing tests | Caught |
|---|---|---|---|---|---|
| 1 | 45 | `diagnostics.py` | literal `p_value=0.084` passed to the response | 1 | yes |
| 2 | 45 | `diagnostics.py` | p-value figure written into the response text | 2 | yes |
| 3 | 45 | `FeatureDiagnosticsView.tsx` | screen renders a `p_value` field again | 1 | yes |
| 4 | 47 | `capital_gate.py` | Gate 1 `passed` with no evidence | 5 | yes |
| 5 | 47 | `capital_gate.py` | test count restored in gate details | 2 | yes |
| 6 | 47 | `schemas.py` | evidence requirement removed from the gate schema | 1 | yes |
| 7 | 47 | `Header.tsx` | header badge "311/311 PASS" restored | 1 | yes |
| 8 | 47 | `CapitalGateView.tsx` | literal gate total restored | 1 | yes |
| 9 | 46 | `ml_rundown.py` | bearish-branch forecast literal restored | 1 | yes |
| 10 | 46 | `ml_rundown.py` | forecast probability and logit as the model forecast | 2 | yes |
| 11 | 46 | `ml_rundown.py` | rule summary attributed to a model | 2 | yes |
| 12 | 46 | `MLRundownPane.tsx` | pane titled as model output | 1 | yes |
| 13 | 57 | `data.py` | loader bypasses the injected cache directory | 9 | yes |
| 14 | 57 | `main.py` | static mount ignores the test's asset directory | 1 | yes |

**Thinnest margins.** Mutants 1, 3, 6, 7, 8, 9, 12 and 14 are each caught by
exactly one test:
- **Source scan only** (1, 3, 7, 8, 9, 12). A pydantic model ignores an extra field, and no browser test exists.
- **Schema test only** (6).
- **Static-root test only** (14).

**Not verified.**
- The A-only state was run: 13 API tests, 12 pass, the same tearsheet error.
- The B-only state was not built or tested as a separate tree. Its type safety is reasoned from T013 and T017.
- No browser was opened, and CI was not run.
