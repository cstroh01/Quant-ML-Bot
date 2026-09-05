# Contract — `scripts/data.py`

The public surface. A change to anything on this page is a spec change, not a
refactor.

**Owns**: download, cache, split/dividend adjustment, and calendar inspection
of daily OHLCV.
**Must not know about**: signals, positions, P&L (CLAUDE.md module table,
Rule 8).

---

## `download_market_data(tickers, period="2y", force_refresh=False, downloader=yf.download)`

Returns the tidy OHLCV frame described in `data-model.md`.

**Guarantees**

| # | Guarantee | Req |
|---|---|---|
| 1 | Daily bars, split/dividend-adjusted | FR-001 |
| 2 | Result cached as CSV under `data/cache/`, keyed by the sorted ticker set and period | FR-002, R5 |
| 3 | A cache file is used only if it holds every requested ticker; otherwise the full set is re-downloaded | FR-003 |
| 4 | Cache writes are atomic — an interrupted write cannot leave a corrupt file that a later run reads as valid | FR-004 |
| 5 | A cache hit performs **zero** network calls | SC-002 |
| 6 | Cache-hit and cache-miss returns are indistinguishable in shape, dtype, and order | FR-008, R6 |
| 7 | Tidy, `Date` a real datetime, sorted by `Ticker` then `Date`, `RangeIndex` | FR-008 |
| 8 | Exactly the requested tickers — no extras from a superset cache | SC-001 |
| 9 | The caller's `tickers` list is not mutated | — |

**Raises**

| Condition | Exception | Req |
|---|---|---|
| `tickers` empty | `ValueError` | — |
| Response empty | `RuntimeError` | FR-006 |
| A requested symbol missing from the response | `RuntimeError` **naming that symbol** | FR-005 |

`force_refresh=True` bypasses the cache unconditionally, valid or not
(FR-007).

`downloader` exists so the module is testable without network (research R4).
It defaults to `yf.download` and is called with the same keyword arguments;
production callers never pass it.

---

## `find_missing_bars(frame)`  *(new — FR-009)*

Returns a `Ticker`/`Date` frame of NYSE sessions that have no bar, per the
Gap Report entity in `data-model.md`.

**Guarantees**

| # | Guarantee |
|---|---|
| 1 | Read-only — `frame` is returned to the caller unmodified; nothing is filled, flagged, or rejected |
| 2 | Weekends and NYSE holidays never appear in the report |
| 3 | Bounded by **each ticker's own** first and last bar, never the frame-wide range |
| 4 | Empty input → empty report, not an error |
| 5 | Output sorted by `Ticker`, then `Date`, with a `RangeIndex` |

**Explicitly not provided**: fill, interpolate, reject, or a `strict` mode.
Auto-fill would need to be checked against Rule 1 before it could exist at all
(research R1); a backward fill writes a value into row `t` that was not
knowable at `t`.

---

## `is_market_holiday(day) -> bool`

True if `day` is an NYSE holiday. Weekends are **not** holidays — a Saturday
returns `False`. Callers wanting "was the market open" want `trading_days`.

## `trading_days(start, end) -> list[date]`

NYSE sessions in `[start, end]`, inclusive both ends, ascending. `start > end`
returns `[]`.

## `cache_path(name) -> Path`

Unchanged. A path inside `data/cache/`, creating the directory if needed.

---

## Timestamp convention

`Date` is **timezone-naive, midnight-normalized**, and denotes a trading
session rather than an instant. Applied identically to the download path and
the cache-read path — guarantee 6 above depends on that being one function and
not two (research R3).

This is the project-wide rule, not a module-local choice: CLAUDE.md,
*Conventions → Timestamps*, splits instants (always tz-aware) from session
labels (always tz-naive midnight), and requires any session label crossing
into instant-space to be localized to `America/New_York` explicitly at that
boundary. A consumer of this frame that needs an instant does that conversion
itself; `data.py` does not do it on the consumer's behalf.
