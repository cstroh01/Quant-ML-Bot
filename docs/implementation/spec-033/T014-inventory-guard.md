# Spec 033 T014 — AST guard consumes the runner inventory's classifications

EXAMPLE — NOT A RESULT. Synthetic planted files only; no market data, no ledger write.
Base: main `600df4d`. Does not tick T014 (tick-only reconciliation is a separate docs PR).
Read-only and unchanged: `tests/fixtures/spec_033/runner_inventory.json`, `scripts/trial_registry.py`,
`scripts/selection_bias.py`.

## Gap closed
Before this change `bypasses()` exempted by folder (only `scripts/` and `reports/api/` were scanned)
and never read `classification`. So an inventoried candidate runner outside those folders was
ignored, and a direct low-level call explicitly classified `test-only` was flagged anyway.

## Behaviour now (`tests/test_033_trial_instrumentation.py`)
- `classified(root)` reads T003's inventory as `{(path, call): classifications}`.
- A call is exempt only when its `(path, call)` is classified `test-only` and nothing else.
  The exemption is per call name, not per file. Line numbers are not used: they drift with edits.
- Every other inventoried path is scanned in addition to `scripts/` and `reports/api/`.
- Fail-closed: an unknown classification is treated as a runner; an inventoried runner path that
  no longer exists is reported as `<path> missing (<classes>)`.
- Primitive set unchanged. `summarize_trades` / `performance_summary` appear in the inventory but
  consume a trade log from an already-guarded run; widening the primitive set is out of scope.

## Red proof (unmodified guard, new tests)
4 failed, 7 passed: `…candidate_outside_scanned_folders`, `…explicit_test_only…`,
`…test_only_exemption_is_scoped…`, `…unknown_classification_and_missing_runner_path…`.
`…never_overrides_a_runner_classification` and `…real_inventory_classes…` pass on the old code
(it flags everything under `scripts/`); they are kept as mutant witnesses. The three pre-existing
planted-bypass controls stay green.

## Rule 12 — `python tests/mutation/run_033_t014_mutants.py`
| Mutant | Witness |
|---|---|
| inventory ignored | T014 CANDIDATE |
| inventoried runner paths not scanned | T014 CANDIDATE |
| test-only exemption ignored | T014 TEST-ONLY |
| exemption keyed by path only | T014 SCOPE |
| test-only wins over a runner class | T014 CONFLICT |
| unknown class exempt | T014 FAIL-CLOSED |
| missing runner path silent | T014 FAIL-CLOSED |

7/7 killed (JUnit failures, never errors). Control: unchanged copy green, 6 collected. Every mutant
compiles. Guard, inventory and all 5 `docs/trials/` files byte-identical after the run.

## Real tree
`test_inventory_and_production_guard` stays green with the inventory consumed: no bypass in the
real tree. All 160 `test-only` entries are under `tests/`; no production file is exempted.

## Suite and ledger (Linux, Python 3.13.16)
- `python -B -m pytest tests -q -p no:cacheprovider`: 1722 passed, 1386 subtests passed, 1 warning,
  exit 0 (main baseline 1716 + 6 new).
- `trials.jsonl` `1bb5dbfe…5275f30f`, `trials.head.json` `f83b1b9b…7d22d764`: unchanged before and
  after. `returns/` absent.
- Owner-side evidence. Exact-head CI and Codex's Windows review are separate.

## Follow-up — exact-path internal exemption (Codex BLOCK @13d915d, P1)
Codex reproduced that any file named `trial_runner.py` / `trial_registry.py` was skipped by basename,
so an inventoried candidate at `tools/trial_runner.py` escaped the guard. The exemption is now the two
canonical paths only (`INTERNAL`). New test
`test_t014_internal_module_exemption_is_exact_canonical_path_only`: red on `13d915d` (1 failed, 11
passed), green after the fix. Covers `tools/trial_runner.py`, `tools/trial_registry.py`,
`scripts/sub/trial_runner.py` (flagged) and the canonical pair (clean control). Driver gains mutant
"internal exemption by basename" → `T014 BASENAME`: 8/8 killed, control green with 7 collected.
Full suite (Linux, Py 3.13.16) on this change: 1723 passed, 1386 subtests, 1 warning, exit 0; ledger unchanged.
