# Feature Specification: Dev loop (scheduled, one unit per run)

**Feature Branch**: `045-dev-loop` (name only; Camden owns Git)
**Spec number**: 045. The highest existing folder is 044. 035, 038 and 039 are
reserved by `docs/V1-FINISH-PLAN.md` and 042 by spec 043's header; none is reused.
**Created**: 2026-09-30
**Status**: Implemented as files only. Nothing has run on GitHub. The cron is
commented out, the ruleset is documented and not applied, and no token option
is implemented. Decisions D-1 to D-6 are **open** (§6). No `git` command and no
pytest run were made by the authoring session. Checked locally 2026-09-30:
`loop_guard.py --self-test` 26/26; actionlint 1.7.12 with shellcheck 0.11.0
exit 0 on all four workflows; the actionlint red proof's planted file fails
with the expected message; PyYAML parses all four. See CHECKPOINT for what is
unverified.
**Input**: Camden, 2026-09-30: "a scheduled GitHub Actions loop that works the
repo while Camden is away, one unit per run, PR out, CI as the gate, Camden as
the merge button." Edit scope: `.github/`, `docs/STATE.md`, `docs/autonomy/`,
and this folder. No change to `scripts/`, `tests/` or `reports/`.

## 1. Why this spec exists

Specs are already cut into ≤300-line units (044 SC-007, 043 review units), and
each unit is run, checked and handed off by a person starting a session. The
loop does that start for him: on a timer, it takes the next unblocked unit,
does it, and leaves a pull request. Camden's role shrinks to the two things
only he can do: explain and merge (Rule 9), and clear human gates.

The loop is a **development** lane. It is not ADR 0002's Operations lane and
never trades, fetches market data, or touches capital.

## 2. Shape of one run

```
triage (read-only) ──► agent (read-only token) ──► publish (write token, no agent code)
  open loop PR?          edits files, runs pytest     guard from main → apply patch
  main red?              writes .loop/result.json     → commit → push → one PR
  builds the prompt      uploads a patch artifact
```

- **WIP limit 1.** At most one open `loop/*` PR. While one is open, a run
  either fixes its failing `test` check or idles. Two open is an error.
- **The agent runs no `git` and no `gh`.** Every Git and GitHub write is a
  workflow step in `publish`, a job in which no agent-written code executes.
- **The agent job's token is read-only.** The agent can execute arbitrary code
  through pytest, so a tool allowlist cannot contain it. A read-only token
  can: nothing the agent runs is able to push, comment, or open a PR.

## 3. Requirements

| ID | Requirement |
|---|---|
| FR-001 | `docs/STATE.md` holds the active spec, the next unblocked task, blockers, lane status, expected red, and the human-gate list. Every loop PR updates it. |
| FR-002 | `.github/workflows/dev-loop.yml` runs on `workflow_dispatch`; the 4-hourly `schedule` is present but commented out. |
| FR-003 | The agent's instructions are the fixed file `docs/autonomy/loop-prompt.md`, read **from `main`** at the triaged SHA, never from the branch under work. |
| FR-004 | Triage order: two or more open loop PRs → fail; one open loop PR → fix its red `test` check, else idle; `main` red → fix that (unless STATE.md lists the red as expected); else new work. |
| FR-005 | New work is the first unchecked, unblocked task of the active spec in STATE.md. One unit per run, ≤300 changed lines (added + deleted, every file, STATE.md included). |
| FR-006 | Branch `loop/<spec>-<task>` (e.g. `loop/043-T020`); a red-`main` fix uses `loop/fix-<label>`. |
| FR-007 | A task needing a human gate is not attempted. The blocker is written to STATE.md and that STATE.md-only change is the run's PR. |
| FR-008 | The agent never touches `docs/trials/`, never runs research or backtest code outside pytest, never edits the pinned 019 files, and never weakens, skips, xfails or deletes a test to turn something green. |
| FR-009 | `publish` enforces FR-005 to FR-008 **in code** (`.github/scripts/loop_guard.py`, taken from `main`), not only in the prompt. A violation fails the run and pushes nothing. |
| FR-010 | Guardrails: workflow concurrency group; `--max-turns`; `timeout-minutes` on every job; job-scoped permissions with `contents` and `pull-requests` the only write scopes; an actor guard admitting only `schedule` or `workflow_dispatch` by `cstroh01`, on `main`, in `cstroh01/Quant-ML-Bot`. |
| FR-011 | `.github/workflows/loop-review.yml`: on PRs from same-repo `loop/*` branches (and on Camden's dispatch), a review-only job using `docs/autonomy/review-prompt.md` from `main`. It checks correctness, lookahead/leakage, module boundaries, edge cases and mutation resilience. It comments only, never approves, never edits, and runs no code. |
| FR-012 | `docs/autonomy/ruleset.md`: exact steps to create the `main` ruleset (require PR, require the `test` check, block force-push). Not applied. |
| FR-013 | `docs/autonomy/token-options.md`: the GITHUB_TOKEN trigger problem, the options and their tradeoffs, and a recommendation. **No option is implemented.** |
| FR-014 | Workflow hygiene: every action on a Node 20 runtime moves to its current major; an `actionlint` job is added; YAML is validated locally if possible, else declared unchecked. |
| FR-015 | Rule 12: the guard and the actionlint step each have a red proof with a green control, run in CI. |

### Pinned 019 files (FR-008)

`scripts/feature_set_comparison.py` and `scripts/multi_ticker_comparison.py`
(frozen, spec 021 D-5), and `scripts/logistic_baseline.py` (its control
functions are frozen by 021 D-2). The loop treats the **whole** of
`logistic_baseline.py` as pinned. That is stricter than D-2, on purpose: an
unattended agent should not be judging which functions in a file are frozen.

### Forbidden paths (FR-009, enforced by `loop_guard.py`)

`.github/`, `docs/autonomy/`, `docs/trials/`, `.specify/memory/`, `CLAUDE.md`,
`docs/SCOPE-V1.md`, `exec/`, `data/`, `.claude/`, `.loop/`, any `.env*`, and
the three pinned files. The loop cannot edit its own workflows, its own
instructions, the constitution, or the ledger. A symlink, a submodule, or a
binary change is also refused.

## 4. Non-goals

- Applying the ruleset, choosing a token option, or uncommenting the cron.
- Any change to `scripts/`, `tests/` or `reports/`.
- Letting the loop act on review comments. Review findings go to Camden; he
  asks for a fix through the existing `@claude` lane (`claude.yml`). Two bots
  answering each other on a timer is a loop with no human in it.
- Fixing PRs from any lane other than `loop/*`.

## 5. Acceptance

| ID | Criterion | How checked |
|---|---|---|
| SC-001 | `actionlint` passes on all four workflows | CI `actionlint` job; locally if a binary could be run (see CHECKPOINT) |
| SC-002 | The actionlint red proof fails a planted `needs:` typo, naming it, and the real tree passes | CI `actionlint` job |
| SC-003 | `loop_guard.py --self-test` kills every planted defect with its message and passes the control | CI `loop-guard` job; run locally by the authoring session |
| SC-004 | First dispatched run: triage picks the expected mode, the agent produces one unit, publish opens one PR whose diff the guard measured | Camden, after D-1 to D-4 |
| SC-005 | A planted forbidden-path change on a dispatched run fails `publish` and pushes nothing | Camden, optional, after SC-004 |

## 6. Decisions for Camden

### D-1 — Rule 10 and a scheduled lane (blocks enabling)

Rule 10's exception covers "an agent invoked from a GitHub issue or PR comment
… to the branch it was invoked on". The loop is invoked by `schedule` or
`workflow_dispatch`, and it creates a new branch. Its design keeps the letter
of "agents do not run git" (the agent runs none; reviewed workflow steps do),
but it is outside the exception's stated trigger and target.

- **(a) Recommended.** Amend Rule 10 in a dedicated commit: workflow steps of
  `dev-loop.yml` may create one `loop/*` branch and open one PR per run, or push
  to the single open `loop/*` PR's branch; never `main`, never force.
- (b) Rule that workflow-step Git is not agent Git, and record that in CLAUDE.md.
- (c) Reject; the loop stays dispatch-only or is removed.

### D-2 — Token (blocks CI on loop PRs)

See `docs/autonomy/token-options.md`. Recommended: a dedicated GitHub App.

### D-3 — Ruleset and Camden's direct pushes

Camden commits to `main` directly today. "Require a pull request" blocks that
unless his role is on the bypass list. See `docs/autonomy/ruleset.md`.
Recommended: apply, with the Repository admin role bypassing.

### D-4 — Repository setting "Allow GitHub Actions to create and approve pull requests"

Needed for the GITHUB_TOKEN to open PRs under D-2 options C and D. Not needed
under B, which lets the setting stay off. The same switch also lets the token
**approve** PRs; the review job's tool allowlist is what stops it doing so.

### D-5 — The active spec

STATE.md was seeded from the tree: 043 is active (Phase 1 red contracts are on
`main`; T020 is next), and 044 waits for 043 because both edit `scripts/data.py`.
Camden confirms or edits it.

### D-6 — Turning on the cron

After D-1 to D-4: uncomment the `schedule` block. Each run is at most 80 agent
turns and 60 minutes; an idle run spends no API tokens. Cadence and budget are
Camden's call.

## 7. Constitution check

| Rule | Effect |
|---|---|
| 1, 5 | Unchanged. The review prompt checks them on every loop PR. |
| 7 | `exec/` is a forbidden path. |
| 9 | Untouched: the loop cannot merge; Camden is the merge button. |
| 10 | D-1. The agent runs no Git; reviewed workflow steps do. |
| 12 | FR-015: guard and actionlint red proofs with controls. |
| 15 / ADR 0002 Research layer | No research or backtest outside pytest; `docs/trials/` forbidden. |
