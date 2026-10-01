# Autonomy: the dev loop

Spec: [`.specify/specs/045-dev-loop/`](../../.specify/specs/045-dev-loop/spec.md).
State: [`docs/STATE.md`](../STATE.md). This folder is a forbidden path for the
loop: it cannot edit its own instructions.

| File | Role |
|---|---|
| `loop-prompt.md` | The agent's fixed instructions, read from `main` each run |
| `review-prompt.md` | The reviewer's fixed instructions, read from `main` |
| `ruleset.md` | Steps for the `main` ruleset (not applied) |
| `token-options.md` | Why loop PRs may not trigger CI, and the options (none implemented) |

## One run

1. **triage** (read-only token). Counts open `loop/*` PRs and reads `test`
   check results, then picks a mode:
   - two or more open loop PRs: fail;
   - one open loop PR: `fix-pr` if its `test` is red (at most 3 tries), else
     **idle** (stops here, no API spend);
   - none, and `main`'s `test` is red: `main-red`;
   - otherwise `new`.

   It then builds the prompt from `main`'s `loop-prompt.md` plus a run-context block.
2. **agent** (read-only token). Claude edits files and runs pytest, then writes
   `.loop/result.json` and `.loop/pr-body.md`. A workflow step packages
   `git diff` as an artifact. The token cannot push, whatever code runs.
3. **publish** (write token, no agent code). On a fresh runner it:
   - applies the patch;
   - runs `main`'s `.github/scripts/loop_guard.py` on what Git measured
     (300-line cap, forbidden paths, STATE.md updated, no binaries or
     symlinks, outcome consistent);
   - commits with a `Dev-Loop-Run:` trailer;
   - pushes `loop/<spec>-<task>` without force;
   - opens one PR.

   Any guard error stops the run with nothing pushed.
4. **Loop review** (`loop-review.yml`) comments on the PR. Camden reads it,
   asks `@claude` for fixes if he wants them, and merges or closes.

## Turning it on (in order)

1. Merge spec 045 once Camden can explain it (Rule 9). Suggested split for
   review:
   - the spec folder and `docs/`;
   - the `test.yml` and `claude.yml` bumps, with the `actionlint` and
     `loop-guard` jobs;
   - `loop_guard.py` and `dev-loop.yml`;
   - `loop-review.yml`.
2. **D-1:** settle Rule 10 for this lane (spec §6).
3. **D-3:** apply the ruleset (`ruleset.md`).
4. **D-2 / D-4:** choose the token option. For the first run, option D (turn
   on "Allow GitHub Actions to create and approve pull requests") is enough
   to find out whether the approval banner is live.
5. **D-5:** confirm STATE.md's active spec and next task.
6. **SC-004:** Actions → *Dev loop* → *Run workflow* on `main`. Read the triage
   summary, the agent log, and the guard line in publish. Review the PR.
7. **D-6:** uncomment the `schedule` block in `dev-loop.yml`.

## Stopping it

- **Immediately:** Actions → *Dev loop* → ⋯ → *Disable workflow*. No commit needed.
- **Pausing:** leave a loop PR open. While it is open and not red, every run idles.
- Merging or closing the open loop PR lets the next run start new work.

## Residual risks (stated, not solved)

- **The agent job holds `ANTHROPIC_API_KEY`** and runs code it writes. A
  misbehaving run could send the key out over the network. `claude.yml` has
  the same exposure today. Mitigation: give the loop its own key with a spend
  limit.
- **The repository is public**, so loop PRs, review comments and STATE.md are public.
- **Public-repo schedules are disabled after 60 days** without repository
  activity (GitHub docs, `schedule` event).
- **Untested on GitHub.** Nothing here has run yet, so action behaviour in
  agent mode with a read-only token is unverified. The CHECKPOINT lists exactly
  what was and was not checked.
