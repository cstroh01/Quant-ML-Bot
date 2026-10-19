# Integration audit — local reconciliation, 2026-10-18 America/New_York

Source inspection baseline: public main `c1dbc854b146095cd47283ef4cbc1b5838f20d94`;
software checkpoint #256: `c57e0f38dd64f933b0f488ecbb44942460588330`.
Operational statements reflect the dated inspection, not fresh account proof.
Camden chose free data, US stocks/ETFs, and no OTC, leveraged or inverse products.

| Area | Existing evidence | Remaining acceptance |
|---|---|---|
| Fidelity | LIVE adapter, guarded loop and private dispatch exist. Public production policy is $200/unarmed. Unexpected security challenges need intervention. | PAPER sessions, previews/holdings, settled cash/budget evidence and final arming SHA; unattended operation remains unproven. |
| Host | Hosted fixture reports exist without establishing production PAPER operation. The inspected Windows PAPER task was disabled; its last run was unsuccessful. Current Fidelity task/preview/holdings evidence was not found at configured paths; older private holdings evidence exists. | Account/host acceptance, notifications and dedicated-host compatibility; inspection does not rule out activity elsewhere. |
| Alpaca/Tiingo | `data_sources.load_058_panel`, `paper_loop.fetch_sleeve_closes`, `fidelity_inputs.build_bundle` and recorded research consume them. | Fresh entitlement, breadth, independent actions and nominal-data acceptance remain dataset-specific. |
| EODHD | Private generic fetching and saved observations predate #257's reusable bounded adapter. Its T009 follow-up refuses unchecked splits/unknown labels. | No credentialed acceptance here. Spec 044 owns split verification; explicitly configure `key_env="EODHD_API_TOKEN"` for the existing local name. |
| Massive | Offline proposal #198 stays held, absent from main. | Contract/terms, endpoint migration, coverage and reconciliation; entitlement is unverified. |
| Other sources | SEC as-of helpers, FRED/ALFRED vintage joins, French attribution and OpenFIGI mapping exist. | Source presence does not establish trained features, historical membership or complete Nasdaq/Treasury/Cboe/Stooq datasets. |

Local credential names were present; values were neither printed nor loaded into a job, and no Fidelity vault was read.
Key presence establishes no validity or entitlement. The cloud-only absence claim does not apply locally.
Retained private provider/action manifests describe historical observations, not fresh availability.
Spec 058 T009 reports EXCLUSIONS with single-source limits (see its [tasks](../../../.specify/specs/058-edge-research-program/tasks.md) at the baseline).
Inspected Fidelity inputs did not establish spec 061 allocation binding.

Spec 058 research remains FAIL (see [results](../spec-058/results-20261016.md) at the baseline).
Spec 061's buffered ETF allocation is not a fitted stock-selection model and claims no edge.
Spec 060's final ETF CSV is unpublished; #255 fixes class reservation.
Spec 062 screens data-collection candidates, not approved training/trading instruments.
Next: reviewed delivery, dated classifications, licensed raw bars, independent OHLCV/actions,
preregistered costed research with purged/embargoed CV and fresh prospective validation,
then account evidence and Camden's LIVE gate. Static survivor snapshots cannot reconstruct
historical members or delisting returns. Old queue labels require individual reconciliation.
Spec 063 is a separate protected draft; deposits do not automatically raise authority.
Current-head acceptance requires [PR #256 checks](https://github.com/cstroh01/Quant-ML-Bot/pull/256/checks).
Reproduce software contracts with `python -m pytest tests/test_062_research_universe.py`.
