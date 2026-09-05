# Feature Specification: Data Ingestion

**Feature Branch**: `001-data-ingestion`

**Created**: 2026-09-05

**Status**: Draft

**Input**: Formalize the existing `scripts/data.py` module (download + cache
daily OHLCV) as the Phase 0 data-layer spec, and close the gaps between what
it does today and what Rules 1/5/6 of the constitution require of it.

**Owns / must not know about** (per CLAUDE.md's module table): this spec owns
download, cache, and split/dividend adjustment of OHLCV data. It must not know
about signals, positions, or P&L — those stay downstream.

---

## Background — what already exists

`scripts/data.py` (84 lines, working) already does most of this:

| Behavior | Present today? |
|---|---|
| Download daily OHLCV via yfinance, `auto_adjust=True` | Yes |
| Cache to `data/cache/<tickers>_<period>.csv` | Yes |
| Treat a cache hit as valid only if every requested ticker is present | Yes |
| Atomic write (temp file + rename) so an interrupted run can't corrupt the cache | Yes |
| Named error when yfinance silently drops a ticker | Yes |
| Named error when the whole download comes back empty | Yes |
| `force_refresh` to bypass the cache | Yes |
| Tests | **No — zero tests on this module today** |
| Gap detection (missing bars, halts) | No — not handled |

This spec formalizes the "yes" rows as requirements (so a future change can't
silently regress them) and specifies the two gaps.

---

## User Scenarios & Testing *(mandatory)*

### Scenario 1 — Cold-cache download (Priority: P1)

A downstream module (signals, backtest harness) asks for OHLCV bars for a list
of tickers over a period, and no cache file exists yet.

**Why this priority**: every other module in the pipeline depends on this
path working correctly; it's the only way data enters the system.

**Independent Test**: call `download_market_data(["AAPL", "MSFT"], "1y")`
against an empty `data/cache/`, with network available. Passes if it returns
one row per ticker per trading day, every OHLCV field populated, and a cache
file now exists.

**Acceptance Scenarios**:

1. **Given** an empty cache and valid tickers, **When**
   `download_market_data` is called, **Then** it returns a tidy DataFrame
   (`Date`, `Ticker`, `Open`, `High`, `Low`, `Close`, `Volume`) sorted by
   `Ticker` then `Date`, and writes a matching cache file.
2. **Given** a ticker yfinance silently drops, **When** the download runs,
   **Then** the error names the specific bad ticker rather than raising a
   bare `KeyError`.
3. **Given** all requested tickers are invalid, **When** the download runs,
   **Then** it raises rather than returning an empty/partial frame silently.

---

### Scenario 2 — Warm-cache read (Priority: P1)

The same tickers/period are requested again.

**Why this priority**: this is what makes iteration during model development
affordable — without it, every re-run re-downloads and re-hits rate limits.

**Independent Test**: call `download_market_data` twice with the same
arguments; the second call must not touch the network and must return
byte-identical data to what's on disk.

**Acceptance Scenarios**:

1. **Given** a complete, valid cache file for the requested tickers, **When**
   `download_market_data` is called again, **Then** it reads from disk and
   makes no network call.
2. **Given** a cache file that is missing one of the currently-requested
   tickers (e.g. a prior call cached `["AAPL"]`, this call asks for
   `["AAPL", "MSFT"]`), **When** the download runs, **Then** it is treated as
   a cache miss and re-downloads the full requested set.
3. **Given** `force_refresh=True`, **When** the download runs, **Then** it
   bypasses any existing cache regardless of validity.

---

### Scenario 3 — Interrupted write (Priority: P2)

A download is interrupted (process killed, network drop) partway through
writing the cache file.

**Why this priority**: a half-written cache silently read as valid on the
next run is a worse failure than no cache at all — it produces wrong data
with no error.

**Independent Test**: simulate an interruption between the temp-file write
and the rename; the previous good cache file (if any) must still be intact
and readable afterward.

**Acceptance Scenarios**:

1. **Given** a write is interrupted before the atomic rename completes,
   **When** the next call reads the cache, **Then** it reads either the
   previous complete file or nothing — never a truncated file.

---

### Edge Cases

- A requested ticker has no trading history in the window (e.g. IPO'd after
  the period start) — what does the returned frame look like for that ticker?
- A ticker is delisted mid-period.
- A requested period spans a market holiday or weekend (expected, not a
  gap) vs. a genuine data gap (halt, outage, provider error) — the module
  must be able to tell these apart later even if it doesn't act on the
  distinction yet (see FR-009).
- Network failure on the *first* call ever made for a given ticker set (no
  prior good cache to fall back to).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST download daily OHLCV data for a given list of
  tickers over a specified period, split/dividend-adjusted
  (`auto_adjust=True`).
- **FR-002**: System MUST cache downloaded data as CSV under `data/cache/`,
  keyed by the requested ticker set and period.
- **FR-003**: System MUST treat a cache file as usable only if it contains
  every currently-requested ticker; otherwise treat it as a miss and
  re-download the full set.
- **FR-004**: System MUST write cache files atomically (write to a temp path,
  then rename) so an interrupted write cannot leave a corrupted file that a
  later run reads as valid.
- **FR-005**: System MUST raise a ticker-specific error when yfinance
  silently omits a requested symbol from its response.
- **FR-006**: System MUST raise an error when the download returns no data
  at all.
- **FR-007**: System MUST support a `force_refresh` flag that bypasses the
  cache unconditionally.
- **FR-008**: The returned DataFrame MUST be tidy — one row per ticker per
  bar, `Date` parsed as a real datetime, sorted by `Ticker` then `Date` — so
  downstream modules never re-implement this parsing themselves.
- **FR-009** *(new — not yet met)*: System MUST make trading-calendar gaps
  inspectable — i.e. a caller can tell "no US market holiday explains this
  missing bar" apart from an ordinary non-trading day. [NEEDS CLARIFICATION:
  does Phase 0 need this to *act* on gaps (flag/reject), or only make them
  inspectable for now? Default assumed below is "inspectable only" — see
  Assumptions.]
- **FR-010** *(Rule 1 — point-in-time correctness)*: No value in any row may
  be computed from a later-timestamped row. Trivially satisfied today because
  nothing is cross-row-computed yet; this requirement exists so that any
  future addition to this module (e.g. a rolling adjustment, a fill-forward
  for gaps) is checked against it before merging.
- **FR-011** *(Rule 5 — tests on anything touching time)*: `parse_dates` and
  the `Ticker`/`Date` sort ship with tests covering: the off-by-one case, the
  boundary case (first/last row), and the gap case (missing bars).
- **FR-012** *(Rule 6 — dependency justification)*: `yfinance` is the sole
  feature dependency this module adds. Justification: free daily OHLCV with
  built-in split/dividend adjustment; no stdlib or already-present dependency
  provides this.

### Key Entities

- **OHLCV Bar**: one ticker, one calendar day — `Open`, `High`, `Low`,
  `Close`, `Volume`, already split/dividend-adjusted.
- **Cache File**: a CSV under `data/cache/`, named from the sorted ticker
  list and requested period; valid only if it is a superset of the currently
  requested tickers.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A cold-cache request for N valid tickers over the default `2y`
  period returns exactly N tickers with zero null OHLCV fields.
- **SC-002**: A warm-cache request for the same tickers/period makes zero
  network calls and returns data identical to the cache file on disk.
- **SC-003**: An interrupted write, simulated in a test, never leaves the
  cache in a state where a subsequent read returns a truncated/corrupt file.
- **SC-004**: 100% of this module's timestamp-handling code paths have a
  regression test covering the three Rule 5 cases (off-by-one, boundary,
  gap) — currently 0%.

---

## Assumptions

- Yahoo Finance (via `yfinance`) remains the sole data source through Phase
  0-1; no fallback provider is in scope for this spec.
- Daily bars only. Intraday data is out of scope.
- US equities only, matching the project's Phase 0-4 scope (equities first,
  Alpaca as the paper/live broker candidate).
- FR-009 (gap inspectability) is satisfied by making gaps *detectable and
  reportable*, not by having the module reject or auto-fill them — auto-fill
  in particular would need to be checked against Rule 1 before it could ever
  be added, since a naive fill-forward reads across time.
- This spec formalizes `scripts/data.py` as it exists rather than requiring a
  rewrite. Rule 6 does not apply to `yfinance` itself (already a dependency,
  not new) — it applies going forward to anything added to satisfy FR-009.
