# Feature Specification: Tearsheet correctness — friction drag, candle basis, null drawdown

**Feature Branch**: `047-tearsheet-correctness` (name only; this spec creates no branch)
**Spec number**: 047, assigned by cloud-lane queue item Q12.
**Created**: 2026-10-05
**Status**: Draft `spec.md` only (queue Q12). No `plan.md`, `tasks.md`, code or test exists.
Plan and tasks follow once this file is merged (queue Q15, Q16).
**Input**: queue Q12; `docs/implementation/spec-038/disclosure-audit-20261003.md` ("the 038
audit"), Question 3 (`:151-154`) and the tearsheet rows at `:78`, `:79`, `:81`.

## 1. Why a separate spec

The 038 audit lists three tearsheet defects "found in passing" and calls them correctness defects,
not only disclosure gaps (`disclosure-audit-20261003.md:151-154`). Queue Q13 (spec 038) assigns
them here: "Tearsheet defects belong to spec 047, not 038". A disclosure gap means a figure lacks
its provenance or its limitation. Each defect below is different: the figure is **wrong**, or it
is drawn against the wrong data. A provenance stamp next to it would not fix it.

047 owns exactly three defects:

| ID | Defect | Audit row |
|---|---|---|
| F1 | The "Drag" figure counts commission only. Its own comment says it also includes slippage. | `:79` |
| F2 | Fill markers taken from the unadjusted bundle are drawn on candles from the adjusted cache. | `:81` |
| F3 | When `max_drawdown` is null, the card shows `0.00%`. | `:78` |

Everything else in the audit belongs to 038: the provenance stamp, the limitations block, the
Rule 15 Sharpe flag, the hard-coded `Rf = 3.78%`, the TutorCard text and the
`reconciliation_passed` wording. 047 must not change that text, so 038's sweep has a fixed target.

## 2. Current state (cited from the tree at `e2ed6f8`)

### F1 — friction drag

- The view computes
  `totalFrictionDrag = tearsheet.trade_log.length * (2 * tearsheet.commission_per_trade)`
  (`reports/web/src/components/views/BacktestTearsheetView.tsx:93`). It shows it as
  `Drag: -$X` (`:158`), under the card's `$commission / bps` heading (`:155`).
- The comment above it says the figure is "$2 * commission * trades + roundtrip slippage" (`:92`).
  The code adds no slippage term.
- The harness does charge slippage. A buy fills at `Open * (1 + rate)` (`scripts/backtest_harness.py:138`)
  and a sell at `quote * (1 - rate)` (`:98`), where `rate = slippage_bps / 10000` (`:84`). Commission is
  charged once on each side (`:99`, `:139`). So the friction actually charged on a closed trade is
  two commissions plus the slippage dollars on both fills. The view drops the slippage dollars.
- The view counts only **closed** trades (`trade_log`). A position still open at the end has paid
  its entry commission and slippage, but it appears nowhere in `trade_log` (`scripts/backtest_harness.py:150-152`). The route
  sets `liquidate=LIQUIDATE_AT_END` (`reports/api/routes/backtest.py:66`), imported from
  `scripts/ma_crossover_backtest.py:42`, where it is `True` today. So this gap is latent. It becomes
  real the moment that constant changes.
- The API sends nothing that would let the view compute slippage dollars correctly. Trade
  `quantity` is not part of `TradeRecord`, and prices are rounded to cents
  (`reports/api/routes/backtest.py:163-171`). Any client-side formula is an approximation.
- The harness's event ledger does not record slippage either. Each event stores the quote as
  `Price` and the commission alone as `Fee` (`scripts/backtest_harness.py:89-94`, `:110`, `:148`).
  So FR-001 needs the harness to record each fill's price or slippage dollars at the moment it
  charges them. Rebuilding them afterwards from `slippage_bps` is what §8 forbids.
- The tutor text tells the reader to act on this figure: "Check the Drag metric: if friction
  consumes > 25% of gross profits…" (`BacktestTearsheetView.tsx:172`). An understated drag makes
  that check pass when it should not.

### F2 — candle basis

- The tearsheet chart draws `ohlcv` (`BacktestTearsheetView.tsx:389-391`). That is the
  `/api/data/ohlcv` response (`reports/web/src/App.tsx:95`, `:109`, `:197`).
- `/api/data/ohlcv` reads whichever CSV `get_cached_ticker_data` finds
  (`reports/api/routes/data.py:36-65`, `:94`). That is the legacy cache written by
  `download_market_data` with `auto_adjust=True` (`scripts/data.py:402`, `:442`): split- and
  dividend-adjusted prices.
- The fills come from the tearsheet, which runs on the unadjusted bundle
  (`reports/api/routes/backtest.py:49`). The harness refuses anything else (`scripts/backtest_harness.py:37-38`).
- Markers are placed by date and labelled with the fill price, for example `BUY @ $…`
  (`reports/web/src/components/charts/CandlestickChart.tsx:163-177`). Before a split, or before any
  dividend, the label states a nominal price that the candle under it never traded at. Both sides
  can also come from different date ranges, because the two files are separate.
- `MarketDataView` overlays the same `tearsheet.trade_log` on the same adjusted bars
  (`App.tsx:219-221`; `MarketDataView.tsx:106-110`), under a caption that says "Split/dividend
  adjusted daily bars" (`:98`). The defect is the same on that surface.
- The chart also draws SMA lines, computed in the browser from the candle `close`
  (`CandlestickChart.tsx:38-60`). The signal itself is computed on `Research_Close`, a causal
  total-return series (`scripts/ma_crossover_backtest.py:55-69`). The overlaid SMAs therefore do not
  show the crossovers the strategy traded, today or after a basis change. On unadjusted candles they
  would also show a false crossover at every split. FR-004a covers this.

### F3 — null drawdown

- The card renders `max_drawdown !== null ? … : '0.00%'` (`BacktestTearsheetView.tsx:143`).
- The API sends `null` when `metrics.max_drawdown` returns `nan` (`reports/api/routes/backtest.py:191`).
  That happens for an empty curve, a non-finite equity value, or a non-positive start
  (`scripts/metrics.py:284-291`). None of these means "no drawdown". A curve that truly never declined
  returns `0.0`, not `nan` (`:297-298`).
- On the same view, the baseline table renders a null drawdown as `—` (`BacktestTearsheetView.tsx:456`).
  The Sharpe card renders a null as `N/A` (`:131`). So the card contradicts its own neighbours.
- Through the route, F3 is latent today. The route always loads a nonempty bundle with positive
  `STARTING_CAPITAL`, and the harness raises on non-finite equity (`scripts/backtest_harness.py:87-88`).
  So the view's `null` branch is reachable only through a future change or a direct response. M6's
  fixture therefore injects `null`; it does not try to produce it through the route.

### Test surface

- The tearsheet route has one success-path test, `tests/test_reports_api.py:107-137`. Nothing
  checks the friction figures, the chart's price basis or the null drawdown.
- The web app has no test runner. Its scripts are `dev`, `build`, `lint` and `preview`
  (`reports/web/package.json`). CI runs `npm ci`, `npm run lint` and `npm run build` only
  (`.github/workflows/test.yml:53-55`, `web` job). So no contract can yet go red on a `.tsx` expression.
  See D-1.

## 3. User scenarios

**US1 (P1) — a reader checks friction.** A reader looks at the friction card to see what costs
took out of the run. The figure equals the commission plus the slippage dollars the harness
actually charged, with the two parts shown separately. It can be traced to the run's fills.
*Independent test:* a fixture with a known number of fills, a known commission and known
slippage gives a total that matches a hand calculation from the fill prices.

**US2 (P1) — a reader looks at fills on a price chart.** Every fill marker sits on a candle from
the same price basis as the fill. If such a candle is not available, the chart shows no fill
markers and says why. *Independent test:* a fixture whose adjusted and unadjusted prices differ
by a 4:1 split never yields a fill marker on an adjusted candle.

**US3 (P2) — a run whose drawdown is not computable.** The card says the drawdown was not
computed (`N/A`, as the Sharpe card does). It never says `0.00%`. A real `0.0` still shows
`0.00%`. *Independent test:* the `null` and `0.0` cases render differently.

### Edge cases (Rule 5)

- **No trades.** Friction is `0` commission and `0` slippage, not missing. Fill markers: none.
- **Open position at the end** (`liquidate=False`). Friction includes the entry side of the open
  position. It excludes an exit that never happened.
- **Split during a held trade.** The exit quantity differs from the entry quantity
  (`scripts/backtest_harness.py:120-122`). Slippage dollars use each fill's own quantity.
- **Rejected entry** (`"rejected"` event, `scripts/backtest_harness.py:143`). It charges nothing
  and counts nothing.
- **Dividend-only history** (no split). The adjusted and unadjusted closes still differ before
  each ex-date, so F2 applies without a split.
- **Bundle and adjusted CSV over different date ranges.** F2's fix must not depend on the two
  ranges matching.
- **First and last session.** A fill on the first or the last session of the bundle has its
  candle drawn, and its friction is counted.

## 4. Requirements

- **FR-001 (F1).** The tearsheet response carries the friction actually charged in the run as
  separate fields: total commission dollars and total slippage dollars. Both are computed in
  Python from the harness's own fills, at full precision, before any display rounding. They cover
  every executed buy and sell, including the entry of a position still open at the end. Rejected
  orders are excluded.
- **FR-002 (F1).** The view shows those fields. It does no friction arithmetic of its own, so the
  expression at `BacktestTearsheetView.tsx:92-93` and its misleading comment are removed. The
  label states what the figure contains (commission plus slippage). Until 046 lands, the slippage
  figure is labelled as flat-bps modeled slippage, not a Rule 13 cost estimate. The new figures
  carry the same provenance the tearsheet already returns (`source_manifest_sha256`,
  `downloaded_at_utc`; `reports/api/routes/backtest.py:181-185`), so they add no figure without a
  source (Rule 11). The fuller stamp is 038's work.
- **FR-003 (F1, boundary).** The friction computation reads fills, not signals. It lives in the
  harness (`backtest_harness.py`, which owns fills), not in `metrics.py` (which must not know
  about fills), not in the route and not in `signals.py` (`CLAUDE.md` module table, Rule 8). The
  route only copies the harness's totals into the response.
- **FR-004 (F2).** A candle chart that shows fill markers draws candles in the same price basis as
  the fills: `unadjusted_dollars`, from the same bundle the run used (D-2).
- **FR-004a (F2).** A chart that shows fill markers draws no SMA computed from the candle closes.
  It either draws the SMA values the signal used, sent by the API from `Research_Close`, or no
  SMA at all (decided in D-2).
- **FR-005 (F2).** Any chart that draws adjusted candles shows no fill markers from an unadjusted
  run. This covers the tearsheet chart and `MarketDataView`. 047 removes the markers only. The
  caption text at `MarketDataView.tsx:98` belongs to 038 (audit `:82`), so 047 leaves it alone.
- **FR-006 (F2, Rule 1).** Bars sent for the chart are the run's own sessions, exactly as loaded,
  with no forward fill, back fill, interpolation, reindexing or resampling: the chart bars equal
  the run frame row for row. (The loader already refuses a bundle with a missing session,
  `scripts/data.py:599-605`, so the risk is a later reindex onto a calendar, not a gap in the bundle.)
- **FR-007 (F3).** A null `max_drawdown` renders as "not computed" (`N/A`) on the card, the same as a
  null Sharpe. A numeric `0.0` renders `0.00%`. The baseline table's nullable fields
  (`reports/web/src/types/api.ts:71-74`) keep rendering `—` and are covered by the same contract.
- **FR-008 (scope).** No text owned by 038 changes: provenance fields, limitations, the Rule 15
  flag, `Rf`, TutorCard copy, `reconciliation_passed`. No existing assertion in
  `tests/test_reports_api.py` is edited or weakened.
- **FR-009 (tests).** Every contract is offline. It uses the existing synthetic-bundle fixtures
  (`tests/unadjusted_fixtures.py`: `session_prices`, `publish_bundle`, `split_series`, used at
  `tests/test_reports_api.py:108-111`). Contracts that need `liquidate=False` or a split call the
  harness directly, because the route fixes `liquidate` to `LIQUIDATE_AT_END`
  (`reports/api/routes/backtest.py:66`). A split fixture must pass `_validate_split_discontinuities`
  (`scripts/data.py:740-755`). No network, no `data/cache/` read, no write to `docs/trials/`.

## 5. Rule 12 — planted defects (each killed, each with a clean control)

A kill counts only when the named contract fails with its own message. Each mutant is applied to an
in-memory or isolated copy and is never committed. Each has a clean control that passes first.

| # | Gate | Planted defect (plausible) | Must fail | Control |
|---|---|---|---|---|
| M1 | FR-001 slippage | Slippage field omitted or zero (today the view counts commission only) | Fixture with `slippage_bps > 0`: slippage total ≠ hand calculation from fill prices × quantities | Fixture with `slippage_bps = 0`: slippage total `0`, commission total matches |
| M1b | FR-001 commission | Commission counted as `2 * commission * len(trade_log)` | `liquidate=False` fixture ending long: commission short by one entry commission | Same fixture with `liquidate=True` passes |
| M2 | FR-001 open position | Slippage summed over closed trades only, missing the open entry | `liquidate=False` fixture ending long, `slippage_bps > 0`: slippage short by the entry's slippage | Same fixture with `liquidate=True` passes |
| M3 | FR-001 split | Exit slippage uses the entry quantity | Fixture with `slippage_bps > 0` and a 4:1 split inside a held trade | Same trade without a split passes |
| M4 | FR-004 basis | Chart bars taken from the adjusted CSV (today's behaviour) | The chart bars do not equal the run frame's `Open/High/Low/Close` row for row (exact), or lack `price_basis == "unadjusted_dollars"`; run on a split fixture and on a dividend-only fixture | Unadjusted bars for the same run pass |
| M4a | FR-004a | SMA computed from candle closes instead of the signal's series | Split fixture: the sent SMA values ≠ SMA of `Research_Close` | SMA from `Research_Close` passes |
| M5 | FR-006 | Chart bars reindexed onto a wider calendar and forward-filled | Chart bars ≠ run frame row for row (an extra session appears) | Bars equal to the run frame pass |
| M6 | FR-007 | Null drawdown renders `0.00%` (today's fallback) | Injected `null` drawdown renders a number | A `0.0` drawdown renders `0.00%`; null baseline fields render `—` |

**Field statements (Rule 12).** M1 to M3 perturb `slippage_bps`, `liquidate` and `Split`, the
inputs the harness reads at `scripts/backtest_harness.py:84`, `:150` and `:120-122`. M4 perturbs
the price basis and checks it exactly, not by tolerance: a dividend-only basis gap is smaller than
a day's open-to-close move, so a tolerance check would pass the adjusted-candle mutant. M6
perturbs `max_drawdown`, the only field the card reads (`BacktestTearsheetView.tsx:143`).

**Known gap.** §8 forbids recomputing slippage from `slippage_bps`. Under today's flat-bps model a
recompute gives the same number, so no mutant can catch it until 046 lands. 046's plan owns that gate.

**The view half.** M1 to M5 test the API and the harness with pytest. That proves the data is right,
not that the view uses it. The view could keep `data={ohlcv}` (`BacktestTearsheetView.tsx:390`) or its
own drag formula (`:93`) and every pytest would still pass. So the wiring of FR-002, FR-004 and
FR-005 has the same TypeScript testing gap as M6.

M6 and the view wiring need a test runner for TypeScript, or the rendered strings must come from
Python. That is D-1. It must not be closed by a test that greps the `.tsx` source for a literal: a
grep passes for any spelling of the same bug, so it is vacuous.

## 6. Success criteria

- **SC-001.** M1 to M6 (with M1b and M4a) are each killed with their own message, and each control passes. The
  evidence is recorded in the PR that closes each unit.
- **SC-002.** `python -m pytest tests` shows no new failure, error or strict XPASS against the
  baseline on `main`. The web lint and build pass in CI.
- **SC-003.** A reader of the tearsheet can't see a commission-only drag, a fill on an adjusted
  candle, or `0.00%` for a drawdown that was not computed. This is checked by M1 to M6, not by eye.
- **SC-004.** Ledger unchanged: `docs/trials/trials.jsonl` line count and SHA-256, and
  `trials.head.json` SHA-256, identical before and after every unit.

## 7. Decisions (open; each needs Camden before the plan fixes it)

- **D-1 — how F3 (and any view-only logic) is tested.** Options: (a) add a minimal web test runner
  as a dev dependency, with a Rule 6 line and a CI step (a `.github/` edit, so human lane);
  (b) extract the formatting into a pure TypeScript function and type-check a table of cases at
  build time (red at `npm run build`, no new dependency; weaker, because `tsc` proves types, not
  values); (c) move the display string to the API so pytest covers it (couples presentation to
  the API). Recommendation: (a). Under any option, the data half of F1 and F2 is pytest-testable,
  because FR-001 and FR-004 put that logic in Python. The view wiring is not (§5, "The view half").
- **D-2 — where the chart's unadjusted bars come from.** Options: (a) the tearsheet response
  carries the run's own bars; (b) a new read-only route serves the bundle's bars by ticker;
  (c) the chart stops drawing candles for runs and draws the equity curve only. Recommendation:
  (a). The bars are then the exact frame the run used. (b) can drift from the run, and (c)
  removes a view. The same decision covers FR-004a: send the signal's SMA values with the bars, or
  draw no SMA on the run chart.
- **D-3 — `MarketDataView`.** Does it keep adjusted candles with no fill markers (FR-005), or move
  to unadjusted bars as well? Recommendation: keep adjusted candles and drop the markers. That view
  is about market statistics, which are conventionally computed on adjusted returns. Changing its
  basis would change `/api/data/stats`, which is out of scope.

- **T005 approved (Camden, 2026-10-09 (gate packet `claude/gate-packet-20261009.md`)).** Adding `npm test` to CI's `web` job is approved. The `.github/` edit
  ships as its own governance PR for Camden's merge.

### Decided 2026-10-09 (Claude under Camden's 2026-10-09 delegation; Codex proposal `DECISIONS-FOR-REVIEW.md` cross-checked; ratified by Camden's merge of this PR)
- **D-1 = (a).** A minimal web test runner as a dev dependency (Vitest plus Testing Library),
  rendering real components against synthetic API responses. It carries a Rule 6 line. CI wiring is
  T005's governance PR.
- **D-2 = (a).** The tearsheet response carries the run's own unadjusted bars and the causal signal
  SMA values (FR-004a: send the SMA). There is no adjusted-cache substitution and no SMA reconstructed
  over nominal candles.
- **D-3.** MarketDataView keeps adjusted candles and drops the run fill markers. `/api/data/stats` is
  unchanged.

## 8. Sequencing and dependencies

- Independent of 035, 041, 043 and 044: no edit to `scripts/data.py`.
- File overlap with 038. Both specs edit `BacktestTearsheetView.tsx`, `reports/api/routes/backtest.py`,
  `reports/api/schemas.py` and `reports/web/src/types/api.ts`. The two must not run at the same
  time (`AGENTS.md`, "Module ownership"). Recommended order: 047 first. It is smaller, it fixes
  values, and 038 then stamps provenance on figures that are already correct. The figures 047 adds
  carry the tearsheet's existing source fields (FR-002), so 047 adds no unsourced figure in the
  meantime (Rule 11).
- 046 (Rule 13 cost model) will replace flat `slippage_bps`. FR-001's fields must be the
  slippage the harness charged, whatever model produced it. They must not be recomputed from
  `slippage_bps`, so 046 does not reopen them.
- Proposed units, ≤300 changed lines each, are for the plan to confirm: U1 friction (FR-001 to
  FR-003, M1 to M3); U2 chart basis (FR-004 to FR-006, M4, M4a and M5); U3 null rendering (FR-007, M6,
  after D-1).

## 9. Out of scope

- Every disclosure item in the 038 audit (see §1).
- The equity-curve drawdown series. It is computed without the `capital_base` anchor
  (`reports/api/routes/backtest.py:145-146`), while `metrics.max_drawdown` anchors on it
  (`scripts/metrics.py:287-289`). The two can disagree on the first bar. This was noticed while
  drafting and is not one of Q12's three defects. Raise it for 038 or a later spec.
- `holding_bars=1` sent as data (`reports/api/routes/backtest.py:170`; audit `:73`): 038.
- The cost model itself (046) and the unadjusted bundle (035, 044).
