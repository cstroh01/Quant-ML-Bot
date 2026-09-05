# Tasks — 004 Enforced Test-Suite CI Workflow

---

## Phase 1 — Workflow file

- [ ] **T001** Create `.github/workflows/test.yml`: triggers on `push`
  (any branch) and `pull_request` (targeting `main`); checks out repo,
  sets up Python 3.12, installs `requirements.txt`, runs
  `python -m unittest discover -s tests`. (FR-001, FR-002)
- [ ] **T002** Confirm no `secrets.` reference anywhere in the new file.
  (FR-003)

## Phase 2 — Verify

- [ ] **T003** On the PR that adds this file, confirm the workflow runs
  and shows a passed check (all 103+ existing tests pass as-is). (SC-002)
- [ ] **T004** Optional, if time/budget allows: push one throwaway commit
  that breaks a single assertion, confirm the check goes red, then revert
  before merge. (SC-001)

## Phase 3 — Docs

- [ ] **T005** `docs/PROJECT_CONTEXT.md`: note that tests are now an
  enforced CI check on push/PR, not self-reported. Note that making it a
  *required* (merge-blocking) status check is a repo-Settings step still
  open for Camden — not part of this spec.

## Out of scope

`claude.yml`, anything under `scripts/` or `tests/`, branch-protection
settings (GitHub repo Settings, not a code change).
