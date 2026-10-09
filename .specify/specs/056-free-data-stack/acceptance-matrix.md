# 056 acceptance detail: adopted M01–M10

Amendment 2026-10-09, F02 / T007. This transcribes the ten rows already adopted by spec.md
FR-007 from Codex's dated 2026-10-07 proposal into repository-readable acceptance detail.
It removes the private-file dependency. It does not certify that an implementation passes.
M11–M23 in the historical proposal are outside this adoption and are not added here.

Every row needs an unchanged valid control and a planted defect failing the named consuming
assertion. Import, collection, environment and network failures are not mutation kills.
Hand-enumerated fixtures must say EXAMPLE — NOT A RESULT. Record the exact tested source revision,
test/node, command, control result and intended failing assertion before calling a row complete.

| ID | Gate / plausible mutant | Field read by the consuming gate | Required failing assertion and control |
|---|---|---|---|
| M01 | Unknown rights treated as allowed | public_derived_permission | Public chart admission refuses rights_unverified; synthetic control admitted. |
| M02 | Private research permission reused for raw export | public_raw_permission | Export gate refuses even when private analysis is approved; explicit allowed-export control passes. |
| M03 | Terms review date ignored | contract expiry/hash | Expired or changed contract invalidates affected permission; current unchanged control passes. |
| M04 | SIP request silently falls back to IEX | request/response feed provenance | Bundle contract refuses feed mismatch; explicit SIP control passes. |
| M05 | Adjusted field wired as raw Close | mapped field/basis | Hand-enumerated split fixture detects nominal price mismatch; correct raw mapping passes. No estimator-derived oracle. |
| M06 | Adjusted volume labeled nominal | declared volume basis | Impact consumer refuses or detects exact share-volume mismatch; nominal control passes. |
| M07 | Split-day factor includes same-day split | effective session comparison | Split-date nominal values differ from literal expected values; prior-day and correct split-date controls retained. |
| M08 | Latest partial/future row admitted | completed-session cutoff | Off-by-one, half-day and future-timestamp assertions refuse; weekend, DST and valid completed-session controls pass. |
| M09 | NYC daily label converted via UTC | session date normalization | Literal session-date equality fails across DST; naive and exchange-local controls agree. |
| M10 | Provider pagination stops after first symbol | next_page_token/coverage | Requested security/session completeness fails; multipage control covers all requested symbols. |

## Evidence status and boundaries

This file defines assertions, not an observed green/red record. Existing offline adapter evidence
is in artifacts/; a row closes only when its exact consuming path and controls are cited.
An adapter test that only checks a metadata label cannot close an impact or publication gate.
No rights are inferred from free access. No timestamp convention, source permission, volume basis,
production cache, broker behavior, ledger append, SafetyConfig or capital gate changes here.
T006's separate authorized first-fetch and hashed-manifest acceptance remains open.
No source-admission result establishes historical survivorship coverage or profitable trading.
