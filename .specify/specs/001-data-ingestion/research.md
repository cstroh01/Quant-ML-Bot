# Research — 001 Data Ingestion

Decisions taken before implementation, with the alternatives that were
rejected and why. Anything here that constrains the code is restated as a
contract in `contracts/data-module.md`.

---

## R1 — FR-009 scope: what "inspectable" means

**Question the spec left open.** FR-009 is marked NEEDS CLARIFICATION: does
Phase 0 need the module to *act* on calendar gaps (flag / reject / fill), or
only make them inspectable?

**Decision: inspectable only.** The module gains a read-only reporting
function. It does not fill, interpolate, reject, or mutate the returned frame
in any way when a gap is present.

**Why.** Three reasons, in order of weight:

1. **The spec's own Assumptions section already resolves it this way** —
   "satisfied by making gaps *detectable and reportable*, not by having the
   module reject or auto-fill them."
2. **Auto-fill is a Rule 1 hazard, not a convenience.** A forward-fill copies
   the last known bar into a later timestamp, which is legal point-in-time; a
   *backward* fill or an `interpolate()` reads across the gap from the far
   side and writes a value into row `t` that was not knowable at `t`. The
   constitution names `fillna(method='bfill')` and `interpolate()` explicitly.
   Shipping a fill mechanism at all creates the affordance for the illegal one
   to be selected later by a caller who has not read Rule 1.
3. **Rejecting is worse than reporting at Phase 0.** A halted or
   provider-glitched bar is common in real data. A module that raises on any
   unexplained gap makes the pipeline unusable on exactly the historical
   windows worth studying, and the natural workaround — a `strict=False` flag
   — is the same silent-failure surface the check was meant to remove.

**Consequence for the caller.** The gap report is a separate call. Ignoring it
is possible, and that is deliberate: the alternative is a module that decides
data policy on behalf of a strategy it is not allowed to know about (Rule 8).

---

## R2 — Which trading calendar, and how it is obtained

**Decision: hand-rolled NYSE calendar, ~90 lines of stdlib date arithmetic.
No new dependency.**

Three options were considered.

| Option | Verdict |
|---|---|
| `pandas_market_calendars` | Rejected — new dependency (Rule 6) |
| `pandas.tseries.holiday.USFederalHolidayCalendar` | Rejected — **wrong**, not merely heavy |
| Hand-rolled NYSE rules | **Chosen** |

`USFederalHolidayCalendar` is already reachable through the installed pandas,
so Rule 6 would not even be triggered by using it. It was still rejected,
because it does not describe the NYSE:

- It **omits Good Friday**, on which the NYSE is closed. Every Good Friday
  would be reported as an unexplained gap — one guaranteed false positive per
  year.
- It **includes Columbus Day and Veterans Day**, on which the NYSE is *open*.
  A genuine missing bar on either day would be silently excused — a false
  negative, which is the direction that actually hurts.

A false negative in a gap detector is the failure mode worth engineering
against, since the whole point of FR-009 is to surface the bar that should not
be missing. Being wrong in that direction twice a year disqualifies the
option.

`pandas_market_calendars` is correct and would work, but it is a new
dependency carrying an exchange database, a `pandas` version coupling, and a
transitive tree, in exchange for rules that fit in one screen and change
roughly once a decade (Juneteenth, 2021). Rule 6 asks what it does that
existing dependencies cannot; here the honest answer is "nothing this module
needs."

**What the hand-rolled calendar covers.** Weekends, plus the ten NYSE
holidays: New Year's Day, MLK Day, Washington's Birthday, Good Friday,
Memorial Day, Juneteenth (2022+), Independence Day, Labor Day, Thanksgiving,
Christmas — each with the NYSE weekend-observation rule (Saturday holiday
observed the preceding Friday, Sunday holiday observed the following Monday).

Good Friday needs Easter, which is computed with the anonymous Gregorian
algorithm — pure integer arithmetic, no table, valid across the Gregorian
range.

**Known limitation, deliberately accepted.** Ad-hoc closures (national days of
mourning, 9/11, Hurricane Sandy) do not follow a rule. A hardcoded set of the
known post-2000 closures is included so they are not reported as gaps. That
set is necessarily incomplete for closures that have not happened yet; the
consequence is a false *positive* — a real closure reported as an unexplained
gap — which is the safe direction, and is why this is acceptable rather than a
blocker.

---

## R3 — Timestamp convention for a daily bar

**Decision: `Date` is a timezone-naive midnight timestamp denoting a trading
session, normalized identically on both the download path and the cache-read
path.**

This is the one place the implementation states a convention rather than
inheriting one, so it is written down here and re-stated in the module
docstring, per CLAUDE.md's requirement that alignment conventions be explicit.

**Why not timezone-aware.** CLAUDE.md says timezone-aware throughout, and that
rule is right for anything denoting an *instant*. A daily bar is not an
instant — it labels a session. Attaching a zone to it forces a choice of
which moment in the session the label means, and every choice creates an
off-by-one across a date boundary for some reader: a bar labelled
`2024-03-08 00:00 America/New_York` converted to UTC becomes `2024-03-08
05:00Z`, and the same bar stored as `2024-03-08 00:00 UTC` and read in
Eastern becomes *March 7th*. That is precisely the class of silent one-bar
shift Rule 5 exists to catch.

**The failure this actually prevents.** The hazard is not abstract. The
returned frame is produced by two different code paths — a fresh download and
a CSV read-back — and a CSV round-trip does not preserve tz-awareness the way
the download produces it. Before this change, a cache *hit* and a cache *miss*
could hand the caller `Date` columns of different dtype for the same request.
Downstream, comparing a naive to an aware timestamp either raises `TypeError`
or, where pandas coerces, shifts the bar. Normalizing both paths through one
function is what makes cache-hit and cache-miss substitutable, which is the
property Scenario 2 is actually asserting.

**Settled — project-wide, not per-module.** This was flagged as needing a
ruling because the answer is not `data.py`'s to make alone. The ruling now
lives in CLAUDE.md under *Conventions → Timestamps*: an **instant** is
timezone-aware without exception; a **session label** is timezone-naive and
midnight-normalized. A session label crossing into instant-space — an order, a
broker call, an intraday join — is localized to `America/New_York` explicitly
by the code doing the crossing, never implicitly and never to UTC.

`_normalize_dates` is that ruling applied, not a local interpretation of it.
The next module that produces a daily bar reads the rule in CLAUDE.md rather
than rediscovering it here.

---

## R4 — How the download path is made testable without network

**Decision: inject the downloader as a default-valued parameter
(`downloader=yf.download`).**

Rule 5 requires tests, and CLAUDE.md requires that no test touch the network —
"a test that requires a download is not a test." The module's error paths
(FR-005 ticker silently dropped, FR-006 empty response) are only reachable
through a yfinance response, so they need a substitutable one.

Rejected: monkeypatching `yf.download` at module scope from the test. It
works, but it makes the seam invisible in the module under test and leaks test
mechanics into import order.

The parameter is keyword-defaulted, so every existing caller
(`ma_crossover_backtest.py`, `return_stats.py`, `data_pipeline_sanity_check.py`,
`logistic_baseline.py`) is unaffected.

---

## R5 — Cache key ordering

**Decision: the cache filename is built from the *sorted, de-duplicated*
ticker set.**

Today the key is `'-'.join(tickers)` in caller order, so
`["AAPL", "MSFT"]` and `["MSFT", "AAPL"]` are the same request that writes two
different files, and neither one is ever a hit for the other. This is a cache
correctness bug rather than a behavioral one — it costs a redundant download
and a redundant file, and it silently doubles the rate-limit pressure the
cache exists to relieve.

The spec already describes the key as "named from the sorted ticker list"
(Key Entities), so this brings the code to the spec rather than changing the
spec.

**Migration.** None. `data/cache/` is gitignored regenerable output; existing
files under the old name are simply never read again and cost one re-download.

---

## R6 — What a cache hit returns

**Decision: the cache-read path is filtered to the requested tickers and
re-sorted through the same tidy function as the download path.**

SC-001 requires a request for N tickers to return exactly N tickers. FR-003
validates a cache file as usable if it is a *superset* of what was asked for,
which means "usable" and "returned as-is" are not the same thing. Routing both
paths through one `_tidy` function makes the two indistinguishable to a
caller, which is what Scenario 2's "returns data identical to the cache file"
is really asserting — identical *content*, arrived at by one code path rather
than two that drift.
