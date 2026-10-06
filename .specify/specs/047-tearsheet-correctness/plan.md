# Implementation Plan: Tearsheet correctness — friction drag, candle basis, null drawdown

**Branch**: `047-tearsheet-correctness` (name only; Camden owns Git) | **Date**: 2026-10-06
**Spec**: [spec.md](spec.md) (merged in PR #42) | **Tasks**: not yet written (queue Q16)
**Input**: queue Q15. Code citations are from the tree at `2942240`. Since the spec's `e2ed6f8`
nothing under `scripts/`, `reports/` or `tests/` changed except one line in
`tests/test_049_paper_loop.py`, so every spec citation still holds; the ones this plan relies on
were re-read at `2942240`.
**Status**: Design only. No code or test is authorized by this file. D-1, D-2 and D-3 stay open;
this plan records a recommendation for each and gates the units that depend on them.

## Summary

Fix three tearsheet values that are wrong, not merely undisclosed. **F1:** the harness records the
slippage dollars it charges on every fill, totals commission and slippage over every executed fill
(open position included), and the route copies the two totals into the response; the view stops
doing friction arithmetic. **F2:** the run's own unadjusted bars, and the SMA values the signal
actually used, travel in the tearsheet response; adjusted candles never carry fill markers.
**F3:** a null drawdown renders `N/A`, never `0.00%`.

Units are cut at **at most 300 lines added plus removed**, measured without Git against pre-unit
copies, tests included (044 SC-007 convention). A unit that would exceed the cap is split, never
compressed. The data half of F1 and F2 is pytest-testable and goes first; every view edit waits on
D-1 so it ships with a test that can go red (Rule 12).

## Technical context

**Language**: Python 3.12 (CI); TypeScript/React for `reports/web/`. **Dependencies**: none new in
the Python units. D-1 option (a) adds one web dev dependency; its Rule 6 line goes in that PR.
**Testing**: `python -m pytest tests`, offline. Route tests use `fixture_client`
(`tests/api_fixtures.py`) and `publish_bundle` / `session_prices` / `split_series`
(`tests/unadjusted_fixtures.py:41`, `:57`, `:67`). The route runs inside `research_attempt`
(`reports/api/routes/backtest.py:60`), which writes only to the labelled synthetic ledger that
`tests/conftest.py:18-23` installs, never to `docs/trials/`. Mutants go through
`tests/mutation_support_019.py::killed` (`:7-21`), which runs the unmutated control first and
counts only an `AssertionError`.
**Constraints**: no edit to `scripts/data.py` (spec §8); no `.github/` edit in a lane unit (D-1 (a)
needs one, so that part is human lane); no text owned by 038 changes (FR-008).

## Constitution check

| Rule | How the design satisfies it |
|---|---|
| 1 / 5 | Chart bars are the run frame row for row: no reindex, fill or resample (FR-006, M5). SMA values are the signal's own causal `Short_SMA_Research` / `Long_SMA_Research` columns (`scripts/ma_crossover_backtest.py:67-68`), never recomputed. Rule 5 edges below are tests. |
| 3 / 13 | Friction totals are the costs the harness charged, never recomputed from `slippage_bps` (spec §8). Until 046, the slippage figure is labelled flat-bps modeled slippage (FR-002). |
| 4 | No strategy change; baseline table untouched. |
| 6 | No new Python dependency. D-1 (a) carries its own line. |
| 8 | Fill-level arithmetic lives in `backtest_harness.py`, which owns fills (FR-003). The route copies totals and frame rows; `metrics.py` and `signals.py` are not edited. |
| 11 / 16 | New figures ride the response's existing `source_manifest_sha256` and `downloaded_at_utc` (`reports/api/routes/backtest.py:182`, `:185`). The fuller stamp and limitations block are 038's. |
| 12 | M1–M6 (with M1b, M4a) and view mutants V1–V3 each killed by its own message with a clean control; view mutants only after D-1. |
| 9 / 10 | Camden merges. Lane rules unchanged. |

## Open decisions that gate units (spec §7; none decided here)

| Decision | Recommendation (spec) | Gates |
|---|---|---|
| D-1 view test method | (a) minimal web test runner + CI step | U1b, U2b, U3 |
| D-2 source of chart bars | (a) the run's own bars in the tearsheet response | U2a, U2b |
| D-2 FR-004a sub-choice | open in the spec: send the signal's SMA, or draw no SMA on the run chart | U2a's SMA fields, M4a |
| D-3 `MarketDataView` basis | keep adjusted candles, drop the fill markers | U2b |

**D-1, how each option lands.** (a) needs a dev dependency in `reports/web/package.json`, a `test`
script, and one line in `.github/workflows/test.yml`'s `web` job (`:53-55`). The `.github/` line is
governance (constitution Rule 10), so U0 is Camden's; the lane units then add test files only.
(b) needs no dependency: each formatter becomes a pure exported function plus a typed case table
that fails `npm run build` (`tsc -b`). It proves types, not values, so it cannot kill M6 by value;
under (b) M6 is reported as not provable and U3 stops at the spec-conflict exit. (c) moves display
strings into the API; pytest then covers M6, at the cost of coupling presentation to the API
(spec D-1 (c)). **Mutation mechanism.** `killed()` execs Python only, so it cannot drive M6 or any
view mutant. Under (a), U0 also adds the TypeScript equivalent: copy the target `.tsx` into a temp
tree, apply one string replacement that must hit one site, run the named web test against the copy,
assert it fails with its own message, and assert the original file's bytes are unchanged.

**D-2, consequence for the API (proposed field names).** Under (a) the response gains
`chart_bars: list[RunBar]`, where `RunBar` is `BarData` (`reports/api/schemas.py:21-28`), and
`chart_price_basis: "unadjusted_dollars"`. Only if the FR-004a sub-choice is "send the SMA",
`RunBar` also carries `short_sma` and `long_sma` (nullable during warm-up); otherwise it carries
neither, M4a is replaced by an oracle that the run chart receives no SMA series, and the chart
draws none.
`BarData` itself is not changed: `/api/data/ohlcv` keeps serving adjusted bars to `MarketDataView`.
Under (b) U2a becomes a new read-only route and M4's oracle compares that route to the run frame;
under (c) U2a and U2b collapse to removing the candle chart, and M4/M4a/M5 become one test that the
response carries no bars. The tasks file is written for whichever is decided.

## Design

### F1 — friction recorded where it is charged (U1a)

- `run_backtest`'s inner `record()` (`scripts/backtest_harness.py:86-94`) gains a keyword
  `slippage=0.` written to a new event column `Slippage` (dollars, ≥ 0).
  - Buy (`:138`, `:148`): `shares * (fill - row.Open)`, i.e. the quantity bought times the price
    concession actually paid.
  - Sell and liquidation (`:98`, `:110`): `quantity * (quote - fill)`, using the quantity held **at
    exit**, after any split (`:120-122`).
  - Rejected (`:143`), mark, split, dividend, payment, initial: `0.`.
- At return (`:156-158`) `attrs` gains `commission_total` and `slippage_total`: the sums of `Fee`
  and `Slippage` over events whose `Event` is `buy`, `sell` or `liquidation`. Because they read
  events, an open entry with `liquidate=False` is counted and an exit that never happened is not.
  Full float precision; no rounding in the harness.
- Every existing ledger column keeps its value. `tests/test_041_pay_date_bound.py:522` compares two
  harness ledgers frame to frame, so the new column appears on both sides; `trial_runner.account`
  (`scripts/trial_runner.py:105-116`) reads only `Phase`, `Date` and `Equity`.
- Route (`reports/api/routes/backtest.py:174-196`): copy the two attrs into new response fields
  `commission_total` and `slippage_total` (rounded to cents only there, after summing).
  `schemas.py`'s `BacktestTearsheetResponse` (`:101-123`) gains both as `float`, with a
  `description` stating the slippage is the flat-bps model's dollars until 046.
- Not touched: `summarize_trades` (`:162`), `metrics.py`, the baseline rows.

### F1 — view (U1b, after D-1)

`api.ts`'s `BacktestTearsheetResponse` (`reports/web/src/types/api.ts:85-99`) gains the two fields.
The view deletes `:92-93` and renders `Commission: -$X · Slippage (flat bps, modeled): -$Y`, plus
their sum, from the response. The card header at `:155`, the `✓ 1e-9` badge at `:159` and the
TutorCard text at `:170-172` are 038's text (FR-008) and are left as found; the plan flags that
`:172`'s "25% of gross profits" check now reads a correct number but still names no gross figure.

### F2 — run bars and signal SMA in the response (U2a, after D-2)

- A route-local helper `_run_bars(signalled)` maps the frame the harness ran on
  (`reports/api/routes/backtest.py:57`) one row to one `RunBar`. It reads a **whitelist** of
  columns only: `Date` → `time` as `%Y-%m-%d`, nominal `Open/High/Low/Close/Volume` unrounded, and
  (SMA sub-choice only) `Short_SMA_Research` / `Long_SMA_Research` → `short_sma` / `long_sma` with
  `NaN` → `null`. The frame also carries forward-dated values such as `Dividend_Pay_Date`; the
  whitelist keeps them off the wire, and a test asserts the `RunBar` key set exactly. No reindex, `ffill`, `bfill`, `interpolate` or
  resample (FR-006). The route stamps `chart_price_basis` from `prices.attrs["price_basis"]`, not
  a literal; `run_backtest` already refuses any other basis (`scripts/backtest_harness.py:37-38`).
- Boundary: the route already holds `signalled`; it formats rows and computes nothing (Rule 8).
- **Basis flag for D-2.** The signal's SMAs are means of `Research_Close`, a total-return index
  anchored at the first nominal close (`scripts/ma_crossover_backtest.py:59-61`). After a split or
  any dividend they are not on the nominal candles' scale (after a 2:1 split, about twice the
  candle). Drawn on the candles' axis they would break FR-004's same-basis intent. So if the SMA is
  sent, U2b draws it on a separate, labelled price scale ("signal SMA, total-return units"), never
  on the candle axis; this is part of the sub-choice Camden decides.
- Session labels stay naive dates (CLAUDE.md "Timestamps"); no localization.

### F2 — view (U2b, after D-1, D-2, D-3)

- `BacktestTearsheetView.tsx:389-391` draws `tearsheet.chart_bars`, not `ohlcv`.
- `CandlestickChart` gains optional `sma` series props; when given it draws them and skips its own
  close-based SMA (`reports/web/src/components/charts/CandlestickChart.tsx:38-60`); when markers are
  shown and no `sma` is given it draws none (FR-004a).
- `App.tsx:219-221` stops passing `tearsheet.trade_log` to `MarketDataView`; `MarketDataView.tsx:106-110`
  passes no `trades`. Its caption at `:98` is 038's (FR-005) and is not edited.

### F3 — null drawdown (U3, after D-1)

`BacktestTearsheetView.tsx:143`'s fallback becomes `'N/A'`, matching `:131`. Under D-1 (a) or (b)
the expression is first extracted to a pure `formatPercentOrNA` used by the card; the baseline
table's `'—'` (`:456`) stays and is covered by the same case table.

## Rule 5 edges → tests

| Edge (spec §3) | Unit | Assertion |
|---|---|---|
| No trades | U1a | both totals `0.0`, present, not null |
| Open position at end (`liquidate=False`) | U1a | totals equal the entry-side hand calculation only |
| Split inside a held trade | U1a | exit slippage uses the post-split quantity |
| Rejected entry | U1a | contributes `0` to both totals |
| First and last session fills | U1a, U2a | counted in totals; their bars present in `chart_bars` |
| Dividend-only history | U2a | `chart_bars` closes equal the nominal frame exactly, and differ from `Research_Close` after the ex-date |
| Bundle and adjusted CSV over different ranges | U2a | `chart_bars` dates equal the bundle's sessions, whatever the adjusted panel spans |

## Mutant oracles (spec §5, made concrete)

Python mutants are one source-string replacement hitting one site, applied through `killed()`;
view mutants use U0's TypeScript mechanism (D-1). Each oracle asserts with its own message, and each
fixture is built so no other assertion fires first (the control proves that).

**How harness mutants become visible.** The route imports `run_backtest` by name
(`reports/api/routes/backtest.py:19`), so a `killed()` exec of `backtest_harness` does not reach
it, and the route rounds to cents. M1–M3 and M1b therefore call `backtest_harness.run_backtest` as a
module attribute, on a hand-built frame with `Buy_Next_Open` / `Sell_Next_Open` set explicitly, and
read `trade_log.attrs` at full precision (`1e-9`). Route coverage of the two response fields is a
separate, non-mutant test: they equal the attrs rounded to cents.

| Id | Planted defect | Fixture and oracle | Control |
|---|---|---|---|
| M1 | Buy-site `slippage=` argument replaced by `0.`; then, in a second `killed()` call, the sell-site one | `slippage_bps=5`, one closed trade: `slippage_total` equals `shares*Open*rate + qty*quote*rate` by hand | `slippage_bps=0`: slippage `0`, commission `2 * c` |
| M1b | `commission_total` computed as `2 * commission_per_trade * len(trades)` | `liquidate=False`, ends long after one closed trade: total short by one commission | same frame, `liquidate=True` |
| M2 | Slippage sum restricted to buy events whose date is in `trades["Entry Date"]` (closed trades only), plus sells | `liquidate=False`, ends long after one closed trade, `slippage_bps>0`: slippage short by the open entry's slippage | same frame, `liquidate=True` (every entry closed, so the mutant agrees) |
| M3 | Exit slippage uses `entry[4]` (entry quantity) instead of `quantity` | Hand-built frame, flat nominal prices with a 4:1 split (spec M3) inside a held trade; `Split` and the post-split price must pass `_validate_split_discontinuities` (`scripts/data.py:740-755`) if built through `publish_bundle`, or be set directly on the harness frame | same trade, no split |
| M4 | In `_run_bars`, the nominal `Close` read replaced by `Research_Close`, the adjusted-units series the frame also carries (today's chart shows adjusted bars) | Route on a split bundle and on a dividend-only bundle: `chart_bars` OHLC equal the run frame **exactly**, and `chart_price_basis == "unadjusted_dollars"` | unmutated route |
| M4a | (SMA sub-choice only.) `_run_bars(signalled, short_window, long_window)`: the `Short_SMA_Research` read replaced by `signalled["Close"].rolling(short_window).mean()`; a second `killed()` for the long column | Split bundle: sent values equal `Short_SMA_Research` / `Long_SMA_Research` | unmutated route |
| M5 | `_run_bars` body gains `.set_index("Date").asfreq("B").ffill()` before mapping rows | Bundle spanning MLK Day and Presidents' Day (2024-01-15, 2024-02-19): `chart_bars` dates equal the bundle's sessions; a holiday appears under the mutant | unmutated route |
| M6 | Null drawdown fallback `'N/A'` reverted to `'0.00%'` | D-1 runner: `null` renders `N/A`; `0.0` renders `0.00%`; null baseline fields render `—` | unmutated formatter |
| V1 | (FR-002, U1b.) View drag reverted to `trade_log.length * (2 * commission_per_trade)` | Fixture response with `slippage_total > 0`: rendered friction equals `commission_total + slippage_total`, and the label contains "flat bps" and "modeled" | unmutated view |
| V2 | (FR-004, U2b.) Tearsheet chart `data={ohlcv}` restored | Rendered chart receives `chart_bars`, not the `ohlcv` prop | unmutated view |
| V3 | (FR-005, U2b.) `MarketDataView` passes `trades` again | Rendered `MarketDataView` chart receives no trades | unmutated view |

**Field statements.** M1–M3 perturb `slippage_bps`, `liquidate` and `Split`, read at
`scripts/backtest_harness.py:84`, `:150`, `:120-122`. M4 perturbs the price column `_run_bars`
reads; equality is exact because a dividend-only basis gap is smaller than a tolerance would
forgive (spec §5). The adjusted-CSV path itself is excluded by construction: `_run_bars` takes
only the run frame, so there is no CSV argument to mutate. M5 perturbs the row index. M4a perturbs
the SMA source column. M6 perturbs `max_drawdown`, the only field the card reads.

**FR-008 (no 038 text changes).** Not a gate, so no mutant: each web PR records a before/after
check that the strings at `BacktestTearsheetView.tsx:131`, `:155`, `:159`, `:170-172` and
`MarketDataView.tsx:98` are byte-identical.

**Known gap (spec §5, unchanged).** A recompute from `slippage_bps` equals the recorded value under
flat bps, so no mutant can catch it before 046; 046's plan owns that gate. The view wiring of
FR-002/FR-004/FR-005 is red-provable only under D-1 (a); under (b) it is not, and the PR says so.

## Review units (each ≤300 changed lines; estimates, re-measured per unit)

| Unit | Content | Files | Rule 12 | Est. lines | Waits on |
|---|---|---|---|---|---|
| U0 | D-1 (a) only: web test runner, `test` script, CI step | `reports/web/package.json`, lockfile, `.github/workflows/test.yml`, TS mutation helper | runner control: a failing case goes red in CI; helper proven on one planted mutant | 40 + lockfile | D-1; **human lane** (`.github/`) |
| U1a | Harness `Slippage` column and totals; route and schema fields | `scripts/backtest_harness.py`, `reports/api/routes/backtest.py`, `reports/api/schemas.py`, `tests/test_047_friction.py` | M1, M1b, M2, M3 | 200 | none |
| U1b | View friction display from the response | `api.ts`, `BacktestTearsheetView.tsx`, web test | V1 | 90 | U1a, D-1 (U0 if (a)) |
| U2a | `RunBar`, `chart_bars`, `chart_price_basis` | `reports/api/routes/backtest.py`, `reports/api/schemas.py`, `tests/test_047_chart_bars.py` | M4, M5, M4a (sub-choice) | 220 | D-2, U1a |
| U2b | Chart draws run bars and signal SMA; `MarketDataView` markers removed | `BacktestTearsheetView.tsx`, `CandlestickChart.tsx`, `App.tsx`, `MarketDataView.tsx`, `api.ts`, web test | V2, V3 | 160 | U2a, D-1, D-3 |
| U3 | Null drawdown `N/A` | `BacktestTearsheetView.tsx`, web test | M6 | 60 | D-1 |

Every unit writes its tests first and records them red for the named reason, then makes them pass
in the same unit. No existing assertion is edited (FR-008); `tests/test_reports_api.py:107-137` is
read-only. U1a and U2a both edit `routes/backtest.py` and `schemas.py`, so they run in sequence;
none of 047's units runs concurrently with a 038 unit (spec §8, shared files).

## Flags for Camden (not fixed here)

- **021 fingerprints.** U1a edits `scripts/backtest_harness.py` and `reports/api/routes/backtest.py`,
  both on 021's T004/T052 whole-file list and both already drifted
  (`.specify/specs/021-finish-spec-019-migration/artifacts/t052-fingerprint-dry-check-20261004.md:59`,
  `:61`). 047 adds further drift to files T052 cannot match today; the frozen AST regions 021 owns
  are not touched by this design, but the T052 close-out must account for it.
- **`reconciliation_passed=True` and "✓ 1e-9".** A hard-coded value (`reports/api/routes/backtest.py:192`)
  and a badge (`BacktestTearsheetView.tsx:159`) presenting a check that does not run; also flagged
  by 035's plan. Not one of 047's three defects; 038 owns the wording.

## Verification per unit

`python -m pytest tests` before and after, with exit code and passed/failed/xfailed/errors; the
ledger check (`docs/trials/trials.jsonl` line count and SHA-256, `trials.head.json` SHA-256,
`docs/trials/returns/` absent) unchanged; `npm run lint` and `npm run build` for any web unit.
Linux runs are evidence; Camden's Windows venv is the gate.

Baseline recorded for this plan on 2026-10-06 at `2942240`, Linux, Python 3.12: exit 0, 1165 passed, 4 xfailed, 0 failed, 0 errors (1,386 subtests passed). U1a re-records it before its first change.

## Out of scope

As spec §9. Additionally: any `CLAUDE.md` or `.github/` edit (U0's CI line is Camden's), and the
TypeScript response type's missing provenance fields (`api.ts:85-99` carries none of
`reports/api/schemas.py:108-112`), which 038's stamp work owns.
