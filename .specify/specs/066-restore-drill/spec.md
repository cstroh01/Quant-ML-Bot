# 066 — Restore drill for durable ops state

Date: 2026-10-23 America/New_York. Status: draft for review.
Baseline: public main `c2dd0ce0d94e44d2ab93e42e00b0ae52a3c77113`.

## Why

The ordinary-operations proposal (`docs/implementation/spec-064/ordinary-operations-proposal.md`,
"Backup restore" row) requires restoring a private test copy and reproducing ownership, intents
and latches without a reset. 057 T010 and 062 T007 cite the same acceptance. The private
`paper-drill.yml` has no restore option. Every state writer (paper-loop, fidelity-preview,
fidelity-live) already keeps two copies of a profile's state: the `ops-state` branch (primary)
and a 90-day `upload-artifact` backup. Nobody has shown the backup restores.

## FR-001 — Pure drill (`scripts/restore_drill.py`)

`drill(primary, backup, *, profile, now, scratch=None)`:

- Refuses (`DrillRefused` / `ValueError`, not FAIL) for a non-portable profile, naive `now`,
  an empty or non-directory input, or a symlink anywhere in either input or the restore.
- Copies the backup into a fresh scratch directory (`tempfile.mkdtemp`, removed afterwards
  unless the caller supplied one). Never writes either input; refuses if either input's
  manifest changed during the drill.
- PASS only if all hold:
  1. The restored copy and the primary have identical relative paths and SHA-256 bytes.
  2. The consumer view is equal at both locations: HALTED/KILL latches, `leases/*.json`,
     `open_intents` (the real `ops_runtime` reader), the real `due_run` decision built from
     `ops/runs.jsonl`, every parsed `*.json`/`*.jsonl` (ownership `bot-positions.json`,
     `cash-basis.json`, allocation state, attempt markers, run logs) and every `*.sqlite`
     (`integrity_check` plus a logical-dump hash, read from a private copy that includes any
     `-wal`/`-shm`, so WAL-resident pages count and the input never gains side files).
  3. Nothing in the restored copy is state the runtime would refuse, even when the primary has
     the same defect: unparseable or non-UTF-8 JSON/JSONL, a lease without `run_id`, a torn
     intent log, a `runs.jsonl` the runner cannot read, or a SQLite failing `integrity_check`.
     A faithful copy of broken state is not a usable restore.
- Evidence: verdict, profile, file count, manifest hash, differing files and views, latches,
  lease names, open-intent count, due-run decision, SQLite names. No values beyond those.

CLI: `--primary --backup --profile --evidence`; exit 0 only on PASS; REFUSED is recorded,
including any unexpected error, so the evidence file is always written.

## FR-002 — Dispatch-only template (`ops/workflows/restore-drill.yml`)

Shipped as its own review unit (template, `tests/test_066_restore_drill_workflow.py`,
`tests/mutation/run_066_restore_workflow_mutants.py`) to keep each unit within 600 lines.


- `workflow_dispatch` with a `profile` choice; no schedule; `contents: read`, `actions: read`.
- No secrets, no broker, no push, no issue, both checkouts `persist-credentials: false`.
- **No concurrency group.** Joining the writers' group would make the drill the group's single
  pending run and cancel a pending PAPER or Fidelity run. Instead, before any checkout, it
  refuses while any writer workflow is queued or running, failing closed on any `gh` error
  except a workflow that is not installed. It checks out `ops-state` at one recorded SHA and,
  after the drill, refuses if `ops-state` has moved (a stale comparison, not a FAIL). The
  drill's own input-change refusal covers local runs only.
- Restores the newest unexpired artifact for the profile (`state-<profile>-<run>`; for
  `live_fidelity` the newer of `fidelity-live-state-<run>` and `fidelity-state-<run>`).
- Uploads `restore-drill.json` as `restore-drill-<profile>-<run>` (90 days).

Known risk the drill exists to find: the paper-loop upload omits `include-hidden-files`, so a
hidden file in PAPER state would be missing from its backup and the drill would FAIL.

## Acceptance

- Tests (`tests/test_066_restore_drill.py`) build state with the real lease and intent writers
  and a real SQLite file. Each planted backup defect (lost latch, lost lease, torn intent log,
  changed ownership, emptied run log, corrupt gate DB, stray file) fails on its own consumer
  view; both-copies corruption fails; a byte-identical restore that reads differently at its new
  location fails; the template contract is checked.
- Mutation: `tests/mutation/run_066_restore_drill_mutants.py`, every mutant killed.
- Operational (Camden, after merge and repin): install the template in the private repo,
  dispatch it once per profile outside 08:00–12:00 ET weekdays, and record the three evidence
  artifacts in STATUS.md. PASS for all three closes the "Backup restore" row; FAIL is a finding,
  not a reason to edit state.

## Out of scope

Restoring into production, editing `ops-state`, changing writer workflows (a hidden-files fix
would be its own reviewed change), and any broker or credential access.
