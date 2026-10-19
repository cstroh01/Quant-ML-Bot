# Integration audit — local reconciliation, 2026-10-18 America/New_York

Source: public main `c1dbc854b146095cd47283ef4cbc1b5838f20d94`; candidate
proposal #256 at `a6430160fd39f3871776a105367575ef8c473553`, with T008 review
corrections pending publication. This is source/private-evidence inspection,
not a broker session, vendor refresh, strategy evaluation or acceptance run.
Camden chose free data, US stocks/ETFs, and no OTC, leveraged or inverse products.

| Area | Existing evidence | Verified remaining acceptance |
|---|---|---|
| Fidelity | LIVE adapter, guarded loop and private preview/submit dispatch exist. Production is $200/unarmed. Unexpected security challenges require intervention. | Gate 4 PAPER sessions, gate 6 previews/holdings and gate 7 settled cash/budget evidence; refresh the final arming SHA. No unattended-operation proof. |
| Host | Six hosted fixture drills passed; production PAPER workflow has zero recorded runs. Windows PAPER task is disabled, last result 1. No Fidelity task/current preview or holdings CSV was found at its configured path; an older private holdings CSV exists. | Actual account/host acceptance, notifications and eventual dedicated-host compatibility. Inspection does not rule out activity elsewhere. |
| Alpaca/Tiingo | `data_sources.load_058_panel`, `paper_loop.fetch_sleeve_closes`, `fidelity_inputs.build_bundle` and recorded research consume these sources. Saved raw-response hashes match. | Fresh entitlement, breadth, independent actions and nominal-data acceptance remain dataset-specific. |
| EODHD | Private generic fetching and six observations already exist. #257 adds the reusable bounded adapter; T009 follow-up refuses unchecked splits/unknown action labels. | Credentialed/account acceptance was not run; independent split verification stays in spec 044. Use `key_env="EODHD_API_TOKEN"` for the existing local key name. |
| Massive | Offline adapter proposal #198 remains held, absent from main. | Contract/terms, endpoint migration and bounded coverage/reconciliation; no current entitlement inferred. |
| Other sources | SEC as-of helpers, FRED/ALFRED vintage joins, French attribution and OpenFIGI mapping exist. | No consumer in the allocation establishes these as trained-model features; mapping is not a historical security master. Nasdaq/Treasury/Cboe/Stooq roles do not establish complete datasets. |

Local credential names exist in `.env`; values were neither loaded into a job nor
printed. No Fidelity vault was read. Key presence establishes neither validity
nor entitlement. The earlier cloud-only absence claim does not apply locally.
101 retained response hashes plus two saved Alpaca action hashes matched; retained
bodies prove historical observations, not fresh availability. Spec 058 T009 remains
EXCLUSIONS (290 excluded ticker-sessions, 45 action mismatches), with documented
single-source limits. The current Fidelity input bundle has no 061 allocation
binding. These private inspection findings remain separate from public CI.

Spec 058 research remains FAIL (`../spec-058/results-20261016.md`). Spec 061's
eight-ETF buffered allocation is not a fitted stock-selection model and claims
no edge. Spec 060's final ETF CSV is unpublished; #255 fixes class reservation.
Spec 062 screens uncapped data-collection candidates, not approved training or
trading instruments. Wider coverage cannot establish performance or broker eligibility.

Next: reviewed source delivery; dated classifications and licensed raw bars;
independent OHLCV/actions; preregistered research with costs, purged/embargoed CV
and fresh prospective validation; then account evidence and Camden's LIVE gate.
Static survivor snapshots cannot reconstruct historical members/delisting returns.
Old queue labels and unchecked tasks require individual source reconciliation;
they are not a verified count of missing code. Spec 063 private-budget work is a
separate protected review draft; deposits do not automatically raise authority.
This audit does not change production capital, pins, credentials or schedules.

T008 verification is reproducible with `python -m pytest tests/test_062_research_universe.py`.
Current-head full-suite acceptance must be bound to the pushed SHA in
[PR #256 checks](https://github.com/cstroh01/Quant-ML-Bot/pull/256/checks).
No unsupported cloud workspace test count is retained as current evidence.
