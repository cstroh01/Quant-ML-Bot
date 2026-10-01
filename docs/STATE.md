# STATE

The loop's working memory, and the one place to see where the repo stands.
**Camden owns** the active spec and every human-gate decision. **A loop PR
updates** Next, Blockers, Expected red, and Lane status in the same PR as its
work. Spec files stay the authority on their own tasks; this file points at them.

_Seeded 2026-09-30 by spec 045 from the tree at `e19d57c`. Camden confirms
the active spec (spec 045 D-5)._

## Active spec

**043 — ledger write guard** ([tasks](../.specify/specs/043-ledger-write-guard/tasks.md)).
Phase 1 (T003–T015) is done; Phase 2 is next, in review-unit order U1 → U2 → ….

Queued behind it, in order: **044** (both edit `scripts/data.py`; 044 also
waits on Camden's T003/T004 reviews), then **040** (043 implements first).

## Next unblocked task

`043 T020` — `pyproject.toml`, exactly the D-5a block in tasks.md.
Then T021 (`scripts/_project.py`) and T022 (`trial_registry.ROOT`), which
together turn `test_043_project_root.py` green.

## Expected red on `main`

None that fails the suite. Phase 1 left 14 deliberate red contracts, now
marked `xfail(strict=True, reason="043 Phase 1 red; guard lands in T020+")`
([phase1-summary](../.specify/specs/043-ledger-write-guard/artifacts/phase1-summary.md)),
so they report as xfailed. **Strict** means the task that makes one pass
**must remove its marker in the same PR**; a strict XPASS fails the suite.

- `tests/test_043_project_root.py`: 7 cases (per-test markers) — T020–T022.
- `tests/test_043_entry_points.py`: E1–E5 (module `pytestmark`) — T023–T026.
- `tests/test_043_incident.py` (module `pytestmark`) — T023–T026.
- `tests/test_043_enabled_control.py` (module `pytestmark`) — T025.

**CI on `main` is red today.** At `e19d57c` the `test` check concluded
`failure` (GitHub API, run started 2026-10-01T00:30Z; `web` passed). The
markers above exist only in the working tree as of 2026-09-30, not in
`e19d57c`, so the red is consistent with the 14 unmarked contracts. The failing
test names were not visible without the log, so that cause is **unconfirmed**.
Once the markers are committed, any failure on `main` is real and is fixed first.

## Blockers (human gate reached; the loop stops here)

| Where | Gate | Waiting on |
|---|---|---|
| 043 T025 | Edits `scripts/feature_set_comparison.py` (E4 workers), a pinned 019 file | Camden: human lane, or lift the pin for this task |
| 044 T003, T004 | Review of `p1_probe.py` | Camden |
| 044 T007, 041 T018 | Live network probe | Camden (041 T018 ran 2026-09-30 and failed; that finding is 044) |
| 033 Phases 8–9 | Backfill bounds for 8 campaign rows | Camden |

## Lane status

| Lane | State |
|---|---|
| Dev loop (`dev-loop.yml`) | **Off.** Dispatch-only; cron commented. Waits on spec 045 D-1 to D-4 |
| Loop review (`loop-review.yml`) | Present; fires on `loop/*` PRs only once the token question (045 D-2) is settled, or by dispatch |
| `@claude` comments (`claude.yml`) | Active |
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

- (none yet)
