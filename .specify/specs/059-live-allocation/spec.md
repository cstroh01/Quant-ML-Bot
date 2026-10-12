# Feature Specification: Preregistered LIVE allocation and v1.2 capital-gate evidence

**Spec number**: 059
**Created**: 2026-10-12
**Status**: Draft. Decisions D-1 to D-5 recorded from Camden's chat answers of 2026-10-12.
**Related**: 033 (ledger), 046 (costs), 049/051/055 (PAPER operations), 052/060 (universe), 057
(Fidelity), 058 (edge research), `docs/SCOPE-V1.md` §11 (v1.2 acceleration amendment, a separate
governance PR), constitution Rules 1–5, 11, 12, 15 (allocation carve-out), 16.

EXAMPLE — NOT A RESULT. This spec contains no performance figure.

## 1. Purpose
Give the bot something honest to trade with real money soon, without claiming an edge.
Spec 058's most likely outcome is that no hypothesis passes Gate 3. This spec does not depend on
that outcome. It fixes, before any 058 research statistic is seen, one simple strategic allocation
that LIVE trades by default, and the evidence that must exist before LIVE arms.

The allocation is a portfolio-construction choice, not a forecast. It makes no claim to beat the
market or any baseline, and every surface says so.

## 2. Recorded decisions (Camden, chat, 2026-10-12)
- **D-1 Gate.** "Allocation, no alpha claim": LIVE trades a preregistered, vol-targeted ETF
  allocation that does not need to beat anything. Gate 3 still runs on 058 and is published; it does
  not block LIVE.
- **D-2 Allocation.** "Vol-targeted multi-asset": inverse-volatility risk parity across asset-class
  sleeves, scaled to a 10% portfolio volatility target, monthly rebalance.
- **D-3 Paper clock.** "10 trading days + replay": at least 10 completed sessions on both PAPER
  profiles with fills reconciled against the cost model, plus a 2020/2022 historical replay through
  the live pipeline.
- **D-4 Fidelity.** "Automated adapter (spec 057)" for LIVE, after 5 clean preview-only sessions
  (`docs/SCOPE-V1.md` §11.3 item 6).
- **D-5 Budget.** Unchanged from 2026-10-09: $100 of settled cash; deposits never raise it.

## 3. The allocation (fixed now; hashed into the ledger before 058 T015 runs)
- **Sleeves (8).** SPY (US equity), EFA (developed ex-US equity), EEM (emerging equity), IEF
  (intermediate Treasuries), TLT (long Treasuries), TIP (inflation-linked Treasuries), GLD (gold),
  DBC (broad commodities). All are in spec 058's universe, so no new data family is opened.
- **Entry.** A sleeve enters on its first full session after listing plus 60 observed sessions.
- **Weights.** At decision session `t`: per-sleeve volatility `σ_i` = 60-session EWMA of daily
  close-to-close returns observed at or before `t`; raw weight `w_i ∝ 1/σ_i`, normalized to sum 1.
- **Vol target.** Portfolio volatility from the 60-session EWMA covariance at `t`; scale all weights
  by `min(1, 0.10 / σ_p)` (annualized, 252 sessions). Gross ≤ 1.0, long-only; the remainder is cash.
- **Timing.** Decisions on the first session of each month from close `t`; orders fill at the open
  of `t+1` (Rule 1). Between decisions, positions are held (no daily re-targeting).
- **Costs.** Spec 046's model only (Rule 13).
- **No tuning.** None of these values may change after this spec merges without a new spec number
  and a new preregistration. A change made after any 058 or 059 result is seen voids D-1.

## 4. Requirements
- **FR-001 Preregistration.** A ledger record holds the §3 rule, the sleeve list, the spec's SHA-256
  and the cost-model version, written before 058 T015 (HUMAN GATE: ledger writes are Camden's).
- **FR-002 Weights builder.** A pure function from a point-in-time price panel to target weights per
  decision session. Tests: hand oracle on two and three assets; perturbing `t+1` changes nothing at
  `t`; gross cap; cash remainder; listing-date entry; months without a decision carry weights forward.
- **FR-003 Backtest report.** Costed walk-forward backtest over the research window (≤ 2023-09-29)
  and, separately labelled, the full available history, beside equal-weight buy-and-hold and a
  seeded random baseline with identical costs (Rule 4). Reports PSR at this family's own N = 1 with
  the line `ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED` and the limitations register (Rule 16).
  It never opens spec 058's sealed holdout.
- **FR-004 PAPER.** Both PAPER profiles trade the allocation through the safety gate, on spec 035
  validated data (queue Q100, Q110).
- **FR-005 Paper evidence.** A per-order report: intended price, fill price, realized cost, modeled
  cost, reconciliation status, sessions completed per profile. It prints PASS only when both
  profiles have ≥ 10 completed sessions and every order reconciled (`docs/SCOPE-V1.md` §11.3 item 4).
- **FR-006 Replay.** The PAPER pipeline with a simulated broker replays 2020-02-03 to 2020-04-30 and
  calendar 2022; the report lists unhandled errors and safety-gate breaches not present in the
  backtest (§11.3 item 5).
- **FR-007 Gate checklist.** One offline command prints each §11.3 item with its evidence artifact,
  commit and date (Rule 11), and refuses to print ARMABLE unless every item has evidence.

## 5. Rule 12 mutants
Weights computed from `t+1` data; per-leg instead of portfolio vol scaling; daily re-targeting
between decisions; gross cap removed; paper-evidence PASS with 9 sessions; replay report ignoring a
gate breach; checklist ARMABLE with one missing artifact.

## 6. Out of scope
Any edge claim; leverage; shorting; changing the allocation on the basis of results; LIVE arming,
which stays Camden's action.

## 7. Disclosed limitations
Survivorship bias in the ETF list (closed ETFs absent); free-tier corporate actions; daily bars only;
costs modeled, not calibrated, until PAPER evidence exists; the replay tests the code path, not
real fills under stress; with $100 and fractional shares, rounding and minimums dominate small
sleeves, and the PAPER small profile ($5,000) is the closer analogue.
