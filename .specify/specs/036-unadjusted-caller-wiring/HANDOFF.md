# Spec 036 stopped at the baseline gate

## Completed

- STEP 0: renamed the eight-file spec directory to 036 and repointed `.specify/feature.json`; updated references except the protected finish plan.
- STEP 1 / T001: D-1 through D-7 marked DECIDED, preserving recommendation substance; added the 021 handoff pointer and marked 018 T024 superseded by 036.
- Required dependency installation completed (exit 0).

## Blocker and verification

Before implementation: **0 passed / 0 failed / 1 collection error**. The failing collection ID is `tests/test_multi_ticker_comparison.py`; line 23 contains non-UTF-8 byte `0x97` without an encoding declaration. This file belongs to the other lane and is expressly protected. No change was made there. The expected 886 passed / 1 failed baseline was not reproduced.

After implementation: **not run; implementation has not started**. T002 remains blocked; T003-T023 remain open. Resume with the required baseline after the owning lane repairs this file. Logs: `baseline.log`, `baseline.xml`.

All explicitly protected files and existing `data/cache/**` files have identical SHA-256 hashes to the pre-work snapshot. No source or test file was edited. No Git command was run.

## Unexpected findings

- `docs/V1-FINISH-PLAN.md:76` contains the old placeholder reference. It remains untouched because the explicit protected-file constraint wins over the broad reference-update instruction.
- Pip reported an existing environment conflict: numba 0.65.1 needs numpy<2.5; the project pins numpy 2.5.2. Installation still exited 0. No requirements were edited.
- D-7 contains historical Norgate references. Its recommendations were preserved as requested, with an explicit note that the authoritative scope permits only free sources. B-1 and F-1 remain open.
- The spec 037 initial-provenance artifact's eight path keys were updated for the rename. Its historical hash values were preserved; they are not current hashes of edited spec files.

## Review units

Only the metadata unit is present. Future sequential units: resolver and fixtures; CLI and signal tests; API and tests; mutation driver and final evidence. Keep each within about 400 changed lines and subdivide if needed. No PR was opened.

## Files touched

- `.specify/feature.json` (2 changed lines)
- `.specify/specs/018-terminal-truthfulness/tasks.md` (2 changed lines)
- `.specify/specs/020-unadjusted-price-data/spec.md` (2 changed lines)
- `.specify/specs/021-finish-spec-019-migration/tasks.md` (4 changed lines)
- `.specify/specs/037-clean-clone-green/artifacts/initial-provenance.json` (16 changed lines)
- `.specify/specs/036-unadjusted-caller-wiring/checklists/requirements.md` (6 changed lines; renamed)
- `.specify/specs/036-unadjusted-caller-wiring/contracts/cli-and-api.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/data-model.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/plan.md` (8 changed lines; renamed)
- `.specify/specs/036-unadjusted-caller-wiring/quickstart.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/research.md` (renamed; content unchanged)
- `.specify/specs/036-unadjusted-caller-wiring/spec.md` (31 changed lines; renamed)
- `.specify/specs/036-unadjusted-caller-wiring/tasks.md` (14 changed lines; renamed)
- `docs/HANDOFF-2026-09-25.md` (11 changed lines)
- `.specify/specs/036-unadjusted-caller-wiring/baseline.log` (new baseline output)
- `.specify/specs/036-unadjusted-caller-wiring/baseline.xml` (new machine-readable baseline)
- `.specify/specs/036-unadjusted-caller-wiring/HANDOFF.md` (this report)

A temporary `.specify/spec036-backup-path.txt` bookkeeping file was created and removed; it is not a deliverable.
