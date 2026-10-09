# 055 F01: missed-run detection on every invocation; strategy version in run identity

Source: Codex cross-review 2026-10-08 (CROSS-REVIEW-MAIN.md, private folder) — `ops_runner.py` L39
(missed-run check sat below the non-due early return: an after-cutoff session and a first-ever miss
were invisible) — and the earlier P1 on PR #75 (strategy version missing from the run identity,
FR-001). Synthetic, fake commands only. EXAMPLE — NOT A RESULT.

## Red (main 2c72c9a, extended `tests/test_055_runner.py`)
```
FAILED tests/test_055_runner.py::test_concurrent_worker_holding_the_lease_blocks_execution
FAILED tests/test_055_runner.py::test_run_identity_records_strategy_version
FAILED tests/test_055_runner.py::test_blank_strategy_version_refuses_before_any_run
FAILED tests/test_055_runner.py::test_after_cutoff_without_a_run_reports_todays_session_missed
FAILED tests/test_055_runner.py::test_first_ever_invocation_after_cutoff_is_a_missed_run
FAILED tests/test_055_runner.py::test_first_ever_miss_is_reported_on_a_later_due_run
FAILED tests/test_055_runner.py::test_missed_run_alert_is_deduplicated_and_exits_nonzero_once
11 failed in 9.72s
```
(The pre-existing tests also fail at red because `run_once` has no `strategy_version` parameter.)

## Fixes
- `run_once` checks missed sessions on every invocation, before the due decision returns, from the
  later of the last completed session and the profile's first-ever invocation (`ops/first_seen.json`).
  Today's session counts once its 09:28 ET cutoff passes.
- Incidents are delivered (deduplicated) on non-due invocations too; the result carries `new_incidents`.
- `main` exits 1 on any new incident, so the workflow's existing `failure()` issue step alerts once;
  repeats of the same incident exit 0.
- `strategy_version` is required, refused when blank, and recorded in each run record.
- `ops/workflows/paper-loop.yml` template passes `--strategy-version "${{ vars.QMB_PINNED_SHA }}"`.

## Not in this unit (still open from the same review)
- Workflow persists state only after the broker command (paper-loop.yml L57) and has no daily-summary
  delivery step (L72). Deferred to avoid colliding with the unpushed 051 T007 draft, which rewrites
  the same template; do after T007 lands.

## Rule 12
`python tests/mutation/run_055_missed_run_mutants.py` → 5/5 killed.
