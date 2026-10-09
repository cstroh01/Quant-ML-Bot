# 055 F02b: state persisted before the broker command; reliable summary and incident delivery

Codex coordination 2026-10-08 23:25 CT; closes the two 055 deployment blockers deferred from #97
(paper-loop.yml persisted only after the broker command; no daily-summary delivery).
Fakes only (Python one-liner commands, recording poster, a scratch local git remote).
EXAMPLE — NOT A RESULT. Stacked on F02a (#103) → #101 → #97.

## Red
`tests/test_055_delivery.py` on the F02a head: collection error — `ops_deliver`,
`summary_from_loop_record` and the `persist_command`/`run_log` parameters did not exist. On that
head the runner had no pre-broker persistence hook and nothing queued or posted a summary.

## Fixes
- `ops_runner.run_once(persist_command=...)`: runs after the lease is claimed and **before** the
  broker command. On non-zero it never runs the command, releases the local lease (nothing durable,
  nothing sent, so a later retry is safe) and queues a `persist_failed` incident (exit 1).
- `run_once(run_log=...)`: every executed run queues one daily summary built from 049's own run
  record (`summary_from_loop_record`): orders by outcome, open reservations from reconciliation,
  and a next action that names UNKNOWN orders, an aborted run, or a missing record.
- Incidents are queued to `ops/outbox/` as they are first recorded, on due and non-due runs alike.
- `scripts/ops_deliver.py`: posts outbox items in order; an item moves to `ops/delivered/` only
  after a successful post, so failures retry and nothing posts twice; corrupt items stay for a human.
  `gh` adapter: one rolling "paper-loop daily summary" issue (comments), one issue per incident (D-3).
- `ops/persist_state.sh`: add/commit-if-changed/push to `ops-state`; non-zero on any failure.
  Exercised against a scratch bare repo: push lands, no-change run succeeds, unreachable remote exits 128.
- `ops/workflows/paper-loop.yml`: `--persist-command` and `--run-log`, a Deliver step (always),
  and the final Persist step reuses the script. actionlint clean.

## Still a human step
The template only runs once Camden installs it in the private companion repo (055 T006) with its
secrets and `ops-state` branch. The failure() issue step stays as a backstop for crashes before
the runner can queue anything (it can duplicate an outbox incident on runner failures).

## Codex follow-up (2026-10-08 23:49 CT)
Red on b979370 (causal assertions, no collection errors):
```
E       AssertionError: assert ('loop record missing' in 'Run status: failed (exit 4)\nProfile: paper_small  Session: 2026-10-08\nData session: not reported  Model: v1\nOrders...ations: 0\nPosition differences: not reported\nNext action: none\nPaper mechanics prototype. Not a performance result.')
{"delivered": 0, "failed": 0}
FAILED tests/test_055_delivery.py::test_a_stale_record_from_yesterday_is_never_reported_as_todays_run
FAILED tests/test_055_delivery.py::test_the_newly_appended_record_is_reported_with_its_data_session
FAILED tests/test_055_delivery.py::test_a_record_for_another_profile_is_not_this_runs_record
FAILED tests/test_055_delivery.py::test_deliver_cli_requires_an_explicit_repository
FAILED tests/test_055_delivery.py::test_workflow_delivery_and_failure_backstop_target_the_running_private_repo
5 failed, 11 passed in 0.53s
```
- The summary reads only bytes the wrapped command appended in this invocation (offset taken
  before the command) and only a record for this profile; otherwise "loop record missing".
  Before, a command that exited before appending was reported with yesterday's last record.
- The summary carries 049's recorded data session ("Data session: YYYY-MM-DD").
- `ops_deliver.py --repo` is required; `gh_poster` always passes `-R owner/name`. The workflow's
  Deliver step passes `--repo "${{ github.repository }}"` (the PRIVATE repo running it; the `qmb`
  checkout's remote is the public repo), and the failure backstop uses `gh issue create -R` with
  the same value. A test reads the workflow file the private repo will install and asserts both.
- Two older tests encoded the bug (pre-written log line; "Data session: not reported") and were
  updated to append in the command and expect the carried session.

## Rule 12
`python tests/mutation/run_055_delivery_mutants.py` → 15/15 killed (includes both workflow targets).
