# Spec 033 checkpoint — stopped at the Phase 7/8 boundary

Camden authorized the narrow DSR source correction and Phase 7 only on
2026-09-22. The correction is applied and T047–T055 CSCV/PBO work is green.
This is **not a completed spec or a merge-ready suite**. Phases 8–10 remain
pending; no Gate 3 artifact, API reader, or Rule 12 comparator/lifetime-N
mutation driver was implemented. `reports/api/routes/capital_gate.py` remains
unchanged. The prior checkpoint is preserved in [HANDOFF-phase6.md](HANDOFF-phase6.md).

The historical backfill is a separate decision. T031/T032 and the real
[manifest](../../trials/backfill/manifest.json) were left alone as requested.
Camden is supplying unresolved campaign bounds. This session's numeric-source
approval does not approve that manifest. No effective-N clustering was added.

## Approved source correction

The paper's fixed non-normal inputs at N=88 evaluate to
**0.910153014744707 — EXAMPLE — NOT A RESULT**, below the unchanged 0.95
threshold. N=46 passes with the same inputs. N=88 is an evaluation of the
paper's inputs, while its actual published example uses N=100; the additional
N=100 test is retained. FR-027, T036, the corresponding examples and Rule 12
fixture descriptions now use the approved target. No formula, non-history
input, count, or threshold was changed.

[The approved proposal](SPEC_CORRECTION_PROPOSAL.md) and the independent
[paper oracle](paper-oracle-check.json) retain the reasoning and source hashes.
Original red logs remain intact. `source-correction-snapshot.json` records the
corrected sources and UTC date.

## Verification evidence

These figures describe software verification, not investment results.
All commands ran from this checkout without git. Evidence paths below are
relative to this directory. Current source hashes, line counts and UTC date
are recorded in `phase7-source-snapshot.json`.

| Check | Evidence | Outcome |
|---|---|---|
| T036 and existing Phase 6 tests after approved correction | `T046-approved-correction-green.txt` | 21 passed |
| Canonical correction-only run | `canonical-source-correction.txt`, `suite-comparison-source-correction.json` | 816 collected; 789 passed, 18 failed, 9 errors |
| T052 before PBO implementation | `T052-pbo-red.txt` | 26 intended missing-behavior assertion failures; no import/collection errors |
| Initial T055 implementation | `T055-pbo-first-check.txt` | 26 passed |
| Additional numerical-boundary defect | `pbo-numeric-boundary-red.txt`, `pbo-numeric-boundary-assertion-red.txt` | Finite extreme returns raised instead of preserving rejected splits; explicit assertion confirmed red |
| Unequal-block independent oracle | `pbo-numeric-boundary-red.txt` | Direct per-row oracle passed alongside the failing boundary case |
| Final PBO plus existing statistics | `T055-pbo-statistics-green.txt` | 49 passed: 28 PBO and 21 DSR/matrix/HAC |
| All spec-033 focused tests plus migrated registry | `phase7-focused-green.txt` | 103 passed |
| Final canonical suite | `canonical-phase7.txt`, `suite-comparison-phase7.json` | 844 collected; 817 passed, 18 failed, 9 errors; no new failing/error nodes |

The correction-only comparison uses the prior `canonical-checkpoint.txt`
baseline: the only removed failing node is
`tests/test_033_dsr.py::test_paper_formula_required_spec_target`. There are no
new failing/error nodes. The Phase 7 comparison uses that corrected canonical
run as its baseline: all 28 added PBO tests pass, with no added/resolved
failing/error node and no failed-versus-error status change. The unchanged reds
are in feature-set comparison, model CV, multi-ticker comparison, reports API
and target equivalence tests; exact node IDs are in the comparison JSON. Each comparison JSON records exact failed/error node IDs,
log SHA-256 and UTC date; it does not infer passing-node details from a terse
pytest log.

## Phase 7 implementation and conventions

All new production code is in `scripts/selection_bias.py`:

- `cscv_blocks` validates existing session labels and partitions chronological
  rows into 16 contiguous blocks. Extra rows go to the earliest blocks, with
  stop-exclusive row bounds and actual first/last sessions. Gaps are not filled.
- `cscv_splits` enumerates every one of the 12,870 choices of eight IS blocks
  and complementary eight OOS blocks. There is no sampling or seed.
- `matrix_pbo` verifies the committed matrix digest, dimensions, dates and
  convention, then consumes the same matrix used by DSR. It accepts no N or
  backfill input. Missing historical series cannot become fabricated columns.
- Selection uses daily excess-log-return Sharpe with sample standard deviation
  (`ddof=1`) and the matrix's risk-free convention. Exact IS ties choose the
  lexicographically smallest trial ID. OOS uses ascending average rank divided
  by M+1. Logit is log(rank/(1-rank)); PBO counts logits at or below zero.
- Block means and centered sums are cached, then combined with row-count
  weights. The independent unequal-block test recomputes every split directly
  from raw rows, without using those production helpers.
- Each record retains the split ID, both block sets, every IS/OOS column
  Sharpe, the IS winner carried OOS, relative rank, logit, degradation and
  invalid-column identities. Degradation means IS winner Sharpe minus that
  same column's OOS Sharpe. Distribution summaries accompany the records.
- Every attempted split is accounted for. Any rejected split makes the
  aggregate undefined; no valid splits gets its own reason. Valid-subset
  summaries remain diagnostic, never a computed PBO or a gate pass.

The labelled analytic fixtures demonstrate a persistent winner and a
complement-reversing winner. The latter includes exact ties and distinguishes
`logit <= 0` from `logit < 0`. Tests also cover column-order invariance, matrix
hash corruption, invalid time labels, gaps, insufficient rows/columns,
non-finite inputs, mixed valid/rejected splits, zero valid splits, risk-free
conversion and OOS perturbations that cannot change the corresponding IS
winner. These are pure-statistics controls, **not** the deferred Rule 12
Gate 3 mutation tests.

## Runtime, memory and review size

`python tests/spec033_pbo_profile.py` is a reproducible, labelled synthetic
probe. [T055-pbo-profile.json](T055-pbo-profile.json) records its exact source
hashes, matrix hash and UTC date. For 1,250 rows by 16 columns, all 12,870
splits were valid. Observed runtime with tracing enabled was 8.674 seconds;
peak traced allocation was 26,604,722 bytes. This measures allocations during
PBO, not total process RSS or a production performance guarantee.

No statistical library or other dependency was added. PBO is pure offline
calculation, with no filesystem, network, model fitting, strategy change or
capital decision. The profiling helper writes only this labelled implementation
verification report.

Review Phase 7 in three pieces: chronological block/admission contracts;
weighted moments plus winner/rank calculations; then exhaustive aggregation,
rejected-split evidence and the independent oracles. The production statistics
module is 263 lines at this checkpoint, with the added PBO section beginning
at `cscv_blocks`. This is a local review aid, not a claim that final T074/T075
acceptance has occurred. The broader ledger/instrumentation review subdivision
in the prior handoff still applies.

## Plan differences and remaining work

The only changed acceptance requirement is Camden's approved numeric-source
correction. Tie policy and split-record representation resolve choices the
plan explicitly left open. Split-level evidence is returned inline; immutable
artifact persistence belongs to the deferred Phase 8/9 work.

An additional adversarial finite-input test exposed arithmetic overflow while
combining block means. Computing normalized weights before multiplication
fixed that defect, after recording the intended red assertion. No invalid
split is dropped to improve the result.

Earlier acceptance gaps remain: the existing Phase 6 tests are green, but
this continuation does not certify every T034–T040 requirement. In particular,
the raw-N unit check manually composes history plus starts; immutable-history
integration and exact HAC gate-boundary checks remain pending. T046 is not
retroactively marked fully complete. Production adapters need complete resolved
semantic config/provenance review; legacy outputs are not automatically
Gate-eligible; actual lifetime N composition and immutable artifact/currentness
integration are pending. The Phase 6 handoff details these limits. This
continuation did not broaden scope to fix them or the pre-existing suite reds.

Resume at Phase 8 only after Camden authorizes it. Preserve the T031 human
boundary and do not run T032 before approval of finite campaign bounds. Keep
raw lifetime N separate from matrix M. Deferred work includes artifact/API
red tests and implementation, planted/control evaluator-route fixtures, both
isolated mutations, final provenance/reference checks, T074 unit-size review
and Camden's T075 Rule 9 explanation. Do not describe the full spec as done.
