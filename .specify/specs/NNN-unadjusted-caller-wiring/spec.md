# Feature Specification: Wire Funded-Ledger Callers to the Unadjusted Pipeline

**Feature Branch**: none. Camden creates it.

**Spec number**: **NNN. Not assigned.** Camden assigns it, per the convention in
spec 021 T055 ("Do not create those specs. Camden assigns numbers."). The
directory name `NNN-unadjusted-caller-wiring` is a placeholder. Rename it when
the number is set. Whether this should be a spec at all, or tasks on 020 or
021, is [D-1](#d-1--a-new-spec-not-a-task-appended-to-021).

**Created**: 2026-09-23

**Status**: Draft. Planning only. Nothing is implemented, and no `git` has been
run. D-1 through D-7 need Camden's sign-off. [Blocker B-1](#b-1--no-dividend-paying-ticker-can-produce-a-bundle-today)
means the success path cannot run on real AAPL data when this spec ships. Only
the fail-closed path can.

**Input**: Camden, 2026-09-23: "`scripts/ma_crossover_backtest.py` still calls
data.py's legacy `download_market_data`, which stamps
`price_basis="research_adjusted"`. It never switched to data.py's unadjusted
pipeline. `backtest_harness.py:37`'s guard therefore always raises. Confirmed
by trial `9feef77f`. Scope: switch callers to the unadjusted pipeline. When a
ticker has no unadjusted data, fail closed with a documented unavailable/503,
and never fall back to adjusted prices."

## Why this spec exists

Spec 019 made the harness refuse any frame that is not declared as
historical-dollar prices (`backtest_harness.py:37-38`). Spec 020 built the only
way to get that declaration: `data.load_unadjusted_market_data(manifest_path)`
(`data.py:822-847`). It stamps `price_basis = "unadjusted_dollars"` only after
the manifest, hashes, row counts, date range, session calendar, action
semantics and split discontinuities all pass.

No production entry point calls that loader. Every `run_backtest` caller still
gets its prices from `download_market_data`, and `_tidy` stamps those
`"research_adjusted"` (`data.py:357`). The guard does what it was built to do
and rejects them.

### What the trial registry shows

`docs/trials/trials.jsonl`, trial `9feef77f-5231-409e-b4db-0b0a493e290d`:

- `started` at 2026-09-23T02:41:51.576Z, followed by `errored`
  (`reason: "ValueError"`) at 02:41:51.581Z.
- Runner: `scripts/ma_crossover_backtest.py:run_backtest`.
- Source: `git_sha 0061e75`.
- Both `market_data` and `prices` were recorded with
  `attrs: {"price_basis": "research_adjusted"}` and 502 rows.

### Corrections to the input

- **This is designed behavior, not an unnoticed regression.** Spec 021
  predicted this exact failure (`021 spec.md:120-124`): "After 021,
  `ma_crossover_backtest.main()` ... fail instead on 020's named reason ...
  Wiring the 020 loader into these callers is not 021's job." 021's
  out-of-scope table gives the owner as "Spec 020 follow-up". The trial record
  is the first live confirmation of that prediction.
- **Line 357 is in `data.py`, not in the script.** `ma_crossover_backtest.py`
  has 283 lines. The legacy import is at `:13` and the call at `:214`. `:357`
  is `_tidy`'s stamp in `data.py`.
- **"Unit 5"** refers to spec 019's harness guard (`019 tasks.md:10`;
  `REVIEW_019.md` Part 1). The HTTP 503 precedent in the codebase is
  `reports/api/routes/safety.py:32` ("live safety gate is not configured").
  This spec uses both: the guard stays as the last line of defense, and the
  route reports the unavailable state the way `safety.py` does.

## Caller inventory

Verified with a grep for `download_market_data`, `load_unadjusted_market_data`,
`execution_price_frame` and `run_backtest(` over `scripts/`, `reports/` and
`tests/`.

### Callers that fund a ledger (reach `run_backtest`)

| Caller | Price source today | Result today | This spec |
|---|---|---|---|
| `scripts/ma_crossover_backtest.py` `main()` `:214`, then `:228`, plus `baseline_results` `:102`, `:114` | `download_market_data([TICKER])`, which is `research_adjusted` | `ValueError` from the guard, logged as an errored trial | **In scope** |
| `reports/api/routes/backtest.py` `get_backtest_tearsheet` `:45`, then `:55` | `get_cached_ticker_data` (`routes/data.py:36`) reads raw cache CSVs. **No `attrs` at all**, so the basis is `None` | `ValueError` from the guard, which surfaces as a 500. It also omits `starting_capital` (`:55`) and `baseline_results`' now-required `starting_capital`/`liquidate` (`:77`). Tracked by 018 T024 | **In scope, if D-3 is accepted** |
| `scripts/logistic_baseline.py` `main()` `:314`, then `:333` | `download_market_data`, which is `research_adjusted` | Same guard `ValueError` | **Out of scope**: [D-4](#d-4--logistic_baselinepy-stays-out) |
| `scripts/multi_ticker_comparison.py` `run_one_ticker` `:235`, then `:135`, `:145`, `:276` | `download_market_data` | Caught per ticker as a `ComparisonFailure` | **Out of scope**: frozen (021 D-5). Already recorded in the 021 T055 handoff (`:230`) |

### Callers that do not fund a ledger (research statistics)

These are correct on adjusted prices, and this spec does not touch them:
`autocorrelation_check.py`, `return_stats.py`, `stationarity_check.py`,
`data_pipeline_sanity_check.py`, `feature_diagnostics.py`,
`feature_set_comparison.py` (frozen) and `walk_forward_cv.py`. None of them
calls `run_backtest`. `download_market_data` stays a legitimate research
loader. This spec does not deprecate it.

## Blockers and flags

### B-1 — No dividend-paying ticker can produce a bundle today

- `YFinanceUnadjustedAdapter` is the only adapter in the tree. By design, it
  writes `Dividend_Pay_Date = NaT` for every dividend (`data.py:985-988`).
- `_validate_corporate_actions` rejects any dividend with no payment date
  (`data.py:634-635`). `cache_unadjusted_market_data` validates before it
  writes (`:886-888`).
- So `download_unadjusted_market_data("AAPL", ...)` raises, and no bundle is
  ever written. `data/cache/unadjusted/` does not exist in the working tree
  today.
- This is spec 020's open question 1 ("Vendor Historical Dividend Payment Date
  Availability", `020 spec.md:162-167`), which is still unanswered.
- **A proposed resolution is [D-7](#d-7--dividend-pay-date-a-declared-conservative-bound-not-a-required-vendor-field)**:
  spec 019's declared conservative bound replaces a vendor-sourced pay date.
  It is awaiting sign-off.

**Consequence:** once this spec ships, the AAPL crossover and the tearsheet
**fail closed on every real run** until 020 Q1 is decided. The spec still has
value. It turns an opaque harness `ValueError` and an HTTP 500 into a named,
documented unavailable state. It also puts the wiring in place, so that
answering 020 Q1 is the only step left. The success path is proven only on
synthetic manifest bundles in tests.

### F-1 — Rule 14 still applies once data exists

A bundle from the yfinance adapter declares `capital_gate_eligible = False`
and four `source_limitations`. Rule 14 forbids reporting a backtest on yfinance
corporate actions until they are cross-checked against a second source. This
spec does not do that check. It requires every output built from a bundle to
print the bundle's provenance, so that no result can look more trustworthy than
its source (FR-008).

### F-2 — The signal basis changes, which is a strategy-behavior change

On nominal `Close`, a split reads as a price crash: AAPL's 4:1 split on
2020-08-31, or NVDA's 10:1 split on 2024-06-10. The 10/30 SMA pair would print
a spurious cross-below. Computing the signal on a split-safe series
([D-2](#d-2--the-signal-reads-research_close-fills-read-nominal-open)) changes
which trades the strategy takes compared with the adjusted-price history. Rule
4 therefore applies: the PR that implements this reports all three rows over
the identical bundle. No figure from earlier adjusted-price runs may be quoted
next to them.

## Decisions

Each decision has a recommendation. None is final until Camden signs off.

### D-1 — A new spec, not a task appended to 021

**Recommendation: a new spec, numbered by Camden.** Do not append it to spec
021. Record a pointer in 021 T055's "020 wiring" handoff bullet.

- 021 scopes this out explicitly, under a different owner ("Spec 020
  follow-up") and a different contract (`021 spec.md:177`). Appending it would
  reverse a recorded scoping decision.
- 021 is still a draft with an open gate. It has a pinned residual count
  (SC-001: 21) and a ≤ 400-line PR budget (SC-005). New work there moves both
  targets.
- 021 T055 already frames this as input to a follow-on: "020 wiring: the two
  entry points that now stop on 020's named reason".
- **Alternative considered: tasks on spec 020.** 021 names 020 as the owner.
  But 020 has only a `spec.md`, with no plan or tasks, and its Q1 (B-1) is
  unanswered. Hanging caller wiring on an undecided data-source question would
  couple two reviews that can land independently.
- **Alternative considered: fold it into 018 T024.** That covers only the
  route, not the CLI. See D-3.

### D-2 — The signal reads `Research_Close`; fills read nominal `Open`

**Recommendation.**

- Build the loaded bundle's causal view with `data.execution_price_frame`. Its
  `Research_Close` chains forward only and never rewrites past rows (Rule 1).
- Compute the SMA signal on a copy whose `Close` is `Research_Close`.
- Carry only the resulting `Buy_Next_Open` and `Sell_Next_Open` booleans onto
  the nominal frame that the harness funds.
- Keep `signals.py` unchanged. It still owns "when to trade" on whatever
  `Close` it is handed.
- The basis translation lives in the caller. That keeps it on the caller's
  side of Rule 8.

**Alternative rejected: SMA on nominal `Close`.** It creates split artifacts
(F-2).

**Alternative rejected: SMA on adjusted prices joined to nominal fills.** That
is two sources for one row, and adjusted history is rewritten backward. Rule 1
forbids it.

### D-3 — This spec absorbs 018 T024 (the tearsheet route)

**Recommendation.** This spec delivers T024's predicted outcome: "an explicit
*unavailable* state until unadjusted prices exist" (`018 tasks.md:95-98`).

- **Missing or invalid bundle:** 503, with a documented detail naming the
  ticker and the reason.
- **Valid bundle:** 200. The route passes the same starting capital and
  end-of-data policy that 021 D-3/D-4 set for the CLI.
- **Status line:** Camden marks 018 T024 "superseded by NNN".
- **Stays in 018:** T025 (4xx request domain), T026 (the NaN oracle) and T029
  (fill-derived cost totals).

**Alternative:** leave T024 in 018. This spec then ships only the loader seam
and the CLI, and the route keeps returning a 500 until 018 resumes.

### D-4 — `logistic_baseline.py` stays out

**Recommendation.** Out of scope. Its features and label are built on
adjusted `Close` and frozen as the pre-019 control (021 D-2, still awaiting
sign-off). Switching its data source changes the control. The harness guard
already stops it before any P&L is produced. Record it in the handoff with 021
D-2 as the gate.

### D-5 — Resolve data before opening the trial attempt

**Recommendation.**

- Load and validate the bundle before `research_attempt` opens.
- If no bundle is available, the run stops without writing a trial record,
  because no configuration was evaluated.
- Once the attempt opens, the current `errored` / `abandoned` semantics apply
  unchanged.

**Alternative:** keep an `errored` record for unavailability. That is honest,
but it inflates the attempt count that the DSR gate (Rule 15) deflates by.

### D-6 — Manifest resolution: exactly one bundle, or fail closed

**Recommendation.** `data.py` gains one resolver that maps
(ticker, cache directory) to a manifest path.

| Bundles found | Result |
|---|---|
| Zero | *unavailable* |
| More than one | *ambiguous*, which also fails closed. It never picks the newest one silently |
| Exactly one | That bundle's manifest path |

The CLI accepts an explicit manifest path that overrides the resolver.

- **No network.** The resolver never downloads. Populating the cache stays an
  explicit, separate step (`download_unadjusted_market_data`).

### D-7 — Dividend pay date: a declared conservative bound, not a required vendor field

Added 2026-09-23. It resolves B-1 and spec 020 Q1. The full analysis is
[research R-8](research.md#r-8-does-anything-need-a-dividend-payment-date-analysis-behind-d-7).
**This is a decision only. No validator code is changed by this draft.**

**The prompt.** Norgate, the incoming OHLCV and survivorship vendor, publishes
dividends on the ex-date only, with no payment date. Should the validator
require the ex-date instead of the payment date?

**What the analysis found.**

- **The ex-date is already required.** An action's `Date` is its ex-date, and
  it must be a bundle session (`data.py:624-626`). The live question is
  whether the pay-date requirement stays.
- **Prices do not use the pay date.** `Research_Close`, signals, labels
  (`targets.py:95`), equity, trade P&L, Sharpe and drawdown depend only on
  the ex-date and the amount.
- **The funded ledger does use it.** The harness books a dividend as
  `Receivable` on the ex-date and moves it to `Cash` on the pay session.
  Buying power is cash only. So the pay date decides whether a re-entry
  between the ex-date and the pay date can be afforded
  (`backtest_harness.py:107-137`). `metrics.equity_curve` reconciles the same
  thing.
- **Nothing else reads it:** not `portfolio_risk`, `live_safety_gate`, the
  reports API or the UI.
- **Spec 019 already defined the substitute and it was never built.** 019
  `spec.md:94` says: "if a payment session is not sourced from the vendor, a
  declared upper-bound session is used", with
  `Pay_Date_Basis ∈ {sourced, bound}`. A late bound only rejects more orders.
  It never admits an unaffordable one. The spec 020 validator is stricter
  than 019's contract, and that gap *is* B-1.

**Recommendation: option C1 now, with C2 allowed later.**

- **Keep the ex-date requirement** exactly as it is.
- **Allow a null dividend pay date only when the manifest declares a
  pay-date policy.** In a new manifest version:
  `dividend_pay_date_policy ∈ {sourced, unbounded, bound_sessions:N}`.
  Version-1 manifests stay strict.
- **Default for Norgate: `unbounded`.** An unsourced dividend stays
  `Receivable` for the whole run: counted in equity, never in buying power.
  It is strictly conservative and needs no figure (Rule 11).
- **`bound_sessions:N`** is allowed only with a cited primary-filing source
  showing that N is an **upper bound** for every dividend in the bundle, not a
  typical lag.
- **The loader resolves the date** and adds `Dividend_Pay_Date_Basis`. The
  harness records `Pay_Date_Basis` on dividend events, as 019 promised. Its
  arithmetic, the metrics reconciliation and the pinned 019 tests are
  unchanged.
- **Reports print the policy** beside the provenance (FR-008).

**Rejected: option B,** which treats a dividend as cash on the ex-date. It
admits orders funded by cash the account did not have, silently. That
reverses 019's safety direction.

**Kept as a later option: option A,** vendor-sourced pay dates (020 Q1
(a)/(b)/(c)). It is the only option with true cash timing, which may matter
for paper-trading reconciliation. It is not needed to unblock backtests.

**Cost of C1.** In a fully allocated cash account (`portfolio_risk`,
`max_gross <= 1`), unpaid dividends accumulate. Re-entries can be rejected
that a real account would admit. Every such rejection is a visible `rejected`
ledger event, and equity-based metrics are unaffected. Today's one-share
callers are not materially affected.

**Where it is implemented.** Not in this spec. D-7 changes spec 020's
contract: the validator, the manifest version, the loader and the harness
event field. Recommended owner: a spec 020 follow-up, or the Norgate-adapter
spec, numbered by Camden. This spec only needs the decision recorded, so that
B-1 has a path. Once D-7 is built and a Norgate bundle exists, this spec's
wiring runs green with no code change.

**Still open, and not settled by D-7:**

- 020 Q2: are Norgate dividend amounts pre- or post-split on the ex-date?
- Rule 14: which source is primary and which is the cross-check.
- Norgate's lack of a pay-date field is Camden's reading of the Norgate
  docs. It was not re-verified here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The Phase 0 crossover runs on declared dollars or says why not (Priority: P1)

Camden runs `python scripts/ma_crossover_backtest.py`. If a valid AAPL bundle
exists, the strategy and both baselines are funded on unadjusted dollars and
reported with the bundle's provenance. If none exists, the script stops. It
names the ticker, says that unadjusted data is unavailable, gives the reason,
and exits nonzero. It does not write a trade log or a figure.

**Why this priority**: this is the gap that the trial registry recorded.

**Independent Test**: build a synthetic manifest bundle in a temp cache
directory, then run `main()` against it and against an empty directory. No
network is used.

**Acceptance Scenarios**:

1. **Given** an empty unadjusted cache, **When** `main()` runs, **Then** it
   raises or exits with the named unavailable error. `download_market_data`
   is never called, and no trade CSV or PNG is written.
2. **Given** one valid synthetic bundle, **When** `main()` runs, **Then**
   every frame handed to `run_backtest` carries
   `price_basis == "unadjusted_dollars"` and the bundle's `source_manifest_sha256`.
3. **Given** a bundle whose data file hash no longer matches, **When** `main()`
   runs, **Then** it fails closed with the manifest's own named check. It does
   not fall back to other data.
4. **Given** a synthetic bundle with a 2:1 split mid-series, **When** signals
   are computed, **Then** no crossover is generated by the split session
   itself (D-2).

### User Story 2 — The tearsheet reports *unavailable* instead of crashing (Priority: P1)

A terminal user opens the backtest tearsheet for a ticker.

**Why this priority**: the route returns an undocumented 500 today.

**Independent Test**: `TestClient` with an injected cache directory.

**Acceptance Scenarios**:

1. **Given** no bundle for the ticker, **When** the tearsheet is requested,
   **Then** the response is 503, and its detail names the ticker and says
   "unadjusted price data unavailable".
2. **Given** an invalid or ambiguous bundle, **When** requested, **Then** 503
   with a detail naming the failed check.
3. **Given** one valid synthetic bundle, **When** requested, **Then** 200,
   with three comparison rows over identical bars and costs.

### User Story 3 — No funded path can reach adjusted prices (Priority: P2)

**Why this priority**: the core invariant this spec exists to protect.

**Independent Test**: a static test over the in-scope files and a mutation
check.

**Acceptance Scenarios**:

1. **Given** the in-scope callers, **When** scanned, **Then** neither
   references `download_market_data` or `get_cached_ticker_data` on a path
   that reaches `run_backtest`.
2. **Given** a mutant that falls back to `download_market_data` when the
   bundle is missing, **When** the suite runs, **Then** at least one test goes
   red (Rule 12).

### Edge Cases

- **Two bundles for one ticker** with different date ranges: *ambiguous*,
  fail closed (D-6).
- **A manifest file that is not JSON, escapes the bundle directory, or declares
  another basis**: the existing checks in `_validate_manifest_bundle` fire, and
  the caller reports them as unavailable with that reason.
- **A requested ticker in lowercase**: canonicalized to upper case before
  resolution, matching `cache_unadjusted_market_data`.
- **A bundle shorter than the long SMA window**: the run proceeds and reports
  zero trades, as today. It is not an unavailable state.
- **The legacy adjusted cache files are present** (`AAPL_2y.csv` and similar):
  they are ignored by every in-scope path.
- **A path-traversal ticker on the API** (`../x`): rejected by the same
  canonical-symbol rule before any filesystem lookup. It never reaches a glob.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `scripts/data.py` MUST expose a resolver from (ticker, cache
  directory) to exactly one manifest path. It returns a named unavailable error
  for zero matches and a named ambiguous error for more than one. It never
  reads the network.
- **FR-002**: The unavailable and ambiguous conditions, and any failure from
  `load_unadjusted_market_data`, MUST be distinguishable by callers from
  programming errors. They use one named exception type (or a small family) in
  `data.py` that carries the ticker and the failed check.
- **FR-003**: `ma_crossover_backtest.main()` MUST obtain prices only through the
  resolver and `load_unadjusted_market_data`. It MUST NOT import or call
  `download_market_data`.
- **FR-004**: When FR-002's error occurs, the CLI MUST print a message naming
  the ticker, the phrase "unadjusted price data unavailable", and the reason,
  then exit with a nonzero status. It MUST write no trade log and no figure.
  Per D-5, no trial record is written.
- **FR-005**: The SMA signal MUST be computed from `Research_Close`, which
  `execution_price_frame` derives causally. Fills, P&L and baselines MUST use
  the nominal bundle frame (D-2).
- **FR-006**: The strategy and both Rule 4 baselines MUST run on the identical
  bundle frame, with identical costs, capital and end-of-data policy.
- **FR-007** *(if D-3 is accepted)*: `routes/backtest.py` MUST load through the
  same resolver and loader. It MUST map FR-002's error to HTTP 503 with a
  documented detail, and MUST pass starting capital and the end-of-data policy
  to `run_backtest` and `baseline_results`.
- **FR-008**: Every report built from a bundle (CLI output and the API
  response) MUST state the source name, `downloaded_at_utc`,
  `capital_gate_eligible` and `source_limitations` (F-1, Rule 11).
- **FR-009**: No in-scope code path may fall back to adjusted prices under any
  condition. Tests MUST include a mutant that adds such a fallback, and that
  mutant MUST be killed.
- **FR-010**: The plot and labels MUST stop describing the prices as
  "Adjusted". The figure plots nominal `Close`, labelled as such, and
  `Research_Close` if it is shown at all.
- **FR-011**: All new tests run without network access, using synthetic bundles
  written through `cache_unadjusted_market_data` with a stub adapter, under
  `tests/`.

### Key Entities

- **Unadjusted bundle**: the existing spec 020 artifact. It has a manifest,
  an OHLCV CSV and an actions CSV under `data/cache/unadjusted/`, named
  `{TICKER}_{start}_{end}.*`.
- **Unavailable error**: new. It carries the ticker, a reason category
  (missing / ambiguous / invalid) and the underlying check message.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With no bundle present, the CLI exits nonzero with the named
  message in 100% of runs, and writes zero files and zero trial records.
- **SC-002**: With no bundle present, the tearsheet returns 503 (not 500) for
  every ticker. `test_backtest_tearsheet` is rewritten to assert the 503, and a
  new test asserts the 200 on a synthetic bundle.
- **SC-003**: Zero references to `download_market_data` remain in the in-scope
  files.
- **SC-004**: Every new gate has a recorded red (a mutant killed) and a green
  control (Rule 12).
- **SC-005**: No performance figure is quoted in the implementing PR. Real data
  is unavailable (B-1), and synthetic-bundle P&L is a test oracle, not a
  result.
- **SC-006**: `python -m pytest tests` shows no new failures relative to the
  pre-change baseline recorded in tasks.md.

## Assumptions

- Spec 021 lane B has landed. The script already declares `STARTING_CAPITAL`
  and `LIQUIDATE_AT_END` (confirmed at `ma_crossover_backtest.py:31`, `:37`,
  and in the trial's recorded `module_defaults`).
- Spec 020's loader and validators are correct, and this spec does not edit
  them. It only adds the resolver and the error type beside them.
- `execution_price_frame`'s `Research_Close` is Rule-1 causal (its docstring:
  "chains total returns forward, never adjusts past rows").
- The CLI keeps reading the default `data/cache/unadjusted/` directory unless
  given an explicit manifest path.

## Out of scope, and who owns it

| Item | Owner |
|---|---|
| A payment-date source, so that real bundles can exist (B-1) | Spec 020 Q1 |
| The Rule 14 second-source cross-check (F-1) | A future data-verification spec |
| `logistic_baseline.py` wiring | After 021 D-2 (D-4) |
| `multi_ticker_comparison.py` | The 021 frozen-file follow-on |
| 018 T025, T026 and T029 | Spec 018 |
| Research-statistics scripts | None. Adjusted prices are correct there |
