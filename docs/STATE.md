# STATE

## Verified checkpoint — 2026-10-17 America/New_York

Public main audited: `c1dbc854b146095cd47283ef4cbc1b5838f20d94`.
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
and LIVE promotion. See its [audit](implementation/spec-062/integration-audit-20261017.md)
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

Cloud audit: no root `.env*` file, no configured vendor secrets/runtime
variables, and vendor hosts absent from the current allowlist. PC/private-repo
keys and task installation were not independently inspected. The Windows
preview input refresher needs Alpaca keys in its environment; it does not
load `.env`. Fidelity uses the separate native-vault credential launcher.

## Working rules

Read `AGENTS.md`, the constitution, `CLAUDE.md`, SCOPE and the numbered spec.
Use `docs/autonomy/queue.json` as a work map, then verify its dependencies:
some ready/blocked labels lag merged work. Keep protected source/pins, trial
bytes, KILL/HALTED and human gates intact. New source acceptance and any LIVE
change must earn their actual evidence; this checkpoint authorizes neither.
