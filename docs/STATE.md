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
U2's T023–T024 are implemented on branch `claude/043-u2-write-guard-20261002`
(recovered cloud-lane patch, draft PR); they are not on `main` until that PR merges.
T025–T026 complete U2.

Queued behind it, in order: **044** (both edit `scripts/data.py`; 044 also
waits on Camden's T003/T004 reviews), then **040** (043 implements first).

## Next unblocked task

`043 T025` is next for 043, and it is a **human gate**: it edits pinned
`scripts/feature_set_comparison.py` (see Blockers). Until T025 lands, production
ledger recording is refused by design (fail closed); only synthetic ledgers write.

The next unit the loop may take without a human gate is **044 probe findings
F2, F3, F7, F8** (`044` `artifacts/p1_rules.py`, `artifacts/p1_probe.py`).

## Expected red on `main`

None that fails the suite. The remaining deliberate red contracts are
`xfail(strict=True)`, so they report as xfailed; the task that makes one pass
**must remove its marker in the same PR** (a strict XPASS fails the suite).

With U2's T023–T024 applied (verified 2026-10-02 on Windows, Python 3.13.14:
1057 passed, 4 xfailed, exit 0; ledger unchanged), four remain:

- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E3]` — T025.
  Its per-ticker isolation boundary prints the refusal until T025's preflight.
- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E5]` — T027 (U3).
- `tests/test_043_entry_points.py::test_e5_serves_recorded_configuration_read_only` — T027 (U3).
- `tests/test_043_enabled_control.py` — T025.

`tests/test_043_incident.py` and `tests/test_043_project_root.py` are no longer xfail.

CI on `main` is green: every check passed at `064637c` (PR #11 merge). The earlier
red at `e19d57c` is resolved.

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
| Cloud scheduled-session lane | **Paused** 2026-10-02. The scheduled task could not push (repository not an authorized source). Moving to a repository-aware Claude Code routine; re-enabled only after one manual run opens a real draft PR |
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
- 043 U2, T023–T024 — produced by the cloud lane, push denied; patch recovered and
  pushed by Camden. Draft.
