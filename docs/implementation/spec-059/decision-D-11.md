# Spec 059 D-11 — research report data (2026-10-15)

`spec.md` is hash-locked by the 059 preregistration (`spec_sha256`), so this decision lives here and in
the declaration's additions-only amendment (`research_data`, `random_seeds`), not in `spec.md`.

**Camden, chat, 2026-10-15 21:33 CT:** "yes to all the stuff to build it", answering Claude's
recommendation to run the allocation report on the verified 058 panel instead of the spec 035 cache.

- **Why.** The spec 035 cache is 7/24 built. FR-003 on it would block `docs/SCOPE-V1.md` §11.3 item 2.
- **What.** The FR-003 research-window report runs on spec 058's D-10 B panel: the private T008 Tiingo
  bodies, the T009 data check, panel hash `3b80b330039b0c1b07b404371005ef71d064e2af093816c324d3546bcc9c7065`
  (the panel 058 T015 runs on). P&L on in-repo back-adjusted raw OHLC; T009 exclusions not tradable;
  action mismatches spliced to zero return. Costs: spec 046 primary on raw nominal bars, quantity
  converted by notional at the decision close. Commission $0 per fill. Starting capital $100,000.
- **Seeds.** B-RND (D-7) seeds 20261015–20261034, fixed now, before any 059 result.
- **Unchanged.** The §3 allocation rule, D-9 (PAPER and LIVE read Alpaca raw SIP bars), D-8 (research
  window only until 058 T016).
- **Disclosed.** Corporate actions before 2016 are single-source Tiingo (058 D-10). The 035 cache
  remains the later upgrade for this report.
- **Order.** 058 T015 ledger lines merged → `amend_family.py 059-allocation --record` → T004 dry-run
  → T004 `--record-trial`. The amendment is refused once any 059 trial exists.
