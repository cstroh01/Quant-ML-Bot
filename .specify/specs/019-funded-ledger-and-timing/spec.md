# 019 — Funded ledger and timing

Authority: audit 2026-09-12 work order 2; the user authorizes this handwritten
spec and six sequential review units without git or Spec Kit commands.

## Frozen decisions

- One instrument, long-only cash account; integer entry quantity, no margin,
  shorts, leverage, external flows, pending orders or financing. Immediate
  next-open orders reserve and consume their full notional plus fee atomically.
  Insufficient cash rejects the order and records the rejection. No resizing.
- Explicit starting capital is required before the first open; no price-derived
  default may choose funding using later information. Initial equity exists
  BEFORE the first event, identified as phase `initial`, not a fake prior day.
- Features and decisions are available after session t closes. Entry is at
  Open[t+1]; an h-session target exits at Open[t+h+1]. Label is
  log(Open[t+h+1]/Open[t+1]), available at that exit open. Purge and minimum
  embargo are h+1 rows. Daily dates are naive session labels; event phase
  distinguishes open/close without pretending midnight is an execution instant.
- Action-spanning price-ratio labels are unavailable; they are not total-payoff
  labels. Split/dividend-aware return-index features chain forward causally.
- Labels are outcomes, never predictors. Known-label training masks apply
  AFTER calendar splits. Inference retains every source session and index.
  A missing prediction means flat at that decision; its exit shifts one session.
- The h-session label is a forecast horizon, not a claim that hysteresis holds
  exactly h sessions. Variable-duration policy returns require separate replay.
- End of batch is not an exit decision. Open positions are marked. Optional
  terminal liquidation is explicitly requested and identified in the ledger.
- Cash accounting accepts only declared historical unadjusted dollar prices
  and explicit split/dividend events. Existing adjusted caches remain research
  inputs and cannot fund a simulation. No cache migration or download this run.
  Split acts before the open; a dividend becomes a receivable on ex-date for
  shares held beforehand, and cash only on its declared payment session.
- Research log predictions plus a hurdle are NOT expected dollar utility
  (audit 25). No profitability claim or new trading strategy is authorized here.

## Acceptance

Hand-calculated event balances; $100 rejects a $201.10 entry; pre-trade $100
through [95,95,90] draws down 10%; corrupt fills/costs fail; overnight-only
pre-entry movement earns nothing; latest feature row survives; prefix/future
perturbation invariance; split and paid dividend reconcile; per-review-unit
red evidence and isolated mutation controls. Synthetic data only.

## Scope disagreements and limits

The derived plan omits 25 from 3.2 and assigns it only to 3.5; audit work order
2 includes 22–25 (and work order 5 also includes 25). Keep 25 in this review;
do not claim its economic estimand problem solved by changing timestamps.
The plan proposes specs 022–025 and target/data before ledger; this run's user
instead assigns spec 019 and ledger-first dependency order. Audit does not
mandate those proposed numbers or that internal order. Findings 03–04 are
work-order-1 prerequisites, not a plan/audit disagreement.

Full portfolio risk, order recovery, dataset provenance storage, empirical
utility calibration and dependent-data inference remain separate milestones.
