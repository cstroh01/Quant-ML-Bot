# Private hosted Fidelity preview (057 T007/T008)

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
