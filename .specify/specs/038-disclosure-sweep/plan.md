# Implementation plan: Rule 11 / Rule 16 disclosure sweep

Queue Q17, report-only output from merged spec 038 (PR #43). Created 2026-10-07 against main `457c5b6242f6c1f6338653487914a4115dd66efa`. This plan adds no code, test, dependency, result, governance edit or implementation permission. D-1–D-5 remain open; Q18 tasks follow only after this plan is reviewed/merged. Camden owns Git.

## Authority, ownership and order

Spec.md is authoritative over recommendations here. All its default dispositions remain intact; no X figure becomes an accepted quotation while D-5 is open. The 2026-10-03 audit is an inventory, not current results or proof of completed remediation. Re-read sites by string before each unit because 047 and future work move lines.

047 goes first on `BacktestTearsheetView.tsx`, `routes/backtest.py`, `schemas.py` and `api.ts`. 035 owns the reconciliation label; 036 owns bundle provenance; 046 owns modeled-cost wording; 033 owns DSR-dependent Sharpe flag removal; 049 owns paper surfaces. Adopt their fields rather than add duplicates. Never edit pinned `logistic_baseline.py`, `feature_set_comparison.py` or `multi_ticker_comparison.py` in an autonomous unit. Never run 033 and 038 against capital_gate.py together.

Every implementation unit is at most 300 added-plus-removed lines including tests/evidence/status. Measure against pre-unit copies without Git. Stop for a plan subdivision/revision if the complete unit exceeds the cap; do not compress or drop tests. Implement one admitted unit at a time. Full-suite command is `python -m pytest tests`; Windows venv is the acceptance gate, Python 3.12 CI is separate evidence.

## Decisions required before consuming them

- D-1: propose `scripts/disclosure.py`, a pure text/provenance helper. Its CLAUDE module-table row is a human governance edit; no unit guesses placement.
- D-2: leave PROJECT_CONTEXT figures S by default. A specific G choice needs a named source and a human network task if regeneration needs new market data.
- D-3: propose same-line `EXAMPLE — NOT A RESULT` labels for the placeholder folds. Serving actual fold configuration is a different API contract and must be chosen first.
- D-4: propose full inline register on README/tearsheet and an unmissable same-surface reference on other panels/views. Do not decide for Camden.
- D-5: absent-source quotations remain blocked. Recommend striking X figures rather than loosening Rule 11. Other accepted interpretations/quarantine need explicit human authority and may require a dedicated constitution amendment.
- M9 and all browser-render claims require the 047 D-1 runtime test runner. A TypeScript source scan is not acceptance.

## Design

The D-1 module owns one register copied verbatim from SCOPE §6, a Sharpe status string, and provenance serialization. Its register parity test parses the actual section boundaries and compares both directions; it cannot test against a duplicated expected list alone. Keep the dividend bound and no-real-capital items, currently missing from README.

Provenance is plain `list[str]` at the Python boundary and a typed API object at the wire. Fields: source artifact and SHA-256, source_identity git_sha or `unknown`, workspace_state, trial id or `none (descriptive, not a trial)`, and aware UTC run time from an injected clock. Data-session end is separate. No Git, network, cached commit, date.today(), inferred trial or invented source.

`plotting.save_figure` consumes a supplied plain stamp, draws a reserved margin and rejects no stamp. It imports no disclosure/trial/strategy module. Migrate all five callers in the same review unit: ma_crossover_backtest, return_stats, data_pipeline_sanity_check, autocorrelation_check, stationarity_check. The latter two stop bypassing save_figure. If the full caller migration cannot fit, subdivide this plan before implementation rather than leave a broken intermediate signature.

The API formats existing provenance and records the actual evaluation fields; it does not evaluate DSR/PBO. Do not remove provisional flags because a module exists. Only 033 current eligible-series evidence may authorize that change. Web views render shared provenance/limitations components from the response, show unknown/null as unavailable, and read actual API values instead of historical literals.

Static Q banners sit at one explicit anchor: first nonblank content line for Markdown, first element inside body for HTML. A document containing any unresolved X figure is Q-pending-D-5 until its disposition is decided; a banner alone cannot close it. S blocks are removed, replaced by a ledger-entry pointer where one exists, otherwise a valid dated quotation/source pointer. A pointer to an unresolved quotation is not accepted results provenance.

G summaries are small committed artifacts under `docs/implementation/spec-038/artifacts/`, with input hashes, source_tree_hash, producing source_identity SHA and date. The artifact cannot claim its own commit. No new outcome figure, production trial/cache write, or network in regeneration tests. If a figure cannot be sourced/regenerated, use S under the recorded disposition.

## Complete disposition and ownership register

Rows cover spec §3 and audit §1–§3. The Q18 tasks register must expand grouped globs into exact paths before any edit; it must fail admission for an unassigned new surface.

| Surface | Disposition / owner | Unit family |
|---|---|---|
| ma_crossover_backtest main, format_comparison, price/SMA figure | Runtime stamp/register, trial id, modeled-cost owner 046 | P, F |
| logistic_baseline panels/comparison | Runtime, pinned human lane | H |
| feature_set_comparison verdict/report/checkpoint panel | Runtime, pinned human lane | H |
| feature_diagnostics format_report | Runtime source/stamp/register | P |
| return_stats moments, return/Sharpe and histograms | Runtime stamp/register, printed caveat/flag | P, F |
| autocorrelation_check ACF panel/plot | Runtime stamp/register | P, F |
| stationarity_check ACF/ADF/verdict/plot | Runtime stamp/register | P, F |
| scratch_aapl_correlations | Runtime input filename/hash/date | P |
| scratch_multiticker_collinearity | Runtime input filename/hash/date | P |
| plotting.save_figure and data_pipeline_sanity_check caller | Mandatory figure stamp; shape-only output excluded | F |
| tearsheet API metrics/equity/trades/baselines | Runtime provenance/register/Rule 15; bundle owner 036 | A |
| tearsheet holding_bars constant | S or compute from actual trade sessions; chosen before code | A |
| served drawdown anchor vs metrics.max_drawdown | One stated anchor, contract for curve/card equality | A |
| reconciliation_passed | 035 FR-007 label, adopt without duplicate wording | 035 |
| data ohlcv/stats/gaps and diagnostics routes | Runtime selected CSV/hash/run time | A |
| data fallback ticker list | S; empty with reason when cache absent | A |
| ml_rundown route and pane | Runtime; last bar labelled separately from run time | A, V |
| api.ts omitted provenance fields | Add typed API fields in matching route/view unit | A, V |
| tearsheet cards/charts/baseline Sharpe/TutorCard/Rf/badge | Runtime response values, flags and register; Sharpe bands S | V |
| friction/chart basis/null drawdown | 047, never reassigned | 047 |
| MarketDataView literals/caption/results | Literal S; partial reconciliation limitation and runtime stamp | V |
| FeatureDiagnosticsView literals/threshold claims/missing zero | S; null unavailable, runtime stamp/register | V |
| CrossValidationView placeholder folds | D-3 label or real API; no guessed choice | V |
| capital_gate overall_readiness and TutorCard | S; view consumes actual API definitions/status | A, V |
| NotComputed / TESTS: NOT REPORTED / evidence validation | Retain existing compliant behavior | Unchanged |
| AUDIT.md, REMEDIATION_PLAN.md, remediation-map.html | Q for committed-source figures; X Q-pending-D-5; Sharpe flags | D |
| Broken audit coverage.csv pointers | Replace with actual coverage.json | D |
| NIGHT_RUN_SUMMARY and cleanup-audit files | Q-pending-D-5; probe arithmetic gets example label | D |
| Closed specs 002/006/012/014/017 result sections | S for absent sources | D |
| Closed spec 009 unsourced result section | S | D |
| PROJECT_CONTEXT result blocks in spec §3 | S unless D-2 explicitly selects evidenced G | D |
| PROJECT_CONTEXT “Sharpe output trusted” claim | S; replace with current Rule 15 requirement | D |
| Six unsourced plots, three duplicated pairs | S; no deletion until exact approved path inventory | D |
| Audit labelling rows §3, lines 128–133 | Same-line example labels, unchanged values | D |
| README | G text/register, no new performance figure | D |
| reports/web/README.md | G product/reproduction text and register | D |
| 049 report/monitor and paper_targets | 049, not this sweep | 049 |

No audit figure is upgraded from quotation to present result. The tasks file must list every exact Q/S/G path, anchor and figure line after current inspection; the grouped inventory is a planning map.

## Review units and dependencies

- B: baseline and exact-path inventory. Read only except evidence. Record full suite, source revision, Python, all trial-file hashes/returns absence and overlapping ownership.
- R: shared register/provenance helper plus parity, clock and source-identity contracts. Depends on D-1/D-4; include governance row via human lane. Model and descriptive stamps are distinct.
- P1: return_stats and feature_diagnostics panels/flags. P2: ACF/stationarity panels. P3: scratch correlations/collinearity panels. P4: MA main/comparison panel. Each separately admitted, depends on R, preserves its actual artifact/trial identity.
- F: save_figure signature plus all five callers and stamped-output contracts. Depends on R and completed P units where shared. Subdivide only through plan revision if complete migration exceeds cap.
- A1: tearsheet provenance and dropped real fields; retain 047 friction/bar fields and 035 label. Depends on R and 047 shared-file handoff. A2: data/diagnostics CSV source. A3: ml_rundown UTC/source. A4: holding-bars/drawdown-anchor with boundary/gap contracts. A5: capital definitions/readiness labels; wait for 033 ownership release.
- V0: shared banner/register components and types. V1 tearsheet; V2 data/diagnostics; V3 ml rundown; V4 CV; V5 capital. Each depends on matching API unit, D-3/D-4 where relevant, 047 file release and the chosen runtime test method. No runner means render acceptance stays open.
- D1: exact-path Q banners/flags only on allowed committed-source documents. D2: each closed-spec S group. D3: PROJECT_CONTEXT strikes/Rule 15 replacement. D4: labelling-only examples and corrected links. D5: README/web README. D6: exact approved unsourced plot removals. X quotations wait on D-5; G regeneration waits on D-2/source authorization.
- H: human-lane pinned panels with the same consuming tests/provenance rules. Do not claim sweep complete without these; the scope explicitly leaves them human-owned.
- C: full acceptance matrix, suite/mutants/unchanged protected manifest, per-unit line counts and remaining limitations. No release closure based on only focused green tests.

These are plan families, not unchecked numbered tasks. Q18 assigns task IDs and complete per-unit file sets after this plan merges. It must separately scope oversized A/V/D groups rather than assume they fit.

## Rule 12 and meaningful controls

| Mutant | Actual consumer and proof | Control |
|---|---|---|
| M1 | Real parsed SCOPE/register parity drops dividend bound; separate temp SCOPE edit | Full parity both directions |
| M1b | README removes one exact register item | Full updated README |
| M2 | Stamp reuses old commit after synthetic HEAD changes; clear GITHUB_SHA | Same tree stable, restored lookup |
| M3 | Run UTC date replaced with last-bar date | Injected clock later than bar |
| M3b | Naive/local date at 02:00Z in New York | UTC clock; noon same-date control |
| M4 | Real stdout Sharpe flag removed; assert at least one numeric Sharpe line matched | Flagged stdout |
| M5 | save_figure accepts missing stamp | Valid stamped file/render |
| M6 | Actual tearsheet limitations omitted or empty | Exact full register response |
| M7 | Copy loses banner at declared anchor | Complete anchored Q document |
| M8 | Numeric-before-Sharpe line loses flag in copy | Complete flagged sentence |
| M9 | Actual results view stops rendering banner | Runtime render all views; conditional runner |

Each kill must carry its own refusal/assertion message, not an import/type/compile failure or another gate. Mutation_support_019 catches any AssertionError, so each oracle has one contract assertion and setup does not assert. Copies/in-memory only; original bytes unchanged. The Sharpe matcher is case-insensitive and matches numeric figures on either side in the same sentence, with a positive-match fixture and false-positive controls.

Time contracts include UTC midnight, session-naive labels, naive clock refusal, first/last/fold boundaries and calendar gaps for holding-bars/drawdown. Source fixtures contain no real strategy/account results, no production cache and no socket calls. Rendered stamped figures are visually inspected so clipping a banner cannot pass a string-only test.

## Close-out and known limits

FR-001–FR-005 runtime coverage, static disposition coverage, full suite and exact red/restored-green controls are separate evidence rows. Hash every docs/trials file before/after, not only trials.jsonl, and preserve absent returns/. Record source hashes for shared/pinned-fingerprint callers and leave 021 close-out unresolved where hashes changed. No human decision, missing source, unsupported render gate or pinned task becomes done merely because this plan exists. Add no result figure and no dependency without Rule 6 justification and the selected human authorization.
