# 055 F02b1–F02b2: summary/incident outbox and its delivery (splits 1–2 of 3 from #104)

Split from #104 (`8279582`) to meet the ≤300 changed-line unit cap (044 SC-007 / 045 FR-005).
Stack: F02b1 → F02b2 delivery (this adds it) → F02b3 persist-before-broker. F02b3's tree equals #104's.
Fakes only. EXAMPLE — NOT A RESULT.

## Changes
- `ops_runtime.summary_from_loop_record`: daily summary from 049's own run record (orders by
  outcome, open reservations, 049's recorded data session); missing or aborted record → next action.
- `ops_runtime.queue_outbox`: durable (atomic) queue item per message.
- `ops_runner`: incidents are queued to `ops/outbox/` when first recorded (due and non-due runs);
  every executed run queues one summary built only from the record the command appended in this
  invocation for this profile (byte offset taken before the command); `--run-log` CLI flag.
- Workflow template passes `--run-log`.
- **F02b2:** `scripts/ops_deliver.py` posts outbox items in order; an item moves to `ops/delivered/`
  only after a successful post (failures retry next run, nothing posts twice, corrupt items stay).
  `gh` adapter: one rolling "paper-loop daily summary" issue, one issue per incident (D-3); `--repo`
  is required and every `gh` call passes `-R owner/name`. The workflow's Deliver step passes
  `--repo "${{ github.repository }}"` (the PRIVATE repo; the `qmb` checkout's remote is public) and
  the failure backstop uses `gh issue create -R` with the same value; a test reads the workflow.

## Red (from #104's history, same assertions)
On F02a `2a69c1b` the summary/outbox API did not exist; on `b979370` (pre-follow-up) the stale-record,
other-profile and data-session assertions failed (5 causal failures recorded on #104).

## Rule 12
`python tests/mutation/run_055_delivery_mutants.py` → 12/12 killed (F02b1's 7 plus moved-before-posting,
failed post dropped, `--repo` optional, and both workflow targets).
