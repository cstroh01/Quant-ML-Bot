# Feature Specification: Free unadjusted data bundle — sources and Rule 14 reconciliation

**Feature Branch**: `035-free-unadjusted-bundle` (name only; Camden owns Git)
**Spec number**: 035, assigned by `docs/V1-FINISH-PLAN.md:49` (S1). The folder name follows
cloud-lane queue item Q9. `docs/HANDOFF-2026-09-25.md:231` proposed
`035-free-unadjusted-data-bundle`; that folder was never created and this one supersedes it.
**Created**: 2026-10-04
**Status**: Draft `spec.md` only (queue Q9). No `plan.md`, `tasks.md`, code, test or run exists.
Plan and tasks follow from this file once it is merged (queue Q10, Q11).
**Input**: queue Q9; `docs/SCOPE-V1.md` §2 (`:37-56`) and §9 (`:163-177`).
**Blocks**: the v1.0 tag (`docs/SCOPE-V1.md` §3 item 1, "the backtester runs").

## 1. What changed since S1 was written, and what 035 still owns

`docs/V1-FINISH-PLAN.md:49-73` gave S1 three jobs. Two now belong to other specs:

| S1 job (FINISH-PLAN) | Owner now | Evidence |
|---|---|---|
| Dividend pay date as a declared bound | **041**, production tasks T007–T017 checked | `.specify/specs/041-dividend-pay-date-bound/tasks.md:37-66`; policy `unbounded` (`041 spec.md:86`; `scripts/data.py:81`) |
| Nominal prices from a split-adjusted yfinance feed | **044** (P-1 probe not yet run) | `044 spec.md:21-37`: `auto_adjust=False` removes dividend adjustment but not split adjustment |
| Rule 14 for **splits** | **044** FR-006: independent EDGAR/exchange table, ratio tolerance relative 1e-9 (D-4), out-of-range events disclosed as unreconciled | `044 spec.md:162-177`, `:333` |
| Rule 14 for **dividends**, plus a price cross-check | **035 (this spec)** | 036 F-1 (`036 spec.md:110-116`, `:488`); 041 T019 "Rule 14 is still owed" (`041 tasks.md:72`); 044 excludes dividend reconciliation beyond P-1 (`044 spec.md:355`) |
| Five-ticker bundle that validates and runs | **035 (this spec)** | 041 T018 ran on 2026-09-30 and **failed**: the split check refused AAPL's 4:1 split, with an observed ratio of 0.978 (`041 tasks.md:68-71`; `041 artifacts/aapl-bundle.txt`). That failure is why 044 exists. |

So 035 does **not** re-open D-7, the `unbounded` policy, 044's reconstruction design, or 044's split
reconciliation and its 1e-9 tolerance. It owns:

1. Verifying the §9 candidate sources before any code depends on them.
2. A primary-source adapter, if verification supports one.
3. A Rule 14 reconciliation of every **dividend**, and a nominal price cross-check, against a free
   second source, with every uncovered dividend recorded as `unreconciled`. Splits keep 044's
   status and vocabulary; 035 carries them into the same manifest counts unchanged.
4. The five-ticker bundle and the first end-to-end `run_backtest` on it.

**Stale citations noted, not fixed here.** `V1-FINISH-PLAN.md:14` cites `data.py:985-988` for the
`NaT` dividend pay date. Today that code is at `scripts/data.py:1202`.

## 2. Current state (cited from the tree at `6b62451`)

- **The adapter seam exists.** `UnadjustedDailySource.fetch` (`scripts/data.py:117-121`) returns an
  `UnadjustedSourceSnapshot` (`:95-114`). The snapshot has no price-basis field (`:98-101`). The
  writer puts `price_basis: unadjusted_dollars` into every manifest it publishes, after validation
  (`:1123`). The loader checks it (`:831-832`) and copies it into `attrs` (`:987`). So the stamp is
  applied at **write** time. Whatever passes the writer's validators is stamped.
- **The writer validates before it writes.** `cache_unadjusted_market_data` (`:1050`) runs
  `_validate_unadjusted_prices`, `_validate_corporate_actions` and
  `_validate_split_discontinuities` (`:1091-1095`). Then it writes data, actions, and the manifest
  last (`:1106-1129`).
- **The only adapter is yfinance.** It calls `history(auto_adjust=False, actions=True)`
  (`:1152-1158`). It always declares `capital_gate_eligible=False` (`:1225`) and four limitations
  (`:1213-1218`).
- **The manifest has no reconciliation field.** Its keys are listed at `:1108-1128`. Nothing
  records whether any action was cross-checked.
- **The harness needs the stamp.** `scripts/backtest_harness.py:37-38` raises unless
  `price_basis == "unadjusted_dollars"`.
- **Provenance already reaches callers.** `capital_gate_eligible` and `source_limitations` are
  carried by `scripts/ma_crossover_backtest.py:275` and `reports/api/routes/backtest.py:183-184`.
- **A field that reads like Rule 14 status.** `reports/api/routes/backtest.py:192` hard-codes
  `reconciliation_passed=True` (schema `reports/api/schemas.py:120`; `reports/web/src/types/api.ts:95`).
  It is not a corporate-action reconciliation. FR-007 must stop a reader taking it for one.
- **The manifest version gate is two-valued.** `scripts/data.py:821` accepts only
  `(1, UNADJUSTED_MANIFEST_VERSION)`, and `:824` applies the pay-date policy only when
  `version == UNADJUSTED_MANIFEST_VERSION`. Bumping the constant would refuse version 2 bundles, or
  send them down the strict version 1 path.
- **No bundle exists.** `data/cache/unadjusted/` has never been written (`docs/SCOPE-V1.md:47`;
  044 §1).

## 3. Candidate sources (every vendor claim UNVERIFIED until FR-001 records it)

Each claim below is from `docs/SCOPE-V1.md` §9 (vendor documentation read 2026-10-03) or §2
(verified 2026-09-25). This spec repeats those claims. It does not test them.

| Role | Candidate | Claim | State |
|---|---|---|---|
| Primary bars | Tiingo EOD, free key | 30+ years; 1,000 requests/day; 500 symbols/month (`SCOPE-V1.md:171`) | UNVERIFIED |
| Primary bars | Tiingo EOD | Whether `open/high/low/close` are nominal, and whether split and dividend fields exist | UNVERIFIED (`:171`). **Tension:** `:49` says Tiingo's corporate-actions API is on no free tier. FR-001 resolves it. |
| Second source | Alpaca Basic, free key | Daily bars since 2016; 200 requests/min (`:172`) | UNVERIFIED |
| Second source | Alpaca | Corporate-action history depth, and whether bars can be requested raw | UNVERIFIED (`:172`) |
| Cross-check | EODHD free | Splits and dividends with `paymentDate`, capped at 1 year (`:49`) | Verified 2026-09-25 |
| Cross-check | yfinance `auto_adjust=False` | Split-adjusted despite the flag (044 §1) | Established 2026-09-30 |
| Cross-check | SEC EDGAR | Spot checks of individual splits from filings (`V1-FINISH-PLAN.md:66-67`) | Available, manual |

If a candidate fails verification, §2's existing sources stand (`SCOPE-V1.md:176`). No paid tier
is proposed or assumed.

## 4. User scenarios

- **US1 — Verified sources (P1).** A reviewer opens `research.md` and sees, for every candidate in
  §3, the documented claim, the observed behavior, the date, and the HUMAN GATE task that observed
  it. *Accept:* no adapter merges whose source row is still UNVERIFIED.
- **US2 — Reconciled bundle (P1).** A reviewer loads any of the five bundles and can see, for every
  action, whether it is `reconciled`, `unreconciled` (no second-source coverage) or refused
  (`mismatch`). *Accept:* the bundle loads only if no action is `mismatch`.
- **US3 — It runs (P1).** `run_backtest` completes on the real AAPL bundle, and its provenance
  shows the source, the reconciliation counts, and the limitations. *Accept:* SC-004.

### Edge cases (Rule 5)

- An action on the first or last session of the second source's coverage window counts as covered.
  The session one before the window start is `unreconciled`.
- Coverage starts mid-history: EODHD covers one year (`SCOPE-V1.md:49`). Alpaca's *bars* start in 2016
  (`:172`), but its corporate-action depth is UNVERIFIED. Actions before coverage are
  `unreconciled`, never dropped and never `reconciled`.
- The sources disagree on an ex-date by one session. This is a `mismatch`, not a fuzzy match. A
  one-bar shift is the failure Rule 5 exists to catch.
- Split ratio convention (`4.0`, `0.25`, `4:1`) is 044 FR-006's concern. When 035 copies 044's split
  status into the manifest, it copies the status and never re-compares raw ratio fields.
- Dividend amount basis: a source may report split-adjusted amounts (044 FR-004 is still open).
  Compare amounts on a declared common basis, or record the action as `unreconciled` with that
  reason.
- A holiday or ad hoc closure inside the window has no bar in either source. That is not a missing
  bar (`scripts/data.py:146`, `:227`, `:269`).
- The second source has a bar the primary lacks, or the reverse. Refuse (`mismatch`).

## 5. Requirements

- **FR-001 — Verify before depending (HUMAN GATE).** Every network observation is one HUMAN GATE
  task, run once by Camden, with its output saved under `docs/implementation/spec-035/`. It records
  the endpoint, the parameters, the UTC time, and the answer to each §3 question for AAPL around its
  2020-08-31 4:1 split, and for NVDA around its 2024-06-10 10:1 split (`036 spec.md:121-122`). No
  test, lane or CI job makes the call.
- **FR-002 — Primary adapter, conditional.** Add a `TiingoUnadjustedAdapter` implementing
  `UnadjustedDailySource` **only if** FR-001 shows that Tiingo's free EOD bars are nominal across
  both splits. Otherwise the primary is yfinance through 044, and this FR is void. The adapter must
  keep the `_validate_split_discontinuities` oracle and `SPLIT_RATIO_RELATIVE_TOLERANCE` unchanged
  (as 044 FR-003 does). It declares `capital_gate_eligible=False` until a later spec says otherwise.
- **FR-003 — Credentials.** Any API key is read from the environment at call time (`.env`,
  gitignored). It is never logged, written to a manifest, placed in an exception message, or
  committed. The adapter and the reconciler fail closed when the key is missing, before any network
  call.
- **FR-004 — Dividend reconciliation.** Sweep the **union** of both sources' dividends over the
  second source's coverage, not just the primary's list. Assign each exactly one status:
  - `reconciled`: same ex-date and same amount, on a declared common amount basis, within the
    declared tolerance (D-2).
  - `mismatch`: covered, but the ex-date or amount disagrees, or one source has a dividend the
    other lacks.
  - `unreconciled`: the second source has no coverage for that session. The reason is recorded.

  Any `mismatch` refuses the write, and nothing is published. A dividend is never silently trusted.
  Splits are not re-matched here. Their status comes from 044 FR-006 unchanged.
- **FR-005 — Price cross-check.** Over the second source's coverage, compare nominal `Close` per
  session within a declared tolerance (D-2). Any session outside it refuses the write. The check
  reads `Close` because that is the column a basis error moves (M1). The test states this, per
  Rule 12.
- **FR-006 — Manifest version 3.** Add `reconciliation_source`, the `reconciliation_coverage` window,
  a per-action `Reconciliation_Status` in the actions table (splits from 044, dividends from FR-004),
  counts by status, and `"universe_policy": "static_survivor_basket"`. The version gate at
  `scripts/data.py:821-824` becomes explicit per version, so a version 2 bundle keeps its own
  pay-date policy. Version 1 and 2 bundles still load and report `reconciliation: not performed`,
  never `reconciled`. The loader refuses a version 3 manifest that has any `mismatch` row, or whose
  counts disagree with its actions table. The loader exposes all of this in `attrs`.
- **FR-007 — Disclosure (Rule 16).** Every surface that already prints bundle provenance (036
  FR-008; `ma_crossover_backtest.py:275`; `routes/backtest.py:183-184`) also prints the counts by
  status. If any action is `unreconciled`, it also prints the words "unreconciled corporate actions".
  The hard-coded `reconciliation_passed=True` (`routes/backtest.py:192`) is renamed, or labelled on
  the same surface, so that it cannot be read as Rule 14 status. Changing the API field is a plan
  decision (Q10).
- **FR-008 — Bundle build (HUMAN GATE).** One script builds AAPL, MSFT, GOOGL, NVDA and AMZN over a
  stated window through `download_unadjusted_market_data`. It is run by Camden, online. It writes
  only under `data/cache/unadjusted/`, and nothing it writes is committed.
- **FR-009 — Offline tests.** Every test uses fakes. A test module that would open a socket fails.
- **FR-010 — No silent fallback.** If the primary fails, the build does not fall back to another
  source for the same ticker within one manifest. A source change is a new manifest with its own
  `source_name`.

## 6. Rule 12 — planted defects (each killed, each with a clean control)

| Id | Plausible defect | Gate that must kill it | Oracle |
|---|---|---|---|
| M1 | **Basis stamp on adjusted data.** The adapter reads Tiingo's adjusted columns, so dividend-adjusted bars pass the writer and the manifest stamps them `unadjusted_dollars` at write time. | FR-005 `Close` cross-check | The fixture has **no split** inside coverage, so `_validate_split_discontinuities` cannot fire first. The primary's bars are dividend-adjusted and the second source's are nominal. The write raises FR-005's message and no file appears. Control: nominal bars pass. |
| M2 | **Back-dated dividend lag on the v3 path.** The FR-006 version gate sends a v3 manifest down a branch that resolves `unbounded` to the ex-date. | The funded-ledger receivable behaviour (041 M1 oracle, `041 spec.md:337-344`). It is **not** the harness date check (`backtest_harness.py:47`), which accepts a pay date equal to the ex-date. | A full-allocation account where a re-buy falls between the ex-date and the final session. The re-buy is `rejected`. Control: the unmutated loader on a v3 and a v2 manifest. |
| M3 | **Coverage laundering.** A dividend before the coverage start is marked `reconciled`. | FR-004 status assignment | A dividend one session before coverage must be `unreconciled`. Control: a dividend on the first covered session is `reconciled`. |
| M4 | **Off-by-one ex-date tolerated.** The matcher accepts ±1 session. | FR-004 | The second source supplies **no bars**, only actions, so FR-005 cannot fire. Dividends one session apart give `mismatch`, and the write refuses with FR-004's message. Control: identical dates. |
| M5 | **One-sided sweep.** The reconciler iterates only the primary's dividends. | FR-004 | The primary omits a dividend the second source has. The result must be `mismatch`. Control: both sources list it. |
| M6 | **Credential leak.** The key appears in an exception or the manifest. | FR-003 | A sentinel key string must not appear in the raised message or any written byte. |
| M7 | **Status laundering in the loader.** A v1 or v2 bundle reports `reconciled`, or a v3 `mismatch` row loads. | FR-006 | Each must report `not performed` or refuse, respectively. Control: a clean v3 bundle loads. |
| M8 | **Disclosure dropped.** The renderer omits the unreconciled line. | FR-007 | A bundle with one `unreconciled` dividend prints the exact phrase. Control: an all-`reconciled` bundle does not. This follows the shape of 041 SC-007. |

A kill counts only when the expected gate refuses with its own message. A refusal by a different
gate is not a kill (044 SC-003, `044 spec.md:300-304`).
Mutants are applied in memory or in a scratch copy, never committed to the module they mimic.
Drivers live under `tests/mutation/` and invoke pytest (`CLAUDE.md`, Tests).

## 7. Success criteria

- **SC-001**: `research.md` has a dated, observed answer for every §3 row, with no row left
  UNVERIFIED that an adapter depends on.
- **SC-002**: M1–M8 are killed and their controls pass. The full suite is no worse than a baseline
  recorded before the first code task.
- **SC-003**: five bundles exist and validate (FR-008). Each manifest records the source,
  `universe_policy`, coverage, and counts by status, with no `mismatch`.
- **SC-004**: `run_backtest` completes on the real AAPL bundle, with the command and its output
  saved as evidence. The output is a smoke test of the machinery. Per Rules 11, 15 and 16, no
  return or Sharpe from it is reported as a result.
- **SC-005**: the ledger is unchanged: `docs/trials/trials.jsonl` byte-identical before and after.

## 8. Decisions

- **D-1 — Second source (open; Camden).** Choose Alpaca bars (2016+) or EODHD (one year) as the
  Rule 14 source, or both in sequence, once FR-001 has recorded what each actually provides.
- **D-2 — Tolerances (open; Camden).** Choose the dividend-amount tolerance for FR-004, and its
  common amount basis, and the `Close` tolerance for FR-005. Split tolerance is already decided by
  044 D-4 and is not re-opened. This spec proposes no figure. Each must be stated with its basis before
  any test encodes it.
- **D-3 — Module placement (open; Camden).** Choose whether reconciliation lives in
  `scripts/data.py`, which 041, 043 and 044 also edit, or in a new data-layer module. A new module
  needs a row in `CLAUDE.md`'s table. That is a governance edit and is flagged here, not made.
- **D-4 — Window (open; Camden).** Choose the build window. 044's SC-001 uses 2016-01-04 to
  2025-12-31 (§1 of that spec). Matching it is the default proposal.

### Decisions recorded (Camden, 2026-10-09 (gate packet `claude/gate-packet-20261009.md`))
- **Retarget (G3-R).** 035 builds the accepted unadjusted cache for the spec 058 ETF universe.
- **D-1.** Alpaca raw SIP, 2016 onward, is the second source. EODHD is rejected: on 2026-10-09 the free
  tier returned one row plus a warning (Codex lane record).
- **D-2.** `Close` tolerance is relative 1e-3. Basis: vendors differ between the official closing
  auction price and the last trade. The dividend amount tolerance is absolute $0.0001 per share at the
  declared per-share basis, because declarations are given to 4 decimals. Values outside tolerance are
  excluded or disclosed, never averaged.
- **D-3.** Reconciliation goes in a new module, `scripts/corporate_actions.py`. Its `CLAUDE.md` row is
  a separate governance PR.
- **D-4.** The window runs from each instrument's listing date to the latest completed session. Spec
  058's seal still governs research use.

## 9. Sequencing

035 edits `scripts/data.py` (unless D-3 says otherwise), and so do 043 and 044. It does not run
concurrently with either. FR-001 and D-1/D-2 can proceed now, because they are docs and human
gates. If FR-002 is void, FR-008 waits on 044. The 046 cost model depends on 035
(`V1-FINISH-PLAN.md:93`).

## 10. Out of scope

- Re-deciding D-7 or the `unbounded` policy (041), or 044's reconstruction.
- Survivorship: the basket stays static (`SCOPE-V1.md` §6). No source here fixes it.
- Point-in-time fundamentals (EDGAR `companyfacts`; `SCOPE-V1.md:174`, deferred by §7).
- Marking any bundle `capital_gate_eligible=True`.
- Anything under `exec/`, `docs/trials/`, the broker, or a paid tier.
