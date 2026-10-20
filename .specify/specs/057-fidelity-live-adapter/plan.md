# Plan: 057
- **U0** (agent, offline) dependency audit report for candidate libraries: pinned version, file
  hashes, network destinations in source, telemetry, credential handling. Output `research.md`.
- **U1** (`exec/fidelity_live.py`, reviewed lane) interface + preview default + gate path + halts, with fakes.
- **U2** (`exec/`, reviewed lane) reconciliation by client id; positions → 054.
- **U3** **Human**: secrets set; supervised preview-only session.

## U4/U5: PC-independent host (2026-10-19)
- T008: portable, preview-only host preflight and fixed child orchestration;
  tests use synthetic environments and injected child processes only.
- T009: private companion manual workflow template, dormant by default, plus
  deployment/acceptance instructions. Existing LIVE adapter is unchanged.
- Commit the numbered extension before implementing it. One isolated feature
  branch from verified main, separate from pending 062/056 work. Keep the PR
  draft; Camden owns private workflow installation and every operational gate.
- No broker call, credential inspection, new dependency, order, scheduling,
  state initialization, arming or pin/profile change during offline development.
