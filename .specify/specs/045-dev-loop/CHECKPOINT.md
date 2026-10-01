# Spec 045 checkpoint

Resume point if a session is cut. Updated after every task. No `git` and no
pytest were run by the authoring session (Camden's instruction, 2026-09-30).

## Done

- T001 spec.md, plan.md, tasks.md.
- T002 docs/STATE.md (seeded: 043 active, next T020).
- T003 docs/autonomy/loop-prompt.md (result contract: `.loop/result.json` + `.loop/pr-body.md`).
- T004 .github/scripts/loop_guard.py. Self-test run locally (Python 3.13.14): 26/26 as expected. Three in-memory guard mutants (cap `>`→`>=`, ledger prefix dropped, STATE rule dropped) each KILLED by a named case. No file mutated on disk.
- T005 .github/workflows/dev-loop.yml (triage / agent read-only / publish write; cron commented).
- T006 docs/autonomy/review-prompt.md, .github/workflows/loop-review.yml (comment-only; dispatchable).
- T007 docs/autonomy/ruleset.md (repo verified public 2026-09-30; not applied).
- T008 docs/autonomy/token-options.md (A/B/B'/C/D; recommends B; none implemented).
- T009 test.yml: checkout v6→v7, setup-python v5→v7 (node20→node24), setup-node v4→v7 (node20→node24), `permissions: contents: read`, new `actionlint` (1.7.12, red proof: planted `needs: biuld`) and `loop-guard` jobs. claude.yml: checkout v6→v7, setup-python v5→v7.
- T010 docs/autonomy/README.md.
- T011 Validation (Windows, scratchpad tools only; nothing installed into the repo or venv):
  - `python .github/scripts/loop_guard.py --self-test`: 26/26.
  - PyYAML (pip --target scratchpad): all four workflows parse.
  - actionlint 1.7.12 (release zip, sha256 matched the published checksums) with
    shellcheck 0.11.0: exit 0 on all four workflows. The first run found four
    SC2016 infos in dev-loop.yml (literal Markdown backticks in printf formats),
    which would have failed CI. Each is now disabled on its line, with a reason.
  - Red proof: the planted `needs: biuld` file exits 1 with
    `job "report" needs job "biuld" which does not exist in this workflow [job-needs]`.
  - Public API, read-only: `main` @ e19d57c has `test` = failure and `web` = success.
    The 043 xfail markers are not in e19d57c (raw file checked). STATE.md records this.
- T012 Spec status line, tasks, this checkpoint.

## Observed during the session (not this spec's change)

- While T003 ran, the working tree gained `xfail(strict=True)` markers on the 14
  043 Phase 1 red contracts, plus a line in 043 `phase1-summary.md`. Not
  authored here. STATE.md "Expected red" was rewritten to match.

## Unverified (needs a real run on GitHub)

- claude-code-action@v1 in agent mode with a read-only `github_token`: does it
  try any write (branch, comment) that fails the step?
- The two `gh --jq` filters in triage (`test_status`, open loop PRs). jq is not
  installed locally; they were not executed. The API shapes they read were
  fetched and match.
- The `gh pr view --json commits` trailer count (fix-attempt cap).
- `git apply --index` of the artifact patch, and the guard on real numstat output.
- `upload-artifact@v7` with an empty `change.patch` (a noop run).
- Whether the GITHUB_TOKEN approval-required `pull_request` behaviour is live here.
- The runner's shellcheck version may differ from 0.11.0.
- The ruleset API payload: `actor_id: 5` and `integration_id: 15368`.

## In progress

- (none) Spec 045's authoring tasks are complete. Camden's tasks T020 to T022 remain.
