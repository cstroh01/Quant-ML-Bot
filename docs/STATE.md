# STATE

## Verified checkpoint — 2026-11-20 America/New_York (LIVE re-armed on spec 069)

Public main `2ff292a` (#336, the §11.3 item 1 refresh after spec 069); both LIVE pins
(`QMB_PINNED_SHA`, `QMB_FIDELITY_PIN`) are `2ff292a`. Camden owns every human-gate decision; nothing
here authorizes a change to LIVE. Spec 061 is an allocation: **NO EDGE CLAIMED; NOT DSR-GATED**. No
performance figure is reported without both baselines and costs.

**The §11.3 capital gate is complete** at `2ff292a`: `python scripts/gate_checklist.py
docs/implementation/spec-059/gate-manifest.json` prints `ARMABLE` (manifest SHA-256 `f48e4052…`).
Item 1 (`item1-evidence-20261112.json`, refreshed 2026-11-20) is the full suite and every mutation
driver run at `338524e` (the spec 069 merge): 3568 passed, 7 skipped; drivers 72/72, each leaving the
tree byte-identical. Items 2–7 are unchanged from the 2026-11-16 checkpoint below.

**LIVE sessions since arming** (private `fidelity-live` runs; records on the private `ops-state` branch):

| Session (ET) | Pin | Run | What happened |
|---|---|---|---|
| 2026-11-16 | `0a6b5ff` | 43893476063 | HALTED, no order filled: Fidelity has no record of the one DBC order the adapter counted as placed (057 D-13). Fixed by spec 068 (#333, merge `1827d5d`): a preview counts only when its reply validates it and a placement only when Fidelity accepts it. Item 1 refreshed (#334, `5b8e4fb`); re-armed 2026-11-17. |
| 2026-11-17 | `5b8e4fb` | 44111211009 | Fidelity refused the first preview (DBC, `respTypeCode` `"E"`); 068 refused it, placement was never called (`place_calls` 0), HALTED. The cause was an account condition at Fidelity that Camden resolved that day; Camden cleared HALTED. |
| 2026-11-18 | `5b8e4fb` | 44332474704 | First trading session: all eight sleeves previewed and placed (`place_calls` 8). The first seven read `FILLED` in the same run. |
| 2026-11-19 | `5b8e4fb` | 44551739454 | HALTED, nothing sent: Fidelity's status list no longer showed the previous session's last order (TLT), so it read unknown (`ReconciliationBlocked`; spec 068's known risk). Camden confirmed the shares in the account; the reservation was released as `FILLED` by hand and HALTED cleared the same day. Fixed by spec 069. |
| 2026-11-20 | `5b8e4fb` | 44760555926 | Clean: account and bot ledger reconciled exactly; no orders (`place_calls` 0). |

**Spec 069** (#335, merge `338524e`): after each accepted placement the adapter looks the order up
read-only at about 2, 5, 10 and 20 seconds and records the first terminal status Fidelity reports; the
next session uses that record only when Fidelity's list shows none of the order's numbers. Camden
repinned to `2ff292a` and re-armed on 2026-11-20 (arming record bound to manifest `f48e4052…`). The
first LIVE run on this code is 2026-11-23; the next trades are expected at the December rebalance
(first December session 2026-12-01). Known risk (spec 069): an order still working after the last look
whose status Fidelity drops by the next session still halts that session, for a hand release.

**PAPER.** Unchanged from the checkpoint below; both profiles ran on 2026-11-20, exit 0.

**Ledger.** `docs/trials/trials.jsonl` SHA-256
`6c3c416edba3ea9b52d05ea59967d20be7b755204787312d731250fc53e7e65e`, unchanged through `2ff292a`.

Limitations are in the README register and travel with every result (constitution Rule 16).

---

## Earlier checkpoint — 2026-11-16 America/New_York (v1.2, final v1; superseded)

Public main at the close-out merge; LIVE pin `0a6b5ff` (the final gate PR's merge).
This checkpoint records merged code and evidence and the observed first LIVE session. Camden owns
every human-gate decision; nothing here authorizes a change to LIVE.

**The §11.3 capital gate is complete.** `python scripts/gate_checklist.py
docs/implementation/spec-059/gate-manifest.json` prints `ARMABLE`:

| §11.3 item | Evidence on main |
|---|---|
| 1 Full suite and mutation suites | `item1-evidence-20261112.json`, run on the gate PR's first commit (3486 passed, 7 skipped; drivers 70/70) |
| 2 Allocation and both baselines | spec 061 trial report (c6524ee) |
| 3 Safety layer and drills | `drill-evidence-20261016.json` (ff83200) |
| 4 PAPER evidence | `paper-evidence-20261109.md`: 11 sessions per profile, 20/20 orders reconciled, realized vs modeled cost per order |
| 5 Historical replay | spec 061 replay evidence (c6524ee) |
| 6 Fidelity | 5 clean API-reconciled preview sessions at pin 89bad88 (11-03, 11-04, 11-05, 11-06, 11-09) |
| 7 $200 settled-cash budget | `item7-budget-evidence-20261112.json`, built on the armed code |

**LIVE.** Camden armed `live_fidelity` on 2026-11-13 (FIDELITY-HOST.md; arming record bound
to the manifest's SHA-256). Cap: $200 of settled cash, never raised by deposits. One attempt per NYSE
session at about 10:10 ET, dispatched by cron-job.org (GitHub's own schedule fires hours late). First
session 2026-11-16 (private run 43893476063, pin `0a6b5ff`): **HALTED, no order filled.** The safety
gate allowed one buy (DBC, 0.755 shares); the adapter previewed and placed it (`place_calls` 1), but
Fidelity has no record of that order, so the reconciliation before the next order found no known
outcome (`ReconciliationBlocked`, FR-013 stage `allocation`) and the run halted before any other
order. The adapter counted a placement Fidelity did not accept as sent (spec 057 D-13). It failed
closed: no money moved. LIVE stays halted (HALTED latched, the DBC reservation open) until a
reviewed fix after v1.2. Spec 061 is an allocation:
**NO EDGE CLAIMED; NOT DSR-GATED**. No performance figure is reported without both baselines and costs.

**PAPER.** `paper_small` and `paper_large` run unattended every trading day at Alpaca paper
(08:05/08:35/09:05 ET dispatches), every order reconciled. `paper_small` buys whole shares only until
its profile's `fractional` flag is set (a recorded Camden decision of 2026-11-03, not yet applied).

**Operations.** Halts latch (`HALTED`/`KILL` on the private `ops-state` branch) and are cleared only by
Camden. Every refusal opens a private issue. Restore drills passed for all three profiles (spec 066).
A failed ops-state push is retried three times and a persist failure halts with a named reason
(057 D-12). Off switch: `QMB_FIDELITY_LIVE_ENABLED` to anything but `true`, or delete the arming secret.

**Ledger.** `docs/trials/trials.jsonl` SHA-256
`6c3c416edba3ea9b52d05ea59967d20be7b755204787312d731250fc53e7e65e` (371 files under docs/trials),
unchanged by every PR from #296 through v1.2.

**V2 (SCOPE §12.2, not v1 blockers).** ML trading decisions and promotion (053); the ~100-ETF universe
and stock research (060/062, including held #198); intraday/crypto/new platforms; reporting/UI sweeps
(038/046/047); capital scaling beyond $200 (spec 065, draft #289).

Limitations are in the README register and travel with every result (constitution Rule 16).

---

## Earlier checkpoint — 2026-10-20 (superseded; kept for the record)

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

## Hosted PAPER and delivery checkpoint — 2026-10-20

GitHub GET evidence at 14:34 UTC: private main remains
`ed4afb5e208c07b83c1a26e4779fcb85b792a03f`; paper-loop is manual-only with no
schedule. Exactly two production runs exist, each attempt one: small preview
[39419036470](https://github.com/cstroh01/Quant-ML-Bot-private/actions/runs/39419036470)
succeeded; large preview
[39419874952](https://github.com/cstroh01/Quant-ML-Bot-private/actions/runs/39419874952)
failed. Retained sanitized inspection records classify the latter as
MARKET_DATA_READ / HTTPError; HTTP status was not retained and cause is unknown.
Small acceptance had capacity exclusions. Neither is a completed/reconciled
trading session. The authorized sequence is closed after failure; no retry,
orders, workflow/pin/profile changes or schedule authority follows.

Final ops-state is `2a4a470bf446db0e4ff190e5cb5172773f17af97`; the failure
commit preserves small-profile state. The PAPER public-code pin remains
`c1dbc854b146095cd47283ef4cbc1b5838f20d94`. Broker-truth reconciliation,
per-order realized/modelled costs and actual notification receipt remain gates.
The Fidelity host template in PR263 is dormant and not installed privately.
Scheduling waits for G16 and Camden's separate workflow merge.

PR255 and PR259 are merged. The current candidate/EODHD/checkpoint stack is
PR256 -> PR257 -> PR258; Codex markers at heads `67dfd7f`, `6ee6aef`,
`5fdcbe7` report no unresolved findings. Q124/report fix PR264 at `010f2616`
and T023 lifecycle PR265 at `7f0ab77` have completed clean Codex markers.
Separate reader and T033/T075 packets remain offline proposals. Saved composed
receipts do not certify merged main or deployed broker code.

Camden's October20 completion instruction waives Claude reviews and requires
recorded Codex second looks for existing/future changes. Adoption is through a
constitution-only human merge; do not infer a merge from this checkpoint.
Check the constitution and current exact-head evidence before delivery. This
documentation grants no new broker, schedule, capital or protected-path authority.

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
