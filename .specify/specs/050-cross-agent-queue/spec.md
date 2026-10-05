# Draft specification 050: cross-agent queue admission and review

**Created:** 2026-10-04. **Status:** proposal only; no implementation authorized.
**Number check:** local spec directory listing ends at 049; reservation search found no 050 allocation. Recheck remote state before adoption.
**Input:** Camden's cloud-usage/Codex research request. Companion: `docs/autonomy/proposals/cloud-usage-and-codex-20261004.md`.

## Problem and intended behavior

The routine checks only Claude PRs and has no atomic reservation. A manual Claude task and a Codex task can select the same item before either opens a PR. The existing workflow reviewer accepts only loop branches. Codex implementation therefore needs explicit ownership, provenance, and independent review before it can share this queue.

Start with Camden dispatching one implementation unit at a time. Optional automation preserves spec 045's read-only triage/agent versus write-capable publisher separation. This spec grants no Git permission, changes no governance, and never touches trading execution or production artifacts.

## Scope and prerequisites

- Initial scope: task reservation contract, all-lane dedupe, provider provenance, review freshness, draft publication, and an optional Codex backend for the existing development loop.
- No production strategy, data, broker, risk, ledger, paper schedule, or capital-gate changes. Q21/Q22 retain spec 049's authority.
- Camden adopts any Rule 10 amendment in its own dedicated commit. Companion governance/prompt/workflow changes require his separate approval and numbered tasks.
- Spec 045 D-1–D-6 remain open until Camden records decisions. The cloud amendment does not settle workflow-step Git authority.
- Before implementation, Camden must approve this spec and commission `plan.md` and `tasks.md` as separately scoped work. This request writes `spec.md` only.

## Functional requirements

| ID | Requirement |
|---|---|
| FR-001 | Admission requires a numbered task or explicitly commissioned spec/report output, exact allowed file set, queue ID, base main SHA, provider, session/task identifier, and lane authorization. Queue readiness alone grants nothing. Missing/inconsistent fields refuse work. |
| FR-002 | Scan all relevant open and merged PRs across Claude, Codex, loop, and human branches, including complete pagination. Match exact queue IDs and structured provenance; never infer independent provider solely from GitHub author. Unavailable API state blocks admission. |
| FR-003 | Immediate mode uses Camden as sole dispatcher, with all automated writers paused and existing writers stopped before reservation. Hold global implementation WIP at one through review until merge/close/cancel. Reviewers read only. No claim that PR scanning alone provides atomicity. |
| FR-004 | Automated admission, if approved, must have one trusted dispatcher and durable atomic compare-and-set reservation storage outside agent write access. At most one active implementation reservation globally. Every enabled producer must participate or be disabled. A missing dispatcher/storage failure blocks all work. |
| FR-005 | Reservation lifecycle records assigned, running, awaiting-review, and released with session ownership. Only trusted dispatcher/Camden updates it. Cancellation requires stopped-writer evidence; expiry never grants automatic takeover. Retry keeps ownership and cannot create a second producer. |
| FR-006 | Queue schema 1 stays human-owned, with ready/blocked/done. Reservation state is separate. Dependencies require verified merged delivery, not a completed chat, closed unmerged PR, or a ready flag. Agents propose queue/STATE changes only in cloud/local mode. Existing 045 STATE requirements remain intact pending separate approval. |
| FR-007 | Cloud tasks use one same-task branch with the correct claude/ or codex/ prefix; provider-created branches count. Local tasks run no Git. Workflow-managed branches remain loop/ under a separately authorized 045 lane. New publication is draft-only; existing target branches cannot be taken over by a different task. |
| FR-008 | Admission and publication independently enforce allowed paths and the existing 300 added-plus-deleted line cap. Preserve every lane-specific protected path, including AGENTS.md, secrets, pinned files and live safety data. Oversized work stops for a specified split. Normalize path separators/case for Windows and reject traversal, symlinks, binaries and rename tricks. |
| FR-009 | In the optional Action backend, triage uses read-only GitHub access; agent has no publishing credential and runs no Git/gh; only trusted wrapper code packages artifacts. Publish uses a fresh runner and trusted-main guard, treats artifacts as data, and never executes/imports/installs agent-written code or runs pytest. |
| FR-010 | Backend is selected from a fixed Camden-approved set (Claude or Codex), not prompt text or a PR field. One backend invocation per admitted run. Codex Action uses a reviewed pinned revision/CLI, Linux, constrained sandbox, and drop-sudo or verified unprivileged execution. No new trading-runtime dependency. |
| FR-011 | Persist provenance of the producing provider/session and exact head revision. Independent review must be by the other provider, static and comment-only, covering that exact revision. Same-provider self-review, old reviews, missing evidence or reviewer failure cannot satisfy admission to Camden's merge decision. |
| FR-012 | Deduplicate reviewer work by repository/PR/head/reviewer-provider. A changed head invalidates prior review evidence. Reviewer consumes trusted instructions and untrusted diff as separate inputs; no bot-trigger mentions, agent approvals, ready transitions or automatic merges. |
| FR-013 | Implementation verification records offline full-suite command, Python version, exit/counts, Windows evidence, isolated Rule 12 mutants and clean controls. Protect production artifacts from writes and verify inventory/hashes; reports never upgrade unrun or stale checks to passing evidence. Documentation-only exceptions need Camden-approved prompt wording. |
| FR-014 | Environment controls deny production credentials and protected writes. Setup allows only required pip/GitHub access; tests use offline synthetic roots. Disable unused hosted search/apps/MCP separately. Provider inference traffic is infrastructure, not permission for arbitrary task egress. Verify subprocess and escalation boundaries before use. |
| FR-015 | No eligible reservation, unmet dependency or unchanged reviewed head exits before model invocation. Record non-secret per-run usage and outcome. Configure a finite runtime, attempt cap and chosen spend cap; API spending is separate from subscription usage. Budget exhaustion returns a blocker, never a weakened gate. |
| FR-016 | Camden alone resolves governance decisions, marks ready, accepts explanations and merges. CI green (including test-windows), required Windows evidence and no unresolved P0/P1 remain separate requirements. No LLM verdict replaces deterministic gates or Camden's comprehension. |

## Rule 12 acceptance: each gate must fail for its own defect

All automated proofs run in isolated copies with fake GitHub/provider/storage clients and no credentials or real remote writes. Each negative case needs a matching valid control, exact refusal code/path, and assertions of no downstream model call or publication where appropriate. Mutate the field the real admission/publisher actually consumes; do not test a duplicate validator.

| Criterion | Planted plausible defect | Required red proof and green control |
|---|---|---|
| SC-001 authorization | Missing task, stale main SHA, unauthorized lane or unknown backend, one field at a time | Real admission refuses each cause; valid reserved task enters once. |
| SC-002 dedupe | Existing Q21 PR on codex/ or human branch on the second API page; Q2/Q21 substring ambiguity | Q21 duplication refused; Q2 alone does not falsely block Q21; incomplete pagination refuses. |
| SC-003 dependencies | Parent PR closed without merge; queue still ready | No child dispatch; merged matching parent permits it. |
| SC-004 atomic claim | Two producers start from the same empty reservation version, synchronized at a barrier | Exactly one obtains reservation and starts; loser has no edits/model call. Removing compare-and-set must make this test fail. |
| SC-005 stale ownership | Expired reservation while old writer still runs; retry with another session ID | No takeover; only confirmed stopped writer plus authorized release permits the next assignment. |
| SC-006 publication scope | Same-task metadata claims another branch; provider prefix mismatch; new PR lacks draft flag | No push/PR on invalid target, and draft API argument asserted on valid new PR. |
| SC-007 path/cap | Protected path through rename, backslash/case, traversal or symlink; 301 changed lines versus 300 | Refuse correct path/cap reason; valid 300-line permitted patch passes. Exercise applied diff, not agent-declared path counts. |
| SC-008 privilege split | Inject publish token into agent job; malicious artifact contains executable hooks/setup/test code | Trusted workflow/config validation rejects token exposure; publisher trace proves no artifact execution. Valid data-only patch publishes through mocked API. |
| SC-009 independent review | Same provider under different account, forged author field, or reviewer head one commit behind | All refused; authenticated opposite-provider record on current head accepted. Clean control proves gate is not always red. |
| SC-010 review dedupe | Duplicate event and then changed-head event | One review per identical key, new review on new head. Mutant dropping head from key must fail. |
| SC-011 verification | Remove Windows evidence, alter production-artifact hash or claim success with nonzero test exit | Each refused for its own field; valid offline evidence accepted. No production artifact is touched by these tests. |
| SC-012 network/filesystem | Controlled harmless disallowed destination, protected fixture write, secret-read sentinel through subprocess | Enforcement denies each; allowed synthetic file and approved dependency destination controls work. No broker/market endpoint is contacted. |
| SC-013 budget/no-op | No item, unchanged head, exhausted spend, or retries beyond cap | Provider invocation count stays zero; one eligible budgeted run invokes once. |
| SC-014 human gate | Agent output requests approval/merge/ready transition | Publisher cannot issue those API operations; draft-only control works. Injection remains inert data. |

Purely human steps are not claimed as automated gates. Record a supervised dry run demonstrating one reservation, one draft, independent current-head review, and Camden's decision. Do not mark acceptance complete based only on written tests; include actual red/control results.

## Proposed implementation boundaries and adoption order

1. Camden adopts governance and manual reservation/prompt protocol; no autonomous edits to governance. Run Q21 locally under spec 049 and record friction.
2. Commission small units for contract/guards and their isolated tests; review each before the next. Future candidate paths are `.github/scripts/`, `.github/workflows/`, `tests/`, and `docs/autonomy/`, all subject to explicit Camden scope approval. This draft authorizes none of them.
3. Add review routing/freshness and prove it on synthetic data. Preserve existing high-signal AGENTS checks.
4. Add optional Codex Action backend behind disabled scheduling, only after 045 decisions and dispatcher enforcement. Pin dependencies with Rule 6 justification.
5. Camden runs one supervised dispatch. Keep cron disabled until actual draft publication, required CI triggering, independent review, network restrictions and budget accounting work.

## Open decisions

- D-1: approve expanded cloud lane or retain local-only Codex implementation.
- D-2: manual reservation indefinitely or trusted automated dispatcher after measured need; storage/atomic primitive and cross-provider integration must be chosen before FR-004 implementation.
- D-3: Q21 local pilot and Q22 cloud, or review-only Codex.
- D-4: settle spec 045 decisions and publishing identity independently; no hidden authorization through this spec.
- D-5: confirm actual Codex branch/draft controls, account review triggers, and environment enforcement; if incompatible, stay local.

## Limitations and evidence

This is a design, not a deployed safety guarantee. Cross-provider review can share blind spots. Prompts do not enforce filesystem boundaries. Cloud product controls and account access need supervised verification. A single-dispatcher reservation prevents races only if every writer participates or is disabled. None of this advances the capital gate.

Current product sources and checked dates live in the companion proposal. The design follows the inspected spec 045 trust split and current repository rules; tests, Actions, network controls, cloud tasks and publication were not executed in this authoring session.
