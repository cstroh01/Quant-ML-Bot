# Integration audit — 2026-10-18 America/New_York
Source baseline: public main `c1dbc854b146095cd47283ef4cbc1b5838f20d94`; software inspection checkpoint #256 `c57e0f38dd64f933b0f488ecbb44942460588330`. Operational findings are dated inspection, not fresh account proof.
Camden chose free data, US stocks/ETFs, and no OTC, leveraged or inverse products.

| Area | Existing evidence | Remaining acceptance |
|---|---|---|
| Fidelity | LIVE adapter, guarded loop and private dispatch exist. Public LIVE cap is $200 (`scripts/mode_config.py` at baseline); inspection did not establish arming acceptance. Unexpected challenges need intervention. | PAPER sessions, previews/holdings, settled cash/budget evidence, final arming SHA and unattended-operation proof. |
| Host | Hosted fixture reports do not establish production PAPER operation. Inspected Windows PAPER task was disabled after an unsuccessful run; configured paths lacked current Fidelity task/preview/holdings evidence, though older private holdings exist. | Account/host acceptance, notifications and dedicated-host compatibility; activity elsewhere is not ruled out. |
| Alpaca/Tiingo | `data_sources.load_058_panel`, `paper_loop.fetch_sleeve_closes`, `fidelity_inputs.build_bundle` and recorded research consume them. | Fresh entitlement, breadth, independent actions and nominal-data acceptance remain dataset-specific. |
| EODHD | Private generic fetching and saved observations predate #257's bounded adapter; its T009 follow-up refuses unchecked splits/unknown labels. | No credentialed acceptance here. Spec 044 owns splits; configure `key_env="EODHD_API_TOKEN"` explicitly for the local name. |
| Massive | Offline proposal #198 stays held, absent from main. | Contract/terms, endpoint migration, coverage and reconciliation; entitlement is unverified. |
| Other sources | SEC as-of helpers, FRED/ALFRED vintage joins, French attribution and OpenFIGI mapping exist. | Presence establishes neither trained features nor complete historical membership or Nasdaq/Treasury/Cboe/Stooq datasets. |

Local credential names existed, without values printed/loaded or vault reads; presence proves no validity/entitlement. The cloud-only absence claim does not apply locally. Retained private manifests describe historical observations, not fresh availability.
Spec 058 T009 reports EXCLUSIONS with single-source limits ([tasks](../../../.specify/specs/058-edge-research-program/tasks.md) at baseline); inspected Fidelity inputs did not establish spec 061 allocation binding.
Spec 058 research remains FAIL ([results](../spec-058/results-20261016.md) at baseline). Spec 061's buffered ETF allocation is not a fitted stock-selection model and claims no edge. Spec 060's final ETF CSV is unpublished; #255 fixes class reservation.
Spec 062 produces data-collection candidates, not approved training/trading instruments. Next: reviewed delivery, dated classifications, licensed raw bars, independent OHLCV/actions, preregistered costed research with purged/embargoed CV and fresh prospective validation, then account evidence and Camden's LIVE gate.
Static survivor snapshots cannot reconstruct historical members/delisting returns. Old queue labels need individual reconciliation. Spec 063 is a separate protected draft; deposits do not automatically raise authority.
Current-head acceptance requires [PR #256 checks](https://github.com/cstroh01/Quant-ML-Bot/pull/256/checks); reproduce contracts with `python -m pytest tests/test_062_research_universe.py`.
