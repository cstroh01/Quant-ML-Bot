# Research: Terminal Truthfulness (Spec 018)

No `[NEEDS CLARIFICATION]` remained in the Technical Context. Each item below
resolves a design choice the spec leaves open. Format: Decision / Rationale /
Alternatives considered.

---

## R1 — How a quantity that was never computed is represented

**Decision.** A shared status vocabulary, carried in the response body:

- `computed`
- `not_computed` — no computation is wired, and the response carries a `reason`
  that names the stage that will supply one
- `unavailable` — the input data does not exist. This keeps the loader's
  existing documented 404, `reports/api/routes/data.py:57`.

Endpoint shapes:
- **Significance endpoint**: `{ticker, status: "not_computed", reason}`.
  `entries` and `screening_alpha` are removed, so no table can render
  (FR-001).
- **Rundown**: a `model_forecast: {status: "not_computed", reason}` object,
  separate from `rule_readings`. The endpoint path `/api/ml/rundown` is kept;
  renaming a URL is not required by any finding.

**Rationale.**
- **Why not an error code.** A 501 or 404 would reach `App.tsx:95-107`, where
  every fetch has `.catch(() => null)`. `null` renders as an endless loading
  spinner (finding 53, out of scope), which is indistinguishable from "still
  loading". A 200 carrying an explicit status can be rendered, and a test can
  check it.
- **Why keep 404 for missing data.** It is a different fact, and the spec's
  edge cases require the two never be merged.

**Alternatives considered.**
- *HTTP 501 Not Implemented*: rendered as a loader, as explained above.
- *Keep `entries` with `p_value: null`*: still renders a table of estimator
  rows. That implies tests were run.
- *Remove the endpoints*: the UI then fails to load instead of saying why, and
  spec 028 would have to reintroduce them.

---

## R2 — Gate evidence states and what makes `passed` unreachable

**Decision.**
- **Status**: `CapitalGateItem.status: Literal["passed","failed","stale","unknown"]`.
- **Evidence**: `evidence: str | None`, a reference to a verification record.
- **Validator**: a pydantic model validator rejects `status != "unknown"`
  with empty evidence.
- **Pass rules**: descriptions state what kind of evidence the gate needs, and
  no pass rule.
- **Criteria owners**: gate 3's criterion is marked "to be predeclared in
  Stage 3.5 (finding 30)"; gates 4 and 5 are marked as Phase 4 and 5.
- **Test status**: `CapitalGateStatusResponse` gains
  `test_run: {status: "not_computed", reason}`, which is the header badge's
  only source.
- **Summary count**: `CapitalGateView` counts `passed` and `unknown` against
  `gates.length`.

**Rationale.**
- **The four states** are the plan's own list (finding 47).
- **Evidence as a string reference.** No verification-artifact format exists
  until spec 028. A typed record defined now would be speculative, and 028
  would redesign it. The validator enforces the property that matters today:
  `passed` needs *something* to point at.
- **The header reads the API** instead of carrying its own claim. That removes
  the second, independent source of pass state behind "311/311".

**Alternatives considered.**
- *Drop gates 4 and 5*: gates are the project's roadmap. Their status is
  honestly unknown, not absent.
- *Keep `pending`/`in_progress`*: those are workflow states, not evidence
  states. Mixing the two is how "in progress" once carried unsourced
  diagnostic figures (`capital_gate.py:28`).
- *Remove the header badge*: the spec requires a UI state that says the value
  is not reported, not silence.

---

## R3 — The fabricated-literal regression

**Decision.** Three layers in `tests/test_terminal_truthfulness.py`, plus a
mutation runner. Full rules are in
[contracts/regression-and-mutation.md](contracts/regression-and-mutation.md).

- **L1 — differential.**
  - **Setup**: every covered endpoint runs against fixture A and fixture B.
    Both use real exchange sessions and are seeded. They differ in length
    (about 300 vs 347 sessions), in price level, and in drift sign (A up,
    B down), so win rates and trade outcomes differ.
  - **Scalars**: each JSON leaf is collected under a path with list indices
    removed. A numeric path fails if its **set of distinct values** is equal
    across A and B.
  - **Text**: for text, the same test applies to the set of *numeric figures*
    extracted from it.
- **L2 — static AST scan** of `reports/api/routes/*.py` and
  `reports/api/schemas.py`. It fails on:
  - a numeric constant passed as a keyword to a schema-class constructor, or
    bound to a local name that is passed that way (one hop)
  - a `True`/`False` constant passed to a field named `passed*` or
    `*reconcil*`
  - a gate `status` string constant other than `"unknown"`
  - any string constant, or f-string constant part (excluding format specs
    and docstrings), containing a numeric figure
  - a numeric default on an annotated schema field
- **L3 — UI source scan** of `reports/web/src/**/*.{ts,tsx}`. It uses named
  patterns:
  - test counts, e.g. `\d+\s*/\s*\d+\s*PASS` and `\d+\s+passed`
  - `P\((Up|Down)\)\s*=`
  - `Logit`
  - p-value literal claims
  - `Kelly`
  - literal improvement ratios such as `\d+x Improvement`
  - `of 5 Gates`
  - in `FeatureDiagnosticsView.tsx`, the correlation fallback `?? 0`
- **Numeric figure** means a decimal (`54.2`, `+0.17`), a percentage (`55%`),
  a ratio (`311/311`), or a bare integer of three or more digits (`301`).
  Two-digit bare integers such as the "10" in "10-day" are deliberately not
  figures. Numeric *leaves* are always checked, whatever their size.
- **Allowlist.** Each entry is `(endpoint, path or schema.field, category,
  reason[, permitted_figure_regex])`. The categories are:
  - *request echo*
  - *configuration* (must equal a named constant)
  - *structural ordinal*
  - *structurally constant* (for example, buy-and-hold is one round trip)
  - *roadmap reference* (text that may contain only `Stage \d+\.\d+`,
    `finding \d{2}` or `spec \d{3}`)

  An entry matching nothing fails the check.
- **Fixture-independent endpoint.** `/api/capital_gate/status` takes no data,
  so L1 cannot apply to it. It is covered by L2 and by explicit state
  assertions (all gates `unknown`, the evidence validator, no figure outside
  roadmap references).
- **Coverage completeness** (PR G): every `GET /api/...` route registered on
  the app must be in the L1 table or the fixture-independent table. The
  `PENDING_COVERAGE` table must be empty.

**Rationale.**
- **Why "set of distinct values" rather than index-by-index equality.** Many
  computed values coincide at individual indices across fixtures: flat-bar
  P&L of 0.0, first-bar drawdown 0.0, positions 0/1. Comparing values at the
  same index would drown the check in false positives. Comparing whole
  sequences lets a repeated literal escape: `holding_bars=1` gives `[1]*5`
  against `[1]*7`. Distinct-value sets catch the literal (`{1}` = `{1}`) and
  pass computed columns.
- **Why L2 exists.** L1 sees only the branch each fixture takes. The bearish
  rundown literal `P(Down) = 53.8%` (`ml_rundown.py:73`) is invisible to a
  fixture pair that both lean bullish.
- **Why L2 scans all string constants rather than keyword values.** The
  fabricated forecast is assigned to a local variable first
  (`ml_rundown.py:61`), then passed on (`:175`).
- **Why the bool rule is field-scoped.** `reconciliation_passed=True`
  (`backtest.py:168`) and `passed_screening=True` (`diagnostics.py:94`) are
  pass badges, but most booleans are not.
- **Precedent.** Specs 012 and 017 use `ast`-based checks (import sets,
  banned identifiers). Spec 007 requires a regression that fails against the
  pre-fix code. Spec 003 uses synthetic data.

**Alternatives considered.**
- *A JSON-schema "computed field" annotation*: needs every future field to be
  tagged correctly, and a missed tag is silent.
- *Snapshot tests of responses*: they pin the fabrication as easily as the
  truth.
- *A regex over route source for digits*: flags every threshold and window
  length, which trains people to ignore it.
- *The TypeScript compiler API for L3*: adds a Node-side test harness, which
  breaks the no-test-dependency convention further.

---

## R4 — Test seam for market data and static assets

**Decision.**
- **Cache seam**: `reports/api/routes/data.py` gains a dependency
  `get_cache_dir() -> Path` returning `data.CACHE_DIR`.
  `get_cached_ticker_data(ticker, cache_dir)` takes it explicitly, and every
  route that loads data declares `cache_dir: Path = Depends(get_cache_dir)`.
- **App factory**: `reports/api/main.py` exposes
  `create_app(*, dist_dir: Path | None = DEFAULT_DIST_DIR) -> FastAPI`.
  `app = create_app()` is kept at module level, so
  `uvicorn reports.api.main:app` and `python -m reports.api.main` are
  unchanged.
- **How tests use it**: they build `create_app(dist_dir=None)` or
  `create_app(dist_dir=<tmp with index.html>)`, and set
  `app.dependency_overrides[get_cache_dir]` to a temporary directory holding
  the fixture.
- **Guard**: `setUpModule` in the API test modules points `data.CACHE_DIR` and
  `routes.data.CACHE_DIR` at a non-existent path, so any read that bypasses
  the seam 404s and fails the test (mutant 15).
- **Fixture writer**: `tests/api_fixtures.py`.
  - **Sessions**: `data.trading_days`.
  - **Prices**: log-normal closes with seeded `numpy.random.default_rng`.
  - **Bar shape**: Open near the previous close; High and Low bracketing
    Open/Close; positive volume.
  - **Tickers**: `AAPL` and `NVDA` (synthetic values).
  - **Output**: the loader's primary filename, in the temporary directory.

**Rationale.**
- **Why `dependency_overrides`.** It is FastAPI's documented substitution
  mechanism and needs no module-global patching. The audit's own probe had to
  patch `CACHE_DIR` twice (`probes.py:86-89`).
- **Why the factory.** It removes the import-time `DIST_DIR.exists()` decision
  (`main.py:54-56`) that tied a test result to whether someone had run
  `npm run build`.
- **Why generate fixtures.** A committed CSV fixture is ignored by
  `.gitignore:20`, and the constitution forbids committing market data.
- **Why the primary filename.** It keeps tests off the glob fallback that
  spec 027 deletes (Complexity Tracking #10).

**Alternatives considered.**
- *`unittest.mock.patch` of `CACHE_DIR`*: works, but leaves the production
  code without a seam, and a patch applied in the wrong module is silent.
- *`app.state.cache_dir`*: comparable. Rejected because it bypasses FastAPI's
  dependency graph, which the error-handling tests also use.
- *A committed `tests/fixtures/*.parquet`*: `*.parquet` is also gitignored,
  and it is still market-shaped data.

---

## R5 — CI jobs

**Decision.**
- **Job `test`**: add `pip install -r reports/requirements-ui.txt` after the
  root requirements. It keeps `python -m unittest discover -s tests` and stays
  on Python 3.12.
- **New job `web`** (`runs-on: ubuntu-latest`,
  `defaults.run.working-directory: reports/web`):
  - checkout
  - `actions/setup-node` on Node `24` with an npm cache keyed on
    `reports/web/package-lock.json`
  - `npm ci`
  - `npm run lint`
  - `npm run build`
- Both jobs run on the existing triggers.
- Action references follow the file's current tag style. SHA pinning,
  permissions and timeouts belong to finding 63 (spec 040).

**Rationale.**
- **Why the UI requirements file.** The API tests need `fastapi` and `httpx`,
  and that file already declares both with Rule 6 justifications.
- **Why a separate web job.** The web build needs Node, and the Python job
  should not.
- **Why Node 24.** The audit built the web terminal successfully on Node
  24.19.0.
- **Why `npm ci`.** It installs exactly the committed lock.

**Alternatives considered.**
- *A single job with both toolchains*: couples a Python failure to a Node
  install.
- *Building `dist` in CI for the Python static test*: R4 removes the need.
- *Merging the UI requirements into `requirements.txt`*: changes what research
  environments install. That is finding 61's dependency-groups work
  (spec 039).

---

## R6 — One cost-domain rule

**Decision.** `scripts/cost_domain.py`, importing only `math`, with:

- **`validate_costs(commission_per_trade, slippage_bps) -> None`**
  - Raises `TypeError` for bool or non-real values.
  - Raises `ValueError` for a non-finite or negative commission.
  - Raises `ValueError` for a non-finite slippage, or one outside `[0, 10000)`.
- **Message format**: each error names the parameter and its value.
- **Constant `MAX_SLIPPAGE_BPS = 10_000`** (exclusive bound).

Callers:
- `backtest_harness.run_backtest` — replaces `:46-49`.
- `metrics.equity_curve` — replaces `:95-100`; `performance_summary` inherits.
- `ml_signal._validate_costs` — delegates the cost part and keeps its `shares`
  checks at `:69-72`.
- The tearsheet request dependency — maps `ValueError`/`TypeError` to 422
  with the parameter name.

**Rationale.**
- **What the rule is.** Finding 04 asks for one rule. `math.isfinite` rejects
  NaN and ±inf, which `x < 0` never did.
- **Why exclusive 10000.** `ml_signal` already rejects ≥ 10000, because the
  break-even divides by `1 − s`; the harness accepts it and then produces a
  zero sale price. Exclusive 10000 is the stricter existing value.
- **Existing tests.** `tests/test_ml_signal.py:178` already expects 10000 to
  be rejected by `ml_signal`.

**Alternatives considered.** See Complexity Tracking #1.
- *Pydantic-only constraints at HTTP*: gives a second definition of the domain
  in the API.
- *Validating in `summarize_trades` only*: too late; the harness would already
  have simulated.

---

## R7 — Harness input validation and reconciliation

**Decision.**
- **Price validation.** `run_backtest` validates before its loop:
  - `Open` and `Close` are numeric
  - every value is finite and `> 0`
  - `Buy_Next_Open` and `Sell_Next_Open` have exactly numpy `bool` dtype

  Nullable `boolean` (with `pd.NA`), object, integer and float columns are
  rejected. The error names the column and the first offending row position.
- **Summary.** `summarize_trades` raises when any `P&L` is non-finite.
  `.sum()` stays, but only on validated values.
- **Reconciliation comparison.** `metrics.equity_curve` fails reconciliation
  when `actual` or `expected` is non-finite. It keeps its `ValueError`
  contract.
- **Reconciliation report.** New
  `metrics.reconciliation_report(prices, trade_log, *, commission_per_trade, slippage_bps)`
  returns `{passed: bool, abs_difference: float | None, tolerance: float}`.
  It uses the same arithmetic as the check, and does not raise on mismatch.
- **Tearsheet route.**
  1. Validate the request.
  2. Run the harness.
  3. Call `reconciliation_report`.
  4. If `passed` is false, raise HTTP 500 with detail `"reconciliation failed"`.
  5. Otherwise build the tearsheet and include the report object.

**Rationale.**
- **What the probes showed.** A NaN fill gave NaN trade P&L, and a
  NaN-skipping sum reported 0.0 (`probe-results.json:11-18`). `NaN > tol` is
  false, so NaN reconciled. A NaN signal is truthy at
  `backtest_harness.py:67`, `:81`.
- **Callers are already compatible.** Every in-repo signal producer emits
  numpy `bool`:
  - `signals.py:39-40`, `:65-66`, `:108-109`, `:143-144`
  - `ml_signal.py:285-286`
  - `logistic_baseline.py:180-189` (`astype(bool)`, then shifts with
    `fill_value=False`)
  - `multi_ticker_comparison.py:262-263`, which goes through `ml_signal`
- **Why a report object.** A boolean that is `true` in every 200 response is a
  constant, not evidence. The computed absolute difference is evidence.
- **Why 500 on failure.** A reconciliation failure on validated input is a
  server defect, not a client error.

**Alternatives considered.**
- *Validate only rows where a fill occurs*: leaves the equity curve marking
  to a NaN close.
- *Coerce int 0/1 signals*: the audit explicitly asks for exact booleans.
- *Keep `reconciliation_passed: bool`*: always true when present, so it
  carries no information.

---

## R8 — Holding bars and cost breakdown

**Decision.**
- **Holding bars.** `ma_crossover_backtest.holding_bars_per_trade(prices,
  trade_log) -> pd.Series[int]`, as exit-row position minus entry-row
  position.
  - It uses the same date-to-row map as `mean_holding_bars`
    (`ma_crossover_backtest.py:53-55`).
  - `mean_holding_bars` is refactored to call it, and its result stays
    bit-identical (`max(1, round(mean))`).
  - A same-session round trip gives 0.
  - The schema field has no default.
- **Cost breakdown.** `backtest_harness.trade_cost_breakdown(trade_log, *,
  commission_per_trade, slippage_bps) -> dict`.
  - `commission_total = 2 × c × n_trades`.
  - `slippage_total = Σ [E·s/(1+s) + X·s/(1−s)]`, where `E` and `X` are the
    recorded slipped entry and exit fills.
  - `spread = None`, with `spread_status = "not_modeled"`.
  - It validates costs through `cost_domain`.
- **Oracle.** Hand-counted sessions on a fixture with a holiday, a same-session
  trip and a forced final exit. Independently, `run_backtest` at zero cost on
  the same signals: `Σ costless P&L − Σ net P&L = commission_total +
  slippage_total` within 1e-9.

**Rationale.**
- **Why `ma_crossover_backtest.py`.** It is the script that already sees both
  the price frame and the trades, and whose existing function performs this
  mapping.
- **Why invert fills.** The harness records `E = O·(1+s)` and `X = O·(1−s)`
  (`backtest_harness.py:68`, `:83`, `:89`), so the raw price is exactly
  recoverable, and the slippage dollars are `E − O` and `O − X`.
- **Why rerun at zero cost for the oracle.** That shares no formula with the
  breakdown.

**Alternatives considered.**
- *Count calendar days*: wrong unit (the baseline logic counts rows for the
  same reason).
- *Store raw opens in the trade log*: changes `TRADE_LOG_COLUMNS`; see
  Complexity Tracking #3.
- *Report spread as 0*: FR-010 forbids it; a zero reads as measured.

---

## R9 — Unrounded export

**Decision.** Remove every `round(...)` applied to response values in
`reports/api/routes/backtest.py` and `reports/api/routes/diagnostics.py`
(including `correlation.round(3)` at `:70`). The UI's existing `toFixed`
calls do all rounding.

**Rationale.** Finding 48 asks for unrounded export. Rounding in the API makes
L1's set comparison coarser, and hides reconciliation differences.

**Alternatives considered.**
- *A `?precision=` parameter*: a feature nobody asked for.

---

## R10 — Tearsheet request validation

**Decision.** A request dependency `TearsheetParams`:

- **Windows**: `short_window: int = Query(10, ge=1, le=252)` and
  `long_window: int = Query(30, ge=2, le=252)`.
- **Costs**: `commission: float = Query(1.0)` and
  `slippage_bps: float = Query(5.0)`, validated by
  `cost_domain.validate_costs`.
- **Cross-field**: `long_window > short_window`.
- **After loading data**: `long_window < number of loaded sessions`.
- **Error body**: FastAPI's standard 422 shape,
  `{"detail": [{"type", "loc": ["query", "<param>"], "msg", "input"}]}`.
  Cross-field and cost errors are raised in that same shape.
- **Unknown ticker**: the existing 404, `{"detail": "No cached data found for
  ticker X"}`.
- **Upper bound 252**: one trading year of window. The UI sliders top out at
  100 (`BacktestTearsheetView.tsx:263-289`).

**Rationale.**
- **Probe failures.** `short>long` and negative commission gave 500, and
  `short_window=0` gave 200 (`probe-results.json:127-133`).
- **Why FastAPI's shape.** One error shape across built-in and custom checks,
  so the contract documents it once.

**Alternatives considered.**
- *400 for cross-field errors*: gives two shapes for one class of client
  error.
- *Clamping windows silently*: produces a normal-looking chart for an invalid
  request, which finding 50 forbids.

---

## R11 — CORS and loopback

**Decision.**
- **Allowed origins**: `ALLOWED_ORIGINS = ("http://localhost:5173",
  "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000")`.
- **Middleware**: `allow_credentials=False`, `allow_methods=["GET"]`, default
  headers.
- **Loopback**: `start()` keeps `host="127.0.0.1"`, pinned by a test that
  patches `uvicorn.run`.

**Rationale.**
- **What the probe showed.** The untrusted origin was reflected with
  credentials (`probe-results.json:134-140`).
- **Credentials.** There is no authentication, so credentials serve no
  purpose.
- **Methods.** Every route is GET.

**Alternatives considered.**
- *Removing CORS entirely*: breaks the Vite dev server on 5173.
- *An environment-variable origin list*: configuration without a consumer.
  Phase 4 designs the remote boundary.

---

## R12 — Exact one-sided McNemar

**Decision.**
- **One-sided p**:
  `p_one_sided = scipy.stats.binomtest(b_wins, a_wins + b_wins, 0.5,
  alternative="greater").pvalue`, computed directly in both directions and
  for ties.
- **Two-sided p**: `p_two_sided` stays statsmodels' exact McNemar.
- **Zero discordant pairs**: the early return (`:375-389`) is unchanged at 1.0.
- **Oracle**: a test computes `Σ_{k=b}^{n} C(n,k) / 2^n` with
  `math.comb`, exhaustively for `n ≤ 30`.
- **Existing test**: `test_mcnemar_is_not_inverted_either`
  (`tests/test_feature_scaling.py:746-752`) is kept, and gains the 0-of-2 case
  and a tie.

**Rationale.**
- **Where the old formula fails.** In the favoured direction (`b > a`),
  `two_sided/2` equals the exact upper tail, because the exact binomial is
  symmetric at 0.5. It fails in the unfavoured direction and for ties, where
  `1 − p₂/2` omits the observed mass: 0 of 2 gives 0.75 instead of 1.0.
- **Why the existing test missed it.** At 60/140 both values exceed 0.9.
- **Saved results.** All four saved comparison entries are favoured
  (`probe-results.json:334`, `:350`, `:366`, `:382`), so no saved value
  changes.
- **Dependency.** `binomtest` is in scipy, already pinned.

**Alternatives considered.**
- *Fix the arithmetic by adding back the observed probability*: re-derives
  what `binomtest` states directly, which is the same reasoning spec 014 used
  for Wilcoxon (`feature_set_comparison.py:415-417`).

---

## R13 — Singular-aware VIF

**Decision.** `variance_inflation_factors` regresses each standardized column
on the other non-constant standardized columns with `numpy.linalg.lstsq`.

- **Zero-variance column**: `NaN` (undefined).
- **Exact dependence** — `SSR ≤ 1e-10 × SST`: `+inf`.
- **Otherwise**: `1 / (1 − R²)`, which is `≥ 1` by construction (clipped at 1
  against round-off).
- **Reasons**: `diagnose()` adds `vif_status: {column: "finite" | "infinite" |
  "undefined"}`.
- **API**: serializes a VIF or condition number as
  `{value: float | null, status}`, because JSON has no infinity.
- **Scratch script**: `scratch_multiticker_collinearity.py` imports the
  function instead of its copy at `:112-120`.
- **Oracle.** A test-local regression, plus statsmodels
  `variance_inflation_factor` on the design with a constant column. Cases:
  - duplicate column
  - `c = 2a − b`
  - constant column
  - `b = a + 1e-3·noise`, matched within a relative 1e-6

**Rationale.**
- **Why a regression, not a pseudo-inverse.** The pseudo-inverse diagonal is
  not VIF for singular matrices; the probe got 0.25 for exact duplicates
  (`probe-results.json:2-5`). Regressing each column states the definition
  directly.
- **Why constants no longer raise.** Standardization leaves a zero column, and
  `corrcoef` then produces NaN rows, which break the SVD (`:6`). Treating the
  column as undefined up front avoids that path.
- **Why the 1e-10 threshold.** It sits far above float64 round-off on
  standardized data, and far below any genuinely near-singular design: the
  1e-3 noise case has `SSR/SST ≈ 1e-6`.

**Alternatives considered.**
- *statsmodels' VIF in production*: it needs an explicit constant column, and
  divides by zero with a warning rather than stating a policy.
- *Keep the pseudo-inverse and post-check the rank*: still returns meaningless
  finite values for the dependent subset.

---

## R14 — The single "not computed" UI state

**Decision.** `reports/web/src/components/common/NotComputedNotice.tsx`, with
props `{label, reason, compact?}`.

- **Look**: neutral grey border, a single "Not computed" or "Not reported"
  heading, and the reason text.
- **Forbidden in it**: spinner, pulse, and green, red or amber success/failure
  colouring.
- **Used by**:
  - significance (FeatureDiagnosticsView)
  - the forecast (MLRundownPane)
  - the header test badge (`compact`)
  - each gate's status chip in CapitalGateView
- **Types**: `types/api.ts` mirrors the schemas. A missing field is typed as
  optional and rendered as not computed, never coerced to 0.

**Rationale.** One component means one visual meaning. FR-002 requires it to
look different from loading, pass and fail.

**Alternatives considered.**
- *Reusing the loading spinner with different text*: this is the confusion
  finding 53 describes.

---

## R15 — Delivery order and PR split

**Decision.** Eight PRs, A through G as tabled in [plan.md](plan.md); PR B
spans US1. Each PR description states:
- the spec (018) and the findings it closes
- that no metric is reported, so Rule 2 and Rule 3 metric fields are N/A
- no new dependency

The regression's coverage table grows per PR. `PENDING_COVERAGE` is emptied by
PR G.

**Rationale.**
- **Size.** CLAUDE.md makes reviewability a hard constraint.
- **Why a growing regression.** It keeps every intermediate state honest
  without temporary allowlists.
- **Why A first.** Every later PR's tests run on its fixtures and CI.

**Alternatives considered.**
- *The plan's original 018/019/020/021 split into four specs*: not used,
  because the run request assigns all of Stage 3.1 to one spec. The flag is
  in the handoff.
- *One PR per finding*: 15 PRs, several of them one-line changes in files
  another PR rewrites.
