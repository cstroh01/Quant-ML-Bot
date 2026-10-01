# Tasks: Dev loop

**Input**: [spec.md](spec.md), [plan.md](plan.md). Single-threaded. Checkpoint
after every task in [CHECKPOINT.md](CHECKPOINT.md). No `git`, no pytest.

- [x] T001 spec.md, plan.md, tasks.md, CHECKPOINT.md.
- [x] T002 `docs/STATE.md`, seeded from the tree (FR-001, D-5).
- [x] T003 `docs/autonomy/loop-prompt.md` (FR-003, FR-005 to FR-008).
- [x] T004 `.github/scripts/loop_guard.py` with `--self-test` (FR-009, FR-015).
- [x] T005 `.github/workflows/dev-loop.yml` (FR-002 to FR-010).
- [x] T006 `docs/autonomy/review-prompt.md` and `.github/workflows/loop-review.yml` (FR-011).
- [x] T007 `docs/autonomy/ruleset.md` (FR-012).
- [x] T008 `docs/autonomy/token-options.md` (FR-013).
- [x] T009 Hygiene: Node 20 actions to current majors; `actionlint` and
  `loop-guard` jobs in `test.yml` (FR-014, FR-015).
- [x] T010 `docs/autonomy/README.md`: how a run works, enablement order.
- [x] T011 Validate: guard self-test, YAML parse, actionlint. Record what ran.
- [x] T012 Status line, CHECKPOINT final, report.

## Camden (after this spec merges)

- [ ] T020 D-1 to D-6 (spec §6).
- [ ] T021 SC-004: one dispatched run.
- [ ] T022 SC-005: optional planted-violation run.
