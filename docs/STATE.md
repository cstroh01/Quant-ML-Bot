# STATE

## 2026-10-17 buffered-allocation adoption draft

Camden chose a fresh costed equal-weight allocation with a 7% target reserve,
after seeing T004; historical A1/B-BH remain untraded research results. New
spec 061 T005 is verified: candidate `8d4dfeda-10ef-4951-bf0e-147090ea9731`,
22/22 series completed, ledger 898 lines, head `c510408010dd8af4e1cdbeeb2c686706a8f33b0aa052272c2353e840ebcc17cc`.
See `docs/implementation/spec-061/trial-report-20261017.md` for costed figures,
post-hoc selection and limitations. This is not an edge claim or deployment.

T006 shared-planner/PAPER/input-bundle adoption is a local review draft. New
replays pass both stress windows at both PAPER budgets, but publication commit
fields deliberately remain unresolved in the gate manifest. Old A1 evidence
does not accept the new policy. LIVE budget remains $100 until the separate
protected $200 change is reviewed and merged; profiles.json is unchanged.
Fidelity fractional sizing requires its own protected 0.001-share precision fix.
Input refresh to 2026-10-16 is blocked: approved Alpaca environment keys absent.
No arming, broker orders, production pin or schedule change. All runtime gates
remain. The older checkpoint below is historical and has not been re-audited here.

The loop's working memory, and the one place to see where the repo stands.
**Camden owns** the active spec and every human-gate decision. **A loop PR
updates** Next, Blockers, Expected red, and Lane status in the same PR as its
work. Spec files stay the authority on their own tasks; this file points at them.

_Seeded 2026-09-30 by spec 045 from the tree at `e19d57c`. Camden confirms
the active spec (spec 045 D-5)._

_Refreshed 2026-10-15 ~20:45 CT by Claude (chat) from the tree at `2f53cd0` (#222 merged). Queue
item status lives in `docs/autonomy/queue.json`; this file summarizes it._

## Active spec

**058 — preregistered multi-asset edge research program**
([spec](../.specify/specs/058-edge-research-program/spec.md),
[tasks](../.specify/specs/058-edge-research-program/tasks.md)). Camden confirmed it on 2026-10-09
(gate G11). Since 2026-10-12 the target release is **v1.2** (`docs/SCOPE-V1.md` §11): specs 059
(preregistered LIVE allocation, no edge claimed) and 060 (ETF universe and free-data additions)
were adopted in #174, and §11.3 replaces §5 as the capital gate while §11 is in force.

## Operating model (2026-10-12, v1.2 acceleration)

- **Lanes.** Parallel Claude cloud lanes split by module ownership
  (`docs/autonomy/routine-prompt.md` v11): A research and gates, B data, C disclosure/reports/costs,
  D operations and PAPER. Any number of open PRs, no two sharing a file; units up to 600 lines.
- **Codex.** Exact-head reviews, Windows verification, bounded fetches (G13).
- **Merges.** Constitution Rule 9b (until v1.2 is tagged or 2026-12-31): agents merge a PR after
  CI, two independent exact-head reviews and the other Rule 9b conditions; Camden reads a daily
  digest. The LIVE money path, `SafetyConfig` values, governance paths and ledger writes stay
  Camden's.
- **PAPER `exec/`.** Agent-built and agent-merged under Rule 7a, keeping the refuses-LIVE test.

## Spec progress (ticked / total boxes in each `tasks.md`, at `2f53cd0` plus this sync)

| Spec | Boxes | Note |
|---|---|---|
| 033 trial ledger, DSR, PBO | 60/75 | Q33b route wiring is a Camden-authorized unit |
| 035 free unadjusted bundle | 7/24 | |
| 038 disclosure sweep | 15/39 | Lane C items ready |
| 044 nominal price reconstruction | 4/36 | Waits on 044 T007/T008 |
| 046 Rule 13 cost model | 7/15 | |
| 047 tearsheet correctness | 8/16 | Q67 blocked on the #158 revision |
| 049 / 051 / 055 PAPER operations | 7/13, 6/9, 5/7 | |
| 057 Fidelity LIVE adapter | 4/6 | Setup done 2026-10-15; preview session 1 on 2026-10-16 |
| 058 edge research | 11/19 | T015 run command merged (#222); T014 part 1 (#189) left open |
| 059 LIVE allocation | 6/10 | T007 harness merged (#207); its real-data run found gross-cap denials, fix in #223 |
| 060 universe and data | 0/8 | Lane B items ready |

## Next unblocked work

| Who | Items |
|---|---|
| Camden | 058 T015 `--record-trial` (dry-run passed on the real panel 2026-10-15, panel hash `3b80b330…`); merge #223; Fidelity preview sessions; PAPER sessions |
| Lane A | Q35, Q98, Q121, Q122, Q124 |
| Lane B | Q73–Q81, Q123, Q125 |
| Lane C | Q49–Q61, Q64, Q68, Q70, Q72, Q92, Q93, Q116, Q119, Q126, Q129, Q130 |
| Lane D | Q128 |

## Expected red on `main`

None. Check runs on `25577e9` all succeeded; full Linux suite in the cloud on `25577e9`:
2427 passed, 12 xfailed, 1386 subtests passed (Python 3.13.16).

Ledger: `docs/trials/trials.jsonl` 174 lines, SHA-256
`1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`; `trials.head.json` SHA-256
`f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`. Family declarations
`058-edge` (+ amendment 1) and `059-allocation` verify.

## Blockers (human gate reached)

| Where | Gate | Waiting on |
|---|---|---|
| 058 T015, T016 | Ledger-writing research and holdout runs | Camden runs them (T015 command in `docs/implementation/spec-058/T015-run-command.md`) |
| §11.3 item 5 | Replay on real data fails on `main` (2020 TLT gross-cap denials) | Camden merges #223 (touches the LIVE planner) |
| 033 Q33b (T063, T064) | `reports/api/routes/capital_gate.py` route reads the Gate 3 artifact | A Camden-authorized unit |
| 044 T003, T004, T007 | Probe reviews and live probe | G12/G13 delegations (Codex lane) |
| 047 Q67 (T010, T011) | Spec text and Q67 `allowed_paths` must be revised for the recorded-payload route, with an explicit as-of session (#158) | A spec 047 revision PR; then Q67 back to `ready` |
| 055 paper-loop `kill` input | Per-profile kill wiring in `ops/workflows/paper-loop.yml` (#168 proposal) | Camden's decision on #168 blocker 1 |
| §11.3 items 6–7 | Fidelity preview sessions; arming LIVE with the $100 budget | Camden |
| LIVE `exec/` (`fidelity_live.py`, `fidelity_reconcile.py`) | Rule 7a line-by-line review | Camden |

## Disagreements between this file's previous text and the tree

- The previous refresh (2026-10-09) described Rule 9a merges and Track A/B; Rule 9b and lanes A–D
  replaced them on 2026-10-12 (#175).
- Spec 058/059 `tasks.md` boxes and `queue.json` lagged merged PRs; synced 2026-10-15 (this PR).

## Delegations (Camden, 2026-10-09 (delegation answers G12–G16 in chat; recorded by Claude))

- **G12.** 044 T003/T004 reviews: Codex plus Claude.
- **G13.** Bounded fetches and the 044 T007 probe: the Codex lane, without a per-run "go".
- **G14.** The 040 T001 kickoff check: the lane.
- **G15.** PAPER drills: Codex.
- **G16.** Enabling the PAPER schedule after all drills pass. The `.github/` PR for it still needs
  Camden's merge.
- **G17 is not in force.** It was written against Rule 9a; Rule 9b condition 3 now governs
  decision PRs (a quoted, dated Camden statement confirmed by a reviewer).

## Human gates (standing list)

The loop never crosses these. Reaching one means: write the blocker above, stop.

- **Merge.** Only as constitution Rule 9b permits while it is in force; every other merge is
  Camden's (Rule 9).
- **D-decisions.** Any spec decision marked open, gated, or "Camden", unless Rule 9b condition 3's
  quoted-and-confirmed exception applies.
- **Live network probes.** Any market-data fetch, vendor API call, or other
  external network use outside pytest's fakes. Exception: bounded fetches in the Codex lane per G13.
- **Capital gate.** `docs/SCOPE-V1.md` §11.3 (and §5 when §11 lapses), any `SafetyConfig` value,
  the LIVE money path in `exec/` (Rule 7a), LIVE arming and budget.
- **Governance text.** The constitution, `docs/SCOPE-V1.md` §5 and §11.3, `docs/autonomy/`
  other than `queue.json` (a lane D sync PR may edit it), `.github/`
  and `.claude/`: changed only on Camden's explicit instruction in chat (Rule 10). Rule 9b
  condition 2 additionally bars agent merges of `docs/autonomy/routine-prompt.md`,
  `docs/autonomy/review-prompt.md`, `.github/workflows/`, `.github/scripts/merge_gate.py`.
- **The ledger.** Any write to `docs/trials/`.
- **Pinned 019 files.** `scripts/feature_set_comparison.py`,
  `scripts/multi_ticker_comparison.py`, `scripts/logistic_baseline.py`.
- **Any task whose text names Camden** as the one who runs, reviews or decides it.
