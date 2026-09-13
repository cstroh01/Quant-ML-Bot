---

description: "Task list for spec 018 — Terminal Truthfulness (audit Stage 3.1)"
---

# Tasks: Terminal Truthfulness (Audit Stage 3.1)

**Input**: Design documents from `.specify/specs/018-terminal-truthfulness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/` (`api-responses.md`, `library-boundaries.md`,
`regression-and-mutation.md`), `quickstart.md`.

**Tests**: Required by the spec (FR-035 – FR-038; SC-001 – SC-011). Within each
phase, test tasks come first and must fail against the pre-fix code before the
implementation tasks run. That is the spec 007 precedent, and it is recorded as
evidence.

**Organization**: One phase per PR from `plan.md`, each labelled with its user
story. Phase 2 is User Story 3 (PR A), because every later PR runs on its
fixtures and CI, so it is blocking even though the spec lists it third.

**Status**: Nothing is implemented. Camden reviews `spec.md`, `plan.md` and this
file before `/speckit.implement` is run.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel: a different file, with no dependency on an
  incomplete task in the same phase.
- **[Story]**: US1–US6 as in `spec.md`.
- Line numbers refer to the tree at audit time (`555343e`). Re-locate the text
  if it has moved; never edit by line number blindly.

## Path Conventions

- Library: `scripts/`. API: `reports/api/`. Web: `reports/web/src/`. Tests:
  `tests/`. CI: `.github/workflows/`.
- No `git` in any task (Rule 10). Evidence is pasted into the *Evidence*
  section at the end of this file.

---

## Phase 1: Setup (before any PR)

**Purpose**: Capture the before-state that the "fails against pre-fix code"
evidence depends on.

- [ ] T001 [P] Copy the pre-fix versions of these files into a scratch directory outside the repository, and record each file's SHA-256 in *Evidence → Baseline snapshot*. This directory is the `--baseline` input for every later PR.
  - `reports/api/routes/diagnostics.py`
  - `reports/api/routes/ml_rundown.py`
  - `reports/api/routes/capital_gate.py`
  - `reports/api/routes/backtest.py`
  - `reports/api/routes/data.py`
  - `reports/api/main.py`
  - `reports/api/schemas.py`
  - `reports/web/src/components/layout/Header.tsx`
  - `reports/web/src/components/views/FeatureDiagnosticsView.tsx`
  - `reports/web/src/components/views/CapitalGateView.tsx`
  - `reports/web/src/components/views/MarketDataView.tsx`
  - `reports/web/src/components/views/BacktestTearsheetView.tsx`
  - `scripts/backtest_harness.py`
  - `scripts/metrics.py`
  - `scripts/ml_signal.py`
  - `scripts/feature_set_comparison.py`
  - `scripts/feature_diagnostics.py`
  - `scripts/ma_crossover_backtest.py`
- [ ] T002 [P] Confirm every producer of `Buy_Next_Open`/`Sell_Next_Open` emits numpy `bool` dtype, and record the findings in *Evidence → Signal dtype audit*.
  - Producers to check: `scripts/signals.py`, `scripts/ml_signal.py`, `scripts/logistic_baseline.py`, `scripts/multi_ticker_comparison.py`.
  - Also check every test in `tests/` that builds these columns directly.
  - If any producer or test builds a non-bool column, stop and amend `spec.md` *Assumptions* before T040.
- [ ] T003 [P] Run `python -m unittest discover -s tests` on the unmodified working tree, and record the test count, failures and errors in *Evidence → Before-state suite*.

---

## Phase 2: User Story 3 — API tests pass on a clean checkout (Priority: P1) — PR A, blocking

**Goal**: The suite passes on a copy with no `data/cache/` contents, no
`reports/web/dist/` and no network. CI installs the declared API dependencies
and builds/lints the web terminal in its own job. Closes finding 57.

**Independent Test**: `quickstart.md` §2 (clean-copy run: 0 failures, 0
errors) and §7 (web lint/build).

### Tests for User Story 3

- [ ] T004 [P] [US3] Create `tests/api_fixtures.py`, a helper module that discovery does not collect (like `tests/context.py`). Follow research R4 and `data-model.md` *FixturePanel*, and state in its docstring that the data is synthetic and that spec 027 replaces the loader it feeds.
  - `panel(seed, sessions, drift, tickers=("AAPL", "NVDA")) -> pd.DataFrame`
    - Tidy `Date`/`Ticker`/OHLCV on `data.trading_days` sessions from 2023-01-03.
    - Seeded `numpy.random.default_rng`.
    - Log-normal closes, with Open near the previous close.
    - High and Low bracket Open and Close; volume is positive.
    - Dates are naive and midnight-normalized.
  - `write_cache(directory, frame) -> Path`
    - Writes `AAPL-AMZN-GOOGL-MSFT-NVDA_10y.csv` inside `directory`.
- [ ] T005 [US3] Create `tests/test_api_fixtures.py`. It must show:
  - The same seed gives an identical frame.
  - Every date is a trading session.
  - OHLC bounds hold.
  - Fixture A (seed 1, ~300 sessions, drift > 0) and fixture B (seed 2, ~347 sessions, drift < 0) differ in length and in every price and volume value.
- [ ] T006 [US3] Rewrite `tests/test_reports_api.py` onto fixtures.
  - `setUpModule` points `data.CACHE_DIR` and `reports.api.routes.data.CACHE_DIR` at a non-existent path.
  - Each test builds `create_app(dist_dir=None)`, with `app.dependency_overrides[get_cache_dir]` returning a temporary directory holding fixture A.
  - Keep all 11 current behaviours, with these changes:
    - Delete the defect assertions at `:83-84` (four significance entries) and `:108-109` (Gate 1 passed). Assert status 200 only there, with a comment naming T021.
    - `test_static_frontend_root` uses `create_app(dist_dir=<tmp>)`, where `<tmp>` holds an `index.html` containing `quant-ml-bot` and `/assets/`.
    - Add `test_api_tests_never_read_real_cache`: with the override removed, an ohlcv request returns 404.

### Implementation for User Story 3

- [ ] T007 [P] [US3] In `reports/api/routes/data.py`:
  - Add `get_cache_dir() -> Path`, returning `data.CACHE_DIR`.
  - Change `get_cached_ticker_data(ticker)` (`:26-57`) to `get_cached_ticker_data(ticker, cache_dir)`, reading from `cache_dir`.
  - Declare `cache_dir: Path = Depends(get_cache_dir)` on `get_ohlcv`, `get_market_stats` and `get_missing_bars`.
  - Leave the fallback ticker list at `:72-74` unchanged; it is finding 18.
- [ ] T008 [US3] Thread `cache_dir: Path = Depends(get_cache_dir)` into every `get_cached_ticker_data` call, changing nothing else:
  - `reports/api/routes/diagnostics.py` (`:34`)
  - `reports/api/routes/ml_rundown.py` (`:28`)
  - `reports/api/routes/backtest.py` (`:43`)
- [ ] T009 [P] [US3] In `reports/api/main.py`:
  - Add `create_app(*, dist_dir: Path | None = DEFAULT_DIST_DIR) -> FastAPI`, which builds the app, adds the existing middleware unchanged (CORS is PR F), includes the routers, registers `/api/health`, and mounts `dist_dir` only when it is not `None` and exists.
  - Keep a module-level `app = create_app()` and `start()` unchanged.
  - Remove the import-time mount at `:54-56`.
- [ ] T010 [P] [US3] In `.github/workflows/test.yml`, add a step `pip install -r reports/requirements-ui.txt` after `:16` in job `test` (research R5; plan Complexity Tracking #4).
- [ ] T011 [US3] In `.github/workflows/test.yml`, add a job `web` (research R5), using the same tag style as the existing actions:
  - `runs-on: ubuntu-latest`
  - `defaults.run.working-directory: reports/web`
  - steps: checkout; `actions/setup-node` with `node-version: "24"`, `cache: npm` and `cache-dependency-path: reports/web/package-lock.json`; `npm ci`; `npm run lint`; `npm run build`
- [ ] T012 [P] [US3] Create `tests/mutation/run_spec_018_mutants.py`, with no `__init__.py` in `tests/mutation/`, as specified in `contracts/regression-and-mutation.md` *Mutation runner*. Stdlib only.
  - Copies the workspace into a temporary directory.
  - Runs the control first.
  - Uses exact-once `find → replace`.
  - Hashes the source before and after.
  - Supports `--only` and `--baseline <dir>`.
  - Prints a Markdown result table.
  - Exits non-zero if any mutant survives.
  - Starts with an empty `MUTANTS` list.
- [ ] T013 [US3] Add mutant 15 (the loader ignores `cache_dir` and reads `CACHE_DIR`) to `tests/mutation/run_spec_018_mutants.py`. Run `--only 15`, and record the table in *Evidence → Mutants*.
- [ ] T014 [US3] Run `quickstart.md` §2 (the robocopy clean copy). Record the test count, failures = 0 and errors = 0, confirm `data/` and `reports/web/dist/` were absent in the copy, and record everything in *Evidence → Clean checkout (PR A)*.
- [ ] T015 [US3] Run `quickstart.md` §7 (`npm ci`, `npm run lint`, `npm run build` in `reports/web`), and record the result in *Evidence → Web build (PR A)*.

**Checkpoint**: The clean copy is green, and CI config has both jobs. PR A
closes finding 57.

---

## Phase 3: User Story 1 — No fabricated evidence reaches the terminal (Priority: P1) 🎯 MVP — PR B

**Goal**: No p-value, forecast probability, model score, test count or passed
gate is displayed without a computation behind it. The fabricated-literal
regression exists, and fails on today's code.

It closes findings 45, 46 and 47, plus two parts of other findings that live in
the same files (plan Complexity Tracking #8):
- the `ml_rundown.py` volume narrative, from finding 49 (FR-015)
- `capital_gate.py:28`, from finding 36 (FR-016)

**Independent Test**: `python -m unittest tests.test_terminal_truthfulness
tests.test_reports_api` passes, and the `--baseline` run against T001's
snapshot fails, naming each fabricated value.

### Tests for User Story 1

- [ ] T016 [P] [US1] Create `tests/test_terminal_truthfulness.py`, containing the numeric-figure tokenizer from `contracts/regression-and-mutation.md` (decimal, percentage, ratio, bare integer of three or more digits) and its own tests. `"54.2%"`, `"+0.17"`, `"311/311"` and `"301"` are figures; `"10-day"` and `"SMA30"` are not.
- [ ] T017 [US1] Add class `DifferentialResponseTests` (L1) to `tests/test_terminal_truthfulness.py`.
  - **Fixtures**: A and B from `tests/api_fixtures.py`, each served through its own override.
  - **Endpoint table**: `/api/data/ohlcv`, `/api/data/stats`, `/api/data/gaps`, `/api/diagnostics/significance`, `/api/diagnostics/collinearity`, `/api/ml/rundown` and `/api/backtest/tearsheet`, all with `ticker=AAPL` and defaults.
  - **Comparison**: normalize list indices to `[]`, then compare distinct-value sets for numeric leaves, and figure sets for text leaves.
  - **Allowlist**: the `AllowlistEntry` tuple, with its reasons, plus a stale-entry test.
  - **Pending coverage**: `PENDING_COVERAGE = {"/api/backtest/tearsheet trade_log[].holding_bars": "PR D (FR-009)", "/api/backtest/tearsheet reconciliation_passed": "PR C (FR-021)"}`. Add nothing else without an owner PR and FR.
- [ ] T018 [US1] Add class `StaticRouteLiteralTests` (L2) to `tests/test_terminal_truthfulness.py`, implementing rules S1–S5 from `contracts/regression-and-mutation.md` over `reports/api/routes/*.py` and `reports/api/schemas.py`.
  - Schema classes are collected by parsing `schemas.py` for `BaseModel` subclasses.
  - One-hop name resolution applies to S1.
  - Docstrings and f-string format specs are excluded from S4.
- [ ] T019 [US1] Add class `UiSourceLiteralTests` (L3) to `tests/test_terminal_truthfulness.py`, covering the US1 patterns only, over `reports/web/src/**/*.{ts,tsx}`: `\d+\s*/\s*\d+\s*PASS`, `\b\d+\s+passed\b`, `P\((Up|Down)\)\s*=`, `\bLogit\b` and `of 5 Gates`. PRs C and E add the rest.
- [ ] T020 [US1] Add class `CapitalGateStateTests` to `tests/test_terminal_truthfulness.py`. It must show:
  - Every gate from `/api/capital_gate/status` is `unknown`, with `evidence is None`.
  - `test_run.status == "not_computed"`.
  - No figure appears outside the roadmap-reference pattern.
  - Building `CapitalGateItem(status="passed", evidence=None)` (and likewise `failed` and `stale`) raises a validation error.
- [ ] T021 [P] [US1] Add honest-state assertions to `tests/test_reports_api.py`:
  - **Significance**: for both AAPL and NVDA, `status == "not_computed"`, a non-empty `reason`, and no `entries`, `p_value` or `screening_alpha` keys.
  - **Rundown**: `model_forecast.status == "not_computed"`, exactly 4 `rule_readings`, and no commentary containing `model`, `ML`, `predict`, `forecast`, `advise`, `institutional`, `flow`, `conviction`, `theorem`, `standard-deviation` or `win rate`.
  - **Capital gate**: all five gates `unknown`.
- [ ] T022 [US1] Run T016–T021 against the pre-fix code with `python tests/mutation/run_spec_018_mutants.py --baseline <T001 dir>`. Confirm the failures name `p_value` (significance), `P(Up) = 54.2%`, `status="passed"`, `301` and `311/311`, and paste the output into *Evidence → Pre-fix failures (PR B)*.

### Implementation for User Story 1

- [ ] T023 [US1] In `reports/api/schemas.py`, per `data-model.md`:
  - **Add**: `NotComputed`.
  - **Significance**: replace `SignificanceEntry`/`SignificanceResponse` (`:55-67`) with `SignificanceResponse{ticker, status, reason}`.
  - **Rundown**: replace `MLInsightItem`/`MLRundownResponse` (`:128-144`) with `RuleReading` and `MLRundownResponse{ticker, as_of_date, model_forecast, rule_summary, rule_readings}`.
  - **Gate item**: `CapitalGateItem` (`:114-120`) gets `status: Literal["passed","failed","stale","unknown"]` and `reason: str`, plus a model validator requiring non-empty `evidence` whenever `status != "unknown"`.
  - **Gate response**: `CapitalGateStatusResponse` gains `test_run: NotComputed`.
- [ ] T024 [P] [US1] In `reports/api/routes/diagnostics.py`, have `get_significance_screening` return `SignificanceResponse(ticker, status="not_computed", reason=...)`, deleting the literal entries and `screening_alpha` at `:86-126` (FR-001; `contracts/api-responses.md`).
- [ ] T025 [P] [US1] Rewrite `get_ml_rundown` in `reports/api/routes/ml_rundown.py` per `contracts/api-responses.md` (FR-003, FR-004, FR-005, and FR-015's volume part):
  - **Return**: `model_forecast=NotComputed(...)`, and four `RuleReading`s built from `Close_To_Short`, `SMA_Spread`, annualized `Rolling_Volatility` and `Rel_Volume`, each with its computed `value`, a plainly stated `rule` and `classification`, and descriptive `commentary`.
  - **Delete**:
    - the forecast block `:52-93`, including the literals at `:61`, `:73` and `:85`
    - the advice at `:67-68`
    - the claims at `:102`, `:121` and `:131`
    - the volume-flow narrative at `:145-168`
    - every `how_to_plan` value
    - the verdict at `:223-229`
- [ ] T026 [P] [US1] Rewrite `reports/api/routes/capital_gate.py` per `contracts/api-responses.md` (FR-007; FR-016's `:28` part):
  - **Gates**: five `CapitalGateItem`s, all `status="unknown"` with `evidence=None`. Each description states the evidence required, with no pass rule and no figures. Each `reason` is a roadmap reference: gate 3 → finding 30 / Stage 3.5; gates 4 and 5 → Phase 4 / Phase 5.
  - **Test run**: add `test_run=NotComputed(...)`.
  - **Delete**:
    - `:18`, the evidence claims
    - `:19-21`, the pass status and "301"
    - `:28`, the literal figures and "proved"
    - `:34`, "remains positive"
- [ ] T027 [P] [US1] Mirror T023 in `reports/web/src/types/api.ts`: `NotComputed`, the new `SignificanceResponse`, `RuleReading`/`MLRundownResponse`, the `CapitalGateItem` status union plus `reason`, and `CapitalGateStatusResponse.test_run`. Fields a UI may receive without a value are optional, never defaulted to 0.
- [ ] T028 [P] [US1] Create `reports/web/src/components/common/NotComputedNotice.tsx` with props `{label: string; reason: string; compact?: boolean}`: neutral grey styling, no spinner, no pulse, and no emerald, rose or amber status colours (research R14).
- [ ] T029 [P] [US1] In `reports/web/src/components/views/FeatureDiagnosticsView.tsx`, replace the significance table (`:141-194`) with `<NotComputedNotice label="Significance screening" reason={significance.reason} />`. Leave the rest of the file for PR D and PR E (FR-002).
- [ ] T030 [P] [US1] In `reports/web/src/components/layout/MLRundownPane.tsx`:
  - Render `model_forecast` with `NotComputedNotice`, and render `rule_readings` (indicator, value, rule, classification, commentary).
  - Reword to rule readings, with no "ML" or "model": the pane title `:50`, the collapsed tab `:35-37`, the loading text `:68`, the verdict label `:83` and the guide `:92-95`.
  - Delete the "How to Plan & Trade" block `:166-175` (FR-004).
- [ ] T031 [P] [US1] Change `reports/web/src/components/layout/Header.tsx` and `reports/web/src/App.tsx` (FR-004, FR-008):
  - **Header badge**: replace the badge at `:104-108` with `<NotComputedNotice compact label="Tests" reason={testRun.reason} />`, fed by a new `testRun` prop.
  - **Header toggle**: rename the ML toggle label at `:90-102` to "Indicator readings".
  - **App**: `App.tsx` passes `capitalGate?.test_run` to `Header`.
- [ ] T032 [P] [US1] In `reports/web/src/components/views/CapitalGateView.tsx` (FR-006, FR-008):
  - **Status chips**: render all four evidence statuses, using `NotComputedNotice` for `unknown` and each gate's `reason`, replacing the `passed`/`in_progress`/pending branches at `:74-151`.
  - **Summary**: count `passed` and `unknown` against `gateStatus.gates.length`, replacing `:27` and `:41`.
  - Leave the decoder `TutorCard` (`:60-69`) for PR E.
- [ ] T033 [US1] Run `npm run lint` and `npm run build` in `reports/web`, fixing only type errors in files US1 touched. Then run `python -m unittest tests.test_terminal_truthfulness tests.test_reports_api`, and record both results in *Evidence → PR B*.
- [ ] T034 [US1] Add mutants 1–6 to `tests/mutation/run_spec_018_mutants.py`, with exact find/replace strings against the post-fix files. Run `--only 1,2,3,4,5,6` and record the table in *Evidence → Mutants*. All must be caught; mutant 3 must be caught by L2.

**Checkpoint**: Clause 1 of the pass condition holds for significance, the
rundown, the gates and the header. The tearsheet has pending-coverage entries
naming PR C and PR D.

---

## Phase 4: User Story 2 — Malformed input cannot produce a successful result (Priority: P1) — PR C

**Goal**: Invalid prices, signals, costs and requests fail explicitly, and the
reconciliation result is computed. Closes findings 03, 04 and 50.

**Independent Test**: `python -m unittest tests.test_cost_domain
tests.test_backtest_harness tests.test_metrics tests.test_ml_signal` passes.
Every malformed row fails as SC-003 requires.

### Tests for User Story 2

- [ ] T035 [P] [US2] Create `tests/test_cost_domain.py` (FR-022, FR-023, FR-024, FR-025; SC-003):
  - **Import set**: `cost_domain` imports exactly `{"math"}`, checked by AST.
  - **Domain table** for `validate_costs`: `True`, `"1"`, `None`, `nan`, `+inf`, `-inf`, `-0.01` and `0` for commission; the same, plus `10000` and `9999.99`, for slippage.
  - **Library boundary**: the same table through `backtest_harness.run_backtest`, `metrics.equity_curve` and `ml_signal.cost_hurdle`.
  - **HTTP boundary** (fixture app from `tests/api_fixtures.py`): `short_window=30&long_window=10`, `commission=-1`, `commission=nan`, `slippage_bps=10000`, `short_window=0`, `short_window=-3`, `short_window=20&long_window=20`, `long_window=253`, `long_window` ≥ fixture sessions, `commission=abc` → 422, where `detail[*].loc` names the parameter and the body has no `trade_log` key; `ticker=ZZZZ` → 404.
- [ ] T036 [P] [US2] Add input-validation tests to `tests/test_backtest_harness.py` (FR-019, FR-020; FR-035a):
  - **Prices**: `Open` NaN, `+inf`, `0` and `-1`, each on a fill row and on a non-fill row; the same for `Close`; all-NaN prices.
  - **Signals**: `Buy_Next_Open` as nullable `boolean` with `pd.NA`, as float with NaN, as int 0/1, and as object strings.
  - **Summary**: `summarize_trades` on a log with NaN `P&L` raises.
  - **Regression**: valid bool frames give bit-identical output to before.
- [ ] T037 [P] [US2] Add reconciliation tests to `tests/test_metrics.py` (FR-020, FR-021):
  - `equity_curve` raises when the trade-log P&L sum is non-finite.
  - `reconciliation_report` returns `passed=True` with a finite `abs_difference ≤ tolerance` on a valid log.
  - It returns `passed=False` on a mismatched log.
  - It returns `passed=False` with `abs_difference=None` on a non-finite log.
  - `tolerance == RECONCILIATION_TOLERANCE`.
- [ ] T038 [P] [US2] In `tests/test_ml_signal.py:671-675`, widen the expected import set to `{"__future__", "numpy", "pandas", "cost_domain"}`, with a docstring line citing spec 018 and plan Complexity Tracking #2. Leave the forbidden-set test at `:677-691` unchanged.

### Implementation for User Story 2

- [ ] T039 [P] [US2] Create `scripts/cost_domain.py` per `contracts/library-boundaries.md`: `MAX_SLIPPAGE_BPS = 10_000` and `validate_costs(commission_per_trade, slippage_bps)`, imports `math` only, with a docstring stating the guarantee and naming spec 018 FR-022.
- [ ] T040 [P] [US2] In `scripts/backtest_harness.py`:
  - Replace `:46-49` with `cost_domain.validate_costs`.
  - Before the loop at `:66`, validate that `Open` and `Close` are numeric, finite and > 0, raising `ValueError` with the column and first position.
  - Validate that `Buy_Next_Open` and `Sell_Next_Open` are exactly numpy `bool`, raising `TypeError` with the column and dtype.
  - In `summarize_trades`, raise `ValueError` if any `P&L` is non-finite (FR-019, FR-020).
- [ ] T041 [P] [US2] In `scripts/metrics.py`:
  - Replace `:95-100` with `cost_domain.validate_costs`.
  - At `:148`, treat a non-finite `actual` or `expected` as a reconciliation failure.
  - Add `reconciliation_report(prices, trade_log, *, commission_per_trade, slippage_bps) -> dict`, sharing the comparison with `equity_curve` and not raising on mismatch (research R7).
- [ ] T042 [P] [US2] In `scripts/ml_signal.py`, make `_validate_costs` (`:47-72`) call `cost_domain.validate_costs` for the two costs, keep its `shares` checks at `:69-72`, and update its docstring.
- [ ] T043 [US2] Change `reports/api/routes/backtest.py` and `reports/api/schemas.py` (FR-021, FR-024, FR-025):
  - **Request dependency**: add `TearsheetParams` (research R10): `short_window` 1–252, `long_window` 2–252, `long_window > short_window`, and costs via `cost_domain`. Each error becomes a 422 in FastAPI's standard `detail` shape, with `loc` naming the parameter. After loading data, check that `long_window` is less than the session count.
  - **Reconciliation**: replace `reconciliation_passed=True` (`:168`) with `reconciliation=ReconciliationReport(**metrics.reconciliation_report(...))`. Raise HTTP 500 with detail `"reconciliation failed"` if `passed` is false.
  - **Schema**: in `schemas.py`, add `ReconciliationReport` and remove `reconciliation_passed`.
- [ ] T044 [US2] In `reports/web/src/types/api.ts` and `reports/web/src/components/views/BacktestTearsheetView.tsx`, replace `reconciliation_passed` with `reconciliation`. The friction card (`:152`, `:159`) shows a reconciled check only when `reconciliation.passed`, and displays `reconciliation.tolerance` from the response instead of the literal `1e-9` (FR-021).
- [ ] T045 [US2] Update the regression in `tests/test_terminal_truthfulness.py`:
  - Remove the `reconciliation_passed` entry from `PENDING_COVERAGE`.
  - Assert that rule S2 finds no pass-flag literal in `backtest.py`.
  - Add `reconciliation.tolerance` to the allowlist as `configuration`, with an equality assertion against `metrics.RECONCILIATION_TOLERANCE`.
  - Add the L3 pattern `✓\s*1e-9`.
- [ ] T046 [US2] Run `--baseline <T001 dir>` for PR C's tests. Confirm the failures show the literal reconciliation flag, NaN and ±inf costs accepted, `slippage_bps=10000` accepted by the harness, and 500/200 on the probe requests. Record them in *Evidence → Pre-fix failures (PR C)*.
- [ ] T047 [US2] Add mutants 8, 9, 10 and 13 to `tests/mutation/run_spec_018_mutants.py`, run `--only 8,9,10,13`, and record the table in *Evidence → Mutants*.
- [ ] T048 [US2] Run `python -m unittest discover -s tests`, `npm run lint` and `npm run build`, and record the results in *Evidence → PR C*.

**Checkpoint**: Clause 2 of the pass condition holds. All P0 findings in Stage
3.1 are closed after PRs B and C.

---

## Phase 5: User Story 4 — Derived numbers in the tearsheet and diagnostics are correct (Priority: P2) — PR D

**Goal**: Holding bars, the cost breakdown, unrounded export, exact McNemar and
singular-aware VIF all match independent oracles. Closes findings 48, 29 and
35.

**Independent Test**: `python -m unittest tests.test_ma_crossover_backtest
tests.test_backtest_harness tests.test_feature_scaling tests.test_reports_api`
passes, with SC-006, SC-007 and SC-008 met.

### Tests for User Story 4

- [ ] T049 [P] [US4] Add `holding_bars_per_trade` tests to `tests/test_ma_crossover_backtest.py` (FR-009, FR-038; SC-006):
  - **Cases**: adjacent sessions = 1; same-session round trip = 0; entry on the first row; forced final exit counted to the last row; an empty log gives an empty integer series.
  - **Holiday gap**: build prices on `data.trading_days` across 2024-07-04 and assert that sessions are counted, not calendar days.
  - **Regression**: `mean_holding_bars` returns the same values as before on the existing cases.
- [ ] T050 [P] [US4] Add `trade_cost_breakdown` oracles to `tests/test_backtest_harness.py` (FR-010; FR-035d; SC-006):
  - **Hand-computed fixture**: two trades at `c=1.0`, `s=5` bps, with `commission_total` and `slippage_total` written as literal expected values derived by hand in a comment.
  - **Identity**: a zero-cost `run_backtest` rerun on the same signals, including a forced final exit, gives `Σ costless − Σ net == commission_total + slippage_total` within 1e-9.
  - **Spread**: `spread_total is None` and `spread_status == "not_modeled"`.
- [ ] T051 [P] [US4] Add McNemar oracle tests to `tests/test_feature_scaling.py` (FR-028; FR-035c; SC-007):
  - **Exhaustive check**: for every `(a_wins, b_wins)` with `1 ≤ a+b ≤ 30`, `p_one_sided` equals `sum(math.comb(n, k) for k in range(b, n+1)) / 2**n` within 1e-12.
  - **Named cases**: the audit probe (labels `[1,1,1,1]`, a=`[1,1,1,0]`, b=`[1,0,0,0]`) returns exactly 1.0; a tie at 3/3; zero discordant pairs returns 1.0.
  - **Regression**: favoured-direction values equal `two_sided/2`.
- [ ] T052 [US4] Add VIF oracle tests to `tests/test_feature_scaling.py` (FR-029; FR-035b; SC-008):
  - **Singular cases**: exact duplicate → `inf`; `c = 2a − b` → `inf`; constant column → `NaN`, without raising.
  - **Near-singular**: `b = a + 1e-3·noise` (seeded) gives a finite value ≥ 1, matching a test-local `numpy.linalg.lstsq` R² regression and statsmodels `variance_inflation_factor` on the design with a constant column, within a relative 1e-6.
  - **Degenerate matrices**: a single column and an all-constant matrix.
  - **Diagnose**: `diagnose()` reports `vif_status`.
- [ ] T053 [P] [US4] Add tearsheet and collinearity tests to `tests/test_reports_api.py` (FR-009, FR-010, FR-011, FR-030):
  - **Holding bars**: on fixture A, `trade_log[].holding_bars` equals the session-position differences computed in the test, and is not constant.
  - **Costs**: `costs` has commission and slippage totals, with `spread_total is None`.
  - **Unrounded**: response floats equal the library outputs exactly.
  - **Collinearity**: the response model serializes a `DiagnosticValue` with `infinite` and `undefined` statuses without error.

### Implementation for User Story 4

- [ ] T054 [P] [US4] In `scripts/ma_crossover_backtest.py`, add `holding_bars_per_trade(prices, trade_log) -> pd.Series`, and make `mean_holding_bars` (`:37-56`) call it without changing its result (research R8).
- [ ] T055 [P] [US4] In `scripts/backtest_harness.py`, add `trade_cost_breakdown(trade_log, *, commission_per_trade, slippage_bps) -> dict` per `contracts/library-boundaries.md`, validating costs via `cost_domain`.
- [ ] T056 [P] [US4] In `scripts/feature_set_comparison.py`, replace `:393-394` with `scipy.stats.binomtest(b_wins, a_wins + b_wins, 0.5, alternative="greater").pvalue`. Update the docstring at `:351-361` to state that the one-sided value is computed directly, not derived (FR-028).
- [ ] T057 [P] [US4] In `scripts/feature_diagnostics.py` (FR-029):
  - Reimplement `variance_inflation_factors` (`:76-94`) as a per-column least-squares regression, with `NaN` for zero variance, `inf` when `SSR ≤ 1e-10·SST`, and `max(1, 1/(1−R²))` otherwise.
  - Replace the docstring's pseudo-inverse rationale.
  - Add `vif_status` to `diagnose`, and make `max_vif`/`max_vif_feature` handle non-finite values per `contracts/library-boundaries.md`.
- [ ] T058 [US4] In `scripts/scratch_multiticker_collinearity.py`, delete the local `variance_inflation_factors` (`:112-120`) and import it from `feature_diagnostics` (plan Complexity Tracking #7).
- [ ] T059 [US4] Change `reports/api/routes/backtest.py` and `reports/api/schemas.py` (FR-009, FR-010, FR-011):
  - **Holding bars**: `TradeRecord.holding_bars` becomes `int` with no default (`schemas.py:77`); the route fills it from `holding_bars_per_trade` (`:154`).
  - **Costs**: add `CostBreakdown` and a `costs` field, filled from `trade_cost_breakdown`.
  - **Rounding**: remove every `round(...)` at `:101-104`, `:119-123`, `:136-139`, `:149-153` and `:163-167`.
- [ ] T060 [US4] Change `reports/api/routes/diagnostics.py` and `reports/api/schemas.py` (FR-011, FR-030):
  - **Schema**: add `DiagnosticValue`; `CollinearityEntry.condition_number` and `max_vif` become `DiagnosticValue`, `max_vif_feature` becomes `str | None`, and correlation values become `float | None`.
  - **Route**: build them from `diagnose()` output, and remove `round(...)` at `:53-57`, `:61-65` and `:70`.
- [ ] T061 [US4] Update `reports/web/src/types/api.ts`, `reports/web/src/components/views/BacktestTearsheetView.tsx` and `reports/web/src/components/views/FeatureDiagnosticsView.tsx` (FR-010, FR-030):
  - **Tearsheet**: replace the commission-only "Drag" at `:92-93` and `:158` with commission and slippage totals from `costs`, plus spread shown as "not modeled".
  - **Diagnostics**: render `DiagnosticValue` as the number, "infinite (exact collinearity)" or "undefined (constant column)" at `:80`, `:88`, `:117` and `:125`.
- [ ] T062 [US4] Update the regression in `tests/test_terminal_truthfulness.py`:
  - Remove the `holding_bars` entry from `PENDING_COVERAGE`.
  - Add allowlist entries only where L1 flags a value that is invariant by construction, each with its reason. Expected entries: buy-and-hold `total_trades` as `structurally_constant`; `commission_per_trade` and `slippage_bps` as `request_echo`.
- [ ] T063 [US4] Run `--baseline <T001 dir>` for PR D's tests; the failures must show `holding_bars=1`, McNemar 0.75 and VIF 0.25. Then add mutants 7, 11, 12 and 16, run `--only 7,11,12,16`, and record everything in *Evidence*.
- [ ] T064 [US4] Run `python -m unittest discover -s tests`, `npm run lint` and `npm run build`, and record the results in *Evidence → PR D*.

**Checkpoint**: The tearsheet is fully covered by L1/L2, and the statistics
oracles are green.

---

## Phase 6: User Story 5 — Explanations and labels say what is shown (Priority: P2) — PR E

**Goal**: Explanatory text matches the displayed data and policy, with no
wrong statistical tutoring and honest strategy/illustration labels. Closes
findings 49, 36 and 54 (the parts not already done in PR B).

**Independent Test**: The PR E classes in `tests/test_terminal_truthfulness.py`
pass, and SC-010 is met.

### Tests for User Story 5

- [ ] T065 [US5] Add the PR E checks to `tests/test_terminal_truthfulness.py` (FR-012 – FR-018; SC-010):
  - **L3 patterns**: `\bKelly\b`, `chance of being luck`, `less than a \d+% chance`, `\d+x\s+Improvement`, and `\?\?\s*0\b`, the last scoped to `FeatureDiagnosticsView.tsx`.
  - **Decoder**: each gate title returned by `/api/capital_gate/status` appears in `CapitalGateView.tsx`'s decoder text, in the same order.
  - **CV label**: `CrossValidationView.tsx` contains the illustration label and no `"Fold "` row count.
  - **Strategy family**: the tearsheet response has `strategy_family == "rule_based_sma_crossover"`, and `BacktestTearsheetView.tsx` contains the rule-based SMA label.
  - **Code and docs**: `scripts/features.py` no longer contains "training support cover its test window", and `.specify/specs/014-scale-free-features/spec.md` ends with the dated audit note.
- [ ] T066 [US5] Run T065 against the pre-PR-E tree (`--baseline`), and record the failures in *Evidence → Pre-fix failures (PR E)*.

### Implementation for User Story 5

- [ ] T067 [P] [US5] In `reports/web/src/components/views/CapitalGateView.tsx:60-69`, rewrite the decoder `TutorCard` so it names the API's five gates in order. Drop "mathematically verified and audited" and "focus on finishing Gate 4", and state that `unknown` means no evidence has been recorded (FR-012).
- [ ] T068 [P] [US5] In `reports/web/src/components/views/FeatureDiagnosticsView.tsx`:
  - **Banner** (`:47`): conditioning is a numerical property and not evidence of an edge; no causal claim about "zero models beat baseline" (FR-016).
  - **Tutor** (`:52-61`): remove the p-value-as-luck text, the discard-by-p rule and the κ/VIF literals (FR-013, FR-014).
  - **Badges** (`:71-73`, `:82`, `:90`, `:108-110`, `:119`, `:127`): derive them from the displayed values against named threshold constants, or remove them (FR-014).
  - **Correlation claim** (`:203`): remove the "exceeds 0.55" claim (FR-014).
  - **Correlation cells** (`:226`): render `null` or undefined correlations as unavailable (FR-015).
- [ ] T069 [P] [US5] In `reports/web/src/components/views/MarketDataView.tsx`, remove the fixed "(3.0 - 12.0)" kurtosis range at `:56` and the Kelly sizing advice at `:86`, and reword `:85` so it doesn't imply a guarantee (FR-015).
- [ ] T070 [P] [US5] In `reports/web/src/components/views/CrossValidationView.tsx`, label the view "Illustration of the splitting scheme — not a saved run". Present the fold rows at `:10-18` as schematic, with no count that reads as a real run's, and reword `:45` accordingly (FR-017).
- [ ] T071 [P] [US5] Add `strategy_family: Literal["rule_based_sma_crossover"]` to `BacktestTearsheetResponse` and set it in the route; mirror it in `types/api.ts`; show "Rule-based SMA crossover — not an ML model" beside the headline metrics; and rename the tab at `:21` to "SMA Backtest & Tearsheet" (FR-018). Files:
  - `reports/api/schemas.py`
  - `reports/api/routes/backtest.py`
  - `reports/web/src/types/api.ts`
  - `reports/web/src/components/views/BacktestTearsheetView.tsx`
  - `reports/web/src/components/layout/TabNavigation.tsx`
- [ ] T072 [P] [US5] In `scripts/features.py:39-42`, reword the comment so ratios make the columns unit-invariant, without claiming training support covers the test window or that stationarity is guaranteed (FR-016).
- [ ] T073 [P] [US5] Append a section `## Audit note — 2026-09-12 (spec 018, finding 36)` to the end of `.specify/specs/014-scale-free-features/spec.md`, stating that good conditioning is a numerical property, not evidence of predictive or economic value. Existing text is not edited (plan Complexity Tracking #6).
- [ ] T074 [US5] Add mutant 17 and run `--only 17`. Then run `npm run lint`, `npm run build` and `python -m unittest discover -s tests`, and record the results in *Evidence → PR E*.

**Checkpoint**: The terminal's text matches its data.

---

## Phase 7: User Story 6 — The local API answers only local origins (Priority: P3) — PR F

**Goal**: A CORS allowlist of loopback development origins, with no
credentials and GET only; loopback bind pinned. Closes finding 51 (its Phase 3
part).

**Independent Test**: The CORS tests in `tests/test_reports_api.py` pass, and
SC-009 is met.

### Tests for User Story 6

- [ ] T075 [P] [US6] Add CORS and bind tests to `tests/test_reports_api.py` (FR-026, FR-027; SC-009):
  - **Untrusted origin**: `Origin: https://untrusted.example` → no `access-control-allow-origin` and no `access-control-allow-credentials`.
  - **Allowed origins**: each of the four `ALLOWED_ORIGINS` is echoed, without credentials.
  - **Preflight**: a request for `POST` from an allowed origin is not allowed.
  - **Bind**: `start()` calls a patched `uvicorn.run` with `host="127.0.0.1"`.

### Implementation for User Story 6

- [ ] T076 [US6] In `reports/api/main.py`, add `ALLOWED_ORIGINS` (research R11), and in `create_app` configure `CORSMiddleware(allow_origins=list(ALLOWED_ORIGINS), allow_credentials=False, allow_methods=["GET"])`, replacing `:31-37`.
- [ ] T077 [US6] Run `--baseline` for T075, confirming the reflected origin and credentials were accepted pre-fix. Add mutant 14, run `--only 14` and the full suite, and record everything in *Evidence → PR F*.

**Checkpoint**: All six stories are complete.

---

## Phase 8: Polish & closure — PR G

**Purpose**: Prove the whole pass condition at once and close finding 58.

- [ ] T078 Add `test_every_api_get_route_is_covered` to `tests/test_terminal_truthfulness.py`. It enumerates `create_app(dist_dir=None).routes`, asserts each `GET /api/*` path is in the L1 endpoint table or in `FIXTURE_INDEPENDENT = {"/api/health", "/api/data/tickers", "/api/capital_gate/status"}`, and asserts `PENDING_COVERAGE == {}` (contracts *Coverage*).
- [ ] T079 Run `python tests/mutation/run_spec_018_mutants.py` with all 17 mutants. The control must pass, all must be caught, and hashes must match before and after. Paste the table into *Evidence → Mutation check (SC-002)*.
- [ ] T080 Run `quickstart.md` §1–§8 end to end, including the clean copy and the manual screen checks. Record each section's result in *Evidence → Final validation*, and state each pass-condition clause next to the evidence that satisfies it.
- [ ] T081 [P] For each PR, make sure its description states what CLAUDE.md requires, and check it off here:
  - spec 018 and the findings it closes
  - what changed and why it is correct
  - "no metric reported", so fold/purge/embargo/commission/slippage fields are N/A
  - "no strategy change", so no baseline table
  - "no new dependency"
  - the plan Complexity Tracking entries it touches
- [ ] T082 [P] In PR G's description, raise the open flags for Camden, without editing `CLAUDE.md` or the constitution:
  - a CLAUDE.md module-table row is needed for `scripts/cost_domain.py` (Complexity Tracking #1)
  - `httpx` versus the "no test dependencies" convention (#4)
  - the `tests/mutation/` location (#5)
  - the appended spec 014 note (#6)
  - the scratch-script edit (#7)
  - the constitution has no rule against unsourced figures in reports (plan *Constitution Check*)

---

## Dependencies & Execution Order

### Phase dependencies

```text
Phase 1 Setup ──► Phase 2 US3 / PR A (blocking)
                      ├──► Phase 3 US1 / PR B ──► Phase 4 US2 / PR C ──► Phase 5 US4 / PR D ──┐
                      │                     └───────────────────────────► Phase 6 US5 / PR E ──┤
                      └──► Phase 7 US6 / PR F ─────────────────────────────────────────────────┤
                                                                                                └──► Phase 8 / PR G
```

- **PR B depends on PR A**: fixtures, seam and runner.
- **PR C depends on PR B**: the regression's `PENDING_COVERAGE` and L2 infrastructure.
- **PR D depends on PR C**: `trade_cost_breakdown` validates through `cost_domain`, and the route already uses `TearsheetParams`.
- **PR E depends on PR B**: rundown and gate text are already honest; the `CapitalGateView.tsx` decoder builds on T032.
- **PR F depends only on PR A**: `create_app`.
- **PR G depends on all of the above.**

### Within each phase

- Tests are written first, then the `--baseline` evidence, then the implementation.
- Schemas come before routes, routes before `types/api.ts`, and types before components.
- Shared-file sequencing: `reports/api/schemas.py` (T023, T043, T059, T060, T071) and `reports/web/src/types/api.ts` (T027, T044, T061, T071) are edited in different PRs, never in parallel within one.

---

## Parallel Examples

### PR A (US3)

```text
T004 tests/api_fixtures.py
T007 reports/api/routes/data.py
T009 reports/api/main.py
T010 .github/workflows/test.yml
T012 tests/mutation/run_spec_018_mutants.py
```

### PR B (US1), after T023

```text
T024 reports/api/routes/diagnostics.py
T025 reports/api/routes/ml_rundown.py
T026 reports/api/routes/capital_gate.py
T027 reports/web/src/types/api.ts
T028 reports/web/src/components/common/NotComputedNotice.tsx
```

Then, after T027 and T028:

```text
T029 FeatureDiagnosticsView.tsx
T030 MLRundownPane.tsx
T031 Header.tsx + App.tsx
T032 CapitalGateView.tsx
```

### PR C (US2)

```text
T035 tests/test_cost_domain.py
T036 tests/test_backtest_harness.py
T037 tests/test_metrics.py
T038 tests/test_ml_signal.py
```

Then T039, and after it:

```text
T040 backtest_harness.py
T041 metrics.py
T042 ml_signal.py
```

### PR D (US4)

```text
T049, T050, T051, T053
T054, T055, T056, T057
```

### PR E (US5)

```text
T067–T073 all touch different files
```

---

## Implementation Strategy

### MVP (PR A, then PR B)

1. Phase 1: capture the baseline.
2. PR A: the suite is green on a clean copy; CI installs the API dependencies and builds the web terminal.
3. PR B: every fabricated forecast, p-value, gate pass and test count is gone, and the regression fails on the old code.
4. **Stop and validate**: `quickstart.md` §2 and §3. The terminal no longer invents evidence.

### P0 milestone (+ PR C)

Adding PR C closes all six Stage 3.1 P0 findings (45, 46, 47, 03, 04) plus 50,
and satisfies clauses 1 and 2 of the pass condition.

### Incremental delivery

PRs D, E and F are independently reviewable once their dependencies above are
met. PR G is the only PR that asserts the whole pass condition.

### Review sizing

Each PR is scoped to one story. Where a PR grows beyond one sitting (PR B is
the likeliest), split backend (T023–T026) from UI (T027–T032) before review,
not after (CLAUDE.md).

---

## Evidence

*Filled in during implementation. Empty until then.*

### Baseline snapshot (T001)

| File | SHA-256 |
|---|---|

### Signal dtype audit (T002)

### Before-state suite (T003)

### Clean checkout (PR A — T014)

### Web build (PR A — T015)

### Pre-fix failures (PR B T022, PR C T046, PR D T063, PR E T066, PR F T077)

### Mutants (T013, T034, T047, T063, T074, T077)

| ID | File | Defect | Tests run | Failed | Caught |
|---|---|---|---|---|---|

### Mutation check (SC-002 — T079)

### Final validation (T080)

---

## Notes

- `[P]` means a different file with no dependency on an incomplete task in the same phase.
- Every story phase ends with evidence recorded above; a checked box without evidence is not complete (finding 67).
- No task runs `git`, touches `.specify/specs/017-position-sizing-risk/`, runs spec 013, or edits `.specify/memory/constitution.md` or `CLAUDE.md`.
