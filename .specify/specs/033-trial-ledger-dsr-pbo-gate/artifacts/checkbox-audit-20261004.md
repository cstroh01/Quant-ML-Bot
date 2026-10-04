# Spec 033 checkbox audit — 2026-10-04

Cloud-lane queue item **Q5** ("033 checkbox reconciliation with evidence per
task"). This is a report only. It changes no checkbox. `tasks.md` is unchanged.
Camden decides which boxes to tick.

- **Tree audited:** `origin/main` at `fc8f442`, read on 2026-10-04 (UTC).
- **Method:** every task in `tasks.md` was checked against the files it names,
  the evidence logs in `docs/implementation/spec-033/`, and the two handoffs
  (`HANDOFF-phase6.md`, `HANDOFF.md`). Nothing under `docs/trials/` was written.
  Hashes were recomputed from read-only copies in memory.
- **No result figures.** Every count below is a test count or a hash. None of
  them is an investment result.

## Why this audit exists

`docs/V1-FINISH-PLAN.md:105-107` says the 033 checkboxes are unreliable. Ten
boxes are ticked: T036 and T047–T055. Most of Phases 1–6 has evidence on disk
but no tick. The plan says to reconcile the boxes before anyone dispatches
Phase 8, so the next agent does not redo finished work.

## Verdict legend

| Verdict | Meaning |
|---|---|
| **EVIDENCED** | The artifact or behavior the task names exists, and a recorded run shows it. Safe to tick. |
| **PARTIAL** | Some of it exists. The gap is named. Do not tick yet. |
| **HUMAN** | The task is Camden's own action. Evidence is listed; only Camden can confirm it. |

A fresh-context review corrected four first-draft verdicts: T014, T034 and T035 moved to PARTIAL, and T032 moved from HUMAN to EVIDENCED (gated on T031).
| **NOT STARTED** | The named file or behavior does not exist on `main`. |

## Summary

| Phase | Tasks | Ticked now | EVIDENCED | PARTIAL | HUMAN | NOT STARTED |
|---|---|---|---|---|---|---|
| 1 Baseline | T001–T006 | 0 | 6 | 0 | 0 | 0 |
| 2 US1 tests | T007–T015 | 0 | 8 | 1 | 0 | 0 |
| 3 US1 impl | T016–T024 | 0 | 8 | 1 | 0 | 0 |
| 4 Backfill | T025–T033 | 0 | 7 | 1 | 1 | 0 |
| 5 Stats tests | T034–T041 | 1 (T036) | 3 | 5 | 0 | 0 |
| 6 Stats impl | T042–T046 | 0 | 3 | 2 | 0 | 0 |
| 7 PBO | T047–T055 | 9 | 9 | 0 | 0 | 0 |
| 8 Gate 3 tests | T056–T061 | 0 | 0 | 0 | 0 | 6 |
| 9 Gate 3 impl | T062–T069 | 0 | 0 | 0 | 0 | 8 |
| 10 Final | T070–T075 | 0 | 0 | 2 | 0 | 4 |
| **Total** | **75** | **10** | **44** | **12** | **1** | **18** |

All ten current ticks are supported. No tick needs to be removed.

## Phase 1 — Baseline, inventory, frozen contracts

| Task | Verdict | Evidence |
|---|---|---|
| T001 | EVIDENCED | `docs/implementation/spec-033/T001-baseline.txt`; `HANDOFF-phase6.md:21` records 750 collected, 723 passed, 18 failed, 9 errors, and does not call that suite green. |
| T002 | EVIDENCED | `T002-registry-baseline.txt`: 10 passed (`HANDOFF-phase6.md:22`). |
| T003 | EVIDENCED | `tests/fixtures/spec_033/runner_inventory.json` lists call sites with a `classification` per site and is labelled `EXAMPLE — NOT A RESULT`. |
| T004 | EVIDENCED | `tests/test_033_trial_ledger.py:1` opens with "Migration path 2: upgrade trial_registry in place; retire its optional writer." |
| T005 | EVIDENCED | `tests/fixtures/spec_033/paper_inputs.json` and `cscv_oracle.json` both carry `label: EXAMPLE — NOT A RESULT` and a `source` key. |
| T006 | EVIDENCED | `tests/spec033_support.py:8-13` freezes event, return, backfill, matrix and Gate 3 field sets plus the reason codes. |

## Phase 2 — US1 tests

| Task | Verdict | Evidence |
|---|---|---|
| T007 | EVIDENCED | `tests/test_033_trial_ledger.py:21` (`test_every_result_choice_changes_hash`) and `:28` (defaults, ordering, paths, finiteness). |
| T008 | EVIDENCED | `test_033_trial_ledger.py:43` (start before callback, duplicates, error, abandoned, interrupted). |
| T009 | EVIDENCED | `test_033_trial_ledger.py:69` (`test_sidecar_complete_atomic_and_bound`); funded-account and net-cost eligibility at `test_033_dsr.py:48-50` (`unfunded`, `no_costs`). |
| T010 | EVIDENCED | `test_033_trial_ledger.py:87` (`test_chain_defects_name_record_or_path`, parametrized defects). |
| T011 | EVIDENCED | `test_033_trial_ledger.py:115` (`test_source_identity_full_sha_no_subprocess`). |
| T012 | EVIDENCED | `test_033_trial_ledger.py:145` (crash after fsync) and `:166` (multiprocess append, stale lock). |
| T013 | EVIDENCED | `test_033_trial_ledger.py:179` (production default versus injected synthetic ledger); `:185` asserts `log_trial` is retired. |
| T014 | **PARTIAL** | `tests/test_033_trial_instrumentation.py:35-55` has the guard, a planted bypass with clean control, and an aliased bypass. But the task says the guard is built "from T003's inventory". `bypasses()` (`:10-33`) never reads the inventory. It exempts calls by folder only, scanning `scripts/` and `reports/api`. `:37` only asserts that the inventory's `calls` list is non-empty. |
| T015 | EVIDENCED | `T015-ledger-red.txt`: 33 assertion failures and 1 clean-control pass, no import or collection errors (`HANDOFF-phase6.md:23`). |

## Phase 3 — US1 implementation

| Task | Verdict | Evidence |
|---|---|---|
| T016 | EVIDENCED | `scripts/trial_registry.py:52` `canonical_json`, `:60` `digest`, `:77` `canonical_config`. |
| T017 | EVIDENCED | `scripts/trial_registry.py:94` `source_identity`, which reads `.git` metadata directly; T011 forbids a `git` subprocess. |
| T018 | EVIDENCED | `trial_registry.py:261` `start`, `:271` `finish`; `:248` counts candidate starts as `n_post_ledger`. |
| T019 | EVIDENCED | `trial_registry.py:130` `validate_rows`, `:146` `immutable_write`. |
| T020 | EVIDENCED | `trial_registry.py:160` `serialized`, `:203` `verify`, `:250` `_append`. |
| T021 | EVIDENCED | `scripts/trial_runner.py:48` `run_trial`, `:119` `research_attempt`. |
| T022 | EVIDENCED | `tests/test_trial_registry.py:6-8` keeps the sole production path and asserts `log_trial` is gone. |
| T023 | **PARTIAL** | The call sites are wrapped and inventoried. `HANDOFF-phase6.md:56-60` says legacy runners' semantic OOS/CV/cost provenance is incomplete and needs per-runner review before FR-003/FR-013 acceptance. Spec 043 later made production recording fail closed (`trial_registry.py:30-50`), and 043 T025/T027 are still open. |
| T024 | EVIDENCED | `T024-ledger-green.txt`: 57 passed, 3 subtests passed. |

## Phase 4 — US2 backfill

| Task | Verdict | Evidence |
|---|---|---|
| T025 | EVIDENCED | `tests/test_033_backfill.py:15` (`test_campaign_schema`). |
| T026 | EVIDENCED | `test_033_backfill.py:20` (Cartesian, addition, upper endpoint, round, then double). |
| T027 | EVIDENCED | `test_033_backfill.py:29` and `:45` (no downward supersession; prior counts read without a caller reminder). |
| T028 | EVIDENCED | `T028-backfill-red.txt`: 12 assertion failures (`HANDOFF-phase6.md:25`). |
| T029 | EVIDENCED | `scripts/trial_backfill.py:18` `calculate_backfill` (pure) and `:57` `write_backfill` (I/O kept separate). |
| T030 | EVIDENCED | `docs/trials/backfill/manifest.json`: 16 campaign rows with evidence and `spec_coverage`; `missing_spec_numbers` says "022-031 absent; do not fabricate campaigns". |
| T031 | **HUMAN** | The task names Camden. `manifest.json` `approval` records Camden Paul Stroh at `2026-09-22T23:04:33Z`, approved manifest SHA-256 `54b45a0a…6ba04`, `approved_n_backfill` 16777216. `BACKFILL_REVIEW.md:1` is titled "APPROVED; T032 COMPLETE". Only Camden can confirm the tick. |
| T032 | EVIDENCED (gated on T031) | `docs/trials/backfill/a47232be-3d05-4c36-b984-f11b29b12a25.json` exists. Its file SHA-256 is `2d8ef10d…45155`, which matches `BACKFILL_REVIEW.md:40`. Its embedded `sha256` (`fb61cc12…f008`) verifies against the artifact's other fields. Its `manifest_hash` `8cc9ef98…bcae` equals `digest()` of the current `manifest.json`. The superseded artifact `a6abdb76-…` is retained. Tick it together with T031. |
| T033 | **PARTIAL** | `T033-backfill-green.txt`: 13 passed. `test_033_backfill.py:53` asserts that no return sidecar is created. The task's other half, that backfill changes `N_current`, has no test that reads an immutable backfill artifact into `N_current` (see T039). |

## Phase 5 — US3 statistics tests

| Task | Verdict | Evidence |
|---|---|---|
| T034 | **PARTIAL** | `tests/test_033_dsr.py:27` (exact shared dates, sorted columns, digest, exclusions) and `:41` (invalid evidence, including `nan`, so no fill). The task's "one committed matrix hash" is not pinned: no test asserts a literal hash value. `:36` only checks that the hash is the same under a different column order. |
| T035 | **PARTIAL** | Present: `test_033_dsr.py:57-68` (missing session, first and last row, future-row perturbation with a current-row control); unequal boundaries at `:29-31`; duplicate, reordered, aware and non-midnight dates at `:40-46`. Missing: there is no fold-join test, despite the test name at `:57`. `HANDOFF.md:131` notes that not every T034–T040 clause is certified. |
| T036 | EVIDENCED (ticked) | `test_033_dsr.py:74-79`: N=88 gives 0.910153014744707 (EXAMPLE — NOT A RESULT) and fails 0.95; N=46 passes. `T046-approved-correction-green.txt`: 21 passed. |
| T037 | **PARTIAL** | `test_033_dsr.py:92-107` pins observed Sharpe, observation count, skewness, Pearson kurtosis and `n_current`. No direct unit test isolates the trial-Sharpe dispersion or the extreme-value benchmark. They are covered only through the paper formula at `:74-85`. |
| T038 | EVIDENCED | `test_033_dsr.py:86-90` covers five structured reasons. `:107` covers `selected_candidate_missing`. |
| T039 | **PARTIAL** | `test_033_dsr.py:97` builds `n = 64 + log.verify()["n_post_ledger"]` by hand. No test composes `N_current` from an immutable backfill artifact. `HANDOFF.md:132-133` names this gap. |
| T040 | **PARTIAL** | `test_033_dsr.py:109-120` has the hand-calculated HAC oracle, the lag ≥ horizon − 1 rule, the risk-free shift and non-positive SE. It has no exact `3.0` case and no case one representable value below. `HANDOFF.md:133` names the missing HAC gate boundary. |
| T041 | EVIDENCED | `T041-statistics-red.txt`: 21 assertion failures (`HANDOFF-phase6.md:27`). |

## Phase 6 — US3 statistics implementation

| Task | Verdict | Evidence |
|---|---|---|
| T042 | EVIDENCED | `scripts/selection_bias.py:23` `_eligible`, `:47` `build_matrix`. |
| T043 | EVIDENCED | `selection_bias.py:72` `deflated_sharpe` returns `undefined(reason)` structures (`:20`). |
| T044 | **PARTIAL** | `selection_bias.py:92` `matrix_dsr` takes `n_current` as an explicit input that is never a column count (`test_033_dsr.py:103`). Real lifetime-N composition from backfill plus ledger is pending (`HANDOFF.md:136-137`). |
| T045 | EVIDENCED | `selection_bias.py:106` `hac_t_stat`; `HANDOFF-phase6.md:64-65` says it reuses `metrics.mean_log_return_se`. |
| T046 | **PARTIAL** | Green: `T046-approved-correction-green.txt`, 21 passed. `HANDOFF.md:133-134` says "T046 is not retroactively marked fully complete", because of the T037, T039 and T040 gaps above. |

## Phase 7 — CSCV/PBO (all ticked)

All nine ticks are supported. Evidence: `T052-pbo-red.txt` (26 intended
failures), `T055-pbo-statistics-green.txt` (49 passed), `phase7-focused-green.txt`
(103 passed), `T055-pbo-profile.json`. Tests are in `tests/test_033_pbo.py:36-237`.
Code is in `scripts/selection_bias.py:119-263`.

## Phases 8–9 — Gate 3 artifact, API, Rule 12 (not started)

T056–T069 are NOT STARTED. None of these exists on `main`:

- `tests/test_033_gate3.py`
- `scripts/generate_gate3_evidence.py`
- `tests/mutation/run_spec_033_gate_mutants.py`

`reports/api/routes/capital_gate.py:3` still says no artifact is read, and every
gate returns `status="unknown"` (`:28-56`). Gate 3's text at `:41` is still
"Deflated Sharpe ratio remains positive…", which is the wording T064 replaces.

## Phase 10 — Final verification

| Task | Verdict | Evidence |
|---|---|---|
| T070 | NOT STARTED | `docs/audit-2026-09-12/REMEDIATION_PLAN.md:181` still assigns finding 30 to spec 035. |
| T071 | NOT STARTED | Depends on Phase 9 rendered fields. |
| T072 | NOT STARTED | Depends on Phase 9. |
| T073 | NOT STARTED | Task order puts it after Phase 9. For reference, today's clean-main run is in this audit's PR body, not here. |
| T074 | **PARTIAL** | A preliminary split is drafted (`HANDOFF-phase6.md:142-158`, `HANDOFF.md:110-115`), but marked "not final acceptance". |
| T075 | **PARTIAL** | A draft explanation exists (`HANDOFF-phase6.md:160-192`). The task names Camden, so only Camden can complete it. |

## Disagreements found

1. **`docs/STATE.md:62` lists a blocker that the tree says is cleared.** STATE
   says "033 Phases 8–9 | Backfill bounds for 8 campaign rows | Camden".
   `V1-FINISH-PLAN.md:101-103` says the same. But `BACKFILL_REVIEW.md` and
   `manifest.json` record Camden's approval on 2026-09-22, and the T032
   artifact exists. The remaining gate is different: `HANDOFF.md:140` says
   "Resume at Phase 8 only after Camden authorizes it."
2. **The manifest file hash in `BACKFILL_REVIEW.md:3` does not reproduce on
   Linux.** The review cites approval-envelope file SHA-256 `98c27aaa…54d7`.
   The LF checkout hashes to `d7a303ac…7bf5`, and a CRLF conversion hashes to
   `96a450c9…3765`. The *canonical* manifest hash `8cc9ef98…bcae` does match,
   and the T032 artifact embeds that same manifest. The likely cause is
   whitespace or encoding at commit time (`.gitattributes` normalizes to LF).
   This is not a count change. Camden may want to confirm it on Windows.
3. **`tasks.md:8-9` still says "No task below is completed by the
   spec-writing change."** The checkpoint at `:338-345` reports progress. A
   reader of the header alone would undercount.

## Proposed checkbox changes for Camden

- **Tick (EVIDENCED, 33):** T001–T013, T015–T022, T024–T030, T038, T041,
  T042, T043, T045.
- **Tick only on Camden's own confirmation (1 + 1):** T031. T032 is
  EVIDENCED but is gated on T031, so tick it at the same time.
- **Leave unticked (PARTIAL, 12):** T014, T023, T033, T034, T035, T037, T039,
  T040, T044, T046, T074, T075.
- **Leave unticked (NOT STARTED, 18):** T056–T073.
- **Keep ticked (10):** T036, T047–T055.

The smallest unit that turns the PARTIAL statistics rows into EVIDENCED is a
tests-only change in `tests/test_033_dsr.py`:

- an exact-3.0 and one-below HAC boundary case (T040);
- `N_current` composed from a synthetic immutable backfill artifact plus ledger
  starts (T039, and the integration half of T033);
- isolated dispersion and extreme-value benchmark checks (T037);
- a fold-join case (T035) and a committed literal matrix hash (T034).

That would close T046. T014 separately needs the guard to read
`runner_inventory.json` for its test-only exemptions. It is not part of this report.
