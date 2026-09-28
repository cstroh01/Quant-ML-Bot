# Feature Specification: Dividend pay date as a declared conservative bound

**Feature Branch**: `041-dividend-pay-date-bound` (name only; Camden owns Git)
**Spec number**: 041, assigned by Camden.
**Created**: 2026-09-27
**Status**: Draft. Not implemented. Nothing in `scripts/` or `tests/` was changed by writing it.
**Input**: Camden, 2026-09-27: implement spec 036 D-7 (DECIDED) so that a
dividend-paying ticker can produce an unadjusted bundle. The decision is not reopened here.
**Blocks**: the v1.0 tag (`docs/SCOPE-V1.md` §3 item 1: "the backtester runs").

## Hard precondition — sequencing

**041 is implemented only after spec 036 has merged.** Both specs edit
`scripts/data.py`, and 041 extends the provenance surface 036 creates (036 FR-008).
They must not run at the same time. Spec 040 (packaging) runs after 041 and is
blocked by it.

## Why this spec exists (spec 036 B-1, verified 2026-09-27)

- `YFinanceUnadjustedAdapter.fetch` writes `Dividend_Pay_Date = pd.NaT` for every
  dividend (`scripts/data.py:985-988`). The comment there says "Never substitute."
- `_validate_corporate_actions` rejects any dividend that has no pay date
  (`data.py:634-635`).
- `cache_unadjusted_market_data` validates before it writes (`data.py:886-888`).
- So `download_unadjusted_market_data("AAPL", ...)` raises, and
  `data/cache/unadjusted/` is never written. Once 036 ships, every real run of the
  AAPL crossover and the tearsheet fails closed. The wiring is correct, but
  there is no bundle to wire to.

## The decision being implemented (copied from spec 036 D-7 and research R-8; not re-derived)

**DECIDED (Camden, 2026-09-26): option C1 now; C2 allowed later with a cited bound.**

What D-7 established:

- **The ex-date is already required.** An action's `Date` is its ex-date and must
  be a bundle session (`data.py:624-626`). What is actually in question is the
  pay-date requirement.
- **Prices do not use the pay date.** `Research_Close`, signals, labels
  (`targets.py:95`), equity, trade P&L, Sharpe and drawdown depend only on the
  ex-date and the amount.
- **The funded ledger does use it.** The harness books a dividend as `Receivable`
  on the ex-date and moves it to `Cash` on the pay session. Buying power is cash
  only (`backtest_harness.py:107-137`), so the pay date decides whether a
  re-entry between the ex-date and the pay date can be afforded.
  `metrics.equity_curve` reconciles the same thing (`metrics.py:146-156`).
- **Spec 019 already defined the substitute, but it was never built.**
  019 `spec.md:94`: "if a payment session is not sourced from the vendor, a
  declared upper-bound session is used, and `Pay_Date_Basis ∈ {sourced, bound}`
  is recorded on the dividend event." The spec 020 validator was written stricter
  than 019's contract, and that gap *is* B-1.
- **The options**, from R-8:

| | Option | Can it admit an unaffordable order? | Needs a figure? |
|---|---|---|---|
| A | Vendor-sourced pay dates | No | Needs a second vendor. None is free for 10 years (`SCOPE-V1.md` §2) |
| B | Treat the dividend as cash on the ex-date | **Yes, silently** | No. **Rejected**: it reverses 019's safety direction |
| **C1** | **Unbounded**: an unsourced dividend never converts to cash within the run. It stays `Receivable` (counted in equity, never in buying power) | **No, strictly conservative** | **No.** It needs no Rule 11 citation |
| C2 | Bound: pay date = ex-date + N sessions, where N is a cited **upper** bound for every dividend in the bundle | No, *if* N really is an upper bound | Yes. N needs primary-filing evidence |

- **Cost of C1, accepted by D-7.** In a fully allocated cash account
  (`portfolio_risk`, `max_gross <= 1`), unpaid dividends accumulate as unusable
  receivable. That can reject re-entries a real account would admit. Every such
  rejection is a visible `rejected` ledger event, and equity-based metrics are
  unaffected. Today's one-share callers are not materially affected.

### Reconciling this spec's prompt with D-7 (flagged, not silently resolved)

The prompt that commissioned this spec describes C1 as "a declared conservative
bound (ex_date + declared_lag)". In D-7's decided text, `ex_date + N` is **C2**,
and C1 is the **unbounded** variant. This spec follows the decided text, as the
prompt instructs ("read D-7 … copy its reasoning"):

- `declared_lag` exists as a single named constant (FR-001). **Its value for this
  spec is "unbounded".** That is C1: there is no finite lag and no figure.
- A finite value is C2. It is refused unless a citation for it as an upper bound
  is set next to it (FR-002). No finite value is proposed here. No source in the
  repository or on the free stack supports one:
  - yfinance exposes ex-dates only.
  - The EODHD free plan has `paymentDate` but covers **one year** of history
    (`SCOPE-V1.md` §2, verified 2026-09-25).
  - A *typical* lag (for example, "AAPL usually pays about a week after the
    ex-date") is not an upper bound. It would be an unsourced figure (Rule 11).
- **Open question Q-1 for Camden:** if a finite lag was intended *now*, that is
  C2 and needs a citation first. The spec does not adopt one.

## Direction of the bound, and what a wrong direction leaks

**The bound errs LATE.** The resolved pay session is never earlier than the true
pay session could be. Under C1 it is later than every session in the bundle.

**Why late is the safe direction for point-in-time correctness.** The ledger's
`Cash` and `Buying_Power` at row `t` must be computable from events at or before
`t` (Rule 1, judged per row). A pay date at or after the true one means `Cash_t`
only ever *understates* the cash truly in hand at `t`.

- An order admitted under the bound would also have been admitted by the real
  account.
- Some orders the real account would admit may be rejected. Each rejection is a
  visible `rejected` event.
- Equity is unaffected in either direction, because the dividend enters `Equity`
  as `Receivable` on the ex-date.

**What a wrong-direction (early) bound would leak.** An early pay date credits
`Cash_t` with dividend money that arrives only at `t' > t`. Row `t`'s buying power
would then depend on an event after `t`, which is a per-row Rule 1 violation
inside the ledger. Concretely:

1. It admits re-entries funded by cash the account did not have.
2. Those trades did not exist, so their fills, commissions, trade P&L, funded
   daily returns, Sharpe and drawdown are fabricated.
3. Through `trial_runner.Attempt.account`, the fabricated return series is written
   into the lifetime trial ledger's return sidecars. There it feeds the DSR/PBO
   gate (Rule 15).

The extreme early bound, `declared_lag = 0`, *is* option B. It is the planted
defect in SC-005.

## User Scenarios & Testing

### User Story 1 — A real dividend-paying ticker produces a bundle (Priority: P1)

Camden runs `download_unadjusted_market_data("AAPL", start, end, ...)`. A bundle
is written to `data/cache/unadjusted/`, and it loads with
`attrs["price_basis"] == "unadjusted_dollars"`. Every dividend in it is marked as
a declared bound, not vendor data.

**Why this priority**: until this works, v1.0 DoD item 1 cannot pass, and every
036 entry point fails closed.
**Independent Test**: offline, a fake `ticker_factory` returns a yfinance-shaped
history with dividends and a split, and the bundle is written and loaded in a
temporary directory. Online, as a one-time manual step, Camden runs the real
download once and the evidence is kept (SC-001).

**Acceptance Scenarios**:
1. Given yfinance history with N > 0 dividends, the bundle is written, its manifest
   declares `dividend_pay_date_policy == "unbounded"`, and the actions file has
   N dividend rows with `Dividend_Pay_Date` empty and `Dividend_Pay_Date_Basis == "bound"`.
2. Given that bundle, `load_unadjusted_market_data` returns a frame where every
   dividend row has a resolved pay date later than the final session and
   `Dividend_Pay_Date_Basis == "bound"`.
3. Given that frame, `run_backtest` completes. Every `dividend` event carries
   `Pay_Date_Basis == "bound"`, and no `payment` event occurs for a bound dividend.

### User Story 2 — Fail-closed paths still fail closed (Priority: P1)

**Acceptance Scenarios**:
1. The source returns no rows → `RuntimeError`, and the cache directory stays empty.
2. The source is missing a session → the price session-contiguity check fails, and
   nothing is written.
3. A dividend's ex-date is not a price session → the ex-date check fails, and
   nothing is written.

### User Story 3 — The validator is not a pass-through (Priority: P1)

Every malformed dividend other than "null pay date under a declared policy" is
still rejected with its existing message. A null pay date is still rejected
whenever the manifest does not declare a non-`sourced` policy (FR-004 table).

### User Story 4 — Every reported result says the pay dates are declared (Priority: P1)

A reader of any output built from a bound bundle can tell that dividend cash
timing is a declared bound and not vendor data (Rule 16).

### Edge Cases

- A dividend on the bundle's final session.
- A split and a dividend on the same ex-date.
- A bundle with zero dividends: the policy is still declared, and there are zero
  bound rows.
- A version-1 manifest with a null pay date (must stay rejected).
- A frame reaching the harness with no basis column (legacy fixtures). Its basis
  is recorded as `unspecified`, never inferred as `sourced`.
- A strategy that exits and re-enters between an ex-date and the resolved pay date
  while cash binds.

## Requirements

### Functional Requirements

**Where the lag lives**

- **FR-001**: `scripts/data.py` MUST define exactly one named constant for the
  declared lag. It is never repeated as a literal at a call site:

  ```python
  # Spec 036 D-7 option C1 (DECIDED 2026-09-26); spec 041.
  # None = unbounded: a dividend with no vendor pay date never converts to cash
  # within the run. It is strictly conservative and involves no figure (Rule 11).
  # A finite value is option C2 and requires DIVIDEND_PAY_DATE_BOUND_SOURCE to
  # cite primary-filing evidence that it is an UPPER bound over every dividend
  # in the bundle. A typical lag is not enough.
  DIVIDEND_PAY_DATE_DECLARED_LAG_SESSIONS: int | None = None
  DIVIDEND_PAY_DATE_BOUND_SOURCE: str | None = None
  ```

  The policy string is derived from these two constants in one function:
  `"unbounded"`, or `"bound_sessions:N"`. The constant affects only bundles
  written from now on. The loader reads the policy from the **manifest**, never
  from the constant, so an existing bundle is always read the way it was written.
- **FR-002**: Writing a bundle MUST fail if the lag is finite and the source is
  empty or missing, if the lag is negative, or if the lag is zero. Zero is option
  B, which D-7 rejected.

**Provenance marking (Rule 11). This is the most important requirement in the spec.**

- **FR-003**: A declared bound MUST be distinguishable from a vendor field at
  every layer, and no layer may launder one into the other:
  - **On disk (actions CSV).** A new column `Dividend_Pay_Date_Basis ∈ {"sourced", "bound"}`
    on every dividend row, empty on split rows. **`Dividend_Pay_Date` on disk holds
    only vendor data.** It is empty for every `bound` row, so a fabricated date never
    sits in a column a reader would take for vendor data.
  - **Manifest.** `UNADJUSTED_MANIFEST_VERSION` becomes 2. Version 2 requires
    `dividend_pay_date_policy ∈ {"sourced", "unbounded", "bound_sessions:N"}`, and
    `dividend_pay_date_bound_source` when the policy is `bound_sessions:N`. The
    manifest hashes the actions file, so the basis column is covered by the
    existing integrity check.
  - **Loaded frame.** The resolved `Dividend_Pay_Date` sits next to
    `Dividend_Pay_Date_Basis` on every dividend row. `attrs` gains
    `dividend_pay_date_policy`, `dividend_pay_date_bound_source`,
    `dividends_sourced` and `dividends_bound` (counts).
  - **Harness ledger.** Every `dividend` event carries `Pay_Date_Basis`: `sourced`,
    `bound`, or `unspecified` when the input frame has no basis column. The harness
    never infers `sourced`.
  - **Adapter.** `UnadjustedSourceSnapshot` gains `dividend_pay_date_policy`,
    **defaulting to `"sourced"`** (the strict value, so an adapter that says
    nothing gets today's behavior). `YFinanceUnadjustedAdapter` declares the
    policy derived in FR-001 and writes `Dividend_Pay_Date_Basis = "bound"` on
    every dividend. Its "Never substitute" comment stays true: the adapter still
    writes no date.

**Validator: relaxed in exactly one place**

- **FR-004**: `_validate_corporate_actions` gains a keyword-only `pay_date_policy`
  argument that defaults to `"sourced"` (strict). Every existing check is kept
  verbatim. The single relaxation: a dividend's pay date may be null **only if**
  its basis is `bound` **and** the policy is not `sourced`. The full rule set for
  a version-2 bundle:

| Dividend row | Policy `sourced` | Policy `unbounded` / `bound_sessions:N` |
|---|---|---|
| basis `sourced`, date present, ≥ ex-date, market session | accept | accept |
| basis `sourced`, date null | **reject** (existing message) | **reject** |
| basis `bound`, date null | **reject** | accept |
| basis `bound`, date present | **reject** (a date in the vendor column claimed as bound) | **reject** |
| basis missing or not in the allowed set | **reject** | **reject** |
| any existing failure (Value ≤ 0 or non-finite, ex-date not a session, tz-aware date, pay date < ex-date, pay date not a session, duplicate row, wrong ticker, unknown type) | **reject** (unchanged message) | **reject** (unchanged message) |
| split row with a pay date or a basis | **reject** | **reject** |

  Version-1 manifests have no basis column. They are validated exactly as today,
  and a null pay date is rejected.

**Loader resolution**

- **FR-005**: `_merge_actions_for_execution` resolves a `bound` row's pay date
  from the manifest policy:
  - `unbounded` resolves to the named sentinel `UNBOUNDED_PAY_DATE`, a naive
    midnight timestamp later than any representable session.
  - `bound_sessions:N` resolves to the N-th market session after the ex-date,
    using `trading_days`, not the bundle's rows, so the result is correct past the
    bundle's end.
  - `sourced` rows keep their vendor date.
  - A `bound` row's resolved date is never earlier than the ex-date plus one
    session. A `sourced` date may equal the ex-date, as it may today.
- **FR-006**: The arithmetic in `backtest_harness.run_backtest` and
  `metrics.equity_curve` is unchanged. The pinned 019 tests
  (`test_019_prices.py::test_missing_pay_date_and_invalid_split_fail`,
  `test_019_conventions.py::test_payment_cannot_be_moved_ahead_of_source_pay_date`)
  stay byte-identical and green. A frame reaching the harness still always carries
  a resolved date.

**Disclosure (Rule 16)**

- **FR-007**: Every surface that 036 FR-008 requires to print bundle provenance
  (the CLI output of `ma_crossover_backtest.py` and the tearsheet API response)
  MUST also print the pay-date policy whenever `dividends_bound > 0`, in this form:
  `Dividend pay dates: declared bound (policy=<policy>), <k> of <n> dividends; NOT vendor data.`
  For `unbounded`, it adds: `dividend cash never becomes buying power within this run.`
  The line comes from the one renderer 036 introduces. If 036 ships more than one,
  041 covers each, and the test enumerates them.
- **FR-008**: Nothing in 041 changes `capital_gate_eligible` (still `False` for
  yfinance) or removes an existing `source_limitations` entry. Rule 14 (the
  second-source cross-check) is untouched and remains owed.

**Tests**

- **FR-009**: All automated tests run offline, with synthetic values labelled
  `EXAMPLE — NOT A RESULT`, using `YFinanceUnadjustedAdapter(ticker_factory=...)`.
  Mutants use the existing `tests/mutation_support_019.py` engine. No third
  harness.

### Key Entities

- **Pay-date policy**: a bundle-level declaration recorded in the manifest.
- **Pay-date basis**: a per-dividend marker (`sourced` | `bound`), carried on
  disk, in the frame, and on the ledger event.

## Success Criteria

- **SC-001 (the real bundle; manual, network, Camden-run once):**

  ```powershell
  python -c "import sys; sys.path.insert(0,'scripts'); from datetime import date; import data; p = data.download_unadjusted_market_data('AAPL', date(2016,1,4), date(2025,12,31), created_by_revision='<full sha>'); f = data.load_unadjusted_market_data(p); print(p); print(f.attrs['price_basis'], f.attrs['dividend_pay_date_policy'], f.attrs['dividends_bound'], f.attrs['dividends_sourced'])"
  ```

  - **Pass**: a manifest path under `data/cache/unadjusted/`, then
    `unadjusted_dollars unbounded <k> 0` with k > 0.
  - Save the manifest JSON and the printed output to
    `.specify/specs/041-dividend-pay-date-bound/artifacts/aapl-bundle.txt`,
    stamped with the date and commit (Rule 11). The market data itself is never
    committed.
  - The date range is the one Camden intends for the 036 CLI. If it differs from
    the range above, the one actually used is what gets recorded.
  - **If this run fails on any *other* check** (contiguity, a split
    discontinuity, an ex-date with no session), that is a data finding to record.
    It is not grounds to relax a check.
- **SC-002 (offline twin, in the suite):** the same flow, driven through a fake
  `ticker_factory` with at least two dividends and one split, writes a bundle to
  `tmp_path` that loads with `price_basis == "unadjusted_dollars"`, and
  `run_backtest` completes on it.
- **SC-003 (fail-closed):** User Story 2's three scenarios raise their named
  errors, and the cache directory contains no file afterwards.
- **SC-004 (not a pass-through):** one parametrized test covers every reject row
  of FR-004's table (under both a `sourced` and an `unbounded` policy where the
  table says so), plus the version-1 null-date rejection. Each case asserts the
  exact error-message fragment, not just `ValueError`. A control case with a
  well-formed bound dividend passes.
- **SC-005 (Rule 12, planted defects; each is killed while its unmutated control
  passes):**
  - **M1 — option B via the loader.** The plausible defect. `unbounded` is resolved
    to the ex-date instead of the sentinel. It looks like a harmless "just use the
    date we have". Oracle: a synthetic funded account at full allocation, in
    which a sell and re-buy fall between the ex-date and the final session. The
    re-buy must be `rejected` because its cost exceeds `Cash` and the dividend is
    still `Receivable`. **Expected red:** the mutant admits the re-buy, the oracle's
    `assertEqual(events.Event.tolist().count("rejected"), 1)` fails, and
    `killed()` reports the mutant as caught.
  - **M2 — pass-through validator.** The null-date check ignores the policy.
    Oracle: a version-1 bundle and a `sourced`-policy bundle with a null dividend
    date must both raise `dividend payment date missing`. Expected red: no raise.
  - **M3 — provenance laundering.** The loader writes `"sourced"` into the basis of
    a resolved row. Oracle: every row in the loaded frame whose on-disk date was
    null has basis `bound`. Expected red: a basis mismatch assertion.
  - **M4 — an uncited finite lag.** Monkeypatch the lag to `5` with the source
    `None`. Writing the bundle must raise the FR-002 error. This is a direct
    assertion, not an in-memory mutant, because it tests configuration.
- **SC-006 (direction):** for `bound_sessions:N` (with a test-only synthetic
  citation), every resolved date is at least `ex_date + N` sessions. For
  `unbounded`, no `payment` event is ever recorded for a bound dividend.
- **SC-007 (disclosure):** a CLI subprocess test and an API test against a
  synthetic bound bundle each assert that the FR-007 line is present. A synthetic
  all-`sourced` bundle does not print it.
- **SC-008 (suite):** `python -m pytest tests` is green, and the count equals 036's
  post-merge count plus exactly the tests enumerated in `tasks.md`.

## Assumptions

- The funded-ledger model (`Equity = Cash + Quantity × Price + Receivable`,
  `Buying_Power = Cash`) is spec 019's and is not changed.
- No new dependency is added.
- No strategy result is produced or claimed by this spec. SC-001's printed counts
  are bundle metadata, not performance figures.

## Out of scope

- Option A (vendor-sourced pay dates) and any finite C2 value (see Q-1).
- Rule 14 reconciliation of dividend amounts and ex-dates against EODHD or EDGAR.
- 020 Q2 (whether dividend amounts are pre- or post-split).
- Any change to `exec/`, `live_safety_gate.py` or `portfolio_risk.py`. Broker
  settled cash comes from the broker, not from this model.
- Packaging (spec 040), which runs after this.

## Open questions for Camden

- **Q-1**: Was `ex_date + declared_lag` meant as a finite lag *now*? If so, that
  is C2 and needs a cited upper bound before any value is set. This spec ships C1
  (unbounded), as D-7 decided.
