# Feature Specification: Enforced Test-Suite CI Workflow

**Feature Branch**: `004-test-ci-workflow`

**Created**: 2026-09-05

**Status**: Draft

**Input**: Close a standing gap noted in this session and in
`docs/PROJECT_CONTEXT.md`'s implicit process record: the repo has
`.github/workflows/claude.yml` (the `@claude` implementation lane) but no
workflow that runs `tests/` automatically. "Tests passing" today means an
agent said so in a PR comment — self-reported, not enforced.

**Owns / must not know about**: this spec adds one new file,
`.github/workflows/test.yml`. It does not modify `claude.yml`, does not
touch any file under `scripts/` or `tests/`, and carries no opinion about
what the tests check — only that they run and that a failure is visible as
a failed check on the PR.

---

## Background

Every prior spec's PR description has stated a test count
("103 tests passing") as a self-report from the implementing agent. Nothing
re-runs that claim. A PR could merge with a broken test, or with a claimed
count that doesn't match reality, and nothing on the PR page would say so.

This is intentionally the smallest possible spec: one new workflow file,
no logic changes, sized to be implementable and reviewable for a fraction
of what specs 002/003 cost, since it is being run under a nearly-exhausted
monthly API budget.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tests run automatically on every push and PR (Priority: P1)

As the project owner, I need the test suite to run on every push and every
pull request, so a failing test shows up as a red check on the PR itself
instead of depending on an agent's self-report.

**Independent Test**: Open a PR that intentionally breaks one test (e.g.
change an assertion to a wrong value). The new workflow's check fails on
that PR. Revert the change; the check passes.

**Acceptance Scenarios**:

1. **Given** a push to any branch or a PR against `main`, **When** the
   workflow runs, **Then** it checks out the repo, installs
   `requirements.txt`, and runs `python -m unittest discover -s tests`.
2. **Given** a test failure, **When** the workflow runs, **Then** the job
   exits non-zero and GitHub shows a failed check on the PR — no separate
   parsing or summary step needed, `unittest`'s own exit code is sufficient.
3. **Given** all tests pass, **When** the workflow runs, **Then** the job
   exits zero and GitHub shows a passed check.

---

### Edge Cases

- The workflow must not require `ANTHROPIC_API_KEY` or any other secret —
  it only installs dependencies and runs the existing test suite, so it
  costs nothing against the capped API budget and can run on every commit
  without limit.
- `data/cache/` is gitignored (Background, CLAUDE.md: "a test that requires
  a download is not a test") — the workflow does not attempt to download or
  restore any cache; the existing test suite already runs without network
  access.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new file `.github/workflows/test.yml` MUST trigger on
  `push` (any branch) and `pull_request` (targeting `main`).
- **FR-002**: The job MUST check out the repo, set up Python 3.12
  (matching `claude.yml`'s version and `requirements.txt`'s pins), install
  `requirements.txt`, then run `python -m unittest discover -s tests`.
- **FR-003**: The job MUST NOT reference `secrets.ANTHROPIC_API_KEY` or any
  other secret — this workflow costs GitHub Actions minutes only (free for
  a public repo), never Console credit.
- **FR-004** *(Rule 6, dependencies)*: No new Python dependency. No new
  GitHub Action beyond `actions/checkout` and `actions/setup-python`,
  already used in `claude.yml`.
- **FR-005**: This spec does not modify `claude.yml` and does not change
  what any existing test asserts.

### Key Entities

- **`.github/workflows/test.yml`**: the only artifact this spec produces.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PR with a deliberately broken test shows a failed check
  from this workflow.
- **SC-002**: A PR with all tests passing shows a passed check from this
  workflow, with no `ANTHROPIC_API_KEY` reference anywhere in the file.

---

## Assumptions

- Making this check **required** (blocking merge on failure) is a GitHub
  branch-protection setting, not a code change — that's Camden's follow-up
  in repo Settings after this merges, out of scope for this spec.
- `pull_request` targets `main` only; feature branches still get the
  `push` trigger on every commit, so failures surface before a PR is even
  opened.
