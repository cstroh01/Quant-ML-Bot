# Spec 033 T058–T061 — immutable artifact, route and offline-command tests

EXAMPLE — NOT A RESULT. Every number below is a synthetic test operand or a test count, never a strategy result.

Queue Q99, the remainder of Q32 that #157 deferred. These tests are in `tests/test_033_gate3.py` under the
module's existing strict xfail, which T062 removes.

## Contract added by these tests

This builds on the T056/T057 contract in `T056-T057-gate3-tests.md`.

- `write_artifact` writes `reports/artifacts/capital_gate/gate3/<artifact_id>.json` once. A second
  write of the same id raises and leaves the bytes unchanged. It appends one
  `{"artifact_id", "path", "sha256"}` row to `index.jsonl`, and `sha256` is the digest of the bytes
  written. Distinct evaluations get distinct ids.
- `current_inputs(artifact, root)` returns today's `ledger_head_hash`, `backfill_hash`, `matrix_hash`
  and `source_identity`, which `assess` uses. It is called positionally. The tests always replace it, so
  its real behaviour is not yet pinned (see Left open).
- `main(argv) -> int` is the offline command (FR-049). It requires `--candidate` and `--family`, and takes
  `--root`. A missing argument raises argparse's nonzero `SystemExit`. Its evidence comes from `gather(candidate=, family=, root=)`. It always writes a new
  artifact and prints its path. The exit code is 0 for passed evidence and nonzero for unknown or stale
  evidence. The output names no other gate and makes no overall-readiness claim (FR-050).
- **T063 (route).** The route reads the **last** `index.jsonl` row under the module attribute
  `capital_gate.ARTIFACT_ROOT`, checks the artifact's bytes against the row digest, and maps
  `assess(artifact, current_inputs(artifact, root))`. Passed, failed and stale results carry the
  row's path as `evidence`. All of these give `unknown` with no evidence:
  - a missing index (with the `NO_EVIDENCE` text, FR-047);
  - a digest mismatch;
  - a row path outside the gate3 directory;
  - a fixture-labelled artifact (FR-048);
  - unknown evidence.

  The GET computes no statistic. The test replaces every `selection_bias` statistic, and `gather`, with
  a failing stub on `selection_bias`, the route module and the generator.
- **T064 (text).** Gate 3's description drops "remains positive". It ties `>= 0.95` to DSR and `>= 3.0`
  to the t-statistic, and names PBO as diagnostic evidence.

Tests per task:

- T058: `test_each_evaluation_writes_a_new_file_and_an_append_only_index_row` and
  `test_a_new_candidate_start_or_changed_config_makes_the_prior_artifact_stale`. The second test uses a
  real synthetic `TrialLedger`. It shows that re-running a candidate, or running it with a changed config,
  is a new start that moves the ledger head, and that `assess` reports that head as stale. The test
  passes the head in by hand, not through `current_inputs`, so the #157 gap is closed only as far as
  `assess`.
- T059: `test_route_serves_indexed_evidence_without_computing` (passed, failed and stale),
  `test_route_stays_unknown_without_a_valid_indexed_artifact`, and
  `test_gate3_text_names_the_real_thresholds_and_diagnostic_pbo`. The existing
  `tests/test_reports_api.py::test_capital_gate_status` still pins today's repository, which has no
  artifact: all five gates are `unknown` with no evidence (FR-047).
- T060: `test_command_requires_explicit_candidate_and_family` and
  `test_command_prints_the_new_path_exits_nonzero_unless_current_and_claims_no_other_gate`.

The tests do not decide the exit code for valid `failed` evidence. FR-049 names only unknown and stale.

## Red (T061)

`python -m pytest tests/test_033_gate3.py --runxfail` fails all 47 tests: the 34 from T056/T057 and 13 new.
The failures come from the missing generator APIs and the current route text:

| Failure | Tests |
|---|---|
| `missing spec-033 behavior: generate_gate3_evidence.compose` | 27 |
| `missing spec-033 behavior: generate_gate3_evidence.assess` | 12 |
| `missing spec-033 behavior: generate_gate3_evidence.main` | 6 |
| `missing spec-033 behavior: generate_gate3_evidence.current_inputs` | 1 |
| `T064: a positive probability is not the gate` (current route text) | 1 |

Under the module's strict xfail the result is `47 xfailed`.

After T062, the T058, T060 and route-unknown tests can pass. The route-evidence and text tests stay red
until T063/T064 change `reports/api/routes/capital_gate.py`. That path is excluded by Rule 9a, so Q33b
covers it and only Camden merges it.

## Green control and planted defects (Rule 12)

A scratch reference generator and a scratch route were written into an isolated copy of the tree. Neither
was committed. All 47 tests pass against them, and `tests/test_reports_api.py` stays green. Each mutant
below was applied to the copy, then reverted, and `cmp` showed the reference clean.

| Mutant | Killed by |
|---|---|
| Write overwrites an existing artifact (`"wb"` for `"xb"`) | `test_each_evaluation_…` |
| Index rewritten, not appended | `test_each_evaluation_…` |
| Index digest of a different serialization than the bytes written | `test_each_evaluation_…`, `test_route_serves_…` |
| `assess` ignores the ledger head | `test_a_new_candidate_start_…`, `test_route_serves_…`, `test_command_prints_…` |
| Route recomputes `counted_dsr` on GET | `test_route_serves_…` |
| Route reads the first index row, not the latest | `test_route_serves_…` |
| Route accepts an index path outside the gate3 directory | `test_route_stays_unknown_…` |
| Route serves a fixture-labelled artifact | `test_route_stays_unknown_…` |
| Route skips the index digest check | `test_route_stays_unknown_…` |
| Route trusts the stored status (no `assess`) | `test_route_serves_…` (stale) |
| Route drops evidence on stale | `test_route_serves_…` |
| Route keeps "remains positive" | `test_gate3_text_…` |
| Command defaults `--family` | `test_command_requires_…` |
| Command exits 0 on stale | `test_command_prints_…` |
| Command omits the artifact path | `test_command_prints_…` |
| Command prints "Gates 1, 2, 4 and 5 passed" | `test_command_prints_…` |
| Command ignores `--candidate` | `test_command_prints_…` |

All 17 mutants were killed. Tests were strengthened twice during this run. First, a draft let two
mutants survive:

- The route-unknown test used to corrupt the artifact to `{}`, which is caught by parsing alone. It now
  plants a well-formed failed artifact edited to read `passed`.
- The command test used to pass candidate `a`, which a hard-coded `"a"` also satisfied. It now passes `b`.

Second, a fresh-context review added these checks: the route serves the latest row, path and label
refusal, `NO_EVIDENCE` details, the wider stubs, thresholds tied to their statistic, and an FR-050 check
that forbids claims but still allows the "remain independent blockers" disclaimer. Stdout and stderr are
both checked.

The run was on Linux with Python 3.12.3. Camden's Windows venv is authoritative.

## Left open (for T062's spec, not decided here)

- **How the route can know the current matrix without computing it.** `current_inputs` must report
  today's `matrix_hash` while the GET computes nothing, but rebuilding the matrix is `build_matrix`. Either
  currentness is defined from hashed inputs (ledger head, sidecar digests, backfill), or the
  no-computation rule must allow it. Until then `current_inputs` is always replaced in these tests.
- **Artifact id.** If the id is a content hash, re-running identical evidence with the same
  `generated_at_utc` cannot write a new artifact (FR-039). The tests only require distinct ids for
  distinct evaluations.
- **Valid `failed` evidence.** Its exit code is not decided, and neither is whether `main` must refuse
  evidence whose `selected_trial` differs from `--candidate`.

FR-043 says an edited sidecar makes an artifact `stale`. In practice `TrialLedger.verify` rejects an
edited return file, so the evidence becomes unverifiable (`ledger_invalid`), not stale. These tests
assert neither. Whether a tampered sidecar should read `stale` or `unknown` is a spec question for T062.
