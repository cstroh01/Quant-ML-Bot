# STATE

The loop's working memory, and the one place to see where the repo stands.
**Camden owns** the active spec and every human-gate decision. **A loop PR
updates** Next, Blockers, Expected red, and Lane status in the same PR as its
work. Spec files stay the authority on their own tasks; this file points at them.

_Seeded 2026-09-30 by spec 045 from the tree at `e19d57c`. Camden confirms
the active spec (spec 045 D-5)._

_Refreshed 2026-10-12 by the lane D daily sync from the tree at `3b54c5b`. Queue
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

## Spec progress (ticked / total boxes in each `tasks.md`, at `3b54c5b`)

| Spec | Boxes | Note |
|---|---|---|
| 033 trial ledger, DSR, PBO | 59/75 | Phase 8 tests merged (#157, #173); Phase 9 is Q97 then Q33 |
| 035 free unadjusted bundle | 5/24 | Q38 (U2 close cross-check) is next |
| 038 disclosure sweep | 10/39 | Q96, Q47, Q57 ready |
| 044 nominal price reconstruction | 4/36 | Q73 baseline ready; later units wait on 044 T007/T008 |
| 046 Rule 13 cost model | 4/15 | U1a/U1b merged (#142, #167); Q71 is next |
| 047 tearsheet correctness | 4/16 | Q66 ready; Q67 blocked until the #158 recorded-payload revision lands |
| 049 / 051 / 055 PAPER operations | 7/13, 6/9, 5/7 | Q106, Q107, Q112 ready (lane D) |
| 058 edge research | 1/18 | Boxes lag merged work: T005 (#126), T006 (#134), T007 (#145), T008 (#140), T010 (#165), T011 (#166) and T012 (#169) merged unticked |
| 059 LIVE allocation | 0/10 | Q108 waits on Q103 |
| 060 universe and data | 0/8 | Q113–Q115 ready (lane B) |

## Next unblocked tasks (queue items `ready` with every dependency merged)

| Lane | Items |
|---|---|
| A | Q103, Q104 (Codex P1s merged in #169/#173), Q97 |
| B | Q38, Q73, Q113, Q114, Q115 |
| C | Q96, Q47, Q57, Q66, Q71 |
| D | Q106, Q107, Q112 |

## Expected red on `main`

None. Check runs on `3b54c5b`: test, test-windows, web, actionlint, loop-guard and CodeQL
(actions, javascript-typescript, python) all succeeded. The last recorded full Linux suite is
1892 passed, 34 xfailed, 0 failed (#169, Python 3.12.3).

Ledger: `docs/trials/trials.jsonl` 174 lines, SHA-256
`1bb5dbfe90c9df370c65910650ade15dd9d0e0366d011e09baf303975275f30f`; `trials.head.json` SHA-256
`f83b1b9be5a608d444d61496899d25139eb56184fd924acd030e61347d22d764`; `docs/trials/returns/` absent.

## Blockers (human gate reached)

| Where | Gate | Waiting on |
|---|---|---|
| 058 T015, T016 | Ledger-writing research and holdout runs | Camden runs them (one command each) |
| 033 Q33b (T063, T064) | `reports/api/routes/capital_gate.py` route reads the Gate 3 artifact | A Camden-authorized unit |
| 044 T003, T004, T007 | Probe reviews and live probe | G12/G13 delegations (Codex lane) |
| 047 Q67 (T010, T011) | Spec text and Q67 `allowed_paths` must be revised for the recorded-payload route, with an explicit as-of session (#158) | A spec 047 revision PR; then Q67 back to `ready` |
| 055 paper-loop `kill` input | Per-profile kill wiring in `ops/workflows/paper-loop.yml` (#168 proposal) | Camden's decision on #168 blocker 1 |
| §11.3 items 6–7 | Fidelity preview sessions; arming LIVE with the $100 budget | Camden |
| LIVE `exec/` (`fidelity_live.py`, `fidelity_reconcile.py`) | Rule 7a line-by-line review | Camden |

## Disagreements between this file's previous text and the tree

- The previous refresh (2026-10-09) described Rule 9a merges and Track A/B; Rule 9b and lanes A–D
  replaced them on 2026-10-12 (#175).
- Spec 058 `tasks.md` boxes lag merged PRs (see the table above). Ticking them belongs in a unit
  whose `allowed_paths` include that file; no such queue item exists yet.

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
