# Tasks — 001 Data Ingestion

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Structure

- [x] **T001** Split `download_market_data` into `_cache_key`,
  `_normalize_dates`, `_tidy`, `_write_atomic`, leaving orchestration thin.
  These are where timestamp bugs live; they cannot be tested through the
  network path alone. (plan §Design)
- [x] **T002** Add the `downloader` parameter, defaulting to `yf.download`,
  so the download and error paths are reachable in a test. (research R4)
- [x] **T003** Sort and de-duplicate tickers in the cache key. (research R5)
- [x] **T004** Route the cache-read path through `_tidy` so a cache hit and a
  cache miss are indistinguishable, and filter a superset cache to the
  requested tickers. (research R6, SC-001)
- [x] **T005** State the timestamp convention in the module docstring and
  apply it in exactly one function. (research R3)

## Phase 2 — Calendar (FR-009)

- [x] **T006** `_easter(year)` — anonymous Gregorian algorithm, for Good
  Friday.
- [x] **T007** `_nth_weekday` / `_last_weekday` helpers.
- [x] **T008** `is_market_holiday(day)` — ten NYSE holidays with the
  Sat→Fri / Sun→Mon observation rule, Juneteenth gated to 2022+, plus the
  known ad-hoc closure set. (research R2)
- [x] **T009** `trading_days(start, end)`.
- [x] **T010** `find_missing_bars(frame)` — per-ticker bounds, read-only, no
  fill. (research R1)

## Phase 3 — Tests (Rule 5, FR-011)

- [x] **T011** `tests/test_data.py` scaffold: temp cache dir per test, fake
  downloader builder, no network.
- [x] **T012** [P] Calendar tests — real NYSE dates across years, both
  observation directions, Juneteenth pre/post-2022, Good Friday present,
  Columbus/Veterans Day *not* holidays, 252-session year count.
  *(Rule 5: off-by-one)*
- [x] **T013** [P] `_normalize_dates` / CSV round-trip — no ±1 day drift,
  identical dtype from both paths. *(Rule 5: off-by-one)*
- [x] **T014** [P] Sort and boundary — first/last row survive, single-row and
  single-ticker frames, `RangeIndex`. *(Rule 5: boundary)*
- [x] **T015** [P] `find_missing_bars` — weekends/holidays report empty; a
  removed mid-week session reports exactly that day; ragged tickers report
  per-ticker; gaps at the very first/last session are outside the window;
  input frame unmodified. *(Rule 5: gap + boundary)*
- [x] **T016** [P] Cache behavior — hit makes zero network calls, subset is a
  miss, superset is filtered, `force_refresh` bypasses, ticker order does not
  matter. (FR-003, FR-007, SC-002)
- [x] **T017** [P] Error paths — empty tickers, empty response, and a dropped
  symbol naming that symbol. (FR-005, FR-006)
- [x] **T018** [P] Atomic write — an interrupted write leaves the previous
  complete file readable. (FR-004, SC-003)

## Phase 4 — Docs

- [x] **T019** README: gap inspection and the timestamp convention.
- [x] **T020** `docs/PROJECT_CONTEXT.md`: spec 001 state.
- [x] **T021** Run `python -m unittest discover -s tests`.

---

## Out of scope

`scripts/signals.py`, `scripts/backtest_harness.py`, `scripts/plotting.py`
(per the issue). No new dependency. No auto-fill, interpolate, or reject
(research R1).
