# Ruleset for `main`: steps (not applied)

Spec 045 FR-012. **Nothing here has been applied.** Camden applies it, after
deciding D-3 (spec §6).

## Why the loop needs it

Without a ruleset, any token with `contents: write` can push straight to
`main`. The dev loop's `publish` job holds one. It only ever pushes `loop/*`
branches, and the agent job's token is read-only, but the guarantee that
nothing reaches `main` except through a reviewed PR belongs to GitHub, not to
a script in the repository it guards. **Apply this before uncommenting the cron.**

Facts this rests on (2026-09-30):

- `cstroh01/Quant-ML-Bot` is **public** (GitHub API: `"visibility": "public"`).
  Rulesets are available on public repositories on GitHub Free.
- The check to require is the job **`test`** in `.github/workflows/test.yml`
  (workflow "Tests"). Required checks match by job name, so no other job in any
  workflow may be named `test`. None is today.

## D-3 first: Camden's direct pushes

Camden commits to `main` directly in GitKraken today (recent history:
`e19d57c`, `bb16148`, `9457d8f`). "Require a pull request" blocks that for
everyone not on the bypass list. Pick one:

- **(a) Recommended. Bypass for the Repository admin role, "Always allow".**
  Camden's own pushes work as now. Loop PRs, which come from
  `github-actions[bot]` (or the app chosen under D-2), are fully gated.
  Cost: Camden's own direct pushes skip the `test` check, as they do today,
  and the merge button on a red loop PR will offer him "bypass rules". Do not
  take it on a loop PR.
- (b) No bypass. Camden also works through PRs. Strictest; changes his workflow.

## Steps (web UI)

1. Repository → **Settings** → **Rules** → **Rulesets** → **New ruleset** →
   **New branch ruleset**.
2. **Ruleset name:** `main`.
3. **Enforcement status:** **Active**.
4. **Bypass list** (D-3 a only): **Add bypass** → **Repository admin** →
   mode **Always allow**.
5. **Target branches:** **Add target** → **Include default branch**.
6. **Rules**, set exactly these:
   - **Restrict deletions**: on.
   - **Block force pushes**: on.
   - **Require a pull request before merging**: on.
     - Required approvals: **0**. (A solo owner cannot approve his own PRs; any
       number above 0 blocks him. Rule 9 is the human gate, not a click.)
     - Dismiss stale approvals, require review from Code Owners, require
       approval of the most recent push, require conversation resolution:
       **off**. (Turning on conversation resolution would make Camden resolve
       every loop-review comment before merging. A defensible choice; off by
       default here.)
   - **Require status checks to pass**: on.
     - **Add checks** → `test`, source **GitHub Actions**. If the search does
       not list it, the check has not run recently; push any branch first, or
       type the name.
     - **Require branches to be up to date before merging**: **off**. With one
       loop PR at a time it buys little and forces an update-branch click on
       every merge.
   - Everything else: off.
7. **Create**.

Optional, later: also require `web` and `actionlint` (from `test.yml`). They
are left out because the request named the Tests check only.

## Equivalent API call (reference only; not run)

The UI is the primary path. This payload follows the REST reference for
"Create a repository ruleset" as fetched 2026-09-30. It has **not** been run,
and two values are **UNVERIFIED**: `actor_id: 5` as the Repository admin role,
and `integration_id: 15368` as the GitHub Actions app. Omit `integration_id`
to accept the check from any source.

```sh
gh api --method POST repos/cstroh01/Quant-ML-Bot/rulesets --input - <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ],
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false } },
    { "type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [ { "context": "test", "integration_id": 15368 } ] } }
  ]
}
JSON
```

## After applying: what to expect

- Until D-2 is settled, a loop PR may show `test` as **expected / waiting**
  forever (see `token-options.md`). The ruleset then blocks the merge. That is
  the ruleset working: it is refusing an unchecked change.
- Check it took: Settings → Rules → Rulesets shows `main` **Active**, and the
  next loop PR's merge box lists `test` as required.
