# Spec 033 T056/T057 — Gate 3 artifact and decision-table tests

EXAMPLE — NOT A RESULT. Every number below is a synthetic test operand or a test count, never a strategy result.

Queue Q32, first part (T056 and T057 only). T058–T060 and the remainder of T061 are still open.

## Contract fixed by the tests (implemented by T062)

`scripts/generate_gate3_evidence.py` must expose:

- `compose(evidence) -> artifact`. This function is pure and recomputes no statistic. `evidence` carries
  the existing `selection_bias` outputs (`counts`, `matrix`, `dsr` from `counted_dsr`, `t_stat`, `pbo`)
  plus `selected_trial`, `generated_at_utc`, `cv`, `costs`, `source_identity`, and optionally `label`.
  The artifact carries every `GATE_FIELDS` key, `status` and `reason_codes` in the frozen `REASONS` order.
- `assess(artifact, current) -> {"status", "reason_codes"}`. It marks passed or failed evidence `stale`
  when the ledger head, backfill, matrix or source identity moved. Unknown evidence stays `unknown`.
- `write_artifact(artifact, root) -> str` returns a repository-relative POSIX path under
  `reports/artifacts/capital_gate/gate3/`. It refuses a fixture-labelled artifact (FR-048).

When `lifetime_count` or `counted_dsr` fails, it returns the real `undefined()` shape, and the result must
be `unknown`, never a `KeyError`. A DSR or PBO whose `matrix_hash` differs from the matrix is not
evidence, so the result is `unknown`. A within-cap family DSR that is undefined is `unknown`; it never falls
back to lifetime N. Thresholds are inclusive: `DSR >= 0.95` and `t >= 3.0`. PBO must be finite, with `S = 16`, and it has
no cutoff. Status precedence is unknown, then failed, then passed.

**Family N (amendment of 2026-10-09).** The gating `dsr` is the family-N DSR while the family is within
its cap. Otherwise it is the lifetime-N DSR. `dsr_lifetime` is always published. `GATE_FIELDS` in
`tests/spec033_support.py` gains `family` and `dsr_lifetime` for this. No other test reads it.

## Red (T061, partial)

The command `python -m pytest tests/test_033_gate3.py --runxfail` fails 34 of 34 tests. Each failure
is the `api()` assertion `missing spec-033 behavior: generate_gate3_evidence.compose|assess`: 23 name
`compose` and 11 name `assess`. Under strict xfail, the module reports `34 xfailed`. T062 must remove
the module `pytestmark`.

## Green control and planted defects (Rule 12)

A scratch reference implementation, never committed, passes all 34 tests. Each mutant below was
applied to a copy of it. The reference was then restored and `cmp` showed it clean.

| Mutant | Killed by |
|---|---|
| `DSR < 0.95` became `<=` (equality fails) | `test_decision_table` |
| `t < 3.0` became `<=` | `test_decision_table` |
| Gate always uses the lifetime DSR | `test_family_dsr_gates_within_cap_…` |
| Family DSR used even after a cap breach | `test_family_dsr_gates_within_cap_…` |
| Reason codes sorted alphabetically | `test_reason_codes_are_known_and_in_frozen_order` |
| `failed` outranks `unknown` | `test_reason_codes_are_known_and_in_frozen_order` |
| PBO `S` not checked | `test_pbo_must_be_s16_and_has_no_invented_cutoff` |
| Invented PBO cutoff `> 0.5` | `test_decision_table`, `test_pbo_must_be_s16_…` |
| `assess` ignores `source_identity` | `test_input_mismatch_is_stale_…` |
| Stale overrides unknown | `test_unknown_evidence_stays_unknown_…` |
| Labelled artifact written to production | `test_fixture_label_travels_…` |
| Absolute evidence path returned | `test_fixture_label_travels_…` |
| NaN DSR compared rather than undefined | `test_decision_table` |
| Undefined family DSR falls back to lifetime | `test_incomplete_or_unverifiable_inputs_are_unknown` |
| `assess` compares only `git_sha` | `test_input_mismatch_is_stale_…` |
| No matrix-hash consistency check | `test_statistics_from_another_matrix_are_not_evidence` |

All 16 mutants were killed. The run was on Linux with Python 3.12. Camden's Windows venv is authoritative.

## Left open

FR-043 also requires `stale` when a sidecar or the selected config changes. Both are recorded in ledger events,
so the ledger head hash covers them. T058 ("a new candidate start makes the prior artifact stale") is the
place to test that directly. Unknown-SHA and dirty-tree ineligibility are already enforced upstream by
`selection_bias._eligible`, which excludes the trial from the matrix. Here, that exclusion surfaces as
`candidate_ineligible`.
