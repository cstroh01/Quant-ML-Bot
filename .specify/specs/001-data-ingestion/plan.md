# Implementation Plan — 001 Data Ingestion

**Spec**: `.specify/specs/001-data-ingestion/spec.md`
**Research**: `research.md` (decisions R1–R6)
**Contract**: `contracts/data-module.md`

---

## Scope

One module and one test file:

- `scripts/data.py` — formalized, plus gap inspection (FR-009)
- `tests/test_data.py` — new; the module has zero tests today (FR-011)

Explicitly **not** touched, per the issue: `scripts/signals.py`,
`scripts/backtest_harness.py`, `scripts/plotting.py`. No call site of
`download_market_data` changes, because every signature change is a
keyword argument with a default.

**No new dependency.** See research R2.

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time | No cross-row computation is added. The gap report *reads* the frame and returns a separate object; it never writes a value into a row. FR-009 is deliberately implemented without any fill (R1). |
| 5 — Tests on time code | The whole point of the PR. `_normalize_dates`, the `Ticker`/`Date` sort, and the calendar all ship with off-by-one, boundary, and gap tests. |
| 6 — Dependencies | Nothing added (R2). |
| 8 — Layer separation | The module gains no knowledge of signals, positions, or P&L. The gap report is data-about-data; deciding what to *do* about a gap stays with the caller (R1). |
| 10 — Version control | Flagged in the PR body: the issue explicitly asks for a pushed branch and a PR, which is the repo owner overriding his own rule for this lane. Noted, not assumed. |

---

## Design

### Structure

`download_market_data` is currently one function doing five things: key the
cache, read it, validate it, download, tidy, write. Testing any one of them
without network means testing all five. The plan splits out the pure parts and
leaves the orchestration thin:

```
cache_path(name)                     unchanged — public
_cache_key(tickers, period)          sorted+deduped filename            (R5)
_normalize_dates(frame)              the one timestamp convention       (R3)
_tidy(frame, tickers)                filter → normalize → sort → reindex (R6)
_write_atomic(frame, path)           temp + rename                    (FR-004)
download_market_data(...)            orchestration + error naming
```

Everything with a leading underscore is internal, but tested directly — these
are where the timestamp bugs live, and testing them only through the network
path is how a module ends up with zero tests.

### The timestamp convention, in one place

`_normalize_dates` is called on **both** the fresh-download frame and the
cache-read frame. That single fact is what Scenario 2 depends on: a cache hit
and a cache miss must be substitutable. Two normalization paths that agree
today drift tomorrow (R3).

### Gap inspection (FR-009)

Public, read-only, additive:

```
is_market_holiday(day)            -> bool
trading_days(start, end)          -> list[date]
find_missing_bars(frame)          -> DataFrame[Ticker, Date]
```

`find_missing_bars` reports, per ticker, every NYSE session between that
ticker's own first and last bar for which no row exists. Two properties matter
and are both tested:

- It is bounded by **each ticker's own** first/last bar, not the frame's.
  Otherwise every IPO and every delisting in a multi-ticker frame reports as
  hundreds of gaps (spec Edge Cases).
- Weekends and holidays are excluded by construction, so a report row means
  "no US market holiday explains this" — which is FR-009's literal wording.

### Not doing

- No fill, no interpolate, no reject (R1).
- No `strict` flag. There is nothing to be strict about if nothing acts.
- No intraday, no non-US, no second provider (spec Assumptions).

---

## Test plan (Rule 5's three cases)

| Rule 5 case | Test |
|---|---|
| **Off-by-one** | A CSV round-trip returns the identical `Date` values — no ±1 day drift from the write/parse cycle. The calendar's observed-holiday shifts (Sat→Fri, Sun→Mon) land on the exact expected date. `find_missing_bars` reports the missing day itself, not its neighbour. |
| **Boundary** | First and last row survive the sort and the round-trip. A gap at the very first / very last session of a ticker's range is outside the reported window by construction, and that is asserted rather than assumed. Single-row and single-ticker frames. |
| **Gap** | Weekend and holiday absences produce an **empty** report; a removed mid-week trading day produces exactly that day. Ragged tickers (different start/end dates) report per-ticker, not frame-wide. |

Plus, outside Rule 5 but required by the spec: cache hit makes zero network
calls (Scenario 2, asserted with a downloader that fails the test if called),
superset/subset cache validity (FR-003), `force_refresh` (FR-007), named
ticker error (FR-005), empty response (FR-006), atomic write leaves the prior
file intact when the write is interrupted (FR-004 / SC-003).

All tests use an injected downloader (R4) and a temp cache directory. Zero
network, zero new test dependencies.

---

## Risks

| Risk | Mitigation |
|---|---|
| Hand-rolled calendar wrong on some year | Tests pin real NYSE dates across several years, including both observation directions and the Juneteenth 2022 start. Errs toward false positives (R2). |
| Timestamp convention disagrees with CLAUDE.md's blanket "tz-aware throughout" | Implemented as the safe reading, isolated to one function, and flagged explicitly in the PR for Camden to rule on (R3). |
| Ad-hoc future closures reported as gaps | Accepted; false positive is the safe direction (R2). |
