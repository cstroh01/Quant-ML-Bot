# 062 — US stock and ETF research candidate universe

Created 2026-10-17 America/New_York. Implements Camden's current request to
expand the project beyond large-company stocks while retaining free data.

## User requirements

Camden, chat, 2026-10-17: "Keep free data for now" and "US stocks and ETFs;
exclude OTC, leveraged and inverse products". These choices extend research
beyond spec 060's ETF-only list. They do not change spec 058's frozen family,
spec 061's execution allocation, any safety limit, or broker authorization.

## Requirements

- FR-001: An offline, deterministic candidate builder includes US-exchange-listed
  common stocks and ETFs without a market-cap or fixed symbol-count cutoff.
  Exclude OTC/other venues, other security types, leveraged/inverse products,
  and instruments whose product classification is unknown. Every known
  instrument receives an inclusion/exclusion reason.
- FR-002: Dated reference snapshots are visible only after observation and
  effect, at the session's 16:00 New York decision cutoff. Instrument ID is the
  join key; reused ticker history must never migrate to another instrument.
  Exclude not-yet-listed, delisted, stale, malformed or incomplete history.
  Read no later bar. Caller supplies explicit research screening thresholds;
  these are not execution limits or a recommended portfolio.
- FR-003: A CLI consumes private normalized reference and raw close/volume CSVs,
  validates before writing, and creates a private candidate CSV plus a JSON
  receipt containing input hashes, policy, date, counts and limitations.
  It never downloads, reads credentials, trains, evaluates, promotes or orders.
- FR-004: Label outputs `CANDIDATE INVENTORY — NOT TRAINING OR TRADING APPROVAL`.
  Candidates still need independent price/action reconciliation, dataset rights,
  complete OHLCV, preregistered research, costs/CV, model promotion and broker
  eligibility. Current survivor snapshots cannot reconstruct historical members.
- FR-005: Record the current Fidelity/data/universe integration gaps and their
  account-dependent acceptance evidence, without marking human gates complete.

## Acceptance

Tests cover listing/delisting/observation boundaries, future perturbations,
missing bars/holidays, reused tickers, explicit flags and all venue/type
exclusions. Rule 12 planted defects remove the time/venue/product screens.
CLI integration proves hashes, stdout provenance and failed-write cleanup. Existing suites stay
green; production ledger bytes remain unchanged. No dependency is added.
