# STATE

The loop's working memory, and the one place to see where the repo stands.
**Camden owns** the active spec and every human-gate decision. **A loop PR
updates** Next, Blockers, Expected red, and Lane status in the same PR as its
work. Spec files stay the authority on their own tasks; this file points at them.

_Seeded 2026-09-30 by spec 045 from the tree at `e19d57c`. Camden confirms
the active spec (spec 045 D-5)._

## Active spec

**043 — ledger write guard** ([tasks](../.specify/specs/043-ledger-write-guard/tasks.md)).
Phase 1 (T003–T015) is done. U1 (T020–T022) is merged on `main` (PR #9).
U2's T023–T024 are merged on `main` (PR #15, merge commit `d8adac3`; recovered
cloud-lane patch). T025–T026 complete U2.

Queued behind it, in order: **044** (both edit `scripts/data.py`; 044 also
waits on Camden's T003/T004 reviews), then **040** (043 implements first).

## Next unblocked task

`043 T025` is next for 043, and it is a **human gate**: it edits pinned
`scripts/feature_set_comparison.py` (see Blockers). Until T025 lands, production
ledger recording is refused by design (fail closed); only synthetic ledgers write.

The next independent cloud candidate is **Q18**, report-only creation of
`.specify/specs/038-disclosure-sweep/tasks.md` from the merged spec and plan.
Q17 dependency is verified by PR #52 changed files. Q10/Q11/Q12/Q13/Q15/Q16,
Q17/Q21/Q22 are delivered; the private queue proposal records their PRs.
No Q18 output exists yet. Implementation choices D-1–D-5 remain open.

044 F2/F3/F7/F8 were delivered by PR #28; unchecked T002a is stale.
T003/T004 reviews and the T007 human network probe remain open.

## Expected red on `main`

None that fails the suite. The remaining deliberate red contracts are
`xfail(strict=True)`, so they report as xfailed; the task that makes one pass
**must remove its marker in the same PR** (a strict XPASS fails the suite).

Four remain at `9084e099de753ff712ab57aa488a191962f01321`. Fresh CI runner checkouts on Linux and Windows
collected 1208 tests: 1204 passed, 4 intentional xfails, 1 warning; both success.
Source: [Tests run 37676782316](https://github.com/cstroh01/Quant-ML-Bot/actions/runs/37676782316),
2026-10-07. Job logs independently read; no current-revision claim relies on
the older d8adac3 or PR-head runs.

- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E3]` — T025.
  Its per-ticker isolation boundary prints the refusal until T025's preflight.
- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E5]` — T027 (U3).
- `tests/test_043_entry_points.py::test_e5_serves_recorded_configuration_read_only` — T027 (U3).
- `tests/test_043_enabled_control.py` — T025.

`tests/test_043_incident.py` and `tests/test_043_project_root.py` are no longer xfail.

CI on `main`: test, test-windows, web (lint/build), actionlint and loop-guard
all succeeded in run 37676782316 at the revision above. This is fresh CI
checkout evidence; separate local Windows post-merge evidence is private.

## Blockers (human gate reached; the loop stops here)

| Where | Gate | Waiting on |
|---|---|---|
| 043 T025 | Three pinned CLI paths and E4 spawned-worker enablement | Camden replaced the earlier human-lane choice with a T025-only agent pin exception on 2026-10-07 for feature_set_comparison.py, logistic_baseline.py and multi_ticker_comparison.py; implementation/review pending; all other pin protections remain |
| 044 T003, T004 | Review of `p1_probe.py` | Camden |
| 044 T007, 041 T018 | Live network probe | Camden (041 T018 ran 2026-09-30 and failed; that finding is 044) |
| 033 Phases 8–9 | Backfill approval COMPLETE; remaining statistics/lifetime-N and Gate 3 prerequisites | Numbered tasks after 035/044/046 acceptance |

## Lane status

| Lane | State |
|---|---|
| Dev loop (`dev-loop.yml`) | **Off.** Dispatch-only; cron commented. Waits on spec 045 D-1 to D-4 |
| Loop review (`loop-review.yml`) | Present; fires on `loop/*` PRs only once the token question (045 D-2) is settled, or by dispatch |
| `@claude` comments (`claude.yml`) | Active |
| Cloud scheduled-session lane | v7 delivered #49. v8 remains a private proposal; require its human adoption and one actual post-v8 draft PR. No schedule change authorized |
| Local sessions | Camden |

## Human gates (standing list)

The loop never crosses these. Reaching one means: write the blocker above, stop.

- **Merge.** Rule 9. Only Camden merges.
- **D-decisions.** Any spec decision marked open, gated, or "Camden".
- **Live network probes.** Any market-data fetch, vendor API call, or other
  external network use outside pytest's fakes.
- **Capital gate.** `docs/SCOPE-V1.md` §5, any `SafetyConfig` value, anything in `exec/` (Rule 7).
- **Governance text.** The constitution, `CLAUDE.md`, `docs/SCOPE-V1.md`,
  ADR acceptance, `docs/autonomy/`, `.github/`.
- **The ledger.** Any write to `docs/trials/`.
- **Pinned 019 files.** `scripts/feature_set_comparison.py`,
  `scripts/multi_ticker_comparison.py`, `scripts/logistic_baseline.py`.
- **Any task whose text names Camden** as the one who runs, reviews or decides it.

## Recent loop PRs

- #8 — 043 Phase 1 review triage (cloud lane). Merged.
- #9 — 043 U1, T020–T022 (cloud lane). Merged.
- #10 — 044 R2 + R10, FR-010 one-line loader pin (cloud lane). Merged.
- #15 — 043 U2, T023–T024. Produced by the cloud lane, whose push was denied; patch
  recovered and pushed by Camden. Merged as `d8adac3`.

## October 7 merged units and unresolved acceptance

- PR #50: Q21 / 049 T011 (`paper_report.py` and its contract); PR #51: Q22 / 049 T012 (`paper_monitor.py` and its contract). Both merged; task checkboxes may lag.
- PR #52: Q17 / 038 plan only. Q18 tasks may now be drafted; no disclosure implementation is certified.
- PR #53: 047 U1a backend accounting/contracts/evidence. D-1/D-2/D-3 and T005 still gate the views; no Rule 13 cost-model completion.
- Backfill approval is COMPLETE per Camden's continuation and the recorded approval/immutable artifact referenced by the 033 checkbox audit. Do not re-request it; stale unchecked boxes do not reopen approval.
- 049 T013 remains reviewed exec work; broker client-ID linkage is unresolved. Paper prototype operation does not establish the capital gate's qualifying clock.
- Scope amendment and 051–055 proposals are unadopted. 050 already exists. 040 remains dependent on 043 and its human preconditions.
