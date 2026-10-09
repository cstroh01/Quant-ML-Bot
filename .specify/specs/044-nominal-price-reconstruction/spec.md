# Feature Specification: Nominal price reconstruction from the yfinance split table

**Feature Branch**: `044-nominal-price-reconstruction` (name only; Camden owns Git)
**Spec number**: 044. This is the next free number. 040, 042 and 043 are taken or reserved and are not reused.
**Created**: 2026-09-30
**Status**: Draft, revised 2026-09-30 for review findings R1–R11 in
[`artifacts/review-codex.md`](artifacts/review-codex.md), per Camden's decisions (§7). No production
code, no tests, and no run of any kind has been made. The P-1 probe is written but has not been run.
**Input**: the SC-001 finding recorded in
[`../041-dividend-pay-date-bound/artifacts/aapl-bundle.txt`](../041-dividend-pay-date-bound/artifacts/aapl-bundle.txt)
(Camden, 2026-09-30, commit `bb16148`).
**Blocks**: the v1.0 tag (`docs/SCOPE-V1.md` §3 item 1), and spec 041's SC-001, which is re-run
as this spec's acceptance test.

## Hard precondition — sequencing

044 edits `scripts/data.py`, and so do 041 and 043. 044 does not run at the same time as either
of them. It starts from the tree in which 041's production tasks are merged. If they are not merged
yet, 044 waits. The SC-001 command depends on 041's `dividend_pay_date_policy` attrs.

## 1. The finding (copied from the SC-001 evidence, not re-derived)

- `download_unadjusted_market_data('AAPL', 2016-01-04, 2025-12-31)` raised
  `split reconciliation check failed: nominal price discontinuity does not match the 4:1 action`
  from `_validate_split_discontinuities`. Nothing was written, and the ledger hashes did not change.
- A read-only diagnostic showed that `yf.Ticker('AAPL').history(auto_adjust=False)` returns
  pre-split Open and Close **already split-adjusted**. The prior close divided by the split-day
  open was 0.978, where the declared ratio was 4.0.
- **Established:** `auto_adjust=False` removes dividend adjustment but not split adjustment. The
  adapter's docstring ("nominal-price adapter") is wrong about its own output. The check refused
  correctly.
- **Not established:** whether `Dividends` and `Volume` are split-adjusted too, and whether the
  provider's split table is complete.

**The existing tests encode the falsified assumption.** The yfinance fakes feed a *nominal* step
across a split: `tests/test_041_pay_date_bound.py::synthetic_history` goes 100 → 50 across a 2:1
split, and the first `YFinanceAdapterTests` history in `tests/test_020_unadjusted_price_data.py`
goes 100 → 25 across a 4:1 split. FR-009 governs the migration.

## 2. The design

For each row at session `t`, with the provider's split events `(d_i, r_i)` from **one response**,
where `r_i` is the new shares per old share:

```
F(t)             = product of r_i over every split with d_i > t     (1.0 if none)
nominal O/H/L/C  = provider O/H/L/C × F(t)
nominal Dividend = provider Dividend × F(t)   only if P-1 finds dividends adjusted (FR-004)
nominal Volume   = provider Volume ÷ F(t)     only if P-1 finds volume adjusted (FR-005)
```

- **Strictly later.** The split's own ex-date row is already post-split, so it is excluded (`>`,
  not `>=`). An off-by-one removes the step, and the oracle refuses (M1).
- **All later splits, including those after the requested `end`.** The provider adjusts to its own
  "now". A split after `end` produces no action row and no step inside the window. So the factor
  comes from the same response as the prices, that response must be current (FR-002), and every
  factor event is validated first (FR-011). A window-only factor is the most plausible bug (M2),
  and no price check can see it.
- **The oracle stays unchanged.** `_validate_split_discontinuities` and
  `SPLIT_RATIO_RELATIVE_TOLERANCE` have zero diff lines (FR-003).

### Point-in-time argument (Rule 1), with its conditions

Writing `P_provider(t, h) = P_nominal(t) / F(t, h)` for a response with horizon `h` gives
`P_provider(t, h) × F(t, h) = P_nominal(t)` for any `h`. Reading later splits to *undo* the
provider's encoding therefore does not, by itself, move a future fact into the value at `t`. The
claim is **conditional**. It holds only if all of the following are true:

- **The factor events are complete and correctly dated.** FR-002 refuses a stale response. FR-011
  refuses malformed events. FR-006 catches a missing or wrong event **only inside its verified
  coverage interval**; after `verified_through`, an event is disclosed as unreconciled, not caught.
- **The dividend and volume conventions are right.** Passing through a split-adjusted dividend
  keeps a dependence on future splits. Dividing already-nominal volume introduces one. That is why
  P-1 decides both, and why unverified volume is blocked from the cost model (FR-005).
- **Provider quantization is small.** Rounded provider values leave a residual (R8). Exact
  invariance is claimed only on exactly representable fixtures. A quantized case documents the
  residual bound instead of asserting identity.

T-PIT (FR-008) tests the conditional claim at the adapter boundary. It uses the same requested
window, adds a later split strictly after it, grows only the response, and also perturbs future
prices and volumes. The reconstructed prefix must not change.

### Rounding policy — D-1, decided: unrounded

Reconstructed prices, dividends and volumes are stored as computed in `float64`, and are not
rounded to cents or whole shares.

| | Round to cents / whole shares | **Store unrounded (chosen)** |
|---|---|---|
| Looks like a real print | Yes | No: `499.230012` carries the provider's rounding noise |
| **Keeps the evidence of a bad factor** | **No.** Distance from the cent grid is the only local sign of an inconsistent factor or adjusted value. Rounding sets it to zero and **masks vendor errors** | **Yes.** The residual stays measurable |
| Pre-2001 fractional prices, e.g. 1/16 | Corrupted | Unaffected |

The cost is sub-cent noise in fills and P&L, which is accepted. No gate is built on the residual.
**EXAMPLE — NOT A RESULT:** a nominal 100 reported as `33.333333` after a 3:1 adjustment
reconstructs as `99.999999`. Its bound is `|rebuilt − nominal| ≤ F × q / 2` for provider quantum `q`.

## 3. User scenarios & testing

- **US1 (P1): a real split ticker produces a bundle.** SC-001 for AAPL 2016-01-04..2025-12-31
  shows a 4:1 step in 2020, the unchanged oracle accepts it, and the bundle loads.
- **US2 (P1): a split the provider omits is caught.** There is no step and no action row. Only
  the independent table catches it, inside its coverage (FR-006).
- **US3 (P1): every surface says the prices are derived.** `source_method` and
  `source_limitations` say so. The CLI already prints both (`scripts/ma_crossover_backtest.py`,
  the `for key in ("source_name", "source_method", ...` loop).

### Edge cases (Rule 5): expected behavior

| Case | Expected |
|---|---|
| Window starts on a split ex-date | Still refused with `no preceding price session`. The sliced bundle is what gets validated, not the larger response |
| Window ends on a split ex-date | Earlier rows include that ratio. The last row excludes it but keeps any still-later factors. The end-day action row is kept |
| Consecutive split sessions `r1`, `r2` | Before both: `r1·r2`. On the first: `r2`. On the second: 1, before any still-later splits |
| First or last row without a split | The first row includes all later factors. The last row need not have `F = 1` |
| Empty sliced window | Refused. Endpoints are never indexed on an empty frame |
| Split and dividend on the same ex-date | `F` excludes that day's split. Both action rows are kept (uniqueness is per Date/Ticker/Action_Type). Applied only if P-1 resolves the convention; otherwise refused (FR-012) |
| Timezone and DST | FR-014 |
| Response ends before the as-of date | Ordinary weekend or holiday lag passes. A missing completed session is refused (FR-002) |
| Malformed post-window event | Refused before any multiplication, even outside reference coverage (FR-011) |
| Missing bars around a split | The existing contiguity check is unchanged |

## 4. Requirements

- **FR-001 Pure function.** One private, pure function in `data.py` takes the validated provider
  frame and returns the nominal frame. It does no I/O and uses no global state. It is the only
  place `F(t)` is computed.
- **FR-002 One current response; requested coverage.** The adapter makes exactly one
  `history(interval="1d", auto_adjust=False, actions=True)` call with `start` set and `end` left
  open. It takes the split events from that same response, validates them (FR-011), reconstructs,
  and only then slices to `[start, end]`.
  - **Horizon.** The adapter takes an injectable clock, defaulting to
    `datetime.now(timezone.utc)`. The as-of instant is localized to `America/New_York`
    explicitly. The last completed session is the latest `trading_days` session on or before the
    as-of date whose 16:00 New York close has passed. The adapter refuses unless
    `last_response_session <= last_completed_session` **and**
    `len(trading_days(last_response_session + 1 day, last_completed_session)) <= 1`. The error is
    `split-factor horizon check failed`. _Amended 2026-10-08 (043 triage F2; same rule already in
    `artifacts/p1_rules.py` and self-checked on PR #92):_ a response ending after the last completed
    session (today's partial bar) gives a reversed, empty range, so the lag reads 0 and would pass;
    the ordering condition is checked first. The manifest records `split_horizon_as_of_utc` and
    `split_factor_basis_through` (the last response session).
  - **Requested coverage.** The sliced window must be non-empty. Its first session must equal
    `trading_days(start, end)[0]`, and its last must equal the last trading day on or before
    `min(end, last_response_session)`. Otherwise the adapter refuses with
    `requested-window coverage check failed`.
- **FR-003 Oracle unchanged.** `_validate_split_discontinuities` and
  `SPLIT_RATIO_RELATIVE_TOLERANCE` have zero diff lines.
- **FR-004 Dividends.** Multiply by `F(t)` if P-1 Q-P3 finds them adjusted. Pass them through if it
  finds them nominal. If Q-P3 is a STOP, the spec stops. This closes spec 020 Q2 for this provider.
- **FR-005 Volume: three outcomes, decided by P-1 Q-P4.**

  | Q-P4 outcome | Treatment | `volume_basis` |
  |---|---|---|
  | adjusted | `Volume ÷ F(t)` | `nominal_reconstructed` |
  | nominal | pass-through | `provider_nominal` |
  | inconclusive | pass-through, plus a limitation line | `provider_unverified` |

  **Blocked from the cost model.** Today no cost-model code reads Volume: a grep of
  `scripts/cost_utils.py` and `scripts/backtest_harness.py` on 2026-09-30 found no reference. This
  spec makes it binding: any cost-model code that reads Volume, such as Rule 13's square-root
  impact term, refuses a frame whose `volume_basis` is not `nominal_reconstructed` or
  `provider_nominal`. The spec that introduces that code carries the red proof. **Dollar-volume
  invariance is not evidence** for any outcome. It holds by construction whenever price and volume
  are scaled inversely, whether or not the convention is right.
- **FR-006 Independent split table.** **The reference table is
  `artifacts/split-table-crosscheck.md`** (D-5). It lists every split for AAPL, MSFT, GOOGL, NVDA and
  AMZN, from the earliest supported bundle date through `verified_through`, and each row cites a
  primary source (an EDGAR accession number or URL, or an exchange notice). The Unit 7 constant in
  `data.py` (in the `AD_HOC_CLOSURES` shape) transcribes that file one for one, and a test asserts
  equality. Two items are **UNVERIFIED today**, and `verified_through` cannot be set until both close:
  - **2026 splits.** Every basket split from 2026-01-01 through the download date is checked
    against the issuer's primary 8-K.
  - **MSFT "no split".** The absence needs its own primary source. A secondary page does not count.

  **Comparison interval.** Events are compared only over the common coverage interval
  `[first window session, min(last_response_session, verified_through)]`. The adapter refuses on a
  date mismatch, or on a ratio mismatch above a relative 1e-9 (D-4). It also refuses any ticker
  absent from the table (D-2). A provider event after `verified_through` is disclosed as
  unreconciled (Rule 14). A reference event after `last_response_session` is not compared: that
  response predates it. The table is a constructor argument, with the committed constant as default.
- **FR-007 Labels (Rule 16).** `source_method` is exactly
  `derived:provisional:yfinance.Ticker.history(interval=1d, auto_adjust=False, actions=True)*later_split_factor`.
  `source_limitations` gains a reconstruction line, plus the dividend and volume treatment lines and
  any unreconciled-event line. `capital_gate_eligible` stays `False`. The docstring is corrected.
- **FR-008 Tests first; red and kill evidence recorded separately.** Contract tests are written and
  observed red for the named reason before the code they test exists. Mutation wiring and
  green-control or kill evidence come after implementation, as separate task statuses (R7).
- **FR-009 Fixture migration is explicit (R6).**
  - Divide the pre-split OHLC of *copies used as yfinance responses*: by 4 in the 020 split
    history, and by 2 in 041 `synthetic_history`. If P-1 finds volume adjusted, multiply pre-split
    volume by the same factor. The original nominal expectations stay unchanged.
  - `split_prices()`, `SyntheticSource` and `session_prices()` stay nominal.
  - The second 020 history has no split event. It is left unchanged, and no split is invented.
  - The 041 history-call assertion changes to require one call with `end` open. Each fake gets an
    injected reference table and a clock whose as-of is within one completed session of its last row.
  - Preserved exactly: 041's Receivable 1.5, zero Cash and Buying_Power, Equity, basis and
    no-payment assertions; 020's null-date refusal and no-write checks.
  - Each migrated test records its intended red assertion. The 020 fetch-options test goes red only
    on the new one-call, open-end assertion. The 020 null-date test is expected to stay green.
- **FR-010 Surfaces.** `price_basis` stays `unadjusted_dollars`. There is one stated exception to
  "loader untouched": the loader copies manifest `volume_basis` into `frame.attrs` (`None` for a
  pre-044 manifest), with no validation change. The harness, metrics and callers are untouched. No
  dependency is added.
  - _Amended 2026-10-02 (cloud lane, 043 review queue; pending Camden's confirmation):_ the exception
    is **exactly one line** in `load_unadjusted_market_data`: the entry
    `"volume_basis": manifest.get("volume_basis"),` in its existing `result.attrs.update({...})`
    dict. Nothing else in that function changes. `tests/test_044_loader_untouched.py` pins the
    pre-044 loader's AST fingerprint with that one entry removed, and refuses a strict
    `manifest["volume_basis"]` read, a duplicate entry, any other `volume_basis` use, and any other edit.
- **FR-011 Factor-event validation, before any multiplication (R4).** Over the full response, not
  only the window:
  - normalized session labels are unique and ascending;
  - every `Stock Splits` value is finite and ≥ 0, where 0 alone means "no split";
  - every event ratio is finite and > 0;
  - the cumulative factor is finite and > 0 on every row.

  A NaN, infinite or negative value refuses with `split-factor event check failed`, naming the
  session. Nothing is silently discarded.
- **FR-012 Same-day split and dividend.** If P-1 leaves the same-day convention UNRESOLVED, the
  adapter refuses a window that contains a dividend on a split ex-date.
- **FR-013 Finite, positive observations (R1).** Reconstructed OHLC pass the existing validator.
  Every factor used is finite and positive (FR-011). A missing observation is never a pass,
  in the adapter or in the probe.
- **FR-014 Session-label alignment (R9).** A zone-aware provider index has its zone dropped with
  the wall date kept (`tz_localize(None)`), is normalized to naive midnight `datetime64[ns]`, and is
  then used for every factor lookup and slice. `start` and `end` are naive midnight bounds. Nothing
  is converted to UTC.

## 5. P-1 — the determination probe (Camden-run, network, once; not in the suite)

The suite has no network (CLAUDE.md), so the determination is a Camden-run probe whose **decision
rules are registered here, before the run**. The probe is `artifacts/p1_probe.py` (CLI), with
its registered rules in `artifacts/p1_rules.py` (split 2026-10-02 so each file is ≤ 300 lines,
R10). It imports only `yfinance`, `pandas`, the stdlib and `p1_rules`, and never imports `scripts/`.

- **`--self-check`** runs offline and writes nothing. It plants each probe-gate defect and checks
  that it goes red while its control passes (Rule 12). The defects are a NaN `Adj Close` (R1), a
  NaN split value (R4), a zone-labelled index across DST (R9), literal factors 8, 4, 4, 1 (R8), the
  volume-step diagnostic labels, five unanimous Q-P4 diagnostics that must still yield
  `provider_unverified` (R2), and a stale versus weekend-lag horizon.
- **`--revision <sha>`** makes one `history(period="max", interval="1d", auto_adjust=False,
  actions=True)` call per basket ticker. It writes `artifacts/p1-determination.txt` with:
  - the run date, the revision, and the yfinance and pandas versions;
  - the SHA-256 of both input CSVs;
  - the ledger hashes before and after;
  - the provider split tables;
  - per-case outcome lines, and PASS or STOP per question.

  **Raw rows:** every provider row behind a decision is written to
  `data/cache/spec044_p1/p1-raw-rows.csv`, which is gitignored because CLAUDE.md forbids committing
  market data. Its SHA-256 and row count are recorded in the committed summary.
- **Coverage is enforced first.** All five responses must end on the same session, within one
  completed weekday of the as-of instant (New York time). The probe cannot import `trading_days`,
  so it counts weekdays. An extra holiday can only cause a false STOP. If coverage fails, every
  question is a STOP.

**Input schemas** (header-only stubs are committed; `artifacts/.gitignore` un-ignores them because
the repository ignores `*.csv`). Dates are `YYYY-MM-DD`, every row needs a citation, and a missing
file, an empty file or a different header is a STOP.

| File | Columns | Constraints |
|---|---|---|
| `p1-filed-ranges.csv` | `ticker, quarter_start, quarter_end, low, high, form, filed_date, accession, source_url` | `form` is `10-K` or `10-Q`. `0 < low ≤ high`. `filed_date` must precede the first split after `quarter_end` |
| `p1-declared-dividends.csv` | `ticker, ex_date, declared_amount, share_basis, declared_date, form, accession, source_url` | `declared_date ≤ ex_date`. `declared_amount > 0`. `share_basis` is `pre_split` or `post_split` when `ex_date` is a split ex-date, and `not_applicable` otherwise |

**Q-P1 uses only a 10-K or 10-Q filed before the split.** A later filing restates its ranges on
the post-split basis, and would "confirm" an unreconstructed series. Believed, UNVERIFIED: the 2018
SEC amendments dropped the Item 5 high/low requirement, so qualifying filings may exist only for
older splits. For example, AAPL FY2013 quarters precede both the 2014 and 2020 splits.

| Question | Evidence | Registered rule |
|---|---|---|
| Q-P1 Cumulative price factor | Filed quarterly ranges (above) | PASS if every row's reconstructed closes lie within [low, high] ±1%, **and** no raw provider close does, **and** at least one row precedes two splits. Any row filed on or after the split, with no later split, or with a missing or non-positive observation is a STOP |
| Q-P2 Is `Close` dividend-adjusted? | `Close` and `Adj Close` on each dividend ex-date from 2016 and on its prior session | Every value must be finite and positive, or STOP (R1). STOP if `Close == Adj Close` before every dividend. PASS if every `(AdjC_p/C_p)/(AdjC_e/C_e)` is within **1e-4** (absolute) of `1 − D/C_p` |
| Q-P3 Dividends (FR-004) | Declared rows (above) | **Required coverage:** the last dividend before each split from 2016, and any dividend on a split ex-date, each derived from the response. A missing required row is a STOP. For each row, `adjusted` means `|provider·F/declared − 1| ≤ `**1e-3**, and `nominal` means `|provider/declared − 1| ≤ 1e-3`. PASS if every informative row (`F > 1`) agrees. Same-day rows must agree with the verdict, or it is a STOP; none means UNRESOLVED (FR-012) |
| Q-P4 Volume (FR-005) | Splits of **4:1 or larger** from 2016, with the **60-session** median volume before versus from the ex-date | **Amended 2026-10-02 (043 review F1, 044 R2; pending Camden's confirmation):** always **inconclusive**, so FR-005's `provider_unverified` branch applies. Medians from different sessions confound share basis with trading activity, so they cannot select a verified branch however many agree. Each split's post/pre step is still recorded as a diagnostic label (`adjusted`-looking in [0.5, 2], `nominal`-looking within 25% of `r`, else inconclusive), with its raw rows. A verified branch needs a same-observation or primary-source contract, added by a later amendment. This STOP does not halt the spec |
| D-3 GOOGL 2014 | The provider's GOOGL splits before 2016 | Records the representation. Not a clean ratio means GOOGL windows before it are refused |

The tolerances (1% Q-P1 band, 1e-4 for Q-P2, 1e-3 for Q-P3, and the Q-P4 bands) are pre-registered.
A STOP on any of them is recorded in the determination file, and any change is made by an open,
dated amendment of this section. They are never re-tuned silently to reach PASS. Q-P4 has no primary
source; it is internal-consistency evidence only.

**Amendment 2026-10-03 (decided by delegation from Camden; drafted by Claude; recorded before any Q-P1 run):** (1) A2 adopted: the Q-P1 pass band is the filed low/high with a ±1% tolerance, as registered above. (2) Derived ex-dates are accepted and carry an `ex_date_basis` column. (3) The 2026-10-02 Q-P4 amendment (always inconclusive, so `provider_unverified`) is confirmed: it fails closed and gives no volume evidence. (4) SC-007 is a one-time disclosure, not an amendment.


## 6. Success criteria

- **SC-001 (acceptance; manual, network, Camden re-runs it once).** This is spec 041's SC-001
  command, at the commit that contains 044:

  ```powershell
  python -c "import sys; sys.path.insert(0,'scripts'); from datetime import date; import data; p = data.download_unadjusted_market_data('AAPL', date(2016,1,4), date(2025,12,31), created_by_revision='<full sha>'); f = data.load_unadjusted_market_data(p); print(p); print(f.attrs['price_basis'], f.attrs['dividend_pay_date_policy'], f.attrs['dividends_bound'], f.attrs['dividends_sourced']); print(f.attrs['source_method'], f.attrs['volume_basis'])"
  ```

  **Pass:** a manifest path under `data/cache/unadjusted/`; then
  `unadjusted_dollars unbounded <k> 0` with k > 0; then a `source_method` beginning
  `derived:provisional:` and the `volume_basis` P-1 selected. The output, the manifest JSON and the
  ledger hashes are saved to `artifacts/sc-001-rerun.txt` with the date and commit. A failure is a
  finding, and no check is relaxed.
- **SC-002 (offline twin).** A provider-shaped fake has no step, one split in the window, one
  after `end`, and at least two dividends. With an injected reference table and clock, it writes a
  bundle to `tmp_path` that loads, and `run_backtest` completes on it.
- **SC-003 (Rule 12 planted defects).** Each defect is planted in memory with
  `tests/mutation_support_019.py::killed`, never in `data.py`. That helper catches only
  `AssertionError`, so each oracle translates **only** its expected, message-matched `ValueError` into
  an `AssertionError`. Any other exception propagates as an error. Positive controls carry a
  matching synthetic reference table and clock. Discriminating fixtures use flat provider prices.

  | ID | Plausible defect | Field perturbed | Killed by |
  |---|---|---|---|
  | M1 | `>=` instead of `>` | `F` at the split row | The unchanged oracle (`does not match the 2:1 action`) on a flat 2:1 split after row 1. Not a small ratio such as 1.25, which fits inside the tolerance |
  | M2 | Factor built from window splits only | `F` for a split after `end` | T-PIT: the same requested window; responses A (no later event) and B (a 2:1 event strictly after `end`, prefix re-adjusted, future prices and volumes perturbed); explicit loaded market fields compared; the fake asserts one open-end call. Reference coverage is coordinated through the FR-006 common interval, so no refusal masks it |
  | M3 | Volume treatment, by P-1 branch | `Volume` | ÷F branch: mutant ×F, killed by hand-enumerated expected volumes. Pass-through branches: mutant ÷F, killed by "Volume equals provider Volume". `provider_unverified`: an extra mutant labels the basis `provider_nominal`, killed by the attrs assertion |
  | M4 | Dividend treatment opposite to P-1 | `Value` of a dividend strictly before a later split | The P-1-pinned dividend test. A dividend on the last split date has `F = 1` and cannot kill it |
  | M5 | The reference comparison is bypassed | The FR-006 comparison | The negative test "provider omits a reference event dated after `end`, inside coverage" fails to refuse, with a valid-table control |
  | M6 | Nearest later split only | `F` before two splits | The unchanged oracle at the first split, on flat 2:1 then 4:1 fixtures |

  Refusals from the wrong gate, a missing fragment, or an unrelated exception are not kills.
- **SC-004 (split-table evidence).** `artifacts/split-table-crosscheck.md` has every basket split,
  its primary citation, the provider value (from P-1) and whether they match. It closes FR-006's two
  UNVERIFIED items. A lane other than the drafting lane has verified it, and Camden has spot-checked
  at least one citation per ticker.
- **SC-005 (oracle untouched).** Zero diff lines in the oracle and its tolerance.
- **SC-006 (suite).** `python -m pytest tests` is green. The count equals the pre-044 count plus
  exactly the tests enumerated in `tasks.md`.
- **SC-007 (unit size, R10).** Every unit's added-plus-removed lines, including evidence and task
  edits, are ≤ 300. Each unit is measured without Git, against copies saved before the unit.

## 7. Decisions — DECIDED 2026-09-30 (Camden)

- **D-1 Rounding: unrounded** (§2).
- **D-2 Tickers outside the reference table: refused.**
- **D-3 GOOGL 2014: P-1 decides the representation.** Windows starting in 2016 or later never use
  it, because `F(t)` uses only later splits.
- **D-4 Ratio tolerance (FR-006): relative 1e-9.**
- **D-5 Cross-check lanes.** An agent drafted the crosscheck from fetched SEC URLs. A different lane
  verifies it, and Camden spot-checks at least one citation per ticker.
- **R1–R11 (review-codex.md): all applied.**
  - **R1:** finite, positive values only. A missing observation is a STOP, and a NaN case is included.
  - **R2:** splits of 4:1 or larger, 60-session medians, disjoint bands, and all five basket splits
    must agree. Otherwise volume passes through unverified and is blocked from the cost model. M3
    branches on the decision, and dollar-volume invariance is dropped. _Superseded in part by the
    2026-10-02 Q-P4 amendment in §5 (medians are diagnostic only), pending Camden's confirmation._
  - **R3:** a horizon within one completed session, using `trading_days`, and the common-coverage
    comparison interval.
  - **R4:** full factor-event validation.
  - **R5:** the fixed-window T-PIT.
  - **R6–R9 and R11:** applied as written. The probe saves raw rows and enforces coverage.
  - **R10:** a hard cap of 300 added-plus-removed lines per unit.
  - **Tolerances:** 1e-4 for Q-P2 and 1e-3 for Q-P3, both pre-registered.

## 8. Out of scope

- Any gate on the cent-grid residual.
- Changing `price_basis`, the harness, or any caller. The loader gets only FR-010's attrs line.
- Building the cost-model Volume refusal. Its obligation is recorded in FR-005.
- Rule 14 reconciliation of dividend amounts or ex-dates beyond P-1.
- Any second provider. Anything under `exec/`, `docs/trials/**`, `live_safety_gate.py` or `portfolio_risk.py`.

## Assumptions

- No strategy result is produced or claimed. P-1 and SC-001 figures are data provenance, stamped
  with their source and date.
- The 041 pay-date policy (`unbounded`) is unchanged.

## Delegations — Camden, 2026-10-09 (delegation answers G12–G16 in chat; recorded by Claude)
- **G12.** The T003/T004 reviews of `p1_probe.py` are delegated to an exact-head Codex review plus an
  independent Claude review. Each records its verdict in the PR with evidence.
- **G13.** The T007 live probe and later bounded fetches may run in the Codex lane on Camden's PC
  without a per-run "go", provided all three of these hold:
  - the request caps and endpoint allowlists hold
  - credentials are never printed
  - raw responses stay private and only sanitized manifests become public
