# The GITHUB_TOKEN trigger problem: options (none implemented)

Spec 045 FR-013, decision D-2. **No option below is implemented.** The dev
loop today opens PRs with the job's default `GITHUB_TOKEN`.

## The problem

GitHub, verbatim (docs source fetched 2026-09-30,
`content/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow.md`
and `data/reusables/actions/actions-do-not-trigger-workflows.md`):

> When you use the repository's `GITHUB_TOKEN` to perform tasks, events
> triggered by the `GITHUB_TOKEN` will not create a new workflow run, with the
> following exceptions:
> * `workflow_dispatch` and `repository_dispatch` events always create workflow runs.
> * `pull_request` events with the `opened`, `synchronize`, or `reopened`
>   activity types: when a workflow using `GITHUB_TOKEN` creates or updates a
>   pull request, the resulting `pull_request` event creates workflow runs in an
>   **approval-required** state. […] a user with write access to the repository
>   can start the runs by selecting **Approve workflows to run**.

The second exception is new. Its feature file in the docs repository says
"currently rolling out on dotcom", so whether it is live **for this repository**
is **UNVERIFIED** until a loop PR shows the banner.

For the loop, that means:

- `test.yml`'s `push` trigger never fires for a loop push.
- `test.yml`'s `pull_request` trigger fires only as an approval-required run
  (if the rollout reached this repo), or not at all.
- `loop-review.yml` is in the same position.
- Under the `main` ruleset (`ruleset.md`), a loop PR whose `test` check never
  runs cannot be merged without a bypass. The ruleset fails closed, as it should.
- Separately, the `GITHUB_TOKEN` can open PRs only if the repository setting
  **Allow GitHub Actions to create and approve pull requests** is on
  (Settings → Actions → General → Workflow permissions). That one switch also
  lets the token *approve* PRs (spec 045 D-4).

## Options

### A. Fine-grained personal access token

A PAT on Camden's account, limited to this repository, Contents and Pull
requests read/write, stored as a secret, used only in `publish`.

- **For:** one secret, simple. Events it causes trigger workflows normally.
- **Against:** it **is Camden**. Loop PRs and pushes are authored as
  `cstroh01`, indistinguishable from his own work, which blurs the Rule 9
  trail ("who wrote this?"). Every guard keyed to `cstroh01` (`claude.yml`'s,
  this repo's dispatch guards) treats the loop as Camden. It is long-lived and
  must be rotated by hand. Anthropic's own action docs advise against static
  PATs where an agent could reach them.

### B. Dedicated GitHub App (**recommended**)

A private app owned by `cstroh01` (e.g. `quant-ml-bot-loop`), installed on this
repository only, with **Contents: read & write** and **Pull requests: read &
write**. Two secrets: its client ID and private key. `publish` mints a token
with `actions/create-github-app-token@v3` (current major; `client-id` input,
`app-id` deprecated) for the run's duration.

- **For:**
  - Short-lived per-run tokens.
  - A distinct identity (`<app>[bot]`), so loop work is never mistaken for Camden's.
  - Events trigger `test.yml` and `loop-review.yml` normally, with no approval
    click and no per-workflow plumbing.
  - The repository setting in D-4 can stay **off**, so no Actions token can
    approve a PR.
  - The token exists only in `publish`; the agent job keeps its read-only token.
- **Against:** about ten minutes of setup. The private key is a long-lived
  secret to store and rotate.

Sketch, for when it is chosen (not in any workflow today):

```yaml
# publish job only
- id: app-token
  uses: actions/create-github-app-token@v3
  with:
    client-id: ${{ secrets.LOOP_APP_CLIENT_ID }}
    private-key: ${{ secrets.LOOP_APP_PRIVATE_KEY }}
# then: actions/checkout `token: ${{ steps.app-token.outputs.token }}`,
# GH_TOKEN from the same output, and the app's bot name/email for commits.
```

### B′. The Claude GitHub App through the action's OIDC exchange

What `claude.yml` does today (`id-token: write`, no `github_token`). Rejected
for the loop: it hands the write token to the job running the agent, which is
exactly the trust boundary the three-job design removes.

### C. Dispatch the checks explicitly

Add `workflow_dispatch` to `test.yml` (and use `loop-review.yml`'s existing
one). After pushing, `publish` runs `gh workflow run test.yml --ref <branch>`
and `gh workflow run loop-review.yml -f pr=<n>`.

- **For:** no new secret; dispatch from `GITHUB_TOKEN` always creates a run.
- **Against:**
  - Needs `actions: write` on `publish`, outside "contents and pull-requests
    only".
  - Whether a dispatched run's `test` check, attached to the branch head
    commit, satisfies the ruleset's required check is **UNVERIFIED**.
  - Every future `pull_request` workflow must be remembered and dispatched by
    hand; forgetting one is silent.
  - Still needs the D-4 setting on, to open the PR at all.
- **The `workflow_call` variant does not work:** a reusable `test.yml` called
  from `dev-loop.yml` reports inside the dev-loop run, against `main`'s commit,
  so the PR's head commit never gets a `test` check.

### D. Status quo: approve the runs

Keep `GITHUB_TOKEN`, turn the D-4 setting on, and click **Approve workflows to
run** on each loop PR.

- **For:** zero setup. Camden opens the PR to merge it anyway.
- **Against:**
  - One click per push, and CI only starts when he arrives, so he waits for it.
  - The loop's `fix-pr` mode never sees a red check until he has clicked.
  - Depends on a rollout that is **UNVERIFIED** here. If it is not live, no run
    is created at all, and the only fallback is a manual push or a
    close-and-reopen.

## Recommendation

**B.** It is the only option that keeps every property the loop was designed
around: least privilege, short-lived credentials, a write token only where no
agent code runs, a non-human identity, and the D-4 switch left off.

**Interim, for the first supervised run (SC-004):** D. If the approval banner
appears, the rollout is live and D works with no setup. If it does not appear,
that is the evidence this file marks as unverified, and B is required.
