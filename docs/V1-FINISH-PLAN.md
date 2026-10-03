# v1.0 Finish Plan — sequenced by dependency

_Written 2026-09-25. Companion to `docs/SCOPE-V1.md`, which defines done. This
file defines order. Numbers are assigned here; Spec Kit's `NNN` placeholder
convention is retired for these items._

---

## The actual blocker, stated precisely

Not missing data. Not a missing vendor. **One unanswered accounting question.**

`YFinanceUnadjustedAdapter` writes `Dividend_Pay_Date = NaT` for every dividend
(`data.py:985-988`), because yfinance exposes ex-dates and not historical payment
dates. `_validate_corporate_actions` rejects any dividend without a payment date
(`data.py:634-635`), and `cache_unadjusted_market_data` validates before writing
(`data.py:886-888`). So no bundle can ever be written for a dividend-paying
ticker, `data/cache/unadjusted/` does not exist, and `backtest_harness.py:37`
raises on every real run.

This is spec 020 Open Question 1, unanswered since 2026-09-12, and it is the
single thing standing between this repository and a system that runs. Buying
Norgate would have answered it by accident, which is why it looked like a data
problem for three sessions.

**This is settled by evidence, not preference.** Verified 2026-09-25: no free
source provides 10 years of historical dividend *payment* dates. yfinance returns
ex-dates only (yfinance issues #568, #2056), Tiingo's corporate-actions API is
paid-tier only, and EODHD returns `paymentDate` but caps its free plan at one year
of history. Under the free-data constraint there is no vendor answer to 020 Q1, so
the declared bound is the only correct resolution.

**Resolution to adopt (spec NNN's D-7): a declared conservative bound.** The
payment date becomes `ex_date + declared_lag`, where the lag is a stated
conservative maximum recorded in the manifest, never a vendor field and never
inferred per-dividend. Dividend cash is therefore credited no earlier than it
could have been received, so the ledger is never optimistic about cash on hand.
The lag and its basis are disclosed per Rule 16 wherever a result appears.

Rejected alternative: exclude dividends from ledger cash entirely. It is also
conservative, but it silently understates total return and makes buy-and-hold
(Rule 4's baseline) wrong in a direction that flatters every strategy compared
against it.

---

## Sequence

### S1 — Spec 035: free unadjusted data bundle _(critical path)_

Resolves 020 Q1 with the declared-bound rule, then builds the cache that does not
yet exist.

- `YFinanceUnadjustedAdapter` stamps `Dividend_Pay_Date = ex_date + declared_lag`;
  the lag, its basis, and its conservatism direction go in the manifest.
- Fetch the five-ticker universe, 10 years, `auto_adjust=False`, with `.actions`
  as a separate table; validate through the existing `_validate_unadjusted_prices`
  and `_validate_corporate_actions` paths.
- **Rule 14 reconciliation against a free second source.** Verified 2026-09-25:
  the only free option is **EODHD's free plan**, which returns `date`, `value`,
  `unadjustedValue` and optionally `declarationDate` / `recordDate` /
  `paymentDate` — but is **capped at 1 year of history**. Tiingo's
  corporate-actions API is on no free tier. Reconciliation therefore covers
  roughly the most recent year and is partial by construction; every action
  outside that window is recorded as **unreconciled** and disclosed per Rule 16,
  never dropped and never silently trusted. SEC EDGAR remains available for
  spot-checking an individual split.
- **Rule 12 red proof:** a mutant that stamps `price_basis="unadjusted_dollars"`
  onto research-adjusted data must be killed, and a mutant that back-dates the
  declared dividend lag must be killed.
- **Acceptance:** `data/cache/unadjusted/` exists, validates, and
  `run_backtest` completes end-to-end on real AAPL data.

### S2 — Spec 036: funded-ledger caller wiring

The existing `NNN-unadjusted-caller-wiring` draft, renamed to `036-`. Switches
`ma_crossover_backtest.py` and the tearsheet route off legacy
`download_market_data` onto `load_unadjusted_market_data`, failing closed with a
documented unavailable state rather than falling back to adjusted prices. Its D-1
through D-7 decisions need sign-off; D-7 is answered by S1.

Ordered after S1 so its success path is proven on real data rather than only on
synthetic manifests.

### S3 — Close spec 021

Two open tasks: T048 (PR-G close-out) and T052 (re-run T004 fingerprints, every
digest unchanged). Small, and it ends the 019 migration that has been open for
eleven days.

### S4 — Spec 033 Phases 8–9: the DSR/PBO gate goes live

Gate 3 artifact, API wiring in `reports/api/routes/capital_gate.py`, DSR and PBO
operational against the real ledger. `capital_gate.py` is now free — spec 034
deliberately did not touch it (pre-work SHA recorded in its HANDOFF).

**Camden's blocking input:** backfill bounds for the 8 unresolved campaign rows
in `BACKFILL_REVIEW.md` (T031/T032). Not a code task. Nothing in this spec
finishes without it.

Note: spec 033's `tasks.md` checkboxes are unreliable — 10 marked done while
T054/T055 are checked and Phase 7 landed. Reconcile the checkboxes against the
tree before dispatching, or the next agent redoes finished work.

### S5 — Review and merge spec 034

Already implemented (28/28 tasks, `scripts/order_gateway.py`,
`reports/api/routes/safety.py`, new tests). Not reviewed, not merged.

**Camden's blocking input:** the real numeric safety limits. REQ-009 ships no
defaults on purpose, so the gate returns HTTP 503 until max position size, gross
exposure, daily-loss cap, and rolling-drawdown threshold are chosen. Those are
decisions about his own risk tolerance, not engineering.

### S6 — Spec 037: green from a clean clone

Measure before fixing. Clone `HEAD` to a scratch directory, run
`python -m pytest tests`, and categorize every failure as churn from a deliberate
contract change versus a real defect — the method that worked on the 019 blast
radius on 2026-09-14.

- CI installs `requirements-dev.txt` so the API tests can import (finding 57).
- Tests depending on gitignored artifacts either generate what they need or skip
  with an explicit documented reason. Nothing is left red.
- A test that passes only because it asserts a hardcoded value is a Rule 11
  violation, not a passing test.

### S7 — Spec 038: Rule 11 and Rule 16 disclosure sweep

Every surface a reader could mistake for results — terminal panels, `reports/`,
tearsheets, README tables, spec results sections — carries provenance and the
applicable limitation. This is the last thing standing between the repo and a
reviewer's respect, and it is the cheapest of all seven.

### S8 — Ship

- Repo split per ADR 0001: private companion repo for tuned parameters, weights,
  risk numbers, and credentials. Nothing sensitive in the public tree.
- Final README pass against the shipped state.
- Tag `v1.0`, public.

---

## v1.1 — paper trading (immediately after)

Spec 039: broker paper adapter under Rule 7 (reviewed lane only, never an
autonomous agent lane), spec 034's gate in the live order path, a scheduled daily
signal report on fresh free data, position reconciliation against broker truth,
and rolling model-decay monitoring. This is what starts the capital gate's
one-to-two-month paper clock.

---

## What this plan will not do

- Relax Rule 9. A PR Camden cannot explain does not merge, deadline or not.
- Relax Rule 10. Agents run no `git`.
- Add a paid vendor.
- Report a Sharpe as a result before the DSR gate is operational (Rule 15).
- Run two agent lanes on `capital_gate.py` in the same window.
