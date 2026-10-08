# Feature Specification: Verified free professional data stack

**Spec number**: 056
**Created**: 2026-10-07
**Status**: Adopted under `docs/SCOPE-V1.md` §10. Research input from the Codex lane
(`DATA-SOURCES-VERIFIED.md`, private). Network fetches remain human-authorized runs.
**Related**: 035 (unadjusted bundle), 044 (nominal reconstruction), 052 (registry), Rule 14.

## 1. Purpose
Choose, verify and adopt the best free data per role, with terms checked for a public repository.

## 2. Requirements
- **FR-001 Role map.** One primary and at least one independent check per role: daily OHLCV
  (raw + adjusted), corporate actions, identifiers/listings/delistings, point-in-time fundamentals,
  macro with vintages, factors.
- **FR-002 Verification record.** Per source: official URL, date checked, free-tier limits, license
  terms for personal research and public-repo derived data, history depth, delisted coverage,
  point-in-time properties. Anything unconfirmed is `UNVERIFIED` and cannot gate a result.
- **FR-003 Manifests.** Every fetched dataset writes a manifest: source, endpoint (no credentials),
  parameters, fetched_at (aware), row counts, SHA-256, license note. Raw data stays in `data/cache/`.
- **FR-004 Cross-source checks.** Close and corporate-action agreement checks between independent
  sources (Rule 14); disagreements are excluded or disclosed, never averaged.
- **FR-005 PIT fundamentals.** EDGAR facts used only as of their `filed` date.
- **FR-006 Keys.** Free API keys are Camden's human gate; stored only as secrets.

## 3. Decisions (quant-ml-genius, provisional until FR-002 records exist)
Candidates: EOD — Tiingo EOD, Alpaca Basic, Stooq/yfinance as tertiary checks; actions — Tiingo,
Alpaca corporate actions, SEC filings; identity — SEC CIK, OpenFIGI, Nasdaq Trader directories;
fundamentals — SEC EDGAR companyfacts/Financial Statement Data Sets; macro — FRED/ALFRED;
factors — Kenneth French Data Library. Final selection is recorded after verification.

## 4. Rule 12 mutants
Adjusted series stamped as raw; manifest missing fetched_at accepted; EDGAR fact used before its
filed date; cross-source mismatch silently averaged; credential appears in a manifest.

## 5. Acceptance
Verification records for every adopted source; manifests and cross-checks implemented offline with
fixtures; one human-authorized fetch per source produces hashed manifests.
