# STATE

## Verified checkpoint — 2026-10-19 America/New_York

Public main audited: `98ab2f716f1c969e6a66032d658841b3a371365c` after #259.
The merge retains #255 and adds exactly the three-file reviewed #259 delta.
The previous version of this file described superseded drafts and a $100 cap.
This checkpoint records merged code/evidence, not an observed running deployment.
Camden owns the active spec and every human-gate decision.

**The project is unfinished. LIVE is NOT ARMABLE.** The read-only command
`python scripts/gate_checklist.py docs/implementation/spec-059/gate-manifest.json`
reports missing items 4, 6 and 7. Do not infer authorization from a passing
test, a replay, a configured budget, an API key, a queue status or this file.

## Allocation and research

- Spec 061 buffered equal weight is implemented in the shared planner and
  PAPER/preview input path. It targets a 7% pre-cost reserve at monthly
  decisions across eight sleeves, with next-session execution. Its reserve
  is not a guaranteed daily cash floor.
- The protected LIVE cap is **$200 of settled cash**, never increased by
  deposits. `SafetyConfig` has percentage limits, not a dollar-budget field.
  All account-specific fractional eligibilities remain unverified here.
- Spec 058 remains the recorded active research spec (G11). Its preregistered
  25-ETF family and spent holdout are unchanged. Its published verdict is
  **FAIL**; see [results](implementation/spec-058/results-20261016.md).
- Spec 061 is an allocation with **NO EDGE CLAIMED**, not an ML stock picker
  or a passing replacement for the failed edge research. Its recorded report
  and costed replay are in [spec-061](implementation/spec-061/).
- Ledger: `docs/trials/trials.jsonl`, 898 lines, SHA-256
  `6c3c416edba3ea9b52d05ea59967d20be7b755204787312d731250fc53e7e65e`;
  anchor SHA-256 `8bec008c52f463c6eaf802b9852e2af4b5969370204b4c59e0261766eeac5a8d`.
  These artifacts exist at the checkpoint. Never rerun a recorded family or
  rewrite its ledger to resume work.

## Current completion request

Camden's 2026-10-17 chat choices: keep free data; expand research to US stocks
and ETFs, excluding OTC, leveraged and inverse products. Spec 062 implements
data-collection candidates for this request, separately from frozen trials
and LIVE promotion. See its [audit](implementation/spec-062/integration-checkpoint-20261019.md)
and [tasks](../.specify/specs/062-expanded-research-universe/tasks.md).
New draft work is not deployed or accepted merely because it exists in a PR.

The current deployment input path uses Alpaca; recorded research uses Tiingo
with Alpaca checks/exclusions. EDGAR/ALFRED adapters are not automatically
features. Supplemental EODHD implementation still needs real first-fetch
acceptance. Massive #198 remains held; its deprecated endpoint assumptions
and use entitlement need resolution. A source key does not prove training use.

## Remaining acceptance and software work

| Area | Required next evidence/work |
|---|---|
| Capital item 1 | Refresh the full and mutation checks at the exact future arming revision. |
| Capital item 4 | Required reconciled PAPER submit sessions on each profile, with per-order modeled/realized costs. |
| Capital item 6 | Distinct clean Fidelity previews and latest-session dedicated-account holdings CSV match. |
| Capital item 7 | Settled cash and restricted-budget evidence; then Camden's own arming decision. |
| Operations | Real fills/reconciliation, notification delivery, host/task and scheduling acceptance. No production scheduling is established by this audit. |
| Data | 044 probe/selections and 035 nominal bundle chain; source entitlement/coverage/rights; independent action/price reconciliation; real expanded-universe receipts. |
| Research | New preregistration and prospective validation for stocks/ETFs; no reuse of the spent 058 holdout. |
| Reporting | 033 matrix currentness/Gate 3 API, 046 cost reporting, 047 tearsheet work and 038 disclosure/UI work remain. |

The legacy dashboard gate route is not the seven-item capital-gate checklist;
it still has evidence-wiring work. Consult the checklist manifest and typed
evidence, not the old dashboard wording, for the current gate inventory.

The earlier cloud-only audit did not inspect the local/private environment.
The 2026-10-18 local reconciliation supersedes its inference that credentials
or hosted infrastructure are absent. Credential values were not inspected;
configured names do not establish authentication, entitlement or acceptance.
The Windows preview input refresher needs Alpaca keys in its environment; it
does not load `.env`. Fidelity uses the separate native-vault launcher.

## Hosted PAPER and review checkpoint — 2026-10-18

Private hosted infrastructure was reverified on 2026-10-19: the production
workflow is manual-only, with no production runs and no production profile
state namespace. Fixture drills are separate evidence. Source pin/tree and
state matched the retained audit; this is not current account acceptance.
Both-profile previews, broker-truth reconciliation, actual notification
receipt and realized-versus-modeled fills remain unverified. Scheduling waits
for G16 and a separate governance PR merged by Camden. No wake-up is implied.

PR #255 was merged by Camden at `8b0916db3c7528b3dccd03d32875eca472807b2d`;
the API-verified merge tree matches reviewed `ad60c5b053cf5ab3ffb97ffb3c8b5e71e8cf5753`.
Its pre-existing D-3 absent-class validator/spec conflict remains separate.
PR #256 at `67dfd7f68acc1e86b457f7ca07e7814f3966ef5e` is draft/held.
T011 corrects Nasdaq segment MIC exclusions; T012 refuses non-session as-of
dates. Its actual-root suite passed 2,613 tests, with 2 skipped and 12 xfailed;
fresh Codex review at that head found no major issues. Independent Claude
review is pending: the CLI was spend-limited, Camden reported no remaining
Claude usage, and the existing GitHub Claude workflow is manually disabled.
These facts do not establish dual-review acceptance. No billing, review routine
or workflow setting was changed.

Usage and integration-audit publication moved to this checkpoint unit to keep
the code PR bounded. PR #257's 056 T010 correction is published at
`6ee6aefe9161693d2b904752ecf160cab3c2bde2`: 32 focused tests and the actual
branch suite passed (2,605 passed, 2 skipped, 12 xfailed); all 1,284 frozen files
and ten protected hashes match. Fresh reviews remain pending; the authorized Codex review resumed on
2026-10-19 after its usage reset. Claude remains unavailable. PR #259 was merged by Camden as
`98ab2f716f1c969e6a66032d658841b3a371365c`, from reviewed head
`69df117eb36ea5c97b8dd32edd38e206ef323d3b`. This does not update a deployed
pin or accept a real Fidelity session.

## Standing delegations retained (Camden, 2026-10-09)

- G12: 044 T003/T004 reviews, Codex plus Claude.
- G13: bounded fetches and the 044 T007 probe, Codex lane, without per-run go;
  the current task's narrower authorization still governs a particular call.
- G14: 040 T001 kickoff check, the lane.
- G15: supervised PAPER drills, Codex, with schedules disabled.
- G16: schedule enablement only after all drills, broker reconciliation and
  notification delivery are verified; the governance PR needs Camden's merge.
- G17 is not in force; constitution Rule 9b condition 3 governs decisions.

## Working rules

Read `AGENTS.md`, the constitution, `CLAUDE.md`, SCOPE and the numbered spec.
Use `docs/autonomy/queue.json` as a work map, then verify its dependencies:
some ready/blocked labels lag merged work. Keep protected source/pins, trial
bytes, KILL/HALTED and human gates intact. New source acceptance and any LIVE
change must earn their actual evidence; this checkpoint authorizes neither.
