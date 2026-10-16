# Tasks: 059 — preregistered LIVE allocation and v1.2 capital-gate evidence

Every code unit: red tests first; a Rule 12 driver in `tests/mutation/` with a clean control;
at most 600 changed lines; the full suite; ledger hashes before and after.
Labels: **HUMAN GATE** = Camden acts. Queue ids in brackets.

- [x] T001 **HUMAN GATE — preregistration (FR-001).** Camden appends the 059 declaration to the _(done: #201, #206; verify_family OK 2026-10-15)_
  ledger with the trial-registry API before 058 T015 runs. An agent prepares the record and the
  command; Camden runs it.
  - Record: `.specify/specs/059-live-allocation/declaration.json` (hashes this spec.md).
  - Command: `python scripts/declare_family.py 059-allocation --record`; paste the output back.
- [x] T002 Weights builder (FR-002) [Q108]. Depends on queue Q103 (058 portfolio vol fix). _(done: #195)_
- [x] T003 Backtest report builder, offline on fixtures (FR-003) [Q109]. _(done: #197)_
- [ ] T004 Bounded data run of the report on the 035 cache (Codex lane), published with provenance.
- [x] T005 PAPER wiring for both profiles (FR-004, Rule 7a) [Q100, Q110]. _(done: #203, #204, #205)_
- [x] T006 Paper evidence report (FR-005) [Q112]. _(done: #187)_
- [ ] T007 Historical replay harness and run (FR-006) [Q111].
- [x] T008 Gate checklist command (FR-007). `python scripts/gate_checklist.py docs/implementation/spec-059/gate-manifest.json`.
- [ ] T009 Rule 12 driver for §5 mutants across T002–T008.
- [ ] T010 **HUMAN GATE — LIVE arming.** Camden reads the T008 checklist and arms LIVE.
