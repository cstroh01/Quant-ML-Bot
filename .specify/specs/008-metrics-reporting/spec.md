# Feature Specification: Metrics Reporting Layer

**Feature Branch**: `008-metrics-reporting`

**Created**: 2026-09-05

**Status**: Draft

**Input**: The backtest harness emits a trade log and nothing else. There is
no equity curve, no Sharpe ratio, and no drawdown anywhere downstream of a
backtest — `return_stats.py` computes those, but on raw price series, not on
strategy results. Phase 3 needs them: a five-ticker comparison table that
ranks strategies by absolute dollar P&L on a one-share position is ranking
share prices, not alpha, and "does this make money" cannot be answered
without a risk-adjusted number.

**Owns / must not know about** (per CLAUDE.md's module table): `metrics.py`
is a **reporting layer below execution**. It reads the harness's *output* — a
trade log — plus the price frame that produced it. It imports neither
`signals.py` nor `backtest_harness.py`, and the harness is not modified. It
knows nothing about how a signal was produced or how a fill was decided; it
only re-expresses a completed trade log as a per-bar series.

---

## Background

`run_backtest` returns `TRADE_LOG_COLUMNS + ["Cumulative P&L"]` — one row per
completed round trip, no per-bar detail. `summarize_trades` reduces that to
trade count, total P&L, and win rate, plus the two cost parameters echoed
back.

That is enough to say whether a strategy made money. It is not enough to say
whether it made money *well*:

- **Cross-ticker comparison is meaningless in dollars.** A one-share position
  in a $600 name and a $100 name are not comparable exposures. Phase 3's
  whole point is running one pipeline over five names.
- **No risk adjustment.** Two strategies with identical P&L and wildly
  different volatility are indistinguishable today.
- **No drawdown.** The single number most likely to decide whether a strategy
  is fundable is not computed anywhere for a strategy.

Rule 4 also needs a common denominator: comparing a strategy against buy-and-
hold on the same instrument requires both to be expressed on the same capital
base.

### What the harness guarantees, and what that simplifies

Two properties of `backtest_harness.py` shape this spec:

1. **There is never an unclosed trade.** `run_backtest:87-98` unconditionally
   marks any still-open position to the final `Close`. Every trade log row is
   a completed round trip with both prices recorded. No open-position handling
   is needed.
2. **Commission is not recoverable from the log.** `Entry Price` and
   `Exit Price` are the slipped fill prices; commission is subtracted from
   `P&L` separately (`:34`, `:75`). A net P&L cannot be decomposed back into
   the costs that produced it — the same argument `summarize_trades:114-121`
   makes. Commission must therefore be passed in, not inferred.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A per-bar equity curve from a trade log (Priority: P1)

As the project owner, I need a completed backtest re-expressed as a per-bar
equity series, so every risk metric below has something to be computed on.

**Why this priority**: Everything else in this spec is a function of the
equity curve.

**Independent Test**: Build a price frame with hand-chosen signals, run the
real `run_backtest` on it, and assert the per-bar P&L series sums to exactly
the trade log's total P&L.

**Acceptance Scenarios**:

1. **Given** a trade entered at bar `e` and exited at bar `x` with recorded
   prices `E` and `X` and commission `c`, **When** the equity curve is built,
   **Then** bar `e` carries `Close[e] - E - c`, bars strictly between carry
   `Close[i] - Close[i-1]`, bar `x` carries `X - Close[x-1] - c`, and every
   unheld bar carries `0`.
2. **Given** any trade log, **When** the per-bar P&L column is summed,
   **Then** it equals the trade log's `P&L` sum to within floating-point
   tolerance. (The four-part attribution telescopes to `X - E - 2c`, which is
   the harness's own P&L expression term for term.)
3. **Given** a price frame and a trade log, **When** the curve is built,
   **Then** it has exactly one row per price bar.

---

### User Story 2 - Risk metrics on that curve (Priority: P1)

As the project owner, I need Sharpe ratio and maximum drawdown computed on
the strategy's equity, using the same conventions the repository already uses
for price series, so two numbers in this repository never mean two different
things.

**Why this priority**: This is what makes the Phase 3 comparison table
readable.

**Independent Test**: Compute Sharpe on a costed and an uncosted run of the
same signals and assert they differ.

**Acceptance Scenarios**:

1. **Given** an equity curve, **When** Sharpe is computed, **Then** it uses
   `TRADING_DAYS_PER_YEAR` and `RISK_FREE_RATE_ANNUAL` from the shared
   constants module and the same annualization arithmetic as
   `return_stats.annualize` — mean × 252, std × √252, excess over the
   risk-free rate.
2. **Given** an equity curve, **When** maximum drawdown is computed, **Then**
   it uses `equity / equity.cummax() - 1` and returns the trough and the
   most recent peak strictly before it, matching `return_stats.main:57-68`.
3. **Given** a drawdown that begins on the very first bar, **When** maximum
   drawdown is computed, **Then** it is captured — the curve is anchored at
   the capital base on bar 0, the same point
   `return_stats.cumulative_price_index` already makes.
4. **Given** the same signals run with and without costs, **When** Sharpe is
   computed for both, **Then** the two values differ — proving costs reach
   the metric (Rule 3).

---

### User Story 3 - Zero trades is a first-class outcome (Priority: P1)

As the project owner, I need a strategy that took no trades to produce a
printable summary rather than an exception or a misleading zero.

**Why this priority**: Phase 3's cost-aware entry rule is expected to gate
out nearly every trade. If the empty path is an afterthought, the headline
result of the phase is an error message.

**Independent Test**: Call every public function with an empty trade log.

**Acceptance Scenarios**:

1. **Given** an empty trade log, **When** the equity curve is built, **Then**
   it is flat at the capital base for every bar, with zero P&L throughout.
2. **Given** a flat equity curve, **When** Sharpe is computed, **Then** it is
   `nan` — not `0.0`, and not `inf`. Zero variance means the ratio is
   undefined, and `0.0` would read as "a real, mediocre result".
3. **Given** a flat equity curve, **When** maximum drawdown is computed,
   **Then** it is `0.0` — a genuine zero, since no decline occurred.
4. **Given** an empty trade log, **When** `performance_summary` is called,
   **Then** it returns a dict with every key present, so a formatter can
   print it without branching.

---

### Edge Cases

- **`e == x`, a same-bar round trip.** Reachable: `Buy_Next_Open` firing on
  the final row enters at `run_backtest:83`, and the end-of-data block at
  `:87-98` exits on that same row. That bar carries `X - E - 2c`.
- **Entry on bar 0.** The bar-`e` formula needs no `Close[e-1]`, so it is
  well-defined. The exit-bar formula does reference `Close[x-1]`, and
  `x >= 1` whenever `x > e >= 0`, so it is safe.
- **A single-bar price frame.** Fewer than two bars means no return
  observations; Sharpe is `nan`.
- **Equity driven to zero or below.** Log returns are undefined there. The
  metric returns `nan` rather than `-inf`, and the condition is reported.
- **Duplicate or unsorted dates in `prices`.** `.loc` with duplicate labels
  silently returns extra rows, producing a longer array than the trade log
  and a wrong curve with no exception. This must raise.
  `download_market_data` returns a long frame sorted by Ticker *then* Date,
  so a multi-ticker frame has duplicate dates — this is not hypothetical.
- **A trade date absent from `prices`.** Must raise, not silently drop.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** *(Rule 8)*: `scripts/metrics.py` MUST NOT import `signals.py`,
  `backtest_harness.py`, `data.py`, or `plotting.py`. It reads a price frame
  and a trade log as plain data.
- **FR-002**: `scripts/backtest_harness.py` MUST NOT be modified by this
  spec.
- **FR-003**: `equity_curve` MUST return one row per price bar, carrying at
  minimum `Date`, `Position`, `Bar P&L`, and `Equity`.
- **FR-004**: The per-bar `Bar P&L` column MUST sum to the trade log's `P&L`
  sum to within `1e-9`.
- **FR-005** *(Rule 3)*: `commission_per_trade` and `slippage_bps` MUST be
  required keyword arguments on `equity_curve` and `performance_summary`, and
  MUST be echoed in `performance_summary`'s output, following the precedent
  `summarize_trades` sets.
- **FR-006**: The capital base MUST be an explicit value, defaulting to the
  first bar's `Close`, and MUST be reported in `performance_summary`'s
  output. A one-share P&L stream has no denominator of its own, so any
  percentage figure depends on a stated base.
- **FR-007**: `equity_curve` MUST validate that `prices` has a unique,
  monotonically increasing `Date` column and a 0-based `RangeIndex`, and MUST
  raise `ValueError` otherwise.
- **FR-008**: Every trade's `Entry Date` and `Exit Date` MUST be present in
  `prices["Date"]`; a missing date MUST raise `ValueError`.
- **FR-009**: Sharpe MUST return `nan` for a constant equity curve, a curve
  with fewer than two return observations, and a curve reaching zero or
  below. It MUST never return `inf` or `0.0` for these cases.
- **FR-010**: `TRADING_DAYS_PER_YEAR` and `RISK_FREE_RATE_ANNUAL` MUST live
  in one place, `scripts/constants.py`, and `return_stats.py` MUST import
  them rather than define them. Two Sharpe ratios in one repository computed
  against two different risk-free rates is precisely the silent inconsistency
  the constitution's preamble describes.
- **FR-011**: `return_stats.py`'s behavior MUST be unchanged by the constant
  extraction — same values, same arithmetic.
- **FR-012** *(Rule 6)*: No new dependency. numpy and pandas only.
- **FR-013** *(Rule 5, tests)*: Tests cover the telescoping invariant, the
  off-by-one (one-bar hold), the boundaries (entry on bar 0, exit on the
  final bar, `e == x`), the gap case (missing session), the empty trade log,
  and the validation guards.

### Key Entities

- **Bar P&L**: the change in the position's value attributable to one bar,
  including any commission charged on that bar.
- **Equity**: `capital_base + cumsum(Bar P&L)`.
- **Capital base**: the stated denominator. Default: the first bar's `Close`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On `sawtooth_prices(200)` with real costs, `Bar P&L` sums to
  the trade log's `P&L` sum within `1e-9`.
- **SC-002**: A one-bar-hold trade puts non-zero P&L on exactly two bars.
- **SC-003**: Sharpe computed with costs differs from Sharpe computed without
  them on the same signals.
- **SC-004**: An empty trade log yields a flat curve, `nan` Sharpe, `0.0`
  drawdown, and a complete `performance_summary` dict.
- **SC-005**: A drawdown beginning on bar 0 is captured.
- **SC-006**: Duplicate dates, non-monotonic dates, a non-`RangeIndex`, and a
  trade date absent from `prices` each raise `ValueError`.
- **SC-007**: `return_stats.py` produces identical values after the constant
  extraction.

---

## Assumptions

- **Capital base convention (b), not (a).** Two honest denominators exist:
  return on invested notional (`pnl_i / Close[i-1]`, zero on flat bars), and
  a fixed capital base (`C0 + cumsum(pnl)`). This spec uses the fixed base.
  It is the only one that yields a well-defined drawdown, and Rule 4 needs a
  common denominator to compare a strategy against buy-and-hold.
- **`Position` means shares held at that bar's close.** A bar on which the
  position is exited at the open therefore shows `Position = 0` while still
  carrying P&L for the gap from the previous close to the exit fill. A
  same-bar round trip shows `Position = 0` on every bar.
- **Annualization is per *bar*, not per calendar day.** 252 is the
  bars-per-year convention inherited from `return_stats.py`. A frame with
  missing sessions is annualized as though its bars were trading days.
- This spec adds no position sizing. The one-share position is a harness
  property and changing it is an execution-layer change under Rule 8.
