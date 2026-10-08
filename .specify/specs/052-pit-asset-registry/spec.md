# Feature Specification: Point-in-time asset registry and eligibility

**Spec number**: 052
**Created**: 2026-10-07
**Status**: Adopted under `docs/SCOPE-V1.md` §10. Offline units authorized. Real-data population waits on 056.
**Depends on**: 056 (sources), 051 (budget/limits for executable checks), 035/044 for reported results.

## 1. Purpose
Replace the hardcoded five-ticker panel with dated instrument identity and two separate decisions —
research eligibility and executable eligibility — each with visible exclusion reasons.

## 2. Requirements
- **FR-001 Identity.** Stable `instrument_id` independent of ticker. Dated history rows for symbol,
  listing venue, listing/delisting, share class and corporate actions, each with `effective_date`
  (session label) and `observed_at` (aware instant) and a source citation.
- **FR-002 As-of queries.** `snapshot(as_of)` returns only facts with `effective_date <= as_of` AND
  `observed_at` no later than the end of the `as_of` session. Today's listing set is never historical membership.
- **FR-003 Research eligibility** (per instrument, per session): history ≥ min sessions, price ≥ floor,
  median 20-session dollar volume ≥ floor, corporate actions reconciled or disclosed, nominal/adjusted
  basis known. Each failure yields a named reason.
- **FR-004 Executable eligibility**: broker tradable, not halted, quote/bar fresh, instrument class
  permitted by the profile (051), spread estimate ≤ cap, participation ≤ cap of 20-session ADV,
  order ≥ broker minimum. Inputs come from an injected read-only snapshot; this module makes no calls.
- **FR-005 Causal membership.** Training/CV membership is selected per row as of that row's session;
  cross-sectional statistics are fit inside the training fold's past only.
- **FR-006 Delistings retained.** Delisted instruments stay in history with delisting date; their
  rows are never dropped. Survivorship limitation (§6) stays until coverage evidence removes it.
- **FR-007 Size categories** (large/mid/small/niche) are labels only; they never bypass FR-003/FR-004.

## 3. Decisions (quant-ml-genius, 2026-10-07; numeric values live in private config)
- **D-1** US common stocks and ETFs on NYSE, Nasdaq, NYSE Arca, Cboe BZX; USD only.
- **D-2** Identity: SEC CIK + share class, OpenFIGI where verified; listings: Nasdaq Trader symbol
  directories; tradability/fractionable: broker asset endpoints. All subject to 056 verification.
- **D-3** Default thresholds: research ≥252 sessions, price ≥ $5, median 20-session dollar volume ≥ $5M;
  executable spread ≤ 50 bps (046 estimate), participation ≤ 1% of 20-session ADV.
- **D-4** Stale: last completed bar older than the previous NYSE session → executable exclusion `stale_bar`.
- **D-5** Delisting: last traded price is the exit; disclosure stays. Benchmark: CRSP-style delisting handling, AFML ch. 1.

## 4. Rule 12 mutants
Future constituent leaks into a past snapshot; ticker change remapped to today's symbol; delisted
name dropped from history; adjusted volume treated as nominal; cross-sectional fit uses future rows;
halt or staleness bypassed; participation/minimum omitted; exclusion reason suppressed.

## 5. Acceptance
Registry snapshots reproducible by hash; eligibility causal; executable checks honor 051; mutants
killed; synthetic panel with delisting, rename, split, halt, stale quote and unsupported class passes.
