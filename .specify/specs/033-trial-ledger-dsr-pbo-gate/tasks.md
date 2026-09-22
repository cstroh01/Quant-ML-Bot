---
description: "Implementation task list for spec 033 — lifetime trial ledger, DSR, PBO, and Gate 3"
---

# Tasks: Lifetime Trial Ledger, DSR, PBO, and Capital Gate 3

**Input**: `spec.md`, `plan.md`, and `research.md` in this directory.  
**Current task boundary**: This file is a future implementation plan. No task
below is completed by the spec-writing change.  
**Tests**: Mandatory and written before implementation. Constitution Rules 1,
5, 11, and 12 make ordinary, provenance, time, planted-defect, and clean-control
tests part of the deliverable.  
**Canonical final command**: `python -m pytest tests`.

## Format

`[ID] [P?] [Story] Description`

- `[P]` means the task can proceed in parallel with another task only when the
  files and prerequisites do not overlap.
- Stories map to `spec.md`: US1 ledger, US2 backfill, US3 DSR/PBO, US4 gate.
- Every red-test task must record that the intended assertion failed. Import,
  environment, and collection errors do not count as TDD red evidence.
- No task runs `git`. Camden commits.

## Phase 1 — Baseline, inventory, and frozen contracts

**Purpose**: Establish the true starting state and prevent a second authority.

- [ ] T001 Run `python -m pytest tests` before implementation and record the
  exact collection/pass/fail/error baseline without calling a pre-existing red
  suite green.
- [ ] T002 Run the focused existing prototype tests
  `python -m pytest tests/test_trial_registry.py -q` and record their baseline.
- [ ] T003 Inventory every production/human-facing call site that can execute or
  render a backtest, including scripts and `reports/api`; classify each as
  candidate runner, required baseline, diagnostic, or test-only in
  `tests/fixtures/spec_033/runner_inventory.json`.
- [ ] T004 Inventory the current `scripts/trial_registry.py`,
  `tests/test_trial_registry.py`, and `docs/trials/trials.jsonl`; choose the one
  migration path allowed by `plan.md` and record it at the top of the new ledger
  test module.
- [ ] T005 [P] Create test-only paper-input and CSCV fixtures under
  `tests/fixtures/spec_033/`, each labelled `EXAMPLE — NOT A RESULT` and each
  carrying a source note.
- [ ] T006 Freeze canonical ledger-event, return-sidecar, backfill, matrix
  manifest, Gate 3 artifact, and reason-code schemas as test constants before
  production implementation.

**Checkpoint**: Current behavior and every intended entry point are known; no
production file has changed yet.

## Phase 2 — US1 tests: authoritative ledger and full OOS evidence

**Goal**: Prove the required ledger behavior fails against the current optional
prototype.

- [ ] T007 [US1] Write canonical configuration tests covering resolved defaults,
  every result-affecting field in FR-003, ordered versus set-like collections,
  repository-relative paths, data digests, finite floats, and SHA-256 stability
  in `tests/test_033_trial_ledger.py`.
- [ ] T008 [US1] Write lifecycle tests proving `started` is appended before the
  callback runs; duplicate hashes count twice; exception, abandoned, and
  start-only/interrupted candidates remain in `N`; and baseline/test roles do
  not become candidate trials accidentally.
- [ ] T009 [US1] Write sidecar tests for complete ordered daily returns, funded
  account/net-cost eligibility, digest and coverage metadata, atomic creation,
  and rejection of paths under `data/cache/`.
- [ ] T010 [US1] Write chain-integrity planted-defect tests for edited, deleted,
  reordered, and duplicated events; truncated final line; missing/corrupt
  sidecar; and disconnected record hash. Add an unmodified clean control and
  assert the specific offending record/path.
- [ ] T011 [US1] Write source-provenance tests for a full 40-hex SHA, detached
  and packed refs, missing `.git`, dirty/unknown workspace state, source-tree
  hash, and the prohibition on invoking a `git` subprocess.
- [ ] T012 [US1] Write concurrent append/crash tests with multiple processes,
  no lost or interleaved record, stale lock behavior, and deterministic
  recovery that never truncates silently.
- [ ] T013 [US1] Write production-default versus injected synthetic-ledger
  tests. Assert there is no production `record=False` path and test runs never
  touch the repository lifetime ledger.
- [ ] T014 [US1] Write an AST/static instrumentation guard from T003's inventory
  that fails for an unwrapped human-facing backtest call and passes for direct
  low-level calls explicitly classified as test-only.
- [ ] T015 Confirm T007-T014 fail for the intended missing ledger behavior
  against the unmodified current source; record each intended failure.

**Checkpoint**: The ledger contract is executable and red before ledger code is
written.

## Phase 3 — US1 implementation: one ledger authority

- [ ] T016 [US1] Implement canonical JSON and configuration normalization in the
  chosen sole ledger module; store the reviewable config and its SHA-256.
- [ ] T017 [US1] Implement full source identity without calling `git`: explicit
  SHA/CI value or direct `.git` metadata, workspace-state handling, and
  deterministic source-tree hash for dirty/unknown runs.
- [ ] T018 [US1] Implement event schemas and validation for `started` and
  terminal lifecycle events; count candidate starts rather than completions.
- [ ] T019 [US1] Implement write-once daily return sidecars outside
  `data/cache/`, canonical row validation, SHA-256, and terminal binding.
- [ ] T020 [US1] Implement cross-platform serialized append, flush/fsync,
  temporary-file rename, hash-chain verification, and explicit partial-write
  recovery behavior.
- [ ] T021 [US1] Implement `trial_runner` lifecycle around an opaque canonical
  research configuration while preserving the Rule 8 boundary with
  `backtest_harness.py`.
- [ ] T022 [US1] Migrate or retire `scripts/trial_registry.py`, its tests, and
  the empty legacy ledger so one production default remains; do not leave a
  compatibility writer that can create a second count.
- [ ] T023 [US1] Instrument every T003 production runner, including candidate
  grids, manual scripts, report/API backtests, and required baselines with their
  correct role.
- [ ] T024 [US1] Make T007-T014 green, then run the focused existing/migrated
  registry tests and the static bypass guard together.

**Checkpoint**: Every real research attempt is durably recorded before its
result, and the repository has one ledger authority.

## Phase 4 — US2 tests and implementation: conservative backfill

**Goal**: Produce an auditable upper-biased historical count without fabricating
returns.

- [ ] T025 [US2] Write manifest-schema tests requiring campaign ID,
  description, evidence references, dimensions, Cartesian upper bound, rerun
  upper bound, remembered range, chosen bound, and unresolved reason in
  `tests/test_033_backfill.py`.
- [ ] T026 [US2] Write a hand-calculated manifest oracle proving full Cartesian
  product, separate-campaign addition without config dedupe, upper-endpoint
  selection, next-power-of-two rounding, then doubling in that exact order.
- [ ] T027 [US2] Write tests that a superseding correction cannot lower the
  effective historical count and that any unresolved/unbounded known campaign
  makes the backfill incomplete.
- [ ] T028 [US2] Confirm T025-T027 fail against the missing backfill
  implementation for the intended reasons.
- [ ] T029 [US2] Implement pure backfill validation and calculation functions;
  keep repository inspection/evidence collection separate from arithmetic.
- [ ] T030 [US2] Draft the real campaign manifest from surviving scripts,
  reports, audit artifacts, and known AI/manual search surfaces. Cite each row;
  do not infer that missing output means no run.
- [ ] T031 [US2] Present the manifest and upper bounds to Camden for explicit
  approval. Until approved, mark the real backfill incomplete and preserve
  Gate 3 as `unknown`.
- [ ] T032 [US2] After approval, write a new immutable backfill artifact with
  formula, intermediate counts, author/approval, UTC date, and SHA-256; never
  overwrite or lower an earlier count.
- [ ] T033 [US2] Make T025-T027 green and verify that backfilled trials change
  `N_current` without creating return sidecars or matrix columns.

**Checkpoint**: `N_backfill` is either approved and immutable or explicitly
incomplete; there is no optimistic fallback.

## Phase 5 — US3 tests: matrix, DSR, and HAC t-statistic

**Goal**: Pin statistical conventions before implementation.

- [ ] T034 [US3] Write matrix tests in `tests/test_033_dsr.py` for funded daily
  OOS eligibility, exact shared dates, deterministic columns, digest checks,
  exclusion reasons, no fill methods, and one committed matrix hash.
- [ ] T035 [US3] Add Rule 1/5 tests for first/last row, unequal boundaries,
  missing/holiday session, duplicate/reordered/aware/non-midnight dates, fold
  joins, and future-row perturbation plus a current-row control.
- [x] T036 [US3] Transcribe the DSR paper's worked-example inputs into the
  labelled fixture and write the direct formula test: `N = 88` gives
  `pytest.approx(0.910153014744707, abs=0.001)` and fails `0.95`; `N = 46` passes `0.95`.
- [ ] T037 [US3] Write unit tests for every named DSR input and convention:
  daily non-annualized Sharpe, observation count, skewness, Pearson kurtosis,
  trial-Sharpe dispersion, extreme-value benchmark, normal CDF, and
  `N_current`.
- [ ] T038 [US3] Write invalid-domain tests for insufficient observations,
  zero dispersion/variance where undefined, non-finite moments, invalid square
  root denominator, `N < 1`, and missing selected candidate; assert structured
  undefined reasons.
- [ ] T039 [US3] Write integration tests proving `N_current` equals immutable
  backfill plus every candidate start, including duplicates and incomplete
  terminal runs, and is not unique-hash/completion/matrix-column count.
- [ ] T040 [US3] Write a hand-calculated HAC t-stat oracle using the existing
  `metrics.mean_log_return_se`, require lag `>= horizon - 1`, and cover exact
  `3.0`, one representable value below, non-positive/undefined SE, and risk-free
  log-return convention.
- [ ] T041 [US3] Confirm T034-T040 fail for the intended missing statistical
  behavior before implementation.

## Phase 6 — US3 implementation: matrix, DSR, and t-statistic

- [ ] T042 [US3] Implement pure return-series validation and exact-intersection
  matrix construction with exclusion manifest and canonical matrix SHA-256.
- [ ] T043 [US3] Implement direct PSR/DSR equations in `scripts/selection_bias.py`
  using SciPy only for normal distribution primitives; expose named inputs and
  structured undefined results.
- [ ] T044 [US3] Integrate lifetime `N_current` without substituting surviving
  matrix columns or an effective correlated-trial count.
- [ ] T045 [US3] Reuse/extract the existing HAC mean standard-error primitive
  without duplicating its formula; calculate the selected candidate's daily OOS
  excess-return t-stat and record actual lag.
- [ ] T046 [US3] Make T034-T040 green, including the paper fixture, then verify
  the reported DSR and t-stat inputs independently from the output object.

**Checkpoint**: DSR and HAC t-stat are pure, source-checked, and tied to the
verified matrix plus lifetime count.

## Phase 7 — US3 tests and implementation: CSCV/PBO S=16

- [x] T047 [US3] Write block-construction tests in `tests/test_033_pbo.py` for
  16 contiguous chronological non-empty blocks, size difference at most one,
  stable boundaries, and rejection below 16 rows.
- [x] T048 [US3] Write a combinations/complement test proving exactly
  `C(16, 8) = 12,870` unique splits, eight IS plus complementary eight OOS
  blocks, and no random sampling.
- [x] T049 [US3] Build an independently calculated deterministic oracle that
  pins the IS winner, same-column OOS result, relative rank, logit sign,
  tie handling, degradation, and final PBO; verify column-order invariance.
- [x] T050 [US3] Write integration tests proving PBO and DSR consume the same
  matrix hash and that missing backfilled series never appear as zero, copied,
  or imputed columns.
- [x] T051 [US3] Write undefined-result tests for insufficient columns,
  non-finite split statistics, invalid/rejected split accounting, and zero valid
  splits; no invalid split may disappear silently.
- [x] T052 [US3] Confirm T047-T051 fail for the intended missing PBO behavior.
- [x] T053 [US3] Implement deterministic 16-block construction and all 12,870
  combinations in `scripts/selection_bias.py`.
- [x] T054 [US3] Implement preregistered IS selection, OOS carry-through,
  deterministic rank/tie convention, rank logits, PBO, degradation, and
  split-level evidence.
- [x] T055 [US3] Make T047-T051 green and record runtime/memory on a
  representative synthetic `T x M` matrix without weakening the exhaustive
  split requirement.

**Checkpoint**: One immutable matrix supports both DSR inputs and valid,
deterministic PBO evidence.

## Phase 8 — US4 tests: immutable Gate 3 evidence and API

**Goal**: Make the permission gate evidence-backed and explicitly non-permissive
when evidence is absent or stale.

- [ ] T056 [US4] Write artifact-schema and reason-code tests in
  `tests/test_033_gate3.py` covering every FR-040 field, ordered reasons,
  repository-relative evidence path, and test-fixture labelling.
- [ ] T057 [US4] Write decision-table tests: both thresholds plus valid PBO pass;
  either threshold below fails; missing/corrupt/undefined/incomplete is unknown;
  ledger/matrix/backfill/source mismatch is stale; exact DSR/t equality passes.
- [ ] T058 [US4] Write immutable artifact/index tests: each evaluation creates a
  new file and append-only index row, prior bytes do not change, digest matches,
  and a new candidate start makes the prior artifact stale.
- [ ] T059 [US4] Write route tests proving the current no-artifact case remains
  `unknown`, non-unknown states carry evidence, Gate 3 text names real
  thresholds, and the GET handler never calls DSR/PBO computation.
- [ ] T060 [US4] Write offline-command tests requiring explicit candidate and
  family, nonzero exit for unknown/stale evidence, printed artifact path, and no
  claim about Gates 1/2/4/5 or overall capital readiness.
- [ ] T061 [US4] Confirm T056-T060 fail against the current hard-coded unknown
  route for the intended missing artifact behavior.

## Phase 9 — US4 implementation and Rule 12 proof

- [ ] T062 [US4] Implement `scripts/generate_gate3_evidence.py` to verify all
  inputs, calculate once offline, write a new immutable artifact, append its
  index record, and never overwrite prior evidence.
- [ ] T063 [US4] Update `reports/api/routes/capital_gate.py` to validate/read the
  indexed artifact, map currentness and decision reasons, attach evidence, and
  perform no statistics during the request.
- [ ] T064 [US4] Replace Gate 3's “remains positive” description with the actual
  inclusive DSR/t-stat thresholds and mandatory diagnostic PBO wording.
- [ ] T065 [US4] Create the Rule 12 planted strategy fixture: fixed candidate
  returns, costs, dates, valid PBO, and t-stat `>= 3`, with source-example
  selection history `N = 88`; assert the real evaluator and route return
  `failed`, `dsr_below_threshold`, and the evidence path.
- [ ] T066 [US4] Create the clean control with the same non-history inputs and
  source-example `N = 46`; assert the real evaluator and route return `passed`.
- [ ] T067 [US4] Implement `tests/mutation/run_spec_033_gate_mutants.py` with an
  unmodified copied-module control, then mutate `DSR >= 0.95` to `DSR > 0` in
  isolation; prove T065 catches it and repository hashes are unchanged.
- [ ] T068 [US4] Add the isolated mutation replacing `N_current` with eligible
  matrix-column count; prove a backfill fixture catches it with a specific
  failure while the clean copied-module control remains green.
- [ ] T069 [US4] Run all spec-033 focused tests plus the mutation driver; record
  control result, mutant-by-mutant catching test, specific reason, and pre/post
  source SHA-256.

**Checkpoint**: Gate 3 has been observed failing for the intended plausible
defect and passing for a clean control through the real API path.

## Phase 10 — Full verification and documentation

- [ ] T070 Update audit/remediation and project-context references that still
  assign this work to spec 035; do not alter audit findings or historical raw
  evidence.
- [ ] T071 Verify no production status or example fixture can be mistaken for a
  real result; every rendered numeric field names its artifact, source hash,
  and date under Rule 11.
- [ ] T072 Verify no new dependency, network access, `git` invocation, `exec/`
  change, strategy change, or uninstrumented production backtest path exists.
- [ ] T073 Run `python -m pytest tests`; compare to T001, report every new or
  pre-existing failure honestly, and do not mark implementation complete while
  the constitution's required full-suite gate is red.
- [ ] T074 Review the implementation in the three units proposed by `plan.md`:
  ledger/instrumentation, backfill/statistics, artifact/API. Record any unit too
  large for Camden to explain and split it before merge.
- [ ] T075 Prepare Camden's Rule 9 explanation: what `N` counts, why backfill is
  upper-biased, why `M != N`, how DSR and PBO use one matrix, why a new trial
  makes evidence stale, and exactly what the planted defect proves.

## Dependencies and Execution Order

```text
Phase 1
  -> Phases 2-3 (ledger)
  -> Phase 4 (backfill)
  -> Phases 5-6 (matrix + DSR + HAC t)
  -> Phase 7 (PBO)
  -> Phases 8-9 (artifact + API + Rule 12)
  -> Phase 10 (full verification)
```

- Backfill arithmetic tests can be drafted while ledger implementation is in
  progress, but the real artifact depends on the authoritative schema.
- Paper formula and PBO oracle fixtures can be drafted independently, but
  integration waits for matrix hashing and lifetime `N`.
- The API changes last. Every earlier implementation phase must leave Gate 3
  `unknown`.
- T031 is a real human approval boundary. The implementation may continue on
  code and fixtures, but no current Gate 3 artifact may pass without approved
  backfill evidence.

## Notes

- PBO is mandatory evidence with no numeric pass threshold in this spec.
- `N_current` is raw conservative lifetime selection count, not effective
  independent trials and not matrix columns.
- A backfilled trial without returns is never a fabricated matrix column.
- Focused green tests do not override a red canonical suite.
- This spec-writing change creates only `spec.md`, `plan.md`, `research.md`, and
  `tasks.md`; all paths named above are future implementation scope.


## Implementation checkpoint — 2026-09-22

The approved source correction and Phase 7 checks above have recorded evidence
in `docs/implementation/spec-033/HANDOFF.md`. Earlier checkboxes have not been
retroactively certified; their partial acceptance and remaining gaps are
documented there. Camden explicitly limited this continuation to Phase 7.
T031/T032 remain untouched. Phases 8–10 are not started by this continuation.
The full-suite merge gate remains subject to the recorded canonical results.
