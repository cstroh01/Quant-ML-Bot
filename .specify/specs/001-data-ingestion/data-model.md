# Data Model — 001 Data Ingestion

Two entities from the spec, plus the gap report FR-009 introduces.

---

## OHLCV Bar frame (the return value of `download_market_data`)

Tidy: one row per ticker per trading session.

| Column | Type | Guarantee |
|---|---|---|
| `Date` | `datetime64[ns]`, tz-naive, midnight-normalized | Labels a trading session, not an instant (research R3). Identical on the download and cache-read paths. |
| `Ticker` | `object` (str) | Exactly the requested symbols, no more (SC-001, research R6). |
| `Open` `High` `Low` `Close` | `float64` | Split/dividend-adjusted (`auto_adjust=True`, FR-001). |
| `Volume` | numeric | Split-adjusted. |

**Ordering.** Sorted by `Ticker`, then `Date`, ascending. Index is a clean
`RangeIndex` (FR-008).

**Point-in-time (Rule 1 / FR-010).** No cell is computed from any other row.
Each row is the provider's report of one session, carried through unmodified
apart from column layout. This is what makes FR-010 trivially true today, and
the property any future change to this module has to re-establish.

---

## Cache File

A CSV under `data/cache/`, gitignored regenerable output.

**Name**: `<sorted-deduped-tickers-joined-by-dash>_<period>.csv`

Sorted so that `["MSFT", "AAPL"]` and `["AAPL", "MSFT"]` are one cache entry
rather than two (research R5).

**Validity**: usable only if the file contains a row for **every** currently
requested ticker (FR-003). A superset is valid and is filtered down on read;
a subset is a miss and triggers a full re-download.

**Write**: to `<name>.csv.tmp`, then `Path.replace` into position. Rename is
atomic on a single filesystem, so an interrupted write leaves the previous
complete file untouched rather than a truncated one that reads as valid
(FR-004, SC-003).

---

## Gap Report (new, FR-009)

The return value of `find_missing_bars`.

| Column | Type | Meaning |
|---|---|---|
| `Ticker` | str | Which symbol the missing session belongs to |
| `Date` | `datetime64[ns]`, tz-naive, midnight | An NYSE session with no row in the frame |

Empty frame (with these columns) means no unexplained gaps.

**What a row means.** "The NYSE was open on this date, this date falls inside
this ticker's own observed history, and there is no bar." Weekends and
holidays are excluded by construction, so a row is never explained by the
calendar — that is the literal content of FR-009.

**What a row does *not* mean.** It is not an error and not an instruction. The
frame is returned unchanged whether or not gaps exist; nothing is filled,
flagged, or rejected (research R1).

**Bounds.** Per ticker, `[first observed bar, last observed bar]` for that
ticker — never the frame-wide range. A ticker that IPO'd mid-period or was
delisted mid-period therefore reports no gaps for the sessions outside its own
history (spec Edge Cases).

---

## Trading Calendar (supporting)

Not persisted; computed. NYSE sessions = weekdays minus:

| Holiday | Rule |
|---|---|
| New Year's Day | Jan 1, observed |
| Martin Luther King Jr. Day | 3rd Monday in January |
| Washington's Birthday | 3rd Monday in February |
| Good Friday | Easter Sunday − 2 days |
| Memorial Day | Last Monday in May |
| Juneteenth | Jun 19, observed — **2022 onward only** |
| Independence Day | Jul 4, observed |
| Labor Day | 1st Monday in September |
| Thanksgiving | 4th Thursday in November |
| Christmas | Dec 25, observed |

**Observation rule**: a holiday falling on Saturday is observed the preceding
Friday; on Sunday, the following Monday.

Plus a fixed set of known post-2000 ad-hoc closures (9/11 week, Reagan and
Ford and Bush mourning days, Hurricane Sandy, Carter mourning day). Necessarily
incomplete going forward; the failure direction is a false positive
(research R2).

**Deliberately not modelled**: half-days. The NYSE closes early on a handful
of sessions, but a shortened session still produces a bar, so it is not a gap.
