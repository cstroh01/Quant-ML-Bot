# Feature Specification: Durable cloud operations on GitHub Actions

**Spec number**: 055
**Created**: 2026-10-07
**Status**: Adopted under `docs/SCOPE-V1.md` §10. Offline units authorized. Workflow files are
`.github/` (governance); private-repo setup and secrets are Camden's human gates.
**Depends on**: 049, 051, ADR 0001 private companion repo.

## 1. Purpose
The daily loop and supporting jobs run with Camden's computer off, free, without daily approvals.

## 2. Requirements
- **FR-001 Due-run identity.** (profile, session, strategy version). A pure function decides whether
  a run is due now: NYSE session, America/New_York with DST, pre-open window, missed-run cutoff.
  Missing an expected session is a recorded failure, never a reason to trade on stale data.
- **FR-002 Single run.** One lease per (profile, session). A second concurrent or repeated run
  for the same key refuses before any broker call. Client order ids persist before submission.
- **FR-003 Durable state.** Runs, reservations, halts and leases persist across runs (private repo
  state, backed up as artifacts). Restart refuses new exposure until reconciliation completes.
- **FR-004 Freshness.** Data, signal, quote and account checks each carry an as-of; any stale stage halts.
- **FR-005 Summaries and alerts.** Daily summary (session, data/model identity, orders by status,
  reservations, position differences, next operator action) and immediate alerts (failure, halt,
  reconciliation mismatch, missed run), deduplicated by incident. Delivered automatically; no approvals.
- **FR-006 Operator controls.** Kill, disarm and resume through `workflow_dispatch` inputs or a
  committed control file; operations never change risk limits or promote models.
- **FR-007 Immutable deploy.** The runner executes a pinned commit of `main`, never a working copy.

## 3. Decisions (2026-10-07)
- **D-1 (Camden)** Host: GitHub Actions in the private companion repo (Student Pack minutes). Laptop
  scheduler stays until a supervised drill passes.
- **D-2 (quant-ml-genius)** Cron at 12:00 and 13:00 UTC on weekdays with the due-run gate deciding
  (covers DST and GitHub cron delay); submit window ends 09:28 ET as in 049.
- **D-3 (Camden + genius)** Notifications: GitHub Issues in the private repo (automatic email to Camden);
  one rolling daily-summary issue, one issue per new incident.
- **D-4 (quant-ml-genius)** State: committed to an `ops-state` branch of the private repo by the workflow
  under `concurrency`, plus a 90-day artifact backup each run.
- **D-5 (quant-ml-genius)** Spare minutes: nightly data refresh, research pipeline and mutation drivers.

## 4. Rule 12 mutants
Missing due session not flagged; DST offset hardcoded; stale bars accepted; two leases for one key;
client id generated after submit; unknown submit retried with a new id; restart skips reconciliation;
alert dedupe drops a changed incident; worker changes a risk limit.

## 5. Acceptance
Mutants killed offline; workflow runs green on the private repo; supervised drills (missed run,
duplicate run, unknown submit, restart) recorded; then the laptop task is retired by Camden.
