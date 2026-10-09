# 053 F01: promotion evidence binding and full-context verified load

Source: Codex cross-review 2026-10-08 (CROSS-REVIEW-MAIN.md, private folder), 053 P1 findings at model_registry.py L50, L105, L122, L130 of main 2c72c9a. Synthetic tests only. EXAMPLE — NOT A RESULT.

## Red (main 2c72c9a, new manifest test)
```
=========================== short test summary info ============================
FAILED tests/test_053_manifest.py::test_partial_expected_context_refuses_before_unpickling[expected0]
FAILED tests/test_053_manifest.py::test_partial_expected_context_refuses_before_unpickling[expected1]
2 failed, 10 passed in 0.08s
```
Promotion tests could not import: `Evidence` had no artifact/config/mode binding.

## Fixes
- `load_verified` refuses unless `expected` names every REQUIRED field, before reading or unpickling.
- `register` records challengers only, bound to artifact and config SHA-256; a champion exists only via `promote`.
- `Evidence` carries artifact_sha256, config_sha256, mode; `promote` refuses any mismatch with the registered challenger or the registry's mode.
- Future-dated Gate 3 evidence refuses (age was −1 and passed).
- `Registry` is bound to one mode and refuses a file holding another mode's events.
- Rollback with no previous champion refuses instead of silently doing nothing.

- Follow-up from Codex's independent Windows review (2026-10-08): `shadow_sessions`, `breaches` and
  `max_evidence_age_sessions` must be non-negative ints (NaN compared False and passed both the
  shadow-length and staleness checks); `gate3_pass`/`oos_beats_baselines` must be real booleans.

## Rule 12
`python tests/mutation/run_053_promotion_fix_mutants.py` → 11/11 killed (NaN counts, truthy non-boolean passes, partial expected accepted, champion via register, future Gate 3, artifact/config/mode unbound, foreign-mode file, unregistered promote, single-champion rollback).
