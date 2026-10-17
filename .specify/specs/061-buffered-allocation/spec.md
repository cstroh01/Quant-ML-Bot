# 061 — buffered equal-weight allocation: fresh costed trial

Date: 2026-10-17. Status: reviewed-lane draft; not adopted for execution.
Extends 059 through a new spec number, as 059 §3 requires for a post-result change.

## Decisions and provenance

Camden, chat, 2026-10-17: **"keep the 7% reserve and record a fresh costed trial.
Don’t adopt B-BH as recorded"**. This decision follows inspection of 059 T004;
it is post-hoc, not an untouched out-of-sample hypothesis. Historical A1 and
B-BH, including B-BH trial c2b0ea46-5d0a-4235-a675-19719d1dc67e, remain unchanged.
That trial is background only, never this allocation's adopted trial or return series.
The separately requested $200 LIVE budget remains a protected, human-reviewed
change; this trial does not change any execution budget, gate or SafetyConfig.

## Frozen definition (B7-EW)

- Universe: SPY, EFA, EEM, IEF, TLT, TIP, GLD, DBC, in that order.
- At the first observed session of each new calendar month, after its close,
  allocate 0.93/k to each of the k sleeves with a close at that session.
  A sleeve with no close is not selected; if none has a close, hold cash.
  No inverse-volatility sizing, volatility target or 60-session warm-up.
  The panel's first row is not treated as a known month opener.
- Target cash is 7% of pre-trade equity at rebalance, before modeled costs.
  It is not a guaranteed daily cash floor after costs or price moves.
- Fill at the next available panel session's open; hold shares between decisions.
- Commission $0 per fill. Spec 046 primary EDGE half-spread plus square-root
  impact Y=1, 21-session windows, on raw nominal bars; convert quantities by
  decision-close notional using the existing 059 T004 cost callback.
- Same frozen research panel as T004, hash
  `3b80b330039b0c1b07b404371005ef71d064e2af093816c324d3546bcc9c7065`;
  research only, through 2023-09-29. No holdout evaluation or new download.
- Starting research capital $100,000; no cash interest; no final liquidation.
  These modeled results do not establish $200-account executability.
- Fresh family `061-buffered-allocation`, one candidate start maximum, no tuning
  or automatic retry. Candidate errors also spend the one start.
- Fresh comparison trials on the identical panel and costs: unbuffered monthly
  equal-weight B-BH, and B-RND using the 20 seeds 20261015 through 20261034.
  Random sleeves are long/flat with probability 1/2 on each monthly decision,
  equal-weighted at 93% gross when nonempty. This matches decision cadence,
  not exact realized turnover; dispersion and this limitation accompany results.

## Acceptance

FR-001: Camden's one command freezes this new declaration through the registry
before starting any series, then starts all 22 series before evaluating any.
Existing 059 declarations and trials cannot be amended or reused.
FR-002: Record funded daily log returns, weight-book digest, panel/source/declaration
provenance, PSR at this family's own N=1, and both costed baselines with seed dispersion.
Label every metric surface `ALLOCATION — NO EDGE CLAIMED; NOT DSR-GATED`;
state post-hoc selection, in-sample evaluation, survivor ETF basket, free corporate
actions, daily bars and modeled costs. CV folds/purge/embargo: not applicable,
single research-window pass with no fitted parameters. No edge claim.
FR-003: Red-first tests distinguish this rule from A1 and unbuffered B-BH;
test future perturbations, monthly/gap boundaries, next-open fills, applied costs,
unfrozen/drifted declarations, start-before-evaluation and rerun refusal.
FR-004: Adoption into PAPER/LIVE and gate item 2 is a later reviewed unit, after
this declaration and costed trial exist. Until then keep production behavior
and all arming/schedule gates unchanged. Do not manufacture 059 amend-2.
