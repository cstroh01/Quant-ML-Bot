# Tasks: 057
- [x] T001 U0 dependency audit of candidate libraries (no credentials, no account calls).
- [x] T002 U1 contracts (fakes) red: no-arming place, gate bypass, credential leak, challenge ignored.
- [x] T003 **Reviewed lane**: implement `exec/fidelity_live.py` U1; Camden reads every line.
- [x] T004 **Reviewed lane**: U2 reconciliation + positions read.
- [ ] T005 **Human (Camden)**: credentials + TOTP seed into secrets; supervised preview-only session.
- [ ] T006 LIVE arming only after `docs/SCOPE-V1.md` §5 passes — Camden.

## Camden's numbered extension, 2026-10-15 (drafts, reviewed lane)
- Q139: fix audited adapter defects, restricted SDK loading, entitlement and settled cash; eight mutants.
- Q135: preview-only daily session, dedicated-account bot-ledger reconciliation, typed five-session evidence; six mutants.
- Q140 (after Q135): child-only credential launcher, Windows Credential Manager/Linux environment, hash-locked keyring; four mutants.
- Q137: dormant allocation loop, reconciliation, gateway, settled-cash/$100 cap; five mutants.
- Q138: SUPERSEDED by Camden's 2026-10-17 local Windows Task Scheduler instruction.
  A public-repository self-hosted runner can execute PR workflow code beside
  credentials. Replacement drafts: scripts/fidelity_preview_day.ps1,
  scripts/install-fidelity-preview-task.ps1, scripts/uninstall-fidelity-preview-task.ps1,
  ops/windows/fidelity-preview-task.xml. See ops/windows/README.md. No runner or
  task installed; reboot/lid-close and five-session evidence are runtime gates.
Authority: codex-task6-fidelity.md and codex-task6b-continue.md; no arming or broker probe authorized.

## PC-independent host extension (Camden, 2026-10-19)
- [ ] T008 U4: portable host preflight and fixed input/preview child commands;
  synthetic-only RED/GREEN/mutation contracts for dates, exact time boundaries,
  DST, holiday/gap, KILL/HALTED/missing state, credential exclusion, parent
  preservation, fixed preview-only argv and redacted child failures. Full suite.
- [ ] T009 U5: dormant manual-only private-host workflow template and operator
  acceptance notes; validate private-main/enable/date/pin guards, shared state
  concurrency, durable pre-login and final state, notifications and backups.
- [ ] T010 **Human (Camden)**: review/install the private workflow, provision
  credential values and state personally, then separately authorize real
  preview reads. Verify Linux runtime, PC-off completion and notification
  delivery; collect T005's five distinct clean preview/holdings sessions.
- [ ] T011 **Human (Camden)**: schedule/ordinary autonomy proposal only after
  accepted operations; LIVE still requires all current SCOPE §11.3 gates and
  personal arming. Do not enable a schedule or infer permission from T008/T009.
- [ ] T012 FR-013 **Reviewed lane** (Camden, 2026-10-26): record a redacted
  failure stage, own-exception message and login diagnostic in failed preview
  records. Synthetic-only RED/GREEN contracts (library text, credentials,
  query strings and account digits never written; guards and halts unchanged;
  clean records unchanged) and planted defects. Camden reads every line; after
  merge and repin he clears `live_fidelity/HALTED` and the next session
  records the cause. This task authorizes no retry and no guard change.
- [ ] T013 D-6a **Reviewed lane** (Camden, 2026-10-28): the 2026-10-28 FR-013
  record shows the halt was our redirect guard refusing Fidelity's permanent
  `/prgw/digital/login/atp` -> `/prgw/digital/signin/atp` 308 on the SDK's
  pre-credential page load. Accept exactly that redirect (exact URL strings)
  before any ecaap request; every near miss (status, method, host, port,
  userinfo, scheme, path, params, case, query, after auth or a later login,
  missing marker, any second hop) still refuses. Synthetic-only RED/GREEN
  contracts through a real httpx redirect-following client on an in-memory
  transport, and planted defects. Camden reads every line; after merge and
  repin he clears `live_fidelity/HALTED`. No retry, no SDK change.
- [ ] T014 D-4a **Reviewed lane** (Camden, 2026-10-29): the 2026-10-29 FR-013
  record shows the moved page followed, password accepted (1200), then session
  1201 and the SDK's own AuthenticationError with no TOTP request: the SDK
  imports pyotp for a base32 seed and the host lock lacked it. Add exactly
  `pyotp==2.10.0` with its wheel hash; offline contracts pin the line, the
  complete-lock shape and both workflows' hash-checked install, plus planted
  defects. Camden reads every line; after merge and repin he clears
  `live_fidelity/HALTED`. No retry, no SDK, wrapper or guard change.


## Local pin preflight correction - 2026-10-18
- [x] T007 Q138 follow-up draft: preserve exact mixed-newline reviewed blobs and verify the pinned Git object before accepting a newline-only representation. Original guard refused the exact main scripts/return_stats.py (161 CRLF, 7 bare LF). Three regressions were red; 12 pin contracts pass, including two semantic bypass defects with clean controls. Patched -CheckPinOnly succeeds against unchanged production main; no credentials or broker calls. This is not an installed task or operational acceptance.
