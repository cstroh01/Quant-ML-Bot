# Plan: Dev loop

**Spec**: [spec.md](spec.md) · **Tasks**: [tasks.md](tasks.md)

## Files

```
docs/STATE.md                           new  FR-001
docs/autonomy/README.md                 new  how the loop works; enablement order
docs/autonomy/loop-prompt.md            new  FR-003, FR-005..FR-008
docs/autonomy/review-prompt.md          new  FR-011
docs/autonomy/ruleset.md                new  FR-012
docs/autonomy/token-options.md          new  FR-013
.github/scripts/loop_guard.py           new  FR-009, FR-015 (stdlib only)
.github/workflows/dev-loop.yml          new  FR-002..FR-010
.github/workflows/loop-review.yml       new  FR-011
.github/workflows/test.yml              edit FR-014, FR-015 (bumps; actionlint and loop-guard jobs)
.github/workflows/claude.yml            edit FR-014 (setup-python bump only)
```

No file in `scripts/`, `tests/` or `reports/` changes. `loop_guard.py` is not a
test module name, so the collection guards do not see it, and pytest never
imports it.

## Design choices

1. **Three jobs, two trust levels.** `triage` and `agent` hold read-only
   tokens. `publish` holds `contents: write` and `pull-requests: write`, and
   runs only reviewed code from `main`: a fresh runner, a checkout of `main`'s
   `.github/scripts` for the guard, and a patch file treated as data.
   Considered and rejected: one job with a tool allowlist. The agent runs
   pytest, pytest runs files the agent wrote, so the allowlist is not a
   boundary; the token is.
2. **Instructions come from `main`.** Triage reads `loop-prompt.md` through the
   contents API at the triaged `main` SHA. The review job does the same with
   `review-prompt.md`. A branch cannot rewrite its own instructions.
3. **The guard measures the applied patch, not the agent's claim.** It reads
   `git diff --cached --numstat -z --no-renames` and `--summary` after
   `git apply --index`. The 300-line cap counts every file, matching 044 SC-007.
4. **WIP limit 1 and the idle rule.** With an open loop PR whose `test` check
   is not failing, the run stops at triage and the agent never starts. This
   halts the loop on a blocked-state PR until Camden merges it, and costs no
   API spend while waiting.
5. **Fix attempts are capped at 3 per PR,** counted by a `Dev-Loop-Run:`
   trailer on loop commits. After three, the run idles and says so.
6. **Review is static.** The reviewer reads the diff and the files; it runs no
   code, because a write-scoped token beside PR-authored code is the classic
   pwn-request shape even from a same-repo branch.

## Validation (this session)

- `loop_guard.py --self-test`: run locally (plain Python, not pytest, touches
  no research code and runs no Git).
- YAML parse: PyYAML installed into the scratchpad, if pip works.
- actionlint: the release binary run from the scratchpad, if it downloads.
- Anything that could not run is listed as unchecked in CHECKPOINT and the report.
