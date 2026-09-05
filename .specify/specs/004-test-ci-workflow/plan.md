# Implementation Plan — 004 Enforced Test-Suite CI Workflow

**Spec**: `.specify/specs/004-test-ci-workflow/spec.md`

---

## Scope

One new file. Nothing else.

- `.github/workflows/test.yml` — new

Explicitly **not** touched: `.github/workflows/claude.yml`, anything under
`scripts/`, anything under `tests/`.

**No new dependency.**

---

## Constitution check

| Rule | Bearing on this plan |
|---|---|
| 5 — Tests required | This spec doesn't add tests to a module; it makes the existing tests actually enforced rather than self-reported. |
| 6 — Dependencies | No new Python dependency; no new Action beyond what `claude.yml` already uses. |
| 10 — Version control | Same Actions-lane carve-out as specs 001–003. |

No other rule bears on a CI-only change.

---

## Design

```yaml
name: Tests

on:
  push:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m unittest discover -s tests
```

No `permissions:` block beyond the default (read-only) — this workflow
never writes to the repo, unlike `claude.yml`. No `secrets:` reference at
all (FR-003).

### Not doing

- No branch-protection API call to mark the check required — that's a
  repo Settings action for Camden, not something a workflow file can do
  to itself.
- No test-result summary/annotation step — `unittest`'s exit code is
  already sufficient for GitHub to show pass/fail (spec's own reasoning,
  User Story 1 Acceptance Scenario 2).
- No matrix of Python versions — `requirements.txt` is pinned to versions
  needing 3.11/3.12; matching `claude.yml`'s single 3.12 avoids a second
  thing to keep in sync.

---

## Test plan

This spec's own "test" is the workflow running itself correctly, which
can't be unit-tested in the usual sense. Verification is behavioral:

| Case | Verification |
|---|---|
| Passing suite | Open the PR with this file added; workflow runs and shows green. |
| Failing suite | Temporarily break one assertion in a throwaway commit on the same branch, confirm the check goes red, then revert before merge. |
| No secret leakage | Grep the new file for `secrets.` — must return nothing (FR-003). |

---

## Risks

| Risk | Mitigation |
|---|---|
| `pull_request` trigger only covers PRs targeting `main` — a PR between two feature branches wouldn't get a fresh run | Not a real pattern in this repo's workflow (every PR here targets `main`); the `push` trigger already covers every commit on every branch regardless. |
| Someone later copies `claude.yml`'s `secrets.ANTHROPIC_API_KEY` into this file "for consistency" | FR-003 and SC-002 exist specifically to make that a spec violation, not a style choice. |
