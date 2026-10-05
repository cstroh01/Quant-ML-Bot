# Implementation Plan: Free unadjusted data bundle — sources and Rule 14 reconciliation

**Branch**: `035-free-unadjusted-bundle` (name only; Camden owns Git) | **Date**: 2026-10-05
**Spec**: [spec.md](spec.md) (merged in PR #34) | **Tasks**: not yet written (queue Q11)
**Input**: queue Q10. Code citations are from the tree at `f84732d`; the only change to `scripts/`
or `reports/` since the spec's `6b62451` is the new `scripts/paper_targets.py`, so every spec
citation still holds.
**Status**: Design only. No code, test, network call or bundle is authorized by this file.

## Summary

Add a Rule 14 **dividend** reconciliation and a nominal `Close` cross-check against one free second
source, record a status per corporate action in a version 3 manifest, disclose the counts on every
surface that already prints bundle provenance, and then build the five-ticker bundle and run
`run_backtest` on AAPL once. Splits keep 044's FR-006 status unchanged. The reconciliation is pure
and offline. Every network observation and the bundle build are HUMAN GATE tasks.

The plan is cut into review units of **at most 300 lines added plus removed**, measured without Git
against pre-unit copies, including tests and evidence (044 SC-007 convention). A unit that would
exceed the cap is split, never compressed.

## Technical context

**Language**: Python 3.12 (CI). **Dependencies**: existing pins only. No vendor SDK; any adapter
uses `requests`, already pinned in `requirements.txt`; anything more needs a Rule 6 line.
**Storage**: bundles under `data/cache/unadjusted/` (gitignored, never committed). Committed
evidence under `docs/implementation/spec-035/`.
**Testing**: `python -m pytest tests`, offline, fakes only (FR-009). Mutants go through
`tests/mutation_support_019.py::killed` (`:7`), which runs the unmutated control first and counts
only an `AssertionError` from the named oracle.
**Constraints**: no Git in local lanes; no network in tests; no write to `docs/trials/**` or
`exec/`; `scripts/data.py` line endings kept exactly as found (mixed CRLF/LF).

## Constitution check

| Rule | How the design satisfies it |
|---|---|
| 1 / 5 | Reconciliation reads and labels; it never changes a price, date or amount. Status is manifest metadata, never a feature. Rule 5 edges (coverage first/last session, one-before-start, ±1-session ex-date, holiday gaps, one-sided bars) are tests in U1/U2. |
| 3 / 13 | Out of scope for the build. SC-004's run is a smoke test; no return or Sharpe from it is reported (Rules 11, 13, 15). |
| 6 | No new dependency planned. |
| 7 | No `exec/`, no broker. API keys come from the environment at call time only (FR-003). |
| 8 | Reconciliation is data-layer only. Signals, harness and sizing never read a status. Callers only print counts (FR-007). |
| 11 / 16 | Counts by status and the exact phrase "unreconciled corporate actions" travel with provenance on the CLI and API. |
| 12 | M1–M9 each killed by its own gate's message, each with a clean control, driven by `tests/mutation/run_035_mutants.py`. |
| 14 | FR-004 union sweep over the declared coverage; uncovered actions are `unreconciled`, never dropped. |
| 9 / 10 | Camden merges. Lane rules unchanged. |

## Open decisions that gate units (spec §8; none decided here)

| Decision | Gates | Why it gates |
|---|---|---|
| FR-001 HUMAN GATE observations, recorded in `research.md` | U4, U5, D-1 | No adapter is written against an UNVERIFIED claim (US1). |
| D-1 second source (Alpaca, EODHD, or both in sequence) | U4 | Decides the fake's response shape and the coverage window. |
| D-2 tolerances and common dividend-amount basis | U1, U2 | Tests may not encode a tolerance before it is decided with its basis. |
| D-3 module placement | U1, U2 | Decides the file the reconciler lives in (below). |
| D-4 build window | U8 | Default proposal: 044 SC-001's 2016-01-04 to 2025-12-31. |

**D-3, recommendation only.** A new pure module, `scripts/corporate_action_reconciliation.py`, with
no I/O, no network, no credentials and no file reads: it holds U1 and U2 only. Network adapters stay
in `scripts/data.py`, the module that owns downloads. Reasons: `scripts/data.py` is edited by 041,
043 and 044 and is 1,252 lines with mixed line endings; a separate module lets U1 and U2 proceed
while 044 still holds `data.py`, and keeps each unit under the cap. Cost: a new row in `CLAUDE.md`'s
module table, which is a governance edit for Camden, not a lane task. If Camden picks `data.py`,
U1 and U2 move into `data.py` and wait on 044 like U3.

**FR-007 API field, proposed (spec §5 left it to this plan).** Do not rename
`reconciliation_passed`. Renaming breaks `reports/api/schemas.py:120`,
`reports/web/src/types/api.ts:95`, and the existing assertion at `tests/test_reports_api.py:118`,
and tests are contracts. Instead add a sibling object `corporate_action_reconciliation`
(`source`, `coverage_start`, `coverage_end`, `close_cross_check`, counts by status, and the
disclosure line or `null`), and give `reconciliation_passed` a schema `description` stating that it
is **not** Rule 14 corporate-action status. The description must not call it an equity-curve check:
it is a hard-coded `True` (`reports/api/routes/backtest.py:192`); the "reconciled equity curve"
comments at `:47` and `:70` sit above a plain `equity_curve()` call with no comparison. **Flag, not
fixed here:** that constant, and the tearsheet text "All metrics are reconciled down to 1e-9
tolerance" and "✓ 1e-9" (`reports/web/src/components/views/BacktestTearsheetView.tsx:170`,
`:159`), present a check that does not run. That is a Rule 11/12 defect for spec 047 or 038.

## Design

### Status vocabulary and data shape

Version 3 adds two columns to the actions table: `Reconciliation_Status` (`reconciled`,
`unreconciled` or `mismatch`) and `Reconciliation_Reason` (required unless `reconciled`). Today
`_validate_corporate_actions` keeps only `CORPORATE_ACTION_COLUMNS` (`scripts/data.py:59-66`,
`:684`) on both the write path (`:1092`) and the load path (`:875`), so extra columns would be
dropped. U3a therefore adds a `CORPORATE_ACTION_COLUMNS_V3` set and passes the column set by
manifest version to that validator; versions 1 and 2 keep today's set byte for byte. Statuses are
joined onto the validated actions after validation and before the write. Split rows copy 044
FR-006's status string unchanged; the reconciler never re-reads a split ratio.
`_merge_actions_for_execution` (`:922-966`) never copies a status column into price rows, so no
status can reach a signal or the harness (Rules 1, 8).

**Coverage** is the intersection of the second source's declared window and the primary's first
and last session. Both ends are inclusive session labels. Sweeps and the `Close` check run only
inside it. Without the clip, a second source covering sessions after the primary's end (EODHD's
one-year window against D-4's default end of 2025-12-31) would refuse every build.

The manifest records `reconciliation_source`, `reconciliation_coverage` (`start`, `end`, or `null`
when the intersection is empty: every dividend is then `unreconciled`), `close_cross_check`
(`performed`, or `not performed: <reason>`), counts by status, and
`"universe_policy": "static_survivor_basket"`.

### Pure reconciler (U1)

`reconcile_dividends(primary, second, coverage, *, amount_tolerance, amount_basis) -> DataFrame`.
Iterates the **union** of both sources' ex-dates and returns one row per union member (M5).
Coverage is inclusive; a dividend outside it is `unreconciled` with reason
`outside second-source coverage` (M3). Ex-dates match exactly by session label; one session apart
is `mismatch` (M4). A one-sided dividend inside coverage is `mismatch`. Amounts compare on the D-2
basis; a source whose basis cannot be stated gives `unreconciled` with that reason.
`assert_no_mismatch(statuses)` raises `ValueError("dividend reconciliation failed: ...")`, naming
each mismatched ex-date. Inputs are never mutated.

### Price cross-check (U2)

`cross_check_close(primary, second, coverage, *, close_tolerance)`. Inside coverage, the two `Date`
sets must be equal (a bar in one source only refuses). Per session, the relative `Close` difference
must be within the D-2 tolerance. It raises `ValueError("close cross-check failed: ...")` with the
first offending session. It reads `Close` because that is the column a dividend-adjusted basis
moves (M1; Rule 12 field statement). Holidays have no bar in either source and are not gaps
(`scripts/data.py:269`, `trading_days`).

### Writer and loader (U3a, U3b, `scripts/data.py`)

- `cache_unadjusted_market_data` (`:1050`) and `download_unadjusted_market_data` (`:1234`) each gain
  an optional `second_source` argument; the download function passes it through, so FR-008's build
  goes through the public entry point. When given, the writer runs U1 then U2 after the existing
  validators (`:1091-1095`) and before any write (`:1106`), so a refusal writes no file, and writes
  version 3. When the second source has no bars, U2 is skipped and `close_cross_check` records
  `not performed: second source has no bars`, which U6 prints. When `second_source` is absent, the
  writer writes version 2 exactly as today, so existing callers and tests are untouched.
- The version gate at `:821-824` becomes an explicit per-version table: version 1 strict, versions 2
  and 3 apply `_validated_pay_date_policy` and hand the same policy to the merge.
- U3b: the loader refuses a v3 manifest with any `mismatch` row (`corporate-action reconciliation
  refused: mismatch`), or whose counts disagree with the actions table (`... counts disagree`). v1
  and v2 load with `attrs["corporate_action_reconciliation"] = "not performed"`. v3 exposes
  source, coverage, `close_cross_check` and counts in `attrs`.

### Second-source adapter and credentials (U4, `scripts/data.py`)

A `SecondSourceSnapshot` (bars optional, dividends required, coverage window, source name) and one
adapter class for the D-1 source, using `requests` through an injectable transport. The key is read
from the environment inside `fetch`; a missing key raises before the transport is called (FR-003).
Exception messages, log records and manifest fields are built from an allow-list of fields, so the
key reaches none of them (M6). U5 reuses the same helper and the same tests.

**FR-009.** Every 035 test module carries an autouse fixture that fails the test on
`socket.create_connection` or `socket.socket.connect`, in the shape of
`tests/test_041_pay_date_bound.py:32-41`. A control test in U1 opens a socket and asserts the
fixture fails it (Rule 12).

### Primary adapter (U5, conditional)

`TiingoUnadjustedAdapter` exists **only if** FR-001 shows Tiingo free EOD bars are nominal across
AAPL 2020-08-31 and NVDA 2024-06-10. Otherwise U5 is void and the primary is yfinance through 044.
If written, it keeps `_validate_split_discontinuities` (`:740`) and
`SPLIT_RATIO_RELATIVE_TOLERANCE` (`:92`) unchanged and declares `capital_gate_eligible=False`.

### Disclosure (U6)

One renderer, `corporate_action_disclosure(attrs) -> str`, beside `pay_date_disclosure`
(`scripts/ma_crossover_backtest.py:153`), used by both the CLI loop (`:275-278`) and the API route
(`reports/api/routes/backtest.py:183-186`), so the two cannot drift. It prints counts by status,
the `close_cross_check` value, and the exact phrase "unreconciled corporate actions" when any action
is `unreconciled` (M8). v1/v2 bundles print `corporate-action reconciliation: not performed`. The
API adds the sibling field to `schemas.py` and a new TypeScript type in `api.ts`; the TS
`BacktestTearsheetResponse` (`api.ts:85-99`) carries none of today's provenance fields, so this is
a new type, not a match to an existing one.

### Build script (U8)

`scripts/build_unadjusted_bundle.py`: loops the five tickers over the D-4 window through
`download_unadjusted_market_data` with the D-1 second source, writes only under
`data/cache/unadjusted/`, and prints each manifest's counts. FR-010: if the primary fails for a
ticker, that ticker fails and no manifest is written for it; no other source is tried. Offline
tests run it against fakes and assert it writes nowhere else. The real run is a HUMAN GATE.

## Review units (each ≤300 changed lines; estimates, re-measured per unit)

| Unit | Content | Files | Rule 12 | Est. lines | Waits on |
|---|---|---|---|---|---|
| U0 | Baseline suite counts and ledger hashes recorded; `research.md` from the FR-001 HUMAN GATE runs | `docs/implementation/spec-035/`, `research.md` | — | 120 | FR-001 runs |
| U1 | Pure dividend reconciler, Rule 5 edges, FR-009 fixture | D-3 module + `tests/test_035_reconcile.py` | M3, M4, M5 | 270 | D-2, D-3 |
| U2 | `Close` cross-check, tests | D-3 module + `tests/test_035_close_check.py` | (M1 gate) | 180 | D-2, D-3 |
| U3a | v3 column set, writer v3 path, `second_source` pass-through, version table | `scripts/data.py` + `tests/test_035_manifest_v3.py` | M1, M2 | 280 | 044 merged, U1, U2 |
| U3b | Loader refusals and `attrs` | `scripts/data.py` + same test module | M7 | 200 | U3a |
| U4 | Second-source adapter, credential allow-list | `scripts/data.py` + `tests/test_035_second_source.py` | M6 | 260 | D-1, U0, U3b |
| U5 | Tiingo adapter (void unless FR-001 supports it) | `scripts/data.py` + test | M1 (adapter variant), M6 | 250 | FR-001, U4 |
| U6 | Disclosure renderer, API field, types | `ma_crossover_backtest.py`, `routes/backtest.py`, `schemas.py`, `api.ts`, `tests/test_035_disclosure.py` | M8 | 200 | U3b |
| U7 | Mutation driver for M1–M9 | `tests/mutation/run_035_mutants.py`, one pytest wrapper | all | 240 | U1–U6, U8 |
| U8 | Build script, offline test | `scripts/build_unadjusted_bundle.py` + test | M9 | 180 | D-4, U4, U6 |
| U9 | HUMAN GATE: build run (SC-003), AAPL `run_backtest` (SC-004), ledger unchanged (SC-005) | `docs/implementation/spec-035/` | — | 80 | U8 |

Every code unit adds its tests first and records them red for the named reason, then makes them
pass in the same unit. No existing assertion is edited. U3a, U3b, U4 and U5 edit `scripts/data.py`
and so never run concurrently with 041, 043 or 044 (spec §9).

## Mutant oracles (spec §6, made concrete)

`killed()` (`tests/mutation_support_019.py:7-19`) counts any `AssertionError` and does not catch
other exceptions. It does not check which gate fired. So each oracle below asserts its own gate's
message fragment, and each fixture is built so that no other gate can fire first; the control run
proves that, because the control must pass.

| Id | Planted defect (one source-string replacement) | Fixture and oracle | Control |
|---|---|---|---|
| M1 | yfinance adapter's `auto_adjust=False` keyword (`scripts/data.py:1156`, matched with its indentation so it hits one site) becomes `True`; with U5, the Tiingo adapter reads its adjusted columns instead | Fake history returns dividend-adjusted bars when asked for adjusted data, with **all four** OHLC columns scaled so `_validate_unadjusted_prices` (`:597-598`) cannot fire; no split in coverage; both sources list the same dividends, so U1 passes. Write raises `close cross-check failed`; temp cache dir is empty | nominal bars write v3 |
| M2 | The version table hands v3 a policy that makes the merge (`:957-958`) use the ex-date for `unbounded` | New test: 041's M1 funded-account oracle shape (`tests/test_041_pay_date_bound.py:319-324`) rebuilt on a **version 3** bundle; exactly one `rejected` re-buy, no `payment`. The existing v2 oracle is not edited and does not cover this | same fixture unmutated; v2 bundle |
| M3 | U1 coverage start comparison shifted by one session | Dividend one session before start: status `unreconciled`, reason `outside second-source coverage` | first covered session `reconciled` |
| M4 | U1 matcher accepts ±1 session | Second source has dividends and **no bars**, so U2 is skipped by design. Dates one session apart: write raises `dividend reconciliation failed` | identical dates write |
| M5 | U1 sweep iterates the primary only | Second-only dividend: the oracle asserts the write raises `dividend reconciliation failed` naming that ex-date (not a status lookup, which would raise `KeyError`) | both list it |
| M6 | Key interpolated into the transport-error message | Key **present**; the fake transport raises; the sentinel key is absent from the message, every `caplog` record, and every written byte | missing key refuses before the transport |
| M7 | Loader reports `reconciled` for v2, or skips the `mismatch` refusal for v3 | v2: attrs read `not performed`. v3: fixture's counts **include** the `mismatch` row, so the counts check cannot fire; load raises `refused: mismatch` | clean v3 loads |
| M8 | Renderer drops the unreconciled line | Exact phrase present | all-`reconciled` bundle omits it |
| M9 | Build script catches a primary failure and retries yfinance | Fake primary fails for one ticker: no manifest for it, and no manifest anywhere whose `source_name` differs from the primary's (FR-010) | all tickers succeed |

M9 is added by this plan: FR-010 is a gate, so Rule 12 requires its red proof.

## Verification per unit

`python -m pytest tests` before and after, with exit code and passed/failed/xfailed/errors; the
ledger check (`docs/trials/trials.jsonl` line count and SHA-256, `trials.head.json` SHA-256,
`docs/trials/returns/` absent) unchanged; strict-xfail markers removed only by the task that makes
them pass. Linux runs are evidence; Camden's Windows venv is the gate.

Baseline recorded for this plan on 2026-10-05 at `f84732d`, Linux, Python 3.12: exit 0, 1165
passed, 4 xfailed, 0 failed, 0 errors. U0 re-records it before the first code unit (SC-002).

## Out of scope

As spec §10. Additionally: the hard-coded `reconciliation_passed` value and the tearsheet's
"reconciled down to 1e-9" text (flagged above for 047/038), and any change to `CLAUDE.md` (D-3's
table row is Camden's edit).
