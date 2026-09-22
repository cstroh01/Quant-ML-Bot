# Spec 033 implementation checkpoint — NOT COMPLETE

The Phase 6 acceptance checkpoint is blocked by a verified contradiction
between FR-027/T036 and the primary paper. No change to that acceptance target
has been authorized. See [the exact correction proposal](SPEC_CORRECTION_PROPOSAL.md).
The implementation and required failing assertion are both preserved.

T031 is separately pending. The [backfill manifest](../../trials/backfill/manifest.json)
is a draft, has `approval: null`, and has no finite lifetime count. No approved
backfill artifact or real Gate 3 evidence has been created. Gate 3's route is
unchanged and remains `unknown`. There is no effective-N clustering.

## Verification evidence

All counts below describe tests, not investment results. Files in this
directory are the run artifacts; `source-snapshot.json` records current source
hashes and UTC generation date. Commands ran in this checkout without git.

| Check | Evidence | Outcome |
|---|---|---|
| T001 original canonical suite | `T001-baseline.txt` | 750 collected; 723 passed, 18 failed, 9 errors |
| T002 original prototype | `T002-registry-baseline.txt` | 10 passed |
| T015 ledger contracts before implementation | `T015-ledger-red.txt` | 33 assertion failures, 1 clean-control pass; no import/collection errors |
| T024 first ledger/runner regression checkpoint | `T024-ledger-green.txt` | 57 passed, 3 subtests passed |
| T028 backfill before implementation | `T028-backfill-red.txt` | 12 assertion failures |
| Backfill nondecreasing immutable supersession | `backfill-supersession-red.txt`, `T033-backfill-green.txt` | Planted lower-count case failed; all 13 backfill tests now pass |
| T041 statistics before implementation | `T041-statistics-red.txt` | 21 assertion failures |
| T046 statistics checkpoint | `T046-statistics-check.txt` | 20 passed; required paper-target assertion fails |
| Current ledger, instrumentation, backfill, migrated registry | `checkpoint-focused.txt` | 54 passed |
| Canonical suite after integration fixes | `canonical-checkpoint.txt`, `suite-comparison.json` | 816 collected; 788 passed, 19 failed, 9 errors. Only new failing node: T036 paper target |

The import-whitelist regression was corrected and both boundary checks passed; the final canonical rerun confirms it. All 18 original failing tests and all 9 original errors remain. No other new failing node exists.

The statistics failure is deliberately **not** skipped, xfailed, relaxed, or
converted to a passing source test. An additional test checks the actual
published paper example. `paper-oracle-check.json` independently reproduces
the formula with Python's standard-library NormalDist, without importing the
implementation.

## What has been written

- `trial_registry.py` is upgraded in place (plan migration path 2), retaining
  the sole production path `docs/trials/trials.jsonl`. The optional `log_trial`
  writer is retired. Its old tests were replaced with migration checks.
- Starts are flushed before callbacks; repeated candidates, exceptions,
  abandonments, and crash-surviving starts count. Baseline and synthetic roles
  remain distinct. Completed funded-account runs preserve ordered daily
  return sidecars, including the initial-capital-to-first-close return.
- Canonical JSON/config hashes, direct full-SHA metadata reads, source-tree
  content hashing, interprocess serialization, exclusive sidecar publication,
  hash chaining, and an external head anchor are implemented. A missing head
  or partial write fails closed. No automatic truncation or orphan-lock
  deletion is permitted.
- Candidate/grid/manual/API call sites are wrapped and inventoried in
  `tests/fixtures/spec_033/runner_inventory.json`. The AST guard has clean,
  direct-bypass, and aliased-bypass controls. Legacy runners' opaque argument
  and module-default snapshots are recorded. Missing semantic OOS/CV/cost
  provenance stays explicit; these records do not become Gate-eligible merely
  because instrumentation exists. Further adapter/completeness review remains
  required before claiming all FR-003/FR-013 production acceptance complete.
- Backfill arithmetic validates full products, repeat counts, remembered upper
  endpoints, separate-campaign addition, upward power-of-two rounding, and
  doubling. Immutable writes read prior artifact counts and cannot lower N.
- Exact shared-date matrix construction, exclusions/digests, direct daily
  PSR/DSR equations, and reuse of `metrics.mean_log_return_se` are implemented.
  Lifetime N is an explicit independent input, not a count of matrix columns.

## Backfill review

The draft inventories 16 campaign rows and all 22 existing pre-033 specs,
with evidence paths, content hashes, and line excerpts. Missing specs 022–031
are not invented. Infrastructure/diagnostic specs are classified rather than
arbitrarily counted as one trial each.

The screening worksheet uses all four estimator/target entries, both feature
sets, four grid points plus the selected/default configuration, and upper
bounds of 113 outer and 113 inner/refold opportunities. This deliberately
overcounts possible execution rather than surviving output. It yields a
**proposed per-batch bound of 510,760**, sourced to the draft's dimensions and
`docs/PROJECT_CONTEXT.md` screening geometry; it is not an approved N.

The original screening, reboot-interrupted attempt, serial rerun, parallel run,
and previous/partial history each have separate rows. The generic script
surface is also retained rather than silently deduplicated against them.
SMA, logistic, model-CV search, multi-ticker, API, possible baseline promotion,
audit inspections, and manual/AI/off-repo history are represented separately.

No repository evidence proves a finite ceiling on historical reruns and
arbitrary manual configuration changes. Therefore `rerun_upper_bound` and
`chosen_upper_bound` remain null where unresolved. Neither the power-of-two
rounding nor the doubling reserve converts an unbounded campaign into a
defensible finite count. Camden must provide bounds/corrections and then
approve the exact finalized manifest. T032 must not run before that approval.

## Plan/code mismatches and implementation issues

1. **Paper target contradiction.** The paper's original non-normal example
   uses N=100, while its N=88 paragraph changes the moments to normal returns.
   Holding the non-history inputs fixed does not produce the spec's 0.905 at
   N=88. See the independently sourced correction proposal; no spec edit made.
2. **New constitutional requirements.** The spec's constitution review stops
   at Rule 12. Current Rules 13–15 also require realistic spread/impact costs,
   independent corporate-action verification, and deflated/provisional reporting.
   The existing harness uses flat-bps costs. These legacy returns are recorded
   but not promoted into eligible evidence; no strategy behavior was changed.
3. **Existing red suite.** Full-suite failures already existed before changes.
   Focused green tests are not merge approval. Baseline node IDs remain in the
   original log and are compared mechanically in `suite-comparison.json`.
4. **Test isolation incident.** A per-test fixture did not protect unittest
   class setup. Verification was stopped; synthetic records were quarantined
   under `.pytest_cache/spec033-quarantine`, and the verified original empty
   production ledger was restored. Hashes and the incident are recorded in
   `test-isolation-incident.json`. Injection now happens at pytest startup;
   shutdown checks that production ledger bytes did not change. Class setup,
   spawned processes, and ordinary tests receive synthetic roots.
5. **Synthetic history performance.** Unrelated implicit mechanical attempts
   now use separate temporary ledgers. Explicit injected ledgers still share
   history for count, crash, and concurrency tests. This avoids repeatedly
   verifying a growing pseudo-lifetime across unrelated class fixtures.
6. **Windows behavior.** Concurrent tests exposed transient lock deletion
   sharing violations and extended-length path prefixes. Owner-only release
   retries and normalized resolved paths address these cases; no stale lock
   is automatically ignored.
7. **Source-reading tools.** Firecrawl was unavailable. Primary PDFs were
   retrieved through web/HTTP and inspected using temporary PDF tooling under
   `.pytest_cache`. No runtime/test requirement file was changed. Tests and
   statistical routines contain no added network access.

## Task boundary and remaining work

This checkpoint is **not** T073 completion and must not be described as a
finished spec. T031 approval/T032 remain pending. T036/T046 are red. Broader
production configuration/provenance acceptance also needs completion/review.

To respect the declared phase dependency and the instruction not to redesign
the reviewed spec, Phase 7 CSCV/PBO implementation and Phases 8–9 immutable
Gate 3 artifacts, API reader, and Rule 12 comparator/lifetime-N mutations have
not been implemented. T070–T075 final acceptance is not marked complete.
Only labelled paper/CSCV input fixtures and frozen schema constants exist for
the later phases. In particular, no mutation-driver success is being claimed.

## Preliminary unit-size review (T074 preparation, not final acceptance)

Do not merge this whole change as a single unit. Retain the plan's dependency
split, with an additional subdivision of the first unit:

1. Ledger persistence/source contracts plus their tests; then lifecycle,
   production adapters, test isolation, and instrumentation guard as a separate
   review. `source-snapshot.json` gives exact file sizes/hashes for this review.
   Camden should explain crash/anchor behavior before reviewing runner changes.
2. Backfill arithmetic and manifest review; then matrix/DSR/HAC and the still
   pending PBO implementation. Manifest approval is its own human decision.
3. Still pending: immutable evidence, route currentness, and both isolated
   mutations. Gate 3 must stay unknown between these units.

The integration unit is too broad to call reviewable merely because individual
files are short. Its semantic config/receipt coverage must be reviewed per
runner. No commit or PR was made; Camden owns the actual version-control split.

## Rule 9 explanation draft (T075 preparation)

**N counts opportunities, not successes.** Add the approved conservative
historical count to every candidate start. Failure, interruption, repetition,
and absent returns cannot erase a start. Required baselines and synthetic tests
are not selected candidates.

**Backfill is deliberately upper-biased.** Count full possible grids and
reruns, add separate campaigns without deduplication, use remembered upper
endpoints, round upward, then double. An unbounded campaign still blocks the
gate; a reserve is not proof that forgotten history was finite.

**M is different from N.** M counts verified return columns that actually exist.
History without surviving returns increases N but never creates invented,
zero-filled, copied, or interpolated columns. DSR's observed moments and trial
Sharpe dispersion come from one committed matrix; its multiple-testing penalty
uses lifetime N. The future CSCV/PBO code must use that exact matrix hash.

**A new start invalidates an old gate assessment.** It changes the ledger head
and lifetime count, so old evidence cannot justify a current pass. This
currentness rule is specified but its artifact/API implementation is pending.

**What the required planted defect will prove.** Holding returns, costs, dates,
PBO and t-stat inputs fixed while increasing only selection history must cause
the real evaluator and API to fail specifically on DSR. Mutating the comparator
to `DSR > 0` or substituting M for N must be caught; an unmutated copy must pass
its clean control. Those mutations have not yet been run and prove nothing
until their actual failure evidence exists. They will test selection-bias
enforcement, not establish alpha, detect leakage, or approve capital deployment.

Before merge, Camden should independently explain why deleting a losing
candidate's return sidecar cannot reduce N, and why a duplicated configuration
can add to N even when it adds no usable matrix column.
