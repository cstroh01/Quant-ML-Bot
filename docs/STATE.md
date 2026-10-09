# STATE

The loop's working memory, and the one place to see where the repo stands.
**Camden owns** the active spec and every human-gate decision. **A loop PR
updates** Next, Blockers, Expected red, and Lane status in the same PR as its
work. Spec files stay the authority on their own tasks; this file points at them.

_Seeded 2026-09-30 by spec 045 from the tree at `e19d57c`. Camden confirms
the active spec (spec 045 D-5)._

## Active spec

**058 — preregistered multi-asset edge research program**
([spec](../.specify/specs/058-edge-research-program/spec.md),
[tasks](../.specify/specs/058-edge-research-program/tasks.md)). Camden confirmed it on 2026-10-09
(gate G11). Spec 033's Gate 3 work is its dependency. 043 is complete (28/28 tasks) and merged.
Specs 051–057 are adopted under SCOPE §10.

_Refreshed 2026-10-09 at `e4899f3`._ Gate answers are recorded in specs 033, 035, 040, 046, 047 and
058. The source is the gate packet `claude/gate-packet-20261009.md`.

## Operating model (2026-10-09)

- **Track A (Claude cloud).** Offline v1.0 code, one draft PR per unit.
- **Track B (Codex).** Windows verification, exact-head reviews, and bounded fetches on Camden's PC
  after his "go".
- **Merges.** Rule 9a permits bounded agent merges until 2026-12-31. All other merges, including
  decisions, governance, `exec/`, safety and ledger changes, are Camden's.

## Next unblocked tasks

| Where | Task | Owner |
|---|---|---|
| 058 T006 | Write the family declaration to `docs/trials` (after #126 merges) | Camden, 1 command |
| 058 T001, T004 | SCOPE universe amendment and `CLAUDE.md` module rows | Governance PRs; Camden merges |
| 058 T007, T010–T013 | Holdout seal, portfolio accounting, signals, sizing, baselines | Track A |
| 058 T008 | Bounded ETF fetch (after T006) | Codex, pre-authorized (G6) |
| 033 T035, T037, T039–T040, T044 | DSR test gaps; Phase 8 is authorized | Track A |
| 046 T003+ | Cost model implementation (T001 and T002 approved) | Track A |
| 032 | Sticky `kill_confirmed` defect: confirm_kill never clears a stored confirmation | Track A finding; safety code, so Camden merges |

## Expected red on `main`

None. CI on `e4899f3`: test, test-windows, web, actionlint, loop-guard and CodeQL all succeeded.
Owner-side Linux runs give 1723 passed on main. Codex independently measured 1723 passed on Windows
at `26983da`.

## Blockers (human gate reached)

| Where | Gate | Waiting on |
|---|---|---|
| 058 T015, T016 | Ledger-writing research and holdout runs | Camden runs them (one command each) |
| 044 T003, T004, T007 | Probe reviews and live probe | Camden |
| 040 T001 | Kickoff check | Camden |
| 038 and 047 decisions | Delegated to Claude; ratified by Camden's merge of the decision PR | Camden merge |
| `exec/` PRs (#101, #112–#117, #119) | Rule 7 line-by-line review record | Camden (blocks LIVE only) |

## Delegations (Camden, 2026-10-09 (delegation answers G12–G16 in chat; recorded by Claude))

- **G12.** 044 T003/T004 reviews: Codex plus Claude.
- **G13.** Bounded fetches and the 044 T007 probe: the Codex lane, without a per-run "go".
- **G14.** The 040 T001 kickoff check: the lane.
- **G15.** PAPER drills: Codex.
- **G16.** Enabling the PAPER schedule after all drills pass. The `.github/` PR for it still needs
  Camden's merge.
- **G17 is not in force.** Lane-merging decision PRs would conflict with constitution Rule 9a
  condition 3. Delegated decisions are ratified by Camden merging the decision PR.

## Human gates (standing list)

The loop never crosses these. Reaching one means: write the blocker above, stop.

- **Merge.** Rule 9: Camden merges. The one exception is a Rule 9a-eligible PR, until 2026-12-31.
- **D-decisions.** Any spec decision marked open, gated, or "Camden".
- **Live network probes.** Any market-data fetch, vendor API call, or other
  external network use outside pytest's fakes. Exception: bounded fetches in the Codex lane per G13.
- **Capital gate.** `docs/SCOPE-V1.md` §5, any `SafetyConfig` value, anything in `exec/` (Rule 7).
- **Governance text.** The constitution, `CLAUDE.md`, `docs/SCOPE-V1.md`,
  ADR acceptance, `docs/autonomy/`, `.github/`.
- **The ledger.** Any write to `docs/trials/`.
- **Pinned 019 files.** `scripts/feature_set_comparison.py`,
  `scripts/multi_ticker_comparison.py`, `scripts/logistic_baseline.py`.
- **Any task whose text names Camden** as the one who runs, reviews or decides it.
