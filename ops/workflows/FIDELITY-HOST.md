# Private hosted Fidelity preview (057 T008/T009)

Review draft only. Alpaca's installed private workflow already executes off-PC;
its automatic initiation still waits for 055 G16. This template adds the missing
portable Fidelity path. No workflow, schedule, credential or host is installed
by adding these source files. No broker run has been demonstrated on Linux.

After independent exact-head reviews and merge, Camden reviews the template and
installs it in the private companion repository through a separate governance PR.
It accepts only private main, a full public-main-ancestor source pin and an
explicit enable variable. It shares PAPER's concurrency group because both
workflows persist to the same ops-state branch. No public self-hosted runner.

Camden must separately authorize a date and provision QMB_FIDELITY_PIN,
QMB_FIDELITY_AUTHORIZED_SESSION and QMB_FIDELITY_PREVIEW_ENABLED. PAPER's existing
pin is unchanged. Credentials and QMB_FIDELITY_PROFILES_JSON are private secrets
he provisions; values never belong in source, workflow inputs or review packets.
The optional SDK lock contains the existing audited 0.2.2 wheel and all its
transitive dependencies for Python 3.12 Linux x86_64. httpx/pydantic implement
its HTTP/model interfaces; standard-library substitutes cannot load that SDK.
Other platforms require a reviewed lock and proof, not an assumed Pi migration.

Before enabling, reconcile/restore the actual dedicated-account state into
ops-state/live_fidelity. Preserve leases, bot ownership, pending intents and
HALTED/KILL. Only then add host-ready.json with exactly
`{"schema":1,"profile":"live_fidelity"}`. The marker acknowledges initialized
state; it does not prove account acceptance or authorize a clean-state reset.
Existing uncertain or consumed sessions must never be retried or deleted.

The helper checks 09:35 inclusive to 12:00 exclusive Eastern on the explicitly
authorized NYSE date, before each child. Input refresh ends at the preceding
completed session. The fixed preview child passes no arming file, persists its
daily lease before login and preserves existing account/cash/ownership/challenge
guards. A successful child needs a matching clean preview record with zero
place calls. Captured child output is discarded; backend payloads are not logs.
Failure notifications include a run URL only; state/backup stays private.

Retain the private run and notification receipts with the PC off. Separately
collect five distinct clean sessions and a latest-session holdings CSV match
through the existing evidence collector; copying raw state is not item-6
acceptance. Today's CSV, when separately supplied, belongs under
state/live_fidelity/holdings/YYYY-MM-DD.csv. No old file may be relabeled.
Authentication challenges halt and require operator action. Scheduling and
LIVE trading remain later reviewed changes behind all SCOPE §11.3 gates.

## Armed LIVE host (057 T011)

`fidelity-live.yml` is the ordinary LIVE template; `scripts/fidelity_live_host.py`
is its helper. Installing it changes nothing until Camden personally arms:

1. All seven §11.3 items are evidenced in `docs/implementation/spec-059/gate-manifest.json`
   on public main and `python scripts/gate_checklist.py` prints `ARMABLE`.
2. Repin `QMB_FIDELITY_PIN` to a main commit containing that manifest.
3. Set private secret `QMB_FIDELITY_ARMING_JSON` to exactly these six keys:
   `profile_name` (`live_fidelity`), `account_fingerprint` (the 64-hex value in
   any clean `preview-sessions/*.json`), `capital_gate_evidence_sha256` (SHA-256 of
   the pinned manifest's bytes), `activated_by` (`Camden`), `activated_at` and
   `expires_at` (ISO instants with an offset).
4. Set `QMB_FIDELITY_PREVIEW_ENABLED=false` and `QMB_FIDELITY_LIVE_ENABLED=true`.
5. Point the external timer at LIVE: in the cron-job.org `qmb preview` job, change
   `fidelity-preview.yml` to `fidelity-live.yml` in the dispatch URL (same body
   `{"ref":"main"}`, same 10:10/10:40/11:10/11:40 ET schedule). GitHub's own
   `schedule:` fires hours late on the private repo and cannot be relied on.

Before any child, the helper reruns the preview preflight, then refuses unless the
record arms exactly this profile now, its digest equals the pinned manifest and the
manifest still checks `ARMABLE`. The record reaches `live_loop.py` only as a 0600
temporary file deleted after the child. A run that fell back to preview, saw a gate
denial, refused, or whose `place_calls` differ from its submitted orders is a
failure: one issue opens per day and the day is not retried. The exception is a
clean `unsettled_cash` refusal (settled cash does not yet show a deposit or the
previous fills; no order, no attempt, no halt): the host reports `UNSETTLED` and the
next session runs normally. Repinning to a commit whose
manifest bytes changed requires a new arming record. Disarm by deleting the secret
or setting `QMB_FIDELITY_LIVE_ENABLED` to anything else.
