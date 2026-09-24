# Research: Wire Funded-Ledger Callers to the Unadjusted Pipeline

Every finding below was read from the tree on 2026-09-23. Line numbers are
from that reading.

## R-1 Where the adjusted basis enters

**Finding.**

- `download_market_data` downloads with `auto_adjust=True` (`data.py:410-417`).
- Every return from it passes through `_tidy`, which stamps
  `attrs["price_basis"] = "research_adjusted"` (`data.py:357`). That covers
  both the cache-hit path (`:408`) and the download path (`:442`).
- The harness rejects anything other than `"unadjusted_dollars"`
  (`backtest_harness.py:37-38`).
- The only code that can apply that stamp is `load_unadjusted_market_data`
  (`data.py:822-847`), after `_validate_manifest_bundle` passes.
- `UnadjustedSourceSnapshot` deliberately has no basis field (`:75-90`).

**Decision.** Keep all of that. Add a ticker-level entry point beside the
loader rather than inside it. The loader keeps its "manifest path in,
validated frame out" contract. The entry point adds resolution and error
normalization.

**Alternative rejected: re-stamping adjusted data.** Spec 020 forbids it
outright (`020 spec.md:115`, `:122`).

## R-2 Resolving a ticker to a manifest

**Finding.**

- Bundles are written as `{TICKER}_{start}_{end}.manifest.json` in the cache
  directory (`data.py:895-897`).
- Tickers are canonicalized with `ticker.upper()` and must match
  `[A-Z0-9.-]+` (`:867-869`).
- The resolver cannot rely on a plain glob `TICKER_*`, because a stem like
  `A_...` must not match `AA_...`. It needs an exact-stem regex:
  `^{re.escape(TICKER)}_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.manifest\.json$`.
- `data/cache/unadjusted/` does not exist in the working tree today.

**Decision.** Apply the same canonicalization and symbol rule first. A ticker
that fails the rule is `invalid` before any filesystem access, which also
closes the path-traversal edge case. Then:

| Bundles matched | Result |
|---|---|
| Zero, or the directory is absent | `missing` |
| More than one | `ambiguous` |
| Exactly one | That path |

**Alternative rejected: choosing the latest `end_date`.** It is silent, and
two bundles can disagree about history (different vendors or revisions). A
caller that wants a specific bundle passes its path explicitly.

## R-3 Which exceptions count as "unavailable"

**Finding.**

- `_read_manifest_document` and `_read_hashed_member` raise
  `FileNotFoundError` (`:679`, `:693`).
- Every validation check raises `ValueError` with a "`<name>` check failed"
  message (`:510-790`).
- `_merge_actions_for_execution` indexes positions by the validated sessions,
  so it cannot fail on a validated bundle.

**Decision.** `load_unadjusted_for_ticker` wraps only the call to
`load_unadjusted_market_data`. It converts `FileNotFoundError` and `ValueError`
into `UnadjustedDataUnavailable(reason="invalid", check=str(error))`, chained
with `from error`.

Nothing outside that single call is wrapped, so a programming error in the
caller still surfaces as itself.

## R-4 Signal basis across splits

**Finding.**

- `sma_crossover_signal` reads `Close` only (`signals.py:22-23`).
- On nominal prices, a 4:1 split divides `Close` by four, and the 10-bar SMA
  crosses below the 30-bar SMA within a few sessions for no economic reason.
- `execution_price_frame` derives `Research_Close` by chaining
  `Split × (Close + Dividend) / Close.shift(1)` forward (`data.py:476-478`).
  It is continuous across splits and uses only data from rows at or before
  each row (Rule 1).

**Decision.** In `ma_crossover_backtest.py`, add
`research_close_signal(nominal, short, long)`. It:

1. Runs `execution_price_frame(nominal)`.
2. Swaps a copy's `Close` for `Research_Close`.
3. Calls `sma_crossover_signal`.
4. Returns the **nominal** frame (with its attrs intact) plus `Buy_Next_Open`,
   `Sell_Next_Open`, and the SMA columns renamed `Short_SMA_Research` and
   `Long_SMA_Research`, so their units are unambiguous.

The route imports the same helper, so the CLI and the API cannot diverge.

**Check.** The spec 020 fixture (`test_020…:23-35`, a 4:1 split on
2024-01-04) extended to at least 40 sessions shows the difference. The helper
emits no signal on the split session. The nominal-`Close` control emits a
cross-below. That pair is the Rule 12 red/green for US1 AS4.

**Alternative rejected: moving the basis choice into `signals.py`.** It would
teach the signal layer about price bases, which crosses Rule 8.

## R-5 The tearsheet test fixture

**Finding.**

- `test_reports_api.py:26-29` builds `synthetic_panel(**FIXTURE_A)` and sets
  `attrs["price_basis"] = "unadjusted_dollars"` by hand.
- `fixture_client` writes the panel to CSV. Attrs do not survive a CSV round
  trip, and the route reads the CSV back through `get_cached_ticker_data`,
  which applies no stamp. So the hand stamp never takes effect, which is why
  018 records `test_backtest_tearsheet` as erroring on the guard.

**Decision.**

- For the tearsheet only, publish a synthetic AAPL bundle into
  `<fixture cache dir>/unadjusted/` through `cache_unadjusted_market_data` with
  a stub adapter.
- Remove the hand stamp.
- The route derives its bundle directory as `cache_dir / "unadjusted"` from the
  existing `get_cache_dir` dependency. The test override therefore steers it,
  and no new dependency is needed.

**Fixture constraint.** The bundle validation requires a complete session
calendar (`trading_days`). The fixture must therefore generate its dates from
`data.trading_days(start, end)`, not from a business-day range.

## R-6 Mutants

| Gate | Mutant | Must be killed by |
|---|---|---|
| No fallback (FR-009) | In `main()`, on `UnadjustedDataUnavailable`, call `download_market_data` instead | CLI unavailable test (no call; nonzero exit) |
| Ambiguity (D-6) | The resolver returns `sorted(matches)[-1]` when there are two | resolver-ambiguous test |
| Stem exactness | The resolver uses the glob `f"{ticker}_*"` | `A` vs `AA` test |
| Signal basis (D-2) | The helper passes the nominal frame to `sma_crossover_signal` | split-session test |
| Load before attempt (D-5) | Load moved inside `research_attempt` | "no trial record" test, against a temporary ledger |
| 503 mapping [D-3] | The route lets the error propagate (500) | tearsheet-503 test |
| Capital threading [D-3] | The route omits `starting_capital` from `baseline_results` | tearsheet-200 test |

The driver lives at `tests/mutation/run_unadjusted_wiring_mutants.py` and
follows `run_spec_018_mutants.py`: it copies to a temp tree, applies one mutant
at a time, invokes pytest, and requires a nonzero exit.

## R-7 Trial ledger interaction

**Finding.** `research_attempt` writes `started` on entry and `errored` on any
exception (`trial_runner.py:114-128`). Trial `9feef77f` is exactly that pair.

**Decision (D-5).** Resolve and load before the `with research_attempt(...)`
block. The test points the ledger at a temporary path, using the conftest-injected `SPEC033_SYNTHETIC_ROOT` ledger (`tests/conftest.py:22-35`), following the existing
`test_033_trial_instrumentation` pattern, and asserts that the file is
unchanged after an unavailable run.

`research_config(..., locals())` will then also record the bundle's attrs,
including `source_manifest_sha256`, which is better provenance than today's.

## R-8 Does anything need a dividend payment date? (analysis behind D-7)

**Question (Camden, 2026-09-23).** Norgate Data is coming in as the OHLCV and
survivorship-bias vendor. Norgate's dividend indicator carries the ex-date
only; the `norgatedata` package has no payment-date field. This is Camden's
reading of Norgate's API docs. It was not independently re-checked here.
Should the bundle validator require the ex-date instead of the payment date?

### Two corrections to the framing

1. **The ex-date is already required.** Each action row's `Date` *is* its
   ex-date, and it must be a price session in the bundle
   (`data.py:624-626`). So the question is not "ex-date instead of pay
   date". It is **whether the payment-date requirement should stay, and what
   replaces it if not.**
2. **Point-in-time correctness is Rule 1, not Rule 5.** Rule 5 requires tests
   on anything touching time. The substance holds: the price series and
   `Research_Close` depend only on the ex-date and the amount
   (`data.py:476-478`).

### Where the payment date is consumed

Found by grepping `Dividend_Pay_Date|payment|receivable` over `scripts/`,
`reports/` and `tests/`. It appears only in `backtest_harness.py`,
`metrics.py` and `data.py`, plus their tests.

| Site | What it does with the pay date | Moves prices? | Moves the account? |
|---|---|---|---|
| `data._validate_corporate_actions` `:632-642` | Requires it for every dividend. It must be ≥ ex-date and must be a market session | — | — (gate only) |
| `data.execution_price_frame` `:473-475` | Requires it, then ignores it in `Research_Close` | No | No |
| `backtest_harness.run_backtest` `:44-47` | Requires it for every dividend | — | — (gate only) |
| `backtest_harness.run_backtest` `:107-128` | On the ex-date, books `quantity × Dividend` as `Receivable` and as trade `Dividend Income`. On the pay session, moves it `Receivable → Cash` | No | **Yes: cash and buying power** |
| `metrics.equity_curve` `:146-156` | Replays pending payments by the source pay date, to reconcile the ledger | No | Checks the harness |
| `targets.py:95` | Masks labels that span an action. **Uses the ex-date (`Dividend`) only** | — | — |
| `portfolio_risk.py`, `live_safety_gate.py`, `reports/api/*`, the web UI | **No reference** | — | — |

The tests that pin this behavior:

- `test_019_prices.py::test_missing_pay_date_and_invalid_split_fail` (`:68-71`);
- `test_019_conventions.py::test_payment_cannot_be_moved_ahead_of_source_pay_date` (`:95-101`);
- the spec 020 validator assertion (`020 spec.md:151`).

### What the pay date actually changes

The ledger has `Equity = Cash + Quantity × Price + Receivable`, and
`Buying_Power = Cash` (spec 019 `spec.md:90-94`). Therefore:

- **Equity, the equity curve, returns, Sharpe, drawdown, and each trade's
  P&L are unchanged by the pay date.** The dividend reaches equity and the
  trade's `Dividend Income` on the **ex-date**, whenever it is paid.
- **Only order admission depends on it.** An entry is rejected when
  `shares × fill + commission > Cash` (`backtest_harness.py:131-137`).
  Between the ex-date and the pay date, the dividend is in equity but cannot
  fund an order. The pay date matters only when a strategy exits and
  re-enters inside that window, *and* cash is binding at that moment.
- **Today's callers essentially never hit that case.** They trade one share
  against a declared $10,000 of capital (`ma_crossover_backtest.py:31`). The
  dependency becomes real under full-allocation sizing (the cash account in
  `portfolio_risk.py:174`, `max_gross <= 1`). There, a re-entry can be short
  by exactly the unpaid dividend. A rejection is recorded as a ledger
  `rejected` event, so the effect is visible, not silent.

**Conclusion.** Camden's intuition is right for prices: the pay date does not
move the price series. It is not right for the account. The funded ledger is
a cash simulation, and one component, order admission, depends on pay-date
timing. That is a real reason not to just delete the requirement. It is not a
reason to require a vendor-sourced pay date, as the next point shows.

### Spec 019 already specified the answer, and it was never built

`019 spec.md:94`: *"If a payment session is not sourced from the vendor, a
declared upper-bound session is used, and `Pay_Date_Basis ∈ {sourced, bound}`
is recorded on the dividend event. A later pay date can only delay cash
conversion and reject more orders, never admit an unaffordable order (Rule
1-safe)."*

Grepping `scripts/` finds no `Pay_Date_Basis`, and no bound. The spec 020
validator was written stricter than 019's contract. That gap is B-1.

The safety argument is one-directional:

| Assumed pay date vs. true pay date | Effect |
|---|---|
| **Later** | Only rejects orders a real account would have admitted. Conservative, and visible as `rejected` events |
| **Earlier** | Admits orders funded by cash the account did not yet have. **Optimistic.** This is the failure the requirement exists to prevent |

### Options

| | Option | Admits an unaffordable order? | Needs a second vendor? | Change surface |
|---|---|---|---|---|
| A | Keep the requirement. Source pay dates elsewhere (020 Q1 (a)/(b)/(c): EDGAR, Polygon/Alpaca, or a curated table) | No | **Yes**, or hand curation | None in code; new ingestion |
| B | Drop the requirement. Treat a dividend as cash on the ex-date | **Yes**, and silently | No | Harness, metrics, validator |
| C1 | 019's bound, **unbounded variant**: a dividend with no sourced pay date never converts to cash within the run. It stays `Receivable`: counted in equity, never in buying power | No (strictly conservative) | No | Data layer, plus recording the basis |
| C2 | 019's bound, **sourced-N variant**: pay date = ex-date + N sessions, where N is a declared upper bound backed by primary-filing evidence | No, *if* N really is an upper bound | No, but N needs evidence (Rule 11) | Same as C1, plus a cited N |

- **B is rejected.** It reverses 019's explicit safety direction.
- **A remains valid, but not needed to unblock.** It is the only option that
  reproduces real cash timing, which may matter later for paper or live
  reconciliation.
- **C1 needs no figure at all.** That means no Rule 11 citation, and it can
  ship immediately.
  - Its cost: in a fully allocated account over a long panel, dividend cash
    accumulates as unusable receivable. That can over-reject re-entries.
  - Each over-rejection is visible in the ledger. Equity-based metrics are
    unaffected.
- **C2 recovers most of what C1 over-rejects**, but N is a sourced figure. It
  must be an upper bound over every dividend in the bundle, not a typical lag.
  No value is proposed here, because there is no source for one in the repo
  (Rule 11).

### Recommended implementation shape (for the implementing spec, not now)

The resolution lives in the data layer, so the harness and metrics contracts
barely move:

1. **Validator** (`_validate_corporate_actions`):
   - A dividend's pay date may be null **only if** the manifest declares a
     pay-date policy.
   - A non-null pay date keeps every existing check.
   - The ex-date requirement is unchanged.
2. **Manifest:** bump `UNADJUSTED_MANIFEST_VERSION` and add
   `dividend_pay_date_policy ∈ {"sourced", "unbounded", "bound_sessions:N"}`.
   `N` requires a `dividend_pay_date_bound_source` citation.
   Version-1 manifests keep today's strict behavior.
3. **Loader** (`_merge_actions_for_execution`):
   - Resolve every null pay date per the policy.
   - Add a `Dividend_Pay_Date_Basis` column with values `sourced` or `bound`.
   - Unbounded means a resolved date later than the final session. The
     harness's `date <= row.Date` test then never pays it, and metrics
     reconcile through the same rule.
4. **Harness:** record `Pay_Date_Basis` on each `dividend` event, as 019
   promised. The arithmetic does not change.
5. **Tests:** the pinned 019 tests stay as they are: a frame reaching the
   harness still always carries a resolved date. Add these:
   - an unbounded dividend never converts;
   - a C2 bound never pays earlier than a sourced date would;
   - a mutant that resolves to the ex-date (option B) is killed.
6. **Reports:** print the policy with the provenance (spec FR-008), so a
   reader knows the cash timing is bounded, not sourced.

### What this does not settle

- **020 Q2**: are Norgate's per-share dividend amounts pre- or post-split as
  of the ex-date? 019 requires "dollars per post-split share". That is
  independent of this decision and still open.
- **Rule 14**: ex-dates and amounts are what the second-source cross-check
  covers. Norgate may *be* that second source for yfinance, or the primary
  with yfinance as the check. That is still to be decided.
- **Live and paper trading**: broker settled-cash balances come from the
  broker, not from this model. Nothing here affects `exec/` or
  `live_safety_gate.py`.
