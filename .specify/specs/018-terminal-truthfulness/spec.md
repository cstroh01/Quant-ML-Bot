# Feature Specification: Terminal Truthfulness (Audit Stage 3.1)

**Feature Branch**: `018-terminal-truthfulness`

**Created**: 2026-09-12

**Status**: Draft — spec, plan and tasks await Camden's review. Nothing is implemented.

**Input**: Stage 3.1 of `docs/audit-2026-09-12/REMEDIATION_PLAN.md` ("Honest
terminal and adversarial regressions"), which carries work order 1 of
`docs/audit-2026-09-12/AUDIT.md`. The terminal currently shows a p-value table,
an ML forecast, a passed capital gate and a test-count badge that no
computation produced. This spec deletes them. It also closes the input-validation, CI
and statistics defects the plan groups into the same stage.

**Owns / must not know about** (CLAUDE.md module table): the reporting API
(`reports/api/`) and web terminal (`reports/web/`) change most. Two library
defects are fixed where they live: `scripts/backtest_harness.py` (fills and
costs), and `scripts/feature_set_comparison.py` / `scripts/feature_diagnostics.py`
(statistics). `scripts/signals.py` and `scripts/data.py` are not touched. No
module learns about a layer it does not already know about; the one shared cost
validator this spec needs is a boundary question, recorded in the plan's
Complexity Tracking rather than settled here.

---

## Scope

### In scope — exactly the 15 findings REMEDIATION_PLAN.md assigns to Stage 3.1

Line numbers are against the tree at audit time (commit `555343e`, 2026-09-12).

| ID | P | Type | Defect | Affected file:line | Requirements |
|---|---|---|---|---|---|
| **45** | P0 | D | The significance endpoint returns four literal p-values (0.084 / 0.215 / 0.042 / 0.310). They are the same for every ticker and disagree with the saved run. | `reports/api/routes/diagnostics.py:81-126` (literals `:92`, `:100`, `:108`, `:116`; pass flags `:94`, `:102`, `:110`, `:118`); rendered by `reports/web/src/components/views/FeatureDiagnosticsView.tsx:141-194`; asserted as correct by `tests/test_reports_api.py:78-84` | FR-001, FR-002 |
| **46** | P0 | D | `P(Up) = 54.2%`, `Logit Score = +0.17` and two sibling literals are presented as a fitted-model forecast. Two sign tests on indicators are labelled "ML", "the model predicts" and "Model advises". | `reports/api/routes/ml_rundown.py:61`, `:73`, `:85` (literals); `:52-93`, `:170-179`, `:223-229` (rule presented as model output); `:67-68` (hurdle advice with literal $2.00 / 10 bps / 55%); `:102`, `:121`, `:131` (unmeasured statistical claims); `reports/web/src/components/layout/MLRundownPane.tsx:35-37`, `:50`, `:68`, `:83`, `:92-95`; `reports/web/src/components/layout/Header.tsx:90-102` | FR-003, FR-004, FR-005 |
| **47** | P0 | D | Gate 1 is hardcoded `passed` with "301 passed in pytest suite", and its description claims null-pipeline and cost-stress evidence. Gate 2 quotes diagnostic figures with no source. The header separately hardcodes "CORE: 311/311 PASS". | `reports/api/routes/capital_gate.py:15-22` (`status="passed"` `:19`; "301" `:20-21`; evidence claim `:18`), `:28` (literal figures), `:34` ("remains positive" rule); `reports/api/schemas.py:114-120`; `reports/web/src/types/api.ts:105-112`; `reports/web/src/components/layout/Header.tsx:104-108`; `reports/web/src/components/views/CapitalGateView.tsx:27`, `:41`, `:74-151`; asserted as correct by `tests/test_reports_api.py:103-109` | FR-006, FR-007, FR-008 |
| **48** | P1 | D | Every trade reports `holding_bars=1`; the audit measured 93/33/43/36/27 for the first five. "Drag" counts commission only but is labelled as total friction. The API rounds values before exporting them. | `reports/api/routes/backtest.py:154` (literal); rounding `:101-104`, `:119-123`, `:136-139`, `:149-153`, `:163-167`; `reports/api/schemas.py:77` (`holding_bars: int = 1`); `reports/web/src/components/views/BacktestTearsheetView.tsx:92-93`, `:148-161` | FR-009, FR-010, FR-011 |
| **49** | P1 | D | The gate decoder describes a different five-gate sequence than the API returns. P-values are explained as "the chance of being luck". Conditioning badges and improvement ratios are unconditional literals. Kelly sizing is taught. An unknown correlation renders as 0.00. Volume is described as institutional-flow evidence. | `reports/web/src/components/views/CapitalGateView.tsx:60-69`; `FeatureDiagnosticsView.tsx:52-61` (p-value text and κ = 422 / VIF = 54 / κ ≈ 24 literals `:58`; discard rule `:59`), `:71-73`, `:82`, `:90`, `:108-110`, `:119`, `:127`, `:180`, `:203`, `:226` (`?? 0`); `MarketDataView.tsx:56`, `:85-86` (Kelly `:86`); `reports/api/routes/ml_rundown.py:145-168` (volume narrative — see Note A) | FR-012 – FR-015 |
| **36** | P1 | R | Good conditioning is presented as the fix for "no model beats baseline" rather than as a numerical property of the matrix. | `FeatureDiagnosticsView.tsx:47`, `:108-110`, `:119`; `reports/api/routes/capital_gate.py:28` ("Spec 014 proved…"); `scripts/features.py:39-42` ("what makes a fold's training support cover its test window"); `.specify/specs/014-scale-free-features/spec.md:9-20` | FR-016 |
| **54** | P1 | G | The CV timeline is a hardcoded six-fold illustration presented as the evaluation's architecture; the saved run has 113 outer folds. The SMA tearsheet sits beside panes that suggest ML. | `reports/web/src/components/views/CrossValidationView.tsx:10-18`, `:43-46`, `:50-113`; `BacktestTearsheetView.tsx:95-162`; `reports/web/src/components/layout/TabNavigation.tsx:21`; `reports/api/routes/backtest.py:98-99`, `:160`; `reports/api/routes/ml_rundown.py:173` | FR-017, FR-018 |
| **03** | P0 | D | A NaN fill gives NaN trade P&L, which the summary reports as 1 trade and 0.0 total. A NaN signal is truthy, so it opens a position. Reconciliation compares with `>`, which is false for NaN, so NaN "reconciles". The API returns `reconciliation_passed=True` as a literal. | `scripts/backtest_harness.py:13-105` (prices `:68`, `:83`, `:89`; signals `:67`, `:81`), `:108-135` (NaN-skipping sum `:126`); `scripts/metrics.py:148`; `reports/api/routes/backtest.py:168`; `BacktestTearsheetView.tsx:152`, `:159` | FR-019 – FR-021 |
| **04** | P0 | D | Cost checks written as `x < 0` accept NaN and infinity. The harness accepts `slippage_bps=10000`, which gives a zero or negative sale price. The API accepts `commission=nan`. | `scripts/ml_signal.py:47-72`; `scripts/backtest_harness.py:46-49`; `scripts/metrics.py:95-100`; `reports/api/routes/backtest.py:39-40` | FR-022, FR-023 |
| **50** | P1 | D | `short_window=30&long_window=10` and `commission=-1` return 500; `short_window=0` returns 200; the workload is unbounded. | `reports/api/routes/backtest.py:34-41` | FR-024, FR-025 |
| **51** | P1 | G | CORS reflects any origin (`"*"`) with credentials allowed. | `reports/api/main.py:30-37` (`"*"` `:33`, `allow_credentials=True` `:34`); loopback bind `:59-62` | FR-026, FR-027 |
| **29** | P1 | D | In the unfavoured direction the one-sided McNemar p-value is computed as `1 − p₂/2`, which drops the observed mass: the probe reports 0.75 for 0 wins in 2, where the exact answer is 1.0. Ties are also wrong. | `scripts/feature_set_comparison.py:391-402` (function `:348`); the existing test cannot see it: `tests/test_feature_scaling.py:746-752` | FR-028 |
| **35** | P1 | D | The pseudo-inverse VIF returns 0.25 for an exact duplicate column and raises an SVD error on a constant column. The scratch script copies the same code. An infinite VIF would also break API serialization. | `scripts/feature_diagnostics.py:76-94` (`pinv` `:93`), `:57-68`; `scripts/scratch_multiticker_collinearity.py:112-120`; `reports/api/routes/diagnostics.py:50-67` | FR-029, FR-030 |
| **57** | P1 | D | On a clean checkout 7 of 11 API tests fail, and CI cannot even import the API test module. Root cause is under *Background*. | `.github/workflows/test.yml:16-17`; `tests/test_reports_api.py:10-17`, `:31-128`; `reports/api/routes/data.py:26-57`; `reports/api/main.py:53-56` | FR-031 – FR-034 |
| **58** | P1 | G | Several tests mirror the formula they check or only check response shape. Mutation evidence lives outside the repository. | `tests/`; spec 017's out-of-repo runner, `.specify/specs/017-position-sizing-risk/quickstart.md:88-91` | FR-035, FR-036 |

**Note A.** REMEDIATION_PLAN.md places finding 49's volume-flow narrative in
`MarketDataView.tsx`. That file contains no volume narrative. The text is in
`reports/api/routes/ml_rundown.py:145-168`, and this spec maps it there.

### Explicitly excluded

- **Real inference, saved-run artifacts and an experiment store are Stage 3.3,
  not this spec.** This stage deletes fabricated numbers; it does not
  construct real ones. Every hardcoded value named above becomes an explicit
  *not computed* response, with a UI state that says so:
  - the `diagnostics.py` p-values
  - the `ml_rundown.py` P(Up) and logit score
  - the `capital_gate.py` Gate 1 claim and its test count
  - the `Header.tsx` test badge

  Wiring fitted-model inference, versioned verification artifacts or a run
  store into these endpoints is excluded. So is the first half of 45's
  plan text ("replace with saved run artifacts"), and so is 47's ↪ "read
  versioned artifacts once 028 exists". No gate can report `passed` until
  that work exists.
- **Parts of finding 58 whose subject this stage does not own.** The plan lists
  six oracles. This spec delivers the three whose subject exists and whose
  correct behaviour this stage defines, plus one it adds, all under FR-035:
  - all-NaN prices
  - exact singular VIF
  - the exact McNemar tail
  - hand-counted holding periods and cost decomposition (the added one)

  The other three move to the specs that build their subject, following the
  plan's own "each later spec adds its own oracle":
  - the **funded-ledger** oracle, because no funded ledger exists (023)
  - the **overnight-only timing** oracle, because the current target fails it
    by design (022)
  - the **planted-signal-versus-noise** and **whole-pipeline future
    perturbation** oracles, because 022 rebuilds the timing contract they
    would pin (022)

  This split contradicts the plan's table and is flagged for Camden in
  `docs/audit-2026-09-12/SPEC_018_HANDOFF.md`.
- **Findings 26 and 30 stay open.** The plan routes a "wording fix" for 26 and
  a "gate text fix" for 30 to 018. They are not Stage 3.1 findings, so they do
  not count toward this spec's scope. The strings in question are removed
  anyway, as consequences of 46 and 47, because each is a claim with no
  evidence behind it:
  - the "Sharpe ≤ 0.3" and "DSR remains positive" pass rules
  - the friction advice attached to a direction reading

  No replacement criterion is defined here.
- **Everything else the audit found in these same files**:
  - the rundown's one-session-stale as-of date (23)
  - the prediction target (22)
  - the funded ledger and drawdown anchoring (01, 02)
  - data validation (14)
  - the fallback ticker list at `reports/api/routes/data.py:72-74` (18)
  - cache path containment (20)
  - the fixed risk-free label in the tearsheet (12)
  - request races, and loading, error and stale states (52, 53)
  - accessibility (55)
  - packaging and runtime contracts (56, 61)
  - CI permission hardening (63)
- **No experiment is rerun and no metric is reported.** The saved
  `data/cache/feature_set_comparison.json` is not regenerated. Finding 29 does
  not change its values, because all four saved entries lie in the favoured
  direction, where the old formula is already exact.

### Scope interpretation — values derived inside one request (finding 48)

Finding 48's holding-period count and cost breakdown are neither inference nor
an experiment store. They are arithmetic on the simulation that the same
request already runs and already returns. The audited defect is that an
existing field reports a constant where that arithmetic belongs. This spec
treats fixing it as correcting a derivation, not constructing a new number.

If the "delete, don't construct" constraint is read more strictly, FR-009 and
FR-010 fall back to *not computed*, exactly as FR-001 does. That choice
belongs in this spec, before implementation, not in a chat.

---

## Background

### Why the terminal is fixed first

The audit's verdict (`AUDIT.md:5`) is that "a more sophisticated model cannot
repair … invented dashboard evidence." A number on the screen is quoted later
as if it were a result. That is the same failure Rule 3 forbids for costless
returns, reached by a different route.

The first deliverable is a terminal whose every figure is computed, or labelled
as not computed. Anything else is built on top of an interface known to invent
evidence.

### Root cause of finding 57 — why API tests fail on a clean checkout

There are three independent causes. Fixing any one of them leaves the other
two.

1. **CI cannot import the module.**
   - `.github/workflows/test.yml:16` installs `requirements.txt` only.
   - `tests/test_reports_api.py:10` imports `fastapi.testclient` at module
     level.
   - `fastapi` and `httpx` are declared only in
     `reports/requirements-ui.txt:7-9`.

   On a clean runner, discovery raises `ImportError` for the module, unittest
   records it as an error, and the job fails before any API assertion runs.
   This follows from the workflow and requirements files; the remote run
   history was not inspected, because doing so needs `git`/GitHub access this
   lane does not use.
2. **The tests read the developer's cache.**
   - Six tests (ohlcv, stats, gaps, collinearity, tearsheet, rundown) reach
     `get_cached_ticker_data` (`reports/api/routes/data.py:26-57`).
   - That function reads the module-level `CACHE_DIR` (`scripts/data.py:46`),
     i.e. `data/cache/`.
   - `data/cache/` is gitignored (`.gitignore:19`, and every CSV by `*.csv` at
     `:20`).
   - Nothing lets a test supply data, so on a clean checkout the function
     reaches `raise HTTPException(404)` at `:57`.
3. **The tests need a built frontend.** `test_static_frontend_root`
   (`tests/test_reports_api.py:123-128`) requires `reports/web/dist`.
   - That directory is build output, ignored by `reports/web/.gitignore:11`.
   - It is mounted at import time, and only if it already exists
     (`reports/api/main.py:54-56`).
   - CI never builds it.

**A fourth fact is why the failure went unnoticed.** Three of the four tests
that pass on a clean checkout pass *because* they assert a fabricated or
fallback value:
- `test_significance_screening` asserts the hardcoded four entries.
- `test_capital_gate_status` asserts the hardcoded Gate 1 pass.
- `test_list_tickers` passes on the hardcoded fallback list returned for an
  empty cache.

The green part of the suite was measuring the fabrication.

**Common root.** Spec 016 wrote the API tests as integration tests against a
warmed working tree: populated cache, built frontend, UI dependencies
installed. CI was not updated when they arrived.

**What is not the fix.** Committing a cache file, pinning local state,
skipping API tests when a dependency is missing, or building the frontend
inside the Python job would each make the suite pass on one machine. None of
them would make it pass on a clean checkout.

### Precedent for the regressions

The adversarial regression (FR-037) and mutation check (FR-036) follow
established repository practice, and cite it accurately:

- **Spec 003** — synthetic-data proof tests (its SC-001 to SC-003). The
  fixtures here are synthetic for the same reason.
- **Spec 007** — "a regression test MUST fail against the pre-fix code" (its
  FR-007 / SC-005). Every regression here must fail against today's code.
- **Spec 012** — an AST check of the module's import set (its T014) and a
  named-defect mutation check (its SC-007). Spec 017 extends the AST approach
  to banned identifiers (`NoKellyPathTests`) and records a mutation table (its
  T030).

Specs 003 and 007 contain no AST or mutation check themselves. The AST and
mutation shape comes from 012 and 017.

This spec departs from 017 in one way, following finding 58: the mutation
runner lives in the repository, not in a scratchpad.

---

## User Scenarios & Testing *(mandatory)*

The user throughout is Camden, reading the terminal to decide what the
research does and does not show, and reviewing the PRs that change it.

### User Story 1 — No fabricated evidence reaches the terminal (Priority: P1)

As the project owner, I need every forecast, p-value, gate state and test count
on the terminal to come from a computation or say plainly that none exists. A
figure I cannot trace is worse than a blank, because I will quote it.

**Why this priority**: These are the audit's P0 truthfulness defects
(45, 46, 47), and they make up the first clause of the pass condition.

**Independent Test**: Run the terminal API against two synthetic fixtures and
inspect every response. No p-value, forecast probability, model score, test
count or passed gate appears. The same inspection run against today's code
finds each of them.

**Acceptance Scenarios**:

1. **Given** any ticker (AAPL, NVDA, or a fixture-only symbol), **When** the
   significance screen is requested, **Then** the response says the screening
   is not computed, gives a reason naming Stage 3.3, and carries no p-value,
   alpha or pass flag. The Feature Diagnostics screen shows a "Not computed"
   state in place of the table.
2. **Given** the ML rundown is requested, **When** the response is inspected,
   **Then** the forecast item says "not computed" and carries no probability,
   score or horizon claim. Every other item is labelled an indicator rule
   reading. No text says a model predicts, detects or advises.
3. **Given** the capital gate status is requested, **When** the response is
   inspected, **Then** no gate is `passed`, every gate is `unknown` with no
   evidence, and no description states a pass rule or a test count. The header
   shows test status as not reported, with no count and no pulsing success
   dot.
4. **Given** today's route and component code, **When** the fabricated-literal
   regression runs, **Then** it fails, naming each fabricated value.
5. **Given** a copy of the post-018 code with any single deleted literal
   restored, including one on a branch no fixture reaches (the bearish
   `P(Down) = 53.8%`), **When** the regression runs, **Then** it fails.

---

### User Story 2 — Malformed input cannot produce a successful result (Priority: P1)

As the project owner, I need corrupt prices, invalid signals, out-of-domain
costs and malformed requests to fail loudly. None of them may produce a normal
tearsheet with a reconciled badge.

**Why this priority**: These are P0 defects 03 and 04 plus finding 50, and they
make up the second clause of the pass condition.

**Independent Test**: A table of malformed library inputs and HTTP requests.
Every library row raises before any trade is simulated; every HTTP row returns
a documented 4xx.

**Acceptance Scenarios**:

1. **Given** a price frame with a NaN, infinite or non-positive open on a fill
   row, **When** the harness runs, **Then** it raises before simulating, and no
   trade log or summary is produced.
2. **Given** a signal column that holds NaN, integers or strings instead of
   booleans, **When** the harness runs, **Then** it raises.
3. **Given** commission NaN, ±inf or negative, or slippage NaN, ±inf, negative
   or ≥ 10000 bps, **When** any public cost-accepting entry point is called
   (harness, cost hurdle, equity curve, HTTP route), **Then** each rejects it
   for the same stated reason.
4. **Given** any of the audit's probe requests (`short_window=30&long_window=10`,
   `commission=-1`, `commission=nan`, `slippage_bps=10000`, `short_window=0`),
   **When** each is sent, **Then** it returns a documented 4xx naming the
   offending parameter, never 200 and never 500.
5. **Given** a request whose reconciliation genuinely fails or produces a
   non-finite total, **When** the tearsheet is requested, **Then** no response
   claims reconciliation passed, and the screen shows no reconciled indicator.

---

### User Story 3 — API tests pass on a clean checkout (Priority: P1)

As the project owner, I need the test suite to pass on a copy of the repository
with no market-data cache, no built frontend and no network. Only then is a
green CI run evidence about the code rather than about my machine.

**Why this priority**: Finding 57 is the third clause of the pass condition,
and the foundation the regressions in Stories 1 and 2 run on.

**Independent Test**: Copy the repository without `data/cache/` contents,
`reports/web/dist/`, `node_modules/` or virtual environments. Install the
declared dependencies, disable network access, and run the suite. It reports
zero failures and zero errors.

**Acceptance Scenarios**:

1. **Given** the clean copy, **When** the full suite runs, **Then** all API
   tests pass and none is skipped.
2. **Given** the real cache directory is made unreadable for the duration of
   the API tests, **When** they run, **Then** their results are unchanged,
   because they read only fixtures.
3. **Given** a CI run, **When** the Python job runs, **Then** it installs every
   dependency the suite imports from files already declared in the repository.
   A separate job installs the locked web dependencies, then builds and lints
   the terminal.
4. **Given** the mutation runner, **When** it runs, **Then** the unmutated
   control passes, every named mutant fails at least one test, and the source
   files hash identically before and after.

---

### User Story 4 — Derived numbers in the tearsheet and diagnostics are correct (Priority: P2)

As the project owner, I need holding periods, cost components, the McNemar
tail and VIF values to match an independent hand calculation.

**Why this priority**: These are P1 defects (48, 29, 35). None fabricates
evidence, but each reports a wrong number.

**Independent Test**: Small fixtures with hand-computed expected values,
compared against code that shares no implementation with the module under
test.

**Acceptance Scenarios**:

1. **Given** a fixture whose trades span a known number of sessions, including
   one across an exchange holiday, one same-session round trip and one forced
   exit at the final bar, **When** the tearsheet is produced, **Then** each
   trade's holding period equals the hand-counted sessions.
2. **Given** that fixture's fills, **When** costs are reported, **Then**
   commission and slippage are separate totals that sum to the difference
   between costless and net P&L, and spread is reported as not modeled, never
   as zero.
3. **Given** a discordant split in either direction or tied, **When** the
   one-sided McNemar p-value is computed, **Then** it equals the exact binomial
   upper tail; 0 favourable of 2 gives exactly 1.0.
4. **Given** an exact duplicate column, a linear combination, a constant column
   and a nearly singular pair, **When** VIF is computed, **Then** they read
   infinite, infinite, undefined (with a reason, no exception), and a finite
   value ≥ 1 matching the oracle.

---

### User Story 5 — Explanations and labels say what is actually shown (Priority: P2)

As the project owner, I need the terminal's explanatory text to match the data
and policy actually displayed, and to avoid teaching statistics wrongly.

**Why this priority**: Findings 49, 36 and 54 mislead without inventing a
number, so they rank below the P0 truthfulness and validation defects.

**Independent Test**: Check the rendered text against the API data and a list
of banned claims. Neither the text scan nor the render check needs a model.

**Acceptance Scenarios**:

1. **Given** the capital gate screen, **When** its explanation is read,
   **Then** it names the same gates, in the same order, as the API response.
2. **Given** the diagnostics screen, **When** its text is read, **Then** no
   sentence equates a p-value with the chance of luck. Every conditioning badge
   follows from the displayed value and a named threshold. No literal
   improvement ratio or κ/VIF figure appears in prose. Good conditioning is
   described as a numerical property, not evidence of an edge.
3. **Given** a correlation cell with no value, **When** the matrix renders,
   **Then** the cell reads unavailable, not 0.00.
4. **Given** any terminal screen, **When** it is searched, **Then** Kelly sizing
   is not recommended and volume is not described as institutional flow.
5. **Given** the CV screen, **When** it renders, **Then** it is labelled an
   illustration of the splitting scheme and shows no real-looking fold count.
   The tearsheet is labelled a rule-based SMA crossover, not an ML model.

---

### User Story 6 — The local API answers only local origins (Priority: P3)

As the project owner, I need the research API to refuse cross-origin requests
from arbitrary sites while it has no authentication.

**Why this priority**: P1 gap 51. The routes are read-only, so no trading
exploit exists, which ranks it last in this stage.

**Independent Test**: Send a request carrying an untrusted `Origin` header,
then one carrying a listed local origin.

**Acceptance Scenarios**:

1. **Given** an untrusted origin, **When** it calls any endpoint, **Then** the
   response carries no allow-origin header, and credentials are never allowed.
2. **Given** a listed loopback development origin, **When** it calls a
   read-only endpoint, **Then** it is allowed.
3. **Given** the provided server entry point, **When** it starts, **Then** it
   binds the loopback interface only.

---

### Edge Cases

- **No data for a ticker vs. no computation.** A ticker the data layer cannot
  serve keeps its documented 404; that is *unavailable*. A ticker with data but
  no wired computation returns a success response whose status is *not
  computed*. The two must never be merged.
- **Zero trades.** Holding periods are an empty list, and the cost totals are
  computed zeros, not literals. The differential regression therefore uses
  fixtures that produce trades in both variants, so zero-valued fields are
  still exercised.
- **Same-session round trip** (reachable, per `scripts/metrics.py:125`). The
  holding period is 0; the field has no default that could make it 1.
- **Forced final exit at the close.** It counts to the final session, and
  slippage uses the close as the reference price.
- **Values invariant by design** are request echoes (commission, slippage),
  configuration (indicator window lengths) and structural ordinals (rank, gate
  number). They are identical across fixtures by construction. Each is named
  individually in a reviewed allowlist with its reason. A stale allowlist
  entry, one matching nothing, fails the check.
- **A numeric literal on a branch no fixture reaches** is caught by the static
  layer, not the differential layer; the bearish rundown branch is the proof
  case.
- **Slippage at the boundary.** 0 bps is valid; 9999.99 bps is valid but
  absurd; exactly 10000 bps is rejected.
- **Zero commission and slippage** remain valid and explicit. The research
  zero-cost controls of specs 012 and 014 must keep working.
- **Nullable boolean signal columns** holding `pd.NA` are rejected, the same as
  NaN.
- **A single-column design matrix**, or one where every column is constant.
  VIF is undefined for each column, with a reason, and nothing raises.
- **McNemar with zero discordant pairs** keeps its existing result, 1.0.
- **The UI receiving a response without an expected field** treats the field as
  not computed, never as zero.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Fabricated evidence — findings 45, 46, 47

- **FR-001** *(45)*: The significance endpoint MUST return, for every ticker:
  - a computation status of *not computed*
  - a reason stating that saved-run wiring arrives in Stage 3.3
  - no p-value, no alpha and no pass flag

  It MUST NOT return any entry list that could render as a results table.
- **FR-002** *(45)*: The Feature Diagnostics screen MUST render a distinct
  *not computed* state for significance, showing the reason. That state must
  look different from loading, passed and failed. The screen MUST NOT render a
  p-value, a PASSED badge or the table.
- **FR-003** *(46)*: The rundown's forecast item MUST carry no probability,
  score, logit or forward-horizon figure. Its status is *not computed*, with a
  reason stating that fitted-model inference arrives in Stage 3.3. Its category
  and headline MUST NOT say "ML" or "forecast".
- **FR-004** *(46)*: Every remaining rundown item, and the summary verdict,
  MUST be labelled an *indicator rule reading*: the rule and the indicator
  value that triggered it. No response text or UI text may say:
  - that a model predicts, detects or advises
  - that these readings are the drivers of an ML prediction

  The following MUST NOT describe their content as ML or model output:
  - the pane title
  - the collapsed tab label
  - the header toggle
  - the loading text
  - the guide callout
  - the verdict card label
- **FR-005** *(46)*: Rundown text MUST NOT assert a quantitative fact that the
  same request does not compute. The sentences carrying the audited examples
  are deleted, not replaced with other unmeasured figures:
  - a 4% move called a "2-standard-deviation stretch"
  - "significantly higher win rates"
  - a named "theorem"
  - a 55% probability threshold
  - a "$2.00 + 10 bps" hurdle unrelated to the request's cost parameters
- **FR-006** *(47)*: A gate's evidence status MUST be exactly one of `passed`,
  `failed`, `stale` or `unknown`. The four MUST stay distinct values end to
  end, in the API schema and the UI type alike, and never collapse to a
  boolean.
- **FR-007** *(47)*: No verification-artifact reader exists before Stage 3.3,
  so every gate MUST report `unknown`, with no evidence and a reason.
  - A gate MUST NOT be representable as `passed`, `failed` or `stale` without
    an evidence reference; the response model rejects that combination.
  - Gate descriptions and details MUST NOT state a pass rule, or claim evidence
    that is not attached. This removes:
    - the test counts
    - the null-pipeline and cost-stress claims
    - "Sharpe ≤ 0.3"
    - "Deflated Sharpe remains positive"
    - Gate 2's literal diagnostic figures
- **FR-008** *(47)*: The header MUST NOT display a test count or a pass state.
  - Its status indicator derives from an API response and reads *not
    reported*, with no success colour or pulse.
  - The capital gate screen's summary MUST count gates by their returned status
    against the number of gates returned, not a literal 5.

#### Correct derived values — finding 48

- **FR-009** *(48)*: A trade's holding period MUST be the number of sessions
  between its entry session and its exit session, counted by position in the
  price frame the request simulated.
  - Calendar days are not used.
  - A same-session round trip is 0.
  - A forced final exit counts to the final session.
  - The field has no default value.
- **FR-010** *(48)*: The tearsheet MUST report commission and slippage as
  separate totals, computed from that request's actual fills. Spread is
  reported as *not modeled* (no value, with a reason), never zero. The screen
  MUST NOT present commission alone as total friction.
- **FR-011** *(48)*: API responses MUST carry unrounded values. Rounding
  happens only when the UI displays them.

#### Explanatory text — findings 49, 36, 54

- **FR-012** *(49)*: The capital gate explanation MUST describe the gates the
  API returns, either derived from the response or tested equal to its titles
  and order. It MUST NOT:
  - call passed gates "mathematically verified and audited"
  - tell the reader which gate to finish
- **FR-013** *(49)*: Terminal text MUST NOT describe a p-value as the
  probability that a result is luck, or that a model is better. It MUST NOT
  prescribe discarding a model by p-value threshold.
- **FR-014** *(49)*: A conditioning badge or improvement statement MUST follow
  from the value shown beside it and a named threshold; otherwise it is
  removed. None of these may appear as a literal:
  - improvement ratios such as "17x"
  - κ or VIF figures in prose
  - an unconditional "WELL-CONDITIONED" or "ILL-CONDITIONED"
  - "Well below 5.0 line"
  - "no pairwise feature correlation exceeds 0.55"
- **FR-015** *(49)*: The terminal MUST NOT show any of the following:
  - a missing, undefined or non-finite correlation as 0.00; it renders as
    unavailable
  - Kelly sizing, taught or recommended
  - volume described as institutional capital flow or as conviction evidence;
    relative volume is described only as a ratio to its trailing mean
  - a fixed range such as "(3.0 - 12.0)" presented as the expected kurtosis
- **FR-016** *(36)*: The terminal and the named docs MUST state that good
  conditioning is a numerical property of the design matrix, not evidence of
  predictive or economic value. Each named location changes as follows:
  - **Diagnostics banner**: no longer attributes "zero models beat baseline" to
    conditioning, or says standardizing "resolves" it.
  - **Gate text**: `capital_gate.py:28` no longer says spec 014 "proved"
    anything.
  - **Code comment**: `scripts/features.py:39-42` no longer claims ratios make
    training support cover the test window.
  - **Spec 014**: `.specify/specs/014-scale-free-features/spec.md` gets a dated
    audit note appended. Its existing text is preserved, not rewritten.
- **FR-017** *(54)*: The CV screen MUST be labelled an illustration of the
  splitting scheme, not a saved run. It MUST NOT present fold rows, month
  labels or counts as a real run's, and MUST NOT hardcode the saved run's fold
  count; real folds arrive with run selectors in Stage 3.3.
- **FR-018** *(54)*: The tearsheet MUST identify its strategy family as a
  rule-based SMA crossover, not an ML model. The identification appears both in
  the response and on screen beside the headline metrics.

#### Input validation — findings 03, 04, 50

- **FR-019** *(03)*: Before simulating anything, the harness MUST reject:
  - any non-finite or non-positive open or close
  - any signal column whose values are not exactly booleans (NaN, `pd.NA`,
    integers and strings are all rejected)

  Rejection is an explicit error. Nothing partial is returned.
- **FR-020** *(03)*: Trade summaries and equity reconciliation MUST NOT treat a
  missing value as zero. A non-finite trade P&L or total MUST fail, not be
  skipped. A reconciliation comparison MUST fail when either side is
  non-finite.
- **FR-021** *(03)*: The API's reconciliation flag MUST reflect the actual
  outcome of that request's reconciliation, never a literal. The UI shows a
  reconciled indicator only when the flag is true. Corrupt input never
  receives a successful tearsheet.
- **FR-022** *(04)*: One cost-domain rule applies at every public entry point
  that accepts costs:
  - **Commission**: finite, and at least 0.
  - **Slippage**: finite, and in [0, 10000) basis points.
  - **Entry points**: the harness, the cost hurdle, the equity curve and
    performance summary, and the HTTP route.

  Zero cost stays valid.
- **FR-023** *(04)*: One table of out-of-domain values MUST be exercised at
  both the library boundary and the HTTP boundary: NaN, +inf, −inf, negative,
  exactly 10000 bps, and a non-numeric string for HTTP.
- **FR-024** *(50)*: The tearsheet request MUST enforce:
  - windows are integers
  - `short_window` ≥ 1
  - `long_window` > `short_window`
  - `long_window` is at most a documented upper bound
  - costs per FR-022
  - the ticker is one the data layer can serve (documented 404 otherwise)
- **FR-025** *(50)*: An invalid request MUST return a documented 4xx whose body
  names the offending parameter. It MUST NOT return 500, or a tearsheet body.

#### Access boundary — finding 51

- **FR-026** *(51)*: Cross-origin access MUST be limited as follows:
  - **Origins**: an explicit list of loopback development origins, with no
    wildcard.
  - **Credentials**: not allowed.
  - **Methods**: read-only.
- **FR-027** *(51)*: The provided server entry point MUST bind the loopback
  interface only, pinned by a test. TLS, authentication, allowed hosts, rate
  limits and a separate execution-API boundary are Phase 4.

#### Statistics — findings 29, 35

- **FR-028** *(29)*: The one-sided McNemar p-value for "B is better" MUST be
  the exact binomial upper-tail probability, computed directly with that
  alternative. This holds in both directions and for ties. The zero-discordant
  case keeps returning 1.0. The two-sided value is still reported.
- **FR-029** *(35)*: VIF MUST read:
  - **undefined** for a zero-variance column, with a stated reason
  - **infinite** for a column exactly linearly dependent on the others
  - **1/(1 − R²)** otherwise, from regressing that column on the others

  No VIF may be below 1. A constant column MUST NOT raise. The scratch script
  MUST use this implementation instead of its own copy.
- **FR-030** *(35)*: The collinearity endpoint MUST serialize infinite and
  undefined VIF or condition-number values explicitly, without a server
  error. The screen shows them as "infinite (exact collinearity)" or
  "undefined (constant column)".

#### Clean CI — finding 57

- **FR-031** *(57)*: The CI Python job MUST install every dependency the test
  suite imports, from dependency files already declared in the repository. No
  new dependency is added.
- **FR-032** *(57)*: API tests MUST get market data only from deterministic
  fixtures they generate:
  - seeded and synthetic
  - on real exchange sessions
  - injected through an explicit seam

  They MUST NOT read `data/cache/` or the network. A guard test MUST fail if
  any API test reaches the real cache directory.
- **FR-033** *(57)*: Static frontend serving MUST be tested against a
  temporary asset directory the test creates. The Python suite MUST NOT
  require the real build output.
- **FR-034** *(57)*: CI MUST install the web terminal's locked dependencies,
  then build and lint it, in a job separate from the Python job.

#### Oracles and regressions — findings 58, 45–48, 03

- **FR-035** *(58)*: This spec ships these independent oracles, each sharing no
  code with the module it checks:
  - **(a)** NaN, all-NaN and non-positive prices, rejected at both the harness
    and HTTP boundaries.
  - **(b)** Exact singular VIF (duplicate, linear combination, constant, nearly
    singular), checked against a regression written in the test and
    cross-checked against an existing independent library implementation.
  - **(c)** The exact McNemar tail, checked against hand-summed binomial
    probabilities.
  - **(d)** Hand-counted holding periods and a hand-computed cost breakdown for
    a small fixture.

  Each oracle MUST fail against today's code (spec 007 precedent).
- **FR-036** *(58, Rule 9)*: The mutation runner MUST live in the repository.
  - It is not collected by test discovery.
  - It applies each named mutant (SC-002) to a copy, never the source.
  - It runs an unmutated control first.
  - It hashes the source before and after.
  - Its result table is recorded in `tasks.md`.
- **FR-037** *(regression, 45/46/47/48/03)*: A fabricated-literal regression
  MUST exist in three layers, and MUST fail against today's code:
  - **L1, differential.** Every endpoint runs against two fixtures that differ
    in every price, every volume and in length. Any numeric value, or numeric
    figure inside text, that is identical in both fails. The only exception is
    a reviewed allowlist entry naming that response field and why it is
    invariant.
  - **L2, static.** Route modules and response schemas are scanned. Failures
    are:
    - a numeric constant, or text constant containing a numeric figure,
      supplied directly to a response field
    - a numeric default on a computed schema field

    The same allowlist applies. This layer covers branches no fixture reaches.
  - **L3, UI source.** Terminal components are scanned for test-count,
    pass-badge, forecast-probability and p-value literal patterns.

  An allowlist entry that matches nothing fails the check.

#### Constitution and process

- **FR-038** *(Rule 5)*: The holding-period computation (FR-009) aligns trades
  to sessions. It ships with tests in the same PR covering:
  - **Off-by-one**: entry and exit on adjacent sessions.
  - **Boundaries**: first row, same session, forced final exit.
  - **Gaps**: an exchange holiday between entry and exit.
- **FR-039** *(Rule 6)*: No new Python or JavaScript dependency.
- **FR-040** *(Rule 8)*: A single cost-domain rule (FR-022) MUST be shared
  without the signal layer importing the harness, or the harness importing the
  signal layer. Any new shared module, and any import that changes an existing
  module's asserted import set, MUST be recorded in the plan's Complexity
  Tracking.
- **FR-041** *(Rule 9, CLAUDE.md size rule)*: This spec MUST be delivered as
  separately reviewable PRs, each referencing spec 018: one for the
  foundation, which lands first, and one per user story. No PR mixes stories.

### Key Entities

- **Computation status**: whether a displayed quantity was produced.
  - `computed`
  - `not computed`: nothing is wired to produce it; carries a reason naming
    the stage that will.
  - `unavailable`: the input data for it does not exist.
- **Gate evidence status**: `passed`, `failed`, `stale` or `unknown`, with an
  optional evidence reference. The reference is required for every state except
  `unknown`.
- **Cost breakdown**: commission total, slippage total, and spread (`not
  modeled`). All come from one request's fills.
- **VIF value**: finite (≥ 1), infinite (exact linear dependence), or undefined
  (zero variance), with a reason.
- **Invariant allowlist entry**: a response field path plus the reason it is
  identical by construction (request echo, configuration, structural ordinal).
- **Fixture pair**: two seeded synthetic OHLCV panels on real exchange
  sessions. They differ in every value and in length, and both produce trades.
- **Mutant**: a named, single, textual defect applied to a copy of one source
  file, expected to fail at least one test.

---

## Success Criteria *(mandatory)*

### Acceptance criteria — Codex's Stage 3.1 pass condition, verbatim

From `docs/audit-2026-09-12/AUDIT.md:229` (work order 1, *Honest dashboard and
adversarial regressions*):

> No fabricated forecast/p-value/pass badge; malformed inputs cannot yield a successful result; clean API fixtures

As restated in `docs/audit-2026-09-12/REMEDIATION_PLAN.md:71-74`:

> - No fabricated forecast, p-value or pass badge.
> - Malformed inputs cannot produce a successful result.
> - API tests pass on a clean checkout with fixtures.

These are this spec's acceptance criteria. The two wordings differ on the third
clause: "clean API fixtures" versus "API tests pass on a clean checkout with
fixtures". This spec holds itself to the stricter plan wording. Clause 1 maps
to SC-001 and SC-002, clause 2 to SC-003, and clause 3 to SC-004 and SC-005.

### Measurable Outcomes

- **SC-001** *(clause 1)*: The terminal shows zero fabricated forecasts,
  p-values, pass badges or test counts. The regression in FR-037 passes on the
  post-018 code, and fails on today's code for each of these:
  - the four significance p-values
  - the three rundown probability/score strings
  - Gate 1's pass and its "301" text
  - the header's "311/311"
  - `holding_bars=1`
  - the literal reconciliation flag
- **SC-002** *(clause 1, mutation check)*: The unmutated control passes, every
  source file hashes identically before and after, and each of these mutants
  fails at least one test:
  1. A significance entry with `p_value=0.084` restored.
  2. `P(Up) = 54.2% | Logit Score = +0.17` restored.
  3. Only the bearish `P(Down) = 53.8%` restored. This branch is unreachable
     from the fixtures, so the static layer must catch it.
  4. Gate 1 `passed`, with no evidence.
  5. "301 passed" restored in gate details.
  6. The header's "311/311 PASS" restored.
  7. `holding_bars=1` restored.
  8. A literal reconciliation pass restored in the tearsheet route. The static
     layer must catch it: once FR-019 holds, a NaN fill is rejected before it
     can reach the route. The NaN comparison in reconciliation itself is
     covered by the FR-020 oracle.
  9. A cost check reverted to `x < 0`, so NaN is accepted.
  10. The boolean-signal check removed.
  11. McNemar reverted to `1 − p₂/2`.
  12. VIF reverted to the pseudo-inverse diagonal.
  13. The window cross-field check removed.
  14. The CORS wildcard with credentials restored.
  15. The API fixture seam bypassed, so tests read `data/cache/`.
  16. Spread reported as `0.0` instead of not modeled.
  17. The correlation fallback `?? 0` restored.
- **SC-003** *(clause 2)*: Every row of the malformed-input table fails
  explicitly:
  - **Library rows**: NaN, ±inf and non-positive prices on fill and non-fill
    rows; all-NaN prices; NaN, `pd.NA`, integer and string signals; every
    out-of-domain commission and slippage. 0 of them return a trade log.
  - **HTTP rows**: the five audit probes, an unknown ticker, zero and negative
    windows, equal windows, an over-bound window, and non-numeric values. 100%
    return a documented 4xx; 0 return 200 or 5xx.
- **SC-004** *(clause 3)*: The full suite passes on a copy of the repository
  run under these conditions:
  - no `data/cache/` contents and no `reports/web/dist/`
  - declared dependencies installed
  - network unavailable

  The suite reports 0 failures and 0 errors. The API test module covers at
  least the 11 behaviours it covers today, rewritten to assert honest states,
  with none skipped.
- **SC-005** *(clause 3)*: On CI, the Python job passes having installed only
  declared dependencies, and a separate web job builds and lints the terminal
  successfully.
- **SC-006**: Holding periods equal the hand-counted sessions for every fixture
  trade, including the holiday gap, the same-session round trip and the forced
  final exit. Commission plus slippage equals costless P&L minus net P&L within
  1e-9. Spread is reported as not modeled.
- **SC-007**: The one-sided McNemar p-value equals the oracle within 1e-12 for
  every favourable/unfavourable count pair with at most 30 discordant pairs,
  including all ties. The audit's probe (0 favourable of 2) returns exactly
  1.0.
- **SC-008**: Duplicate and linear-combination columns read infinite, and a
  constant column reads undefined with no exception. A nearly singular pair
  reads a finite value ≥ 1 matching the oracle within a relative 1e-6. The
  response model serializes infinite and undefined values without error.
- **SC-009**: An untrusted origin receives no allow-origin header; credentials
  are never allowed; a listed loopback origin is allowed. The entry point binds
  loopback.
- **SC-010**: Text checks pass on the terminal source and rendered data:
  - The gate explanation matches the API's gate titles and order.
  - No "Kelly" appears.
  - No p-value-as-luck or model-discard-by-p phrasing appears.
  - An unknown correlation renders as unavailable.
  - The CV screen carries an illustration label.
  - The tearsheet carries a rule-based SMA label.
  - No rule reading is described as ML or model output.
- **SC-011**: The change reports no new metric, adds no dependency, and
  modifies no saved research artifact.

---

## Assumptions

- **No evidence reader exists before Stage 3.3.** Gates therefore stay
  `unknown` and the significance and forecast fields stay *not computed* until
  specs 027/028 land. That is the intended end state of this stage, not a gap
  in it.
- **Loopback development origins** are the Vite development-server ports
  already named in `reports/api/main.py:33`, 5173 and 3000, on `localhost` and
  `127.0.0.1`. The API's own served frontend is same-origin and needs no CORS
  entry.
- **Fixtures are generated inside the tests.** A committed CSV fixture would be
  ignored by `.gitignore:20` (`*.csv`), and the constitution forbids
  committing market data in any case.
- **Installing `reports/requirements-ui.txt` in CI is a tension, not a
  resolution.** It is the existing, already-justified declaration of `fastapi`
  and `httpx`. But `httpx` is needed only by the test client, which sits
  against CLAUDE.md's "no test dependencies" convention. The tension is
  recorded in the plan's Complexity Tracking and in the handoff, not resolved
  here.
- **The web CI job uses the Node major version the audit built with (24).** The
  exact action and version pin is a plan decision. Action SHA pinning is
  finding 63, spec 040.
- **The rundown's `as_of_date` stays one session behind the raw data** until
  finding 23 is fixed in Stage 3.2. This spec neither fixes nor relabels it.
- **Tests that asserted fabricated values are rewritten, not deleted.**
  `tests/test_reports_api.py:78-84` and `:103-109` asserted the defect; they
  now assert the honest state.
- **Signal columns are required to be the boolean dtype.** Every caller today
  produces booleans (`scripts/signals.py:39-40`, `:65-66`, `:108-109`,
  `:143-144`; `scripts/ml_signal.py:285-286`); the plan audits the rest
  (`scripts/logistic_baseline.py:224-225`,
  `scripts/multi_ticker_comparison.py:262-263`) before the check is enforced.
- **Spec 017 is not touched**, and spec 013's real run stays on hold (Stage
  0.1).
