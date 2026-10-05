# Tasks: Free unadjusted data bundle — sources and Rule 14 reconciliation

**Input**: [spec.md](spec.md) (merged in PR #34), [plan.md](plan.md) (merged in PR #40).
**Status**: Draft (queue Q11). Every task is future work and unchecked. This file authorizes no
code, test, network call, bundle or Git operation by itself.
**Order**: single-threaded, dependencies stated per task and summarized at the end.

## Standing rules

- **HUMAN GATE** marks a task that needs a network call, a decision, or a review that only a person
  may make. Only those tasks name a person. Every other task is offline and takeable by a lane once
  its dependencies are met; it does not become a human gate by wording.
- M1–M9 are the plan's mutant table (plan.md, "Mutant oracles"); M1–M8 match spec §6, M9 is the
  plan's FR-010 addition. A kill counts only when the named gate refuses with **its own** message
  fragment. A refusal by another gate, an import error, an unrelated exception, or a zero-test run
  is not a kill (044 SC-003). Every kill has a clean control that must pass first.
- Mutants run through `tests/mutation_support_019.py::killed` (`:7`), in memory, never committed to
  the module they mimic. Its `old` string must hit exactly one site (`:11`).
- Tests go under `tests/`, use fakes only, and carry the FR-009 autouse socket guard in the shape of
  `tests/test_041_pay_date_bound.py:35-41`. No existing assertion is edited or weakened. In
  particular `tests/test_reports_api.py:118` (`reconciliation_passed`) stays as it is (plan, FR-007).
- No test may encode a tolerance, amount basis, second source or window before D-1, D-2 or D-4 is
  recorded with its basis.
- Each unit is ≤300 added-plus-removed lines, including tests and evidence, measured without Git
  against copies saved before the unit starts. A unit that would exceed it stops for a plan
  revision; it is never compressed to fit.
- `scripts/data.py` keeps its line endings exactly as found (mixed CRLF/LF). U3a, U3b, U4 and U5 edit
  it, so none runs while 041, 043 or 044 holds that file (spec §9).
- Ledger check before and after every unit: `docs/trials/trials.jsonl` line count and SHA-256,
  `docs/trials/trials.head.json` SHA-256, `docs/trials/returns/` absent (SC-005).
- Evidence files are `docs/implementation/spec-035/<name>.md`. Linux runs are evidence; Camden's
  Windows venv is the gate.

## Phase 0 — verification and decisions (HUMAN GATE except T004)

- [ ] T001 **HUMAN GATE — FR-001 network observations, Camden, online, once per source.**
  Files: `docs/implementation/spec-035/fr001-<source>-<YYYYMMDD>.md` (one per source: Tiingo EOD,
  Alpaca Basic, EODHD free). **Task:** for AAPL around 2020-08-31 and NVDA around 2024-06-10, record
  the endpoint, parameters (no key), UTC time, and the observed answer to every spec §3 question:
  nominal or adjusted OHLC across each split, split and dividend fields and their history depth,
  dividend amount basis, and coverage start. **Acceptance:** each §3 row has a dated observation or
  stays UNVERIFIED with the reason. No key, token or header value appears in any file (FR-003).
  **Rule 12 planted defect:** a review copy of one record with the UTC time removed, or with the
  NVDA window omitted, must be refused by the T002 checklist; the complete record is the control.
  **Depends on:** none.

- [ ] T002 Compile `research.md` from T001's saved records only. Files:
  `.specify/specs/035-free-unadjusted-bundle/research.md`. **Acceptance:** one row per spec §3 row
  with claim, observation, date and the T001 file that observed it; the yfinance row cites 044's
  evidence (`044 spec.md` §1), and the SEC EDGAR row cites a recorded split spot-check or stays
  UNVERIFIED; a row whose evidence file is
  absent stays UNVERIFIED; no figure without a cited record (Rule 11). A checklist at the top lists
  the fields T001 requires. **Rule 12 planted defect:** a draft row marked verified that cites no
  T001 file must fail the checklist; a fully cited row passes. **Depends on:** T001.

- [ ] T003 **HUMAN GATE — decisions D-1 to D-4, Camden.** Files: spec §8 (decision lines only).
  **Task:** record D-1 (second source, from T002's evidence), D-2 (dividend-amount tolerance and
  common basis, `Close` tolerance, each with its basis), D-3 (module placement; if the new module is
  chosen, the `CLAUDE.md` table row is part of this gate), D-4 (build window). **Acceptance:** every
  later task cites the recorded value, never a guess. **Rule 12 planted defect:** a unit diff that
  encodes a tolerance absent from spec §8 must be rejected at review; a diff citing the recorded
  D-2 line is the control. **Depends on:** T002.

- [ ] T004 U0 baseline. Files: `docs/implementation/spec-035/u0-baseline-<YYYYMMDD>.md`.
  **Acceptance:** `python -m pytest tests` on clean `main` with exit code and
  passed/failed/xfailed/errors, Python version, commit, and the ledger check. This is SC-002's
  baseline. **Rule 12:** not a gate; no planted defect. **Depends on:** none.

## U1 — pure dividend reconciler (≤300 lines; plan U1)

- [ ] T005 Write contracts first. Files: `tests/test_035_reconcile.py`. **Acceptance:** red, for
  the missing function, on: union sweep (one row per ex-date in either source); coverage first and
  last session `reconciled`, one session before start and one session after end `unreconciled`
  with reason `outside second-source coverage`; empty coverage makes every dividend `unreconciled`; ex-dates one
  session apart `mismatch`; one-sided dividend inside coverage `mismatch`; amount outside the D-2
  tolerance `mismatch`; unstated amount basis `unreconciled` with that reason; inputs unmutated;
  `assert_no_mismatch` raises `dividend reconciliation failed` naming each mismatched ex-date.
  A control test opens a socket and asserts the FR-009 guard fails it. **Rule 12 planted defects:**
  M3, M4, M5; record each exact failing assertion before implementing. **Depends on:** T003, T004,
  and 044 merged if D-3 places the reconciler in `scripts/data.py` (plan, D-3).

- [ ] T006 Implement `reconcile_dividends` and `assert_no_mismatch`. Files: the D-3 module
  (`scripts/corporate_action_reconciliation.py` if chosen; no I/O, network, credentials or file
  reads), `tests/test_035_reconcile.py`. **Acceptance:** T005 passes; M3 killed on status assignment, and M4 and M5 killed at
  this level through `assert_no_mismatch` raising `dividend reconciliation failed`, each through
  `killed()` with its control green. The write-level M4/M5 oracles follow in T009. **Depends on:** T005.

## U2 — `Close` cross-check (≤300 lines; plan U2)

- [ ] T007 Write contracts first. Files: `tests/test_035_close_check.py`. **Acceptance:** red on:
  a session present only in the primary refuses, and a session present only in the second source
  refuses; a relative `Close` difference just outside the
  D-2 tolerance refuses with `close cross-check failed` naming the first offending session, just
  inside passes; sessions outside coverage are ignored; a holiday absent from both sources is not a
  gap; first and last covered sessions are checked. The test states that it perturbs `Close`
  because that is the column a dividend-adjusted basis moves (Rule 12 field statement). **Rule 12
  planted defect:** the comparison reads `Open` instead of `Close`; a fixture perturbing only
  `Close` must go red. Control: identical bars pass. **Depends on:** T006.

- [ ] T008 Implement `cross_check_close`. Files: the D-3 module, `tests/test_035_close_check.py`.
  **Acceptance:** T007 passes; the `Open`-for-`Close` mutant is killed with its control green.
  **Depends on:** T007.

## U3a — manifest v3 writer path (≤300 lines; plan U3a)

- [ ] T009 Write contracts first. Files: `tests/test_035_manifest_v3.py`. **Acceptance:** red on:
  `CORPORATE_ACTION_COLUMNS_V3` keeps `Reconciliation_Status` and `Reconciliation_Reason` through
  validation; versions 1 and 2 keep today's column set; `cache_unadjusted_market_data` and
  `download_unadjusted_market_data` accept `second_source` and write version 3 with
  `reconciliation_source`, `reconciliation_coverage`, `close_cross_check`, counts by status, and
  `"universe_policy": "static_survivor_basket"`; split rows copy 044's status unchanged; `Reconciliation_Reason` is required unless the status is
  `reconciled`, and an unknown status is rejected; coverage is clipped to the primary's first and
  last session, so a second source extending past the primary's end writes and does not refuse; a
  `mismatch` or a `Close` refusal leaves the temp cache dir empty; no `second_source` writes
  version 2 exactly as today; a second source with no bars records
  `not performed: second source has no bars`; the version table sends v2 and v3 through
  `_validated_pay_date_policy`. **Rule 12 planted defects:** M1 (`old` string: the indented `auto_adjust=False,` keyword line at
  `scripts/data.py:1156`, since `auto_adjust=False` occurs at three sites and `killed()` requires
  one; fixture: all four OHLC columns
  dividend-scaled, no split in coverage, identical dividends, oracle `close cross-check failed`,
  control nominal bars write v3) and M2 (041 M1 funded-account oracle rebuilt on a v3 bundle:
  exactly one `rejected` re-buy and no `payment`; controls: unmutated v3 and v2), and the
  write-level M4 (second source with dividends and no bars, dates one session apart) and M5
  (second-only dividend), each raising `dividend reconciliation failed` naming the ex-date; controls:
  identical dates write, both sources list it. The existing v2
  oracle in `tests/test_041_pay_date_bound.py` is not edited. **Depends on:** T008 and 044 merged.

- [ ] T010 Implement the U3a writer path. Files: `scripts/data.py`, `tests/test_035_manifest_v3.py`.
  **Acceptance:** T009 passes; M1, M2 and write-level M4/M5 killed with controls green; `scripts/data.py` line-ending
  mix unchanged (record CRLF and LF counts before and after). **Depends on:** T009.

## U3b — loader refusals and `attrs` (≤300 lines; plan U3b)

- [ ] T011 Write contracts first. Files: `tests/test_035_manifest_v3.py`. **Acceptance:** red on:
  a v3 manifest with a `mismatch` row (counts consistent) raises
  `corporate-action reconciliation refused: mismatch`; counts disagreeing with the actions table
  raise `... counts disagree`; v1 and v2 load with
  `attrs["corporate_action_reconciliation"] == "not performed"`; a clean v3 exposes source,
  coverage, `close_cross_check` and counts in `attrs`; the frame built by `_merge_actions_for_execution`
  carries no `Reconciliation_*` column, and `run_backtest` output is identical for the same data
  written as v2 and as v3 (Rules 1, 8). **Rule 12 planted defect:** M7 (both
  variants). Control: a clean v3 loads. **Depends on:** T010.

- [ ] T012 Implement the loader. Files: `scripts/data.py`, `tests/test_035_manifest_v3.py`.
  **Acceptance:** T011 passes; M7 killed with its control green; line endings unchanged.
  **Depends on:** T011.

## U4 — second-source adapter and credentials (≤300 lines; plan U4)

- [ ] T013 Write contracts first. Files: `tests/test_035_second_source.py`. **Acceptance:** red on:
  a `SecondSourceSnapshot` with optional bars, required dividends, coverage and source name; the
  adapter for the D-1 source parses a fake transport response shaped from T001's saved record; a
  missing key raises before the transport is called; the D-1 source's `research.md` row is verified,
  and the test cites it (US1); error messages, log records and manifest
  fields are built from an allow-list. **Rule 12 planted defect:** M6 (key present, fake transport
  raises, sentinel absent from the message, every `caplog` record and every written byte).
  Control: missing key refuses before any transport call. **Depends on:** T003, T012.

- [ ] T014 Implement the adapter. Files: `scripts/data.py`, `tests/test_035_second_source.py`.
  **Acceptance:** T013 passes; M6 killed with its control green; `requests` is the only transport
  (no new dependency, Rule 6); no test opens a socket; `scripts/data.py` line-ending mix unchanged
  (CRLF and LF counts recorded before and after). **Depends on:** T013.

## U5 — Tiingo primary adapter (conditional; ≤300 lines; plan U5)

- [ ] T015 Void unless T002 records Tiingo free EOD bars as nominal across both splits. If void,
  record "void per research.md row <n>" here and skip. Otherwise, contracts first in a new
  `tests/test_035_tiingo.py`, then `TiingoUnadjustedAdapter` in `scripts/data.py`, keeping
  `_validate_split_discontinuities` and `SPLIT_RATIO_RELATIVE_TOLERANCE` unchanged and
  `capital_gate_eligible=False`, with the `scripts/data.py` CRLF and LF counts recorded before and
  after. **Rule 12 planted defects:** M1 adapter variant (reads adjusted
  columns) and M6 on this adapter. Controls: nominal fake bars write; missing key refuses first.
  **Depends on:** T002, T014.

## U6 — disclosure (≤300 lines; plan U6)

- [ ] T016 Write contracts first. Files: `tests/test_035_disclosure.py`. **Acceptance:** red on:
  `corporate_action_disclosure(attrs)` prints counts by status and `close_cross_check`; prints the
  exact phrase "unreconciled corporate actions" when any action is `unreconciled`; prints
  `corporate-action reconciliation: not performed` for v1/v2; the CLI loop and the API route both
  carry the same line; the API response adds `corporate_action_reconciliation` beside an unchanged
  `reconciliation_passed`, whose schema description says it is not Rule 14 status. **Rule 12
  planted defect:** M8. Control: an all-`reconciled` bundle omits the phrase. **Depends on:** T012.

- [ ] T017 Implement the renderer and wiring. Files: `scripts/ma_crossover_backtest.py`,
  `reports/api/routes/backtest.py`, `reports/api/schemas.py`, `reports/web/src/types/api.ts`,
  `tests/test_035_disclosure.py`. **Acceptance:** T016 passes; M8 killed with its control green; the
  web lint and build pass. **Depends on:** T016.

## U8 — build script (≤300 lines; plan U8)

- [ ] T018 Write contracts first. Files: `tests/test_035_build_bundle.py`. **Acceptance:** red on:
  the script loops the five tickers over the D-4 window through `download_unadjusted_market_data`
  with the D-1 second source; it writes only under the given cache root (assert no other path in a
  temp tree changes); it prints each manifest's counts; a primary failure for one ticker writes no
  manifest for that ticker and tries no other source. **Rule 12 planted defect:** M9 (failure caught
  and retried through yfinance). Control: all tickers succeed. **Depends on:** T003, T014, T017.

- [ ] T019 Implement `scripts/build_unadjusted_bundle.py`. Files: that script,
  `tests/test_035_build_bundle.py`. **Acceptance:** T018 passes; M9 killed with its control green;
  no network in tests. **Depends on:** T018.

## U7 — mutation driver (≤300 lines; plan U7)

- [ ] T020 Collect M1–M9 into one driver. Files: `tests/mutation/run_035_mutants.py` and one pytest
  wrapper `tests/test_035_mutants.py`. **Acceptance:** each mutant reports killed by its own message
  fragment with its control green; the wrapper collects at least one case (collection guard). The
  driver runs `killed()` and never writes a mutated file. **Rule 12 planted defect:** a driver copy
  whose M4 entry targets a string that no longer exists must fail on `killed()`'s one-site assertion,
  not report killed; the unedited driver is the control. **Depends on:** T019 (and T015 if not void).

- [ ] T021 Close the offline units. Files: `docs/implementation/spec-035/offline-close-<YYYYMMDD>.md`,
  this file. **Acceptance:** full suite exit code and counts against T004 (no new failure, no strict
  XPASS), every unit's measured line total, M1–M9 kill and control evidence, ledger check unchanged.
  **Rule 12 planted defect:** a close report missing one mutant's control line must fail the
  checklist; the complete report passes. **Depends on:** T020.

## U9 — real build and smoke run (HUMAN GATE)

- [ ] T022 **HUMAN GATE — FR-008 bundle build, Camden, online, once.** Files:
  `docs/implementation/spec-035/build-<YYYYMMDD>.md`; bundles under `data/cache/unadjusted/`, never
  committed. **Acceptance:** SC-003: five manifests with source, `universe_policy`, coverage and
  counts by status, no `mismatch`; any refusal recorded as a finding, never relaxed. **Rule 12
  planted defect:** an evidence copy with one manifest's counts removed must fail the SC-003
  checklist; the full record passes. **Depends on:** T021.

- [ ] T023 **HUMAN GATE — SC-004 AAPL `run_backtest` on the local bundle, Camden.** Files:
  `docs/implementation/spec-035/aapl-smoke-<YYYYMMDD>.md`. **Acceptance:** the command, commit, date
  and output saved; provenance shows source, counts and limitations; labelled a smoke test, with no
  return or Sharpe reported as a result (Rules 11, 15, 16); ledger check unchanged (SC-005).
  **Rule 12 planted defect:** an evidence copy that quotes a return without the smoke-test label and
  limitations must fail review; the labelled record passes. **Depends on:** T022.

- [ ] T024 Hand off. Files: this file, spec Status line. **Acceptance:** state which SCs are met with
  their evidence files, which actions remain `unreconciled` and why, and that
  `capital_gate_eligible` stays `False`. **Rule 12:** not a gate. **Depends on:** T023.

## Dependency summary

T001 → T002 → T003. T004 any time before T005.
T003, T004 → T005 → T006 → T007 → T008 → (044 merged) → T009 → T010 → T011 → T012.
T012 → T013 → T014 → T015 (conditional). T012 → T016 → T017.
T014, T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024.

Lane-takeable once their dependencies hold: T002, T004 to T021, T024. HUMAN GATE: T001, T003,
T022, T023.
