# Tasks: 058 — preregistered multi-asset edge research program

Every code unit runs in this order:
1. Red tests first.
2. A Rule 12 driver in `tests/mutation/`, with an unchanged-copy control.
3. At most 300 changed lines.
4. The full suite.
5. Ledger hashes recorded before and after the unit.

Labels:
- **HUMAN GATE**: Camden acts.
- **Codex**: a bounded fetch on Camden's PC after his "go".

Order matters: D-1(a) requires T006 to land before T007.

## Phase 0 — governance and baseline
- [ ] T001 **HUMAN GATE — SCOPE amendment (D-2), Camden.**
  - Files: `docs/SCOPE-V1.md` only, in its own PR.
  - Change: replace the 5-ticker universe statement with the §4 ETF universe.
  - Keep: the survivorship limitation, reworded for ETFs (closures absent).
  - Camden reviews and merges.
- [ ] T002 **Spec 033 family-N amendment.**
  - Files: `.specify/specs/033-trial-ledger-dsr-pbo-gate/spec.md` only (a dated decision line, citing 058 D-1).
  - Content:
    - Gate 3 may evaluate a preregistered family at `N_family` while D-1's four conditions hold.
    - The lifetime-`N` DSR is always computed and published beside it.
- [x] T003 Baseline.
  - Files: `docs/implementation/spec-058/baseline-<YYYYMMDD>.md`.
  - Record:
    - the suite counts
    - the ledger hashes
    - proof that no §4 ticker appears in `scripts/`, `reports/` or `docs/trials/`
- [ ] T004 **HUMAN GATE — module placement, Camden.**
  - The repo has no portfolio-level (multi-asset weights) accounting today; `backtest_harness.run_backtest` is single-asset.
  - Proposal:
    - a new `scripts/portfolio_backtest.py` owns weights→fills→P&L for a panel
    - a `CLAUDE.md` module-table row is added in a separate governance PR
  - Signals stay in `scripts/signals.py`; sizing stays in `scripts/portfolio_risk.py`.

## Phase 1 — preregistration and seal (before any §4 data exists)
- [x] T005 Family declaration contract. _(done: #126)_
  - Files: `tests/test_058_family.py`, then `scripts/trial_registry.py` (an additive declaration record type).
  - The declaration carries:
    - the §5 table
    - the selection rule
    - the holdout date
    - the `N_family` cap
    - the universe
    - the 046 cost-model version
    - the SHA-256 of `spec.md`
  - A run in family `058-edge` without a matching declaration is refused.
  - Exceeding the cap reverts the family to lifetime N, and the run says so.
  - Synthetic ledger only.
- [x] T006 **HUMAN GATE — write the declaration to the real ledger, Camden.**
  - A one-command write. Camden runs it; agents never write `docs/trials/`.
  - Record the resulting ledger hashes.
  - Done 2026-10-09T20:58Z (commit df477f8b, `docs/trials/families/058-edge.json`), before D-8 and D-9.
- [x] T006a **HUMAN GATE — Camden runs `python scripts/amend_family.py 058-edge --record` (D-8, D-9).** _(done: #200, #206)_
  - Camden chose an additions-only amendment over redeclaring (chat, 2026-10-12 20:57 CT: "A").
  - Adds only `gate3` and `common/sizing`; any changed or removed frozen value is refused.
  - Until it is recorded, `verify_family("058-edge")` refuses on source drift, so no 058 trial can start.
  - Must run before any 058 trial: one trial makes the declaration final.
- [x] T007 Holdout seal contract (FR-002). _(done: #145)_
  - Files: `tests/test_058_holdout.py`, then the loader path that serves §4 data.
  - Sessions ≥ 2023-10-02 are refused without a one-shot token bound to the selected configuration hash.
  - A second use of the token is refused.
  - Mutants:
    - the cutoff shifted by one session
    - the token reused
    - the token bound to a different hash

## Phase 2 — data (Codex, after T006)
- [x] T008 **Codex — bounded fetch, Camden's "go".** Tiingo EOD for the 25 §4 tickers, full history.
  - The script refuses to run unless the T006 declaration hash is present.
  - Raw data stays private. A sanitized manifest is published per FR-005.
  - The check source is Alpaca raw SIP, 2016 onward.
  - Done (Camden tick, 2026-10-15): fetched 2026-10-09, manifests `T008-fetch-20261009.md`,
    `t008-tiingo-20261009.json`, `t008-alpaca-20261009.json`; 75/75 private bodies re-hashed before T009.
- [x] T009 Cross-source and corporate-action checks (056 FR-004, Rule 14).
  - Disagreements are excluded or disclosed, never averaged.
  - Evidence: `docs/implementation/spec-058/data-check-<YYYYMMDD>.md`.
  - Done 2026-10-15 (Camden, chat, 16:43 CT: "A"): `data-check-20261015.md`, status EXCLUSIONS, 290 excluded
    ticker-sessions, panel hash `3b80b330`. Strict D-10: mismatched actions are not applied and their sessions
    are excluded.

## Phase 3 — strategies and accounting (after T004)
- [x] T010 Portfolio accounting. _(done: #165)_
  - Files: `tests/test_058_portfolio.py`, then the T004 module.
  - Execution: signal at close `t`, fill at the open of `t+1`.
  - Costs: spec 046's model.
  - Instruments: a ticker with no row on a session is not tradable that session.
  - The test includes a hand-computed two-asset oracle.
- [x] T011 Signals H1–H8. _(done: #166)_
  - Files: `tests/test_058_signals.py`, then `scripts/signals.py`.
  - Per hypothesis:
    - a lookahead test (perturbing future rows leaves the current signal unchanged)
    - a listing-date test (no signal before the full lookback has been observed)
- [x] T012 Sizing. _(done: #169, #179, #212)_
  - Files: `scripts/portfolio_risk.py`. Reuse `volatility_target_weights` and `apply_gross_cap`.
  - Add tests only where behavior is new: the 10% target and gross ≤ 1.0.
- [x] T013 Combos H9/H10 and Rule 4 baselines. _(done: #169, #192, #220)_
  - Baselines: equal-weight buy-and-hold and a seeded random signal.
  - Baselines use the same period and costs as the candidates, and are excluded from `N_family`.

## Phase 4 — research runs (after 046 T001/T002; D-5)
- [x] T014 Walk-forward runner. _(done: edge_walk_forward + run_058_t015; §5 selection in run_058_t016.selection, #238)_
  - Purged and embargoed (Rule 2), with the embargo ≥ the longest lookback.
  - The research window ends at 2023-09-29.
  - Every run goes through `research_attempt(family="058-edge")`.
- [x] T015 Run all 15 configurations once. _(done: 2026-10-16, ledger 808 events head 144024934a68; resumed after a GitKraken auto-stash interruption (#230))_
  - Record:
    - the family DSR at `N_family`
    - the lifetime-N DSR
    - HAC t
    - PBO (S = 16)
    - baselines
    - folds, purge, embargo and costs
  - Apply the §5 selection rule.
  - Result-bearing; reviewed before publication.

## Phase 5 — holdout and gate
- [x] T016 **HUMAN GATE — holdout run, Camden authorizes.** _(done 2026-10-16, authorized in chat: H10, 758 sessions, D-4 pass; ledger 854, head fb604ba367d1)_
  - One run of the selected configuration on sessions ≥ 2023-10-02, recorded in the ledger.
  - Pass condition: D-4.
- [x] T017 Gate 3 evidence artifact (033 Phases 8–9). _(done: reports/artifacts/capital_gate/gate3/5779c9c5…json, failed; verdict FAIL)_
  - The verdict is PASS only if the research-window Gate 3 passes **and** D-4 passes.
  - Otherwise FAIL, published as it is.
- [x] T018 Publication. _(done: docs/implementation/spec-058/results-20261016.md, README)_
  - Content:
    - the tearsheet
    - limitations
    - the FR-006 fields
    - README truthfulness
  - A PASS hands off to spec 053's shadow sessions and the PAPER clock. It never arms LIVE.
