# Tasks: Tearsheet correctness — friction drag, candle basis, null drawdown

**Input**: [spec.md](spec.md) (merged in PR #42), [plan.md](plan.md) (merged in PR #48).
**Status**: Draft (queue Q16). Every task is future work and unchecked. This file authorizes no
code, test, dependency or Git operation by itself.
**Citations**: from the tree at `e0b0f78`. Nothing under `scripts/`, `reports/` or `tests/` changed
since the plan's `2942240`, so the plan's line numbers still hold.
**Order**: single-threaded, dependencies stated per task and summarized at the end.

## Standing rules

- **HUMAN GATE** marks a task that needs a decision, a governance edit, or a review only a person
  may make. Only those tasks name a person as the one who acts. Every other task is offline and
  takeable by a lane once its dependencies are met.
- **Line numbers are as of `e0b0f78`.** Once an earlier unit edits a file, later units locate each
  cited site by its string, not its line number, and re-cite it in their evidence.
- **Decisions are not assumed.** The view tasks (U1b, U2b, U3) are written for the plan's
  recommendations: D-1 (a), D-2 (a), D-3 keep adjusted candles and drop the markers. If T001, T002 or
  T003 records a different option, every task marked "assumes" below is void until this file is
  revised in its own PR. A lane never reinterprets a void task to fit the recorded option.
- Mutants M1–M6 (with M1b, M4a) and V1–V3 are the plan's table ("Mutant oracles"). A kill counts
  only when the named contract fails with **its own** assertion message. Another assertion, an
  import error, an unrelated exception (`TypeError`, `KeyError`, a compile error), or a zero-test
  run is not a kill. Every kill has a clean control that passes first.
- `killed()` counts any `AssertionError` (`tests/mutation_support_019.py:16-19`) and does not
  check the message. So each oracle passed to it holds exactly one `assert`, for its own contract;
  fixture setup raises anything but `AssertionError`. Each oracle's message names its mutant id.
- **Two kinds of control.** `killed()` runs the *unmutated* oracle first (`:12`). Spec §5's
  controls are different: the *mutant* must pass on the control fixture (for example M1b with
  `liquidate=True`). Those run through a test-local `survives(module, old, new, oracle)` that
  mirrors `killed()`, including the one-site and unchanged-bytes checks, and asserts the oracle
  raises nothing under the mutant. Both kinds are recorded for every mutant that has a spec control.
- Python mutants run through `tests/mutation_support_019.py::killed` (`:7-21`), in memory, never
  committed. Its `old` string must hit exactly one site (`:11`). Harness mutants (M1–M3, M1b) call
  `backtest_harness.run_backtest` as a module attribute and read `trade_log.attrs` at full
  precision (`1e-9`), because the route imports `run_backtest` by name
  (`reports/api/routes/backtest.py:19`) and rounds to cents.
- View mutants V1–V3 and M6 use U0's TypeScript mechanism: copy the target `.tsx` to a temp tree,
  apply one replacement that hits exactly one site, run the named web test against the copy, assert
  it fails with its own message, and assert the original file's bytes are unchanged. A view mutant
  must type-check and compile against the code it mutates; one that does not is not a kill.
- Tests go under `tests/` (Python) or the web test location U0 fixes (TypeScript). All are offline
  and use the synthetic fixtures in `tests/unadjusted_fixtures.py` (`session_prices` `:41`,
  `publish_bundle` `:57`, `split_series` `:67`) and `fixture_client` (`tests/api_fixtures.py`). No
  `data/cache/` read, no network, no write to `docs/trials/`.
- No existing assertion is edited or weakened. `tests/test_reports_api.py:107-137` is read-only
  (FR-008).
- **FR-008 text check.** Every web unit records, before and after, that 038's text is
  byte-identical: in `BacktestTearsheetView.tsx` the `Rf = 3.78% (3m T-Bill)` line (`:133`), the
  `FRICTION MODEL` header and its `$commission / bps` line (`:151`, `:155`), the `✓ 1e-9` badge
  (`:159`) and the whole TutorCard (`:166-173`); and `MarketDataView.tsx:98`'s caption.
- **021 fingerprints.** U1a and U2a edit `scripts/backtest_harness.py` and
  `reports/api/routes/backtest.py`, both on 021's T004/T052 whole-file list. Each such unit records
  the files' SHA-256 before and after in its evidence so 021's close-out can account for the drift
  (plan, "Flags for Camden").
- Each unit is ≤300 added-plus-removed lines, tests and evidence included, measured without Git
  against copies saved before it starts. A unit that would exceed it stops for a plan revision; it
  is never compressed to fit.
- No 047 unit runs while a 038 unit holds `BacktestTearsheetView.tsx`, `routes/backtest.py`,
  `schemas.py` or `api.ts` (spec §8). No edit to `scripts/data.py`, `metrics.py` or `signals.py`.
- Ledger check before and after every unit: `docs/trials/trials.jsonl` line count and SHA-256,
  `docs/trials/trials.head.json` SHA-256, `docs/trials/returns/` absent (SC-004).
- Evidence files are `docs/implementation/spec-047/<name>.md`. Linux runs are evidence; Camden's
  Windows venv is the gate.

## Phase 0 — decisions and baseline (HUMAN GATE except T004)

- [x] T001 **HUMAN GATE — D-1, view test method, Camden.** Files: spec §7 (decision line only).
  **Task:** record (a) web test runner, (b) typed case table at build, or (c) display strings in
  the API, with the basis. **Acceptance:** the recorded option is cited by T005, T008, T012 and
  T014. **Rule 12 planted defect:** a unit diff that adds a web test dependency with no recorded
  D-1 line must be rejected at review; a diff citing the D-1 line is the control. **Depends on:** none.

- [x] T002 **HUMAN GATE — D-2 and its FR-004a sub-choice, Camden.** Files: spec §7 (decision line
  only). **Task:** record the source of chart bars ((a) run bars in the response, (b) a new route,
  (c) no candle chart for runs) and, under (a), whether the signal's SMA is sent and, if so, that it
  is drawn on a separate labelled scale (plan, "Basis flag for D-2"). **Acceptance:** T010 cites the
  recorded option and sub-choice. **Rule 12 planted defect:** a T010 draft that asserts `short_sma`
  with no recorded sub-choice must be rejected at review; one citing the line is the control.
  **Depends on:** none.

- [x] T003 **HUMAN GATE — D-3, `MarketDataView` basis, Camden.** Files: spec §7 (decision line
  only). **Acceptance:** T012 cites the recorded option. **Rule 12 planted defect:** a T012 draft
  that changes `/api/data/stats` must be rejected at review; one that only drops markers is the
  control. **Depends on:** none.

- [ ] T004 Baseline. Files: `docs/implementation/spec-047/baseline-<YYYYMMDD>.md`. **Acceptance:**
  `python -m pytest tests` on clean `main` with exit code, passed/failed/xfailed/errors, Python
  version, commit, and the ledger check; `npm run lint` and `npm run build` results for
  `reports/web`. This is SC-002's baseline. **Rule 12:** not a gate; no planted defect.
  **Depends on:** none.

## U0 — web test runner (HUMAN GATE; assumes D-1 (a); plan U0)

- [ ] T005 **HUMAN GATE — U0, Camden (edits `.github/`).** Files: `reports/web/package.json`, its
  lockfile, `.github/workflows/test.yml` (`web` job, `:53-55`), the TypeScript mutation helper under
  `reports/web/` (no Python test-module name). **Acceptance:** `npm test` runs in CI's `web` job;
  the PR carries the Rule 6 line for the runner. **Rule 12 planted defect:** a deliberately failing
  case turns the `web` job red; the helper reports killed on one planted mutant the test detects,
  reports **survived** on one it does not, refuses a replacement hitting zero or two sites, and does
  not count a failure carrying a different message. The passing case and an unmutated copy are the
  controls. **Depends on:** T001.

## U1a — friction recorded where it is charged (≤300 lines; plan U1a)

- [ ] T006 Write contracts first. Files: `tests/test_047_friction.py`. **Acceptance:** red, for the
  missing attrs and fields, on: `trade_log.attrs` carries `commission_total` and `slippage_total`;
  no trades gives both `0.0`, present and not null; one closed trade with `slippage_bps=5` gives
  slippage `shares*Open*rate + qty*quote*rate` and commission `2*c`, by hand at `1e-9`;
  `liquidate=False` ending long after one closed trade counts the open entry's commission and
  slippage and no exit; a 4:1 split inside a held trade uses the post-split quantity at exit
  (`scripts/backtest_harness.py:120-122`); a rejected entry (`:143`) adds `0` to both; fills on the
  first and the last session are counted; the ledger's new `Slippage` column is `≥ 0`, `0.` on every
  non-fill event, and every pre-existing ledger column keeps its value; the route's
  `commission_total` and `slippage_total` equal the attrs rounded to cents. Split fixtures built
  through `publish_bundle` pass `_validate_split_discontinuities` (`scripts/data.py:740-755`);
  harness-only fixtures set `Buy_Next_Open` / `Sell_Next_Open` and `Split` directly. Each test states
  the field it perturbs (`slippage_bps` `:84`, `liquidate` `:150`, `Split` `:120-122`).
  **Rule 12 planted defects:** M1 (two `killed()` calls: buy-site, then sell-site `slippage=`
  replaced by `0.`), M1b, M2, M3; record each exact failing assertion before implementing. Spec §5
  controls through `survives()`: M1 with `slippage_bps=0`, M1b and M2 with `liquidate=True`, M3
  with no split. **Depends on:** T004.

- [ ] T007 Implement U1a. Files: `scripts/backtest_harness.py` (`record()` gains `slippage=0.`;
  buy `shares*(fill-row.Open)`, sell and liquidation `quantity*(quote-fill)`; attrs sum `Fee` and
  `Slippage` over `buy`, `sell`, `liquidation` only, one separate expression per total so M1b and
  M2 each hit one site; exit slippage is computed in `sell()` before `quantity` and `entry` are
  reset at `:108-109`, so M3's `entry[4]` is still in scope), `reports/api/routes/backtest.py` (copy and
  round to cents), `reports/api/schemas.py` (two `float` fields; the slippage description says it is
  the flat-bps model's dollars until 046), `tests/test_047_friction.py`. **Acceptance:** T006
  passes; M1, M1b, M2 and M3 killed with controls green; `summarize_trades`, `metrics.py` and the
  baseline rows untouched; friction never recomputed from `slippage_bps` (spec §8);
  `tests/test_041_pay_date_bound.py:522` still passes unedited; 021 file hashes recorded.
  **Depends on:** T006.

## U1b — view friction display (≤300 lines; assumes D-1 (a); plan U1b)

- [ ] T008 Write contracts first. Files: a web test beside the view, at the location T005 fixes.
  **Acceptance:** red on: given a fixture response with `slippage_total > 0` and a trade count whose
  `2 * commission * trades` differs from `commission_total`, the card renders `commission_total` and
  `slippage_total` as given, and no sum (FR-002: the view does no friction arithmetic; the plan's
  "plus their sum" conflicts with it, and a total, if wanted, is a response field added by a plan
  revision); the label names commission and slippage and contains "flat bps" and "modeled".
  **Rule 12 planted defect:** V1 (the commission figure reverted to
  `trade_log.length * (2 * commission_per_trade)`). Control: the unmutated view. **Depends on:**
  T005, T007.

- [ ] T009 Implement U1b. Files: `reports/web/src/types/api.ts` (two fields),
  `BacktestTearsheetView.tsx` (delete `:92-93`, render the response fields), the T008 test.
  **Acceptance:** T008 passes; V1 killed with its control green; lint and build pass; FR-008 text
  check recorded. **Depends on:** T008.

## U2a — run bars and chart basis in the response (≤300 lines; assumes D-2 (a); plan U2a)

- [ ] T010 Write contracts first. Files: `tests/test_047_chart_bars.py`. **Acceptance:** red on:
  `chart_bars` equals the run frame's `Date`, `Open`, `High`, `Low`, `Close`, `Volume` row for row,
  **exactly**, on a split bundle and on a dividend-only bundle (where `Close` differs from
  `Research_Close` after the ex-date); `chart_price_basis == "unadjusted_dollars"`, stamped from
  `prices.attrs["price_basis"]`; each bar's key set equals the whitelist exactly, so forward-dated
  columns such as `Dividend_Pay_Date` never appear; dates are naive `%Y-%m-%d` session labels; a
  bundle spanning 2024-01-15 and 2024-02-19 yields exactly the bundle's sessions; first and last
  sessions present; an adjusted CSV over a different range changes nothing; `/api/data/ohlcv` and
  `BarData` unchanged. SMA, per T002: either `short_sma` / `long_sma` equal `Short_SMA_Research` /
  `Long_SMA_Research` with `NaN` as `null`, or the key set has no SMA field. Each test states the
  field it perturbs (price column, row index, SMA source). The dividend-only bundle is built in the
  test module through `publish_bundle`, so it passes the bundle validators like any other fixture.
  **Rule 12 planted defects:** M4 (`Close` read replaced by `Research_Close`), M5
  (`.set_index("Date").asfreq("B").ffill().reset_index()` inserted, so the mutant fails the
  session assertion rather than raising `KeyError`), and under the SMA sub-choice M4a (two `killed()`
  calls, short then long) or, under no SMA, M4a′ (a `short_sma` entry added to the whitelist; the
  key-set oracle must fail). Oracles run through the route on `fixture_client`. **Depends on:**
  T002, T007.

- [ ] T011 Implement U2a. Files: `reports/api/routes/backtest.py` (route-local `_run_bars`, a
  whitelist read with no reindex, fill, interpolation or resample), `reports/api/schemas.py`
  (`RunBar`, `chart_bars`, `chart_price_basis`), `tests/test_047_chart_bars.py`. **Acceptance:**
  T010 passes; M4, M5 and M4a or M4a′ killed with controls green; the route computes
  nothing beyond formatting (Rule 8); 021 file hashes recorded. **Depends on:** T010.

## U2b — chart draws run bars; `MarketDataView` drops markers (≤300 lines; assumes D-1 (a), D-2 (a), D-3; plan U2b)

- [ ] T012 Write contracts first. Files: web tests at the T005 location. **Acceptance:** red on:
  the tearsheet chart receives `tearsheet.chart_bars`, not the `ohlcv` prop (the fixture gives the
  two different values); a chart given run bars draws no close-based SMA (FR-004a), whatever the
  viewer's marker toggle (`showMarkers`, `CandlestickChart.tsx:34`, is UI state and is not the key);
  `MarketDataView`, given no run bars, keeps its close-based SMAs; when the SMA is sent, it is drawn
  on its own labelled scale, never the candle axis; `MarketDataView`'s chart receives no trades; a
  run with no trades draws no fill markers. **Rule 12 planted defects:** V2 (the chart fed `ohlcv`
  again), V3 (`MarketDataView` passes the tearsheet trades again), V4 (the run-bars condition that
  suppresses the close-based SMA forced false). T012 records each exact replacement; each must
  compile against T013's code. Controls: the unmutated views. **Depends on:** T003, T009, T011.

- [ ] T013 Implement U2b. Files: `BacktestTearsheetView.tsx` (`:389-391`),
  `CandlestickChart.tsx` (a run-bars prop and optional `sma` props; when run bars are given, the
  close-based SMA memos `:38-64` are not computed and the overlays at `:133-151` draw only the sent
  SMA, on its own scale, or nothing), `App.tsx` (`:219-221`), `MarketDataView.tsx` (`:106-110`;
  caption `:98` untouched), `api.ts`, the T012 tests. **Acceptance:** T012 passes; V2, V3 and V4
  killed with controls green; lint and build
  pass; FR-008 text check recorded. **Depends on:** T012.

## U3 — null drawdown renders `N/A` (≤300 lines; assumes D-1 (a); plan U3)

- [ ] T014 Write contracts first. Files: a web test at the T005 location. **Acceptance:** red on:
  a pure `formatPercentOrNA` renders `null` as `N/A` and `0.0` as `0.00%`; the card uses it; the
  baseline table's null fields still render `—` (`BacktestTearsheetView.tsx:456`). The test states
  that it perturbs `max_drawdown`, the only field the card reads (`:143`). **Rule 12 planted
  defect:** M6 (fallback reverted to `'0.00%'`). Control: the unmutated formatter. Under D-1 (b) this
  task stops at the spec-conflict exit, since `tsc` cannot kill M6 by value (plan, D-1).
  **Depends on:** T005, T009 (shared file; U3 needs D-1 only, so it does not wait on U2b's
  decisions, but never runs concurrently with U2b).

- [ ] T015 Implement U3. Files: `BacktestTearsheetView.tsx` (`:143`), the T014 test.
  **Acceptance:** T014 passes; M6 killed with its control green; lint and build pass; FR-008 text
  check recorded. **Depends on:** T014.

## Close

- [ ] T016 Close the spec. Files: `docs/implementation/spec-047/close-<YYYYMMDD>.md`, this file,
  the spec Status line. **Acceptance:** full suite exit code and counts against T004 (no new
  failure, error or strict XPASS); web lint and build green; every unit's measured line total;
  M1–M6, M1b, M4a or M4a′ and V1–V4 each with its kill, its unmutated control and, where spec §5
  names one, its `survives()` control (SC-001);
  ledger check unchanged (SC-004); 021 hash drift listed for 021's close-out. **Rule 12 planted
  defect:** a close report missing one mutant's control line must fail the checklist; the complete
  report passes. **Depends on:** T013, T015.

## Dependency summary

T001, T002, T003 any time. T004 → T006 → T007.
T001 → T005. T005, T007 → T008 → T009.
T002, T007 → T010 → T011. T003, T009, T011 → T012 → T013.
T005, T009 → T014 → T015. T013, T015 → T016. U2b and U3 share a file and run one at a time.

Lane-takeable once their dependencies hold: T004, T006 to T016 except T005. U1a (T006, T007) waits
on no decision and can start now. HUMAN GATE: T001, T002, T003, T005.
