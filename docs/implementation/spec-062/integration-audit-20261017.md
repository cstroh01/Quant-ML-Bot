# Integration audit — 2026-10-17 America/New_York

Source checkpoint: public main `c1dbc854b146095cd47283ef4cbc1b5838f20d94`.
This is a code/evidence audit, not a broker session or a new strategy evaluation.
Camden's current choices: free data; US-listed stocks and ETFs; exclude OTC,
leveraged and inverse products. Spec 062 implements the new research scope.

## Fidelity and autonomy

The adapter and dormant allocation loop exist (`exec/fidelity_live.py`,
`exec/live_loop.py`). Orders require arming and the gateway; unknown outcomes,
account/holdings mismatches and security challenges halt rather than retry.
An initial TOTP step is supported, but unexpected challenges need Camden.
The repository supplies a local Windows preview task, not an installed,
verified unattended LIVE service. Its source pin is unchanged by this work.

The read-only gate command was rerun against the checkpoint manifest:
`python scripts/gate_checklist.py docs/implementation/spec-059/gate-manifest.json`.
It reports **NOT ARMABLE**: items 4 (PAPER evidence), 6 (Fidelity previews and
holdings reconciliation) and 7 (settled cash/budget evidence) are missing.
Item 1 also requires refresh at the eventual arming revision. Do not infer
runtime acceptance from the existing fakes-only tests or replay.

The current limit is $200, and account-specific fractional eligibility for
the allocation sleeves is unverified. A broad research universe does not
expand that limit or authorize any additional LIVE symbols.

## Data actually consumed

| Source | Implementation / current consumer | Remaining acceptance |
|---|---|---|
| Alpaca | `data_sources.AlpacaDailyBars`; `paper_loop.fetch_sleeve_closes` feeds PAPER and `fidelity_inputs.build_bundle`. Raw SIP is explicit. Also checks the historical research panel. | Current credentials, entitlement and fresh input receipts on the running host. |
| Tiingo | `TiingoDailyRaw`; private T008 bodies feed `load_058_panel` and the recorded 058/061 research after T009 checks/exclusions. | Broader symbol coverage, quotas, current receipts and independent action coverage. |
| EODHD | Supplemental one-year action role in 056's verified research record. No production EODHD adapter or model consumer found under `scripts/`/`exec/`. | Offline adapter, account entitlement, bounded fetch, nominal amount/volume semantics and reconciliation. |
| Massive | Separate PR #198 held; adapter absent from main. | Resolve contract/terms, migrate deprecated actions, verify ETF/reference coverage with bounded receipts, then reconciliation. |
| SEC EDGAR | Submissions/companyfacts adapters and as-of helpers exist. | No fundamentals feature consumer was found in the current trading allocation; filing-acceptance joins and restatements need dataset-level validation. |
| FRED/ALFRED | Adapter and conservative vintage join exist in `data_sources.py` / `macro_sources.py`. | Not consumed by the allocation's signals. New features require a new preregistered research family. |
| French factors | Adapter exists; attribution role only. | Not an alpha input; downloaded versions and use rights remain dataset-specific. |
| OpenFIGI | Mapping adapter exists. | Not a complete historical security master or delisting-return database. |
| Nasdaq/Treasury/Cboe/Stooq | Candidate roles/verification notes; no completed comprehensive dataset pipeline inferred. | Dated reference snapshots, endpoint/rights/availability verification; unknown stays unknown. |

Consumer trace: `scripts/data_sources.py:load_058_panel`,
`scripts/run_061_buffered_trial.py`, `exec/paper_loop.py:fetch_sleeve_closes`,
`scripts/fidelity_inputs.py:build_bundle`, and imports under `scripts/`,
`exec/`, `reports/api/`. Adapter presence does not establish training use.

This cloud checkout contains **no `.env*` file**; only filenames/existence
were checked. Environment status reports no configured secrets or runtime
variables, and vendor destinations are not in the current allowed-host list.
No credential contents or authenticated vendor responses were inspected.
Windows/private-GitHub secrets are not automatically available here.
The Windows Fidelity preview helper does not load `.env`: its Alpaca input
refresh needs `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` in its environment.
Fidelity credentials use the separate native Windows vault launcher.

## External contracts checked today (documentation only)

- [Massive migration](https://massive.com/blog/new-splits-and-dividends-endpoints):
  old split/dividend endpoints are deprecated. This conflicts with #198's
  unverified Polygon-compatible v3 assumption; leave that PR held.
- [Massive pricing](https://massive.com/pricing?product=stocks): Basic advertises
  $0, five calls/minute and two years of history. This cannot supply the
  three years required by spec 060's ETF screen on its own.
- [Massive data terms](https://massive.com/legal/market-data-terms-of-service),
  sections 2 and 5: display/non-display, strategy and derived-work restrictions
  require entitlement clarification before this project's proposed use.
- [Nasdaq directory definitions](https://nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs):
  useful listing/test/ETF flags, not a historical survivorship-free database.

No API key, price payload or raw market dataset was fetched during these checks.
Existing 056 research remains the more detailed role/terms record; today's
documentation read is not proof of account entitlement or completeness.

## Universe and research acceptance

The recorded 058 research uses its frozen 25-ETF universe. The deployment
allocation targets eight ETF sleeves. Spec 060's approximately 100-ETF list
has a builder but no published final `docs/universe/etf_universe_v1.csv`.
Q125 fixes the builder's missing per-class reservation without changing trials.
Spec 062 adds uncapped stock/ETF **data-collection candidates** with immutable
IDs, dated metadata, history/liquidity checks and named exclusions.

The current allocation is buffered monthly equal weight, not a fitted ML
stock-selection model. The published 058 research verdict is **FAIL**
(`docs/implementation/spec-058/results-20261016.md`); the 061 allocation is
explicitly **NO EDGE CLAIMED**. A wider universe does not change those verdicts.
Professional-quality data work here means verified timing, stable identity,
corporate actions, missingness, independent checks, immutable versions,
realistic costs and evaluation discipline. Adding feeds by count cannot
substitute for these properties or establish an advantage over institutions.

## Completion dependencies

1. Deliver the reviewed Q125 fix and 062 candidate screen. Obtain real dated
   listing/classification snapshots and licensed free raw bars; run the screen
   with explicit research thresholds and retain private hash-bound receipts.
2. Finish 060 source verification, EODHD/Massive action integration and independent
   reconciliation. Do not manufacture missing payment dates or historical members.
3. Finish the existing 044/035 nominal-data chain after its probe/selection gates;
   finish 033's matrix-currentness and Gate 3 API route, 046 cost reporting,
   047 tearsheet work and 038 disclosure/UI work. These remain software gaps.
4. Preregister new stock/ETF research before evaluation, retain every trial,
   train transformations inside purged/embargoed folds, compare identical-cost
   baselines and use fresh prospective validation after the spent 058 holdout.
5. Verify PAPER submissions/fills/reconciliation/cost evidence, notification
   delivery and host scheduling; collect the required Fidelity preview sessions,
   latest holdings CSV match and settled-cash evidence. These require the actual
   configured accounts/host and cannot be supplied by a code-only change.
6. Refresh final checks at the reviewed target, obtain Camden's protected-path
   review and LIVE decision, then verify deployed operation. This audit arms,
   schedules and submits nothing.

Stored queue at the checkpoint: 70 done, 40 ready, 18 blocked, five deferred
(`docs/autonomy/queue.json`, counted in this audit). Those are queue labels,
not a revalidated completion count: e.g. Q128 is still ready despite its merged
implementation. Task/status documents require evidence-based reconciliation.
The project is **not fully complete** at this checkpoint or after the candidate
screen alone; no account gate is marked complete by this report.
