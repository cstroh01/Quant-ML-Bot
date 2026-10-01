# Spec 043: T003 through T015 complete

Measured 2026-09-30 with Camden's venv, Python 3.13.14. Stopped before T020.

## Suite evidence

- T003: `python -m pytest tests`: exit 0; 1003 passed, 0 failed, 0 errors.
- Final: `python -m pytest tests --tb=line`: exit 1; 1012 passed, 14 failed, 0 errors; 2 warnings.
- Collected 1026 = baseline 1003 + 23 new cases. Existing 1003 passed; new cases: 9 passed / 14 failed.
- This matches Phase 1: T011/T012 default write guards are red; D-1 B enabled control is red until T025; root gates are red until T020-T022.
- No acceptance gate was skipped or marked xfail. The guard is not implemented yet.
- Commands, copy paths, timings and real-ledger manifests are in `baseline-clean-*` and `phase1-full-*`.

## Observed red proofs

EXAMPLE — NOT A RESULT: all input bundles and model stubs are synthetic.
E1 wrote 44 records / 22 sidecars; E2 46 / 22; E3 230 / 110; E4 16 / 0.
All four real mains completed; E4 used two spawned workers. Copy verify() passed.
E5 made two successful identical GETs: each added 44 records / 22 sidecars; N rose 87 to 89.
The direct incident call wrote 6 records / 3 sidecars. Named changed paths and hashes are in `phase1-full-events.jsonl`.
The enabled E1 control hit argparse's unimplemented --record-trial flag (exit 2; no writes).
Six root cases lack the T021 resolver. The extra-depth registry case names the wrong root.
The planted depth proof and eight isolation/tripwire cases passed; root's valid control awaits implementation.
Model shortcuts and the initial E5 IPC setup correction are disclosed in `entry-red.md`.
The initial baseline environment mistake is retained and explained in `baseline.md`.

## Scope and integrity

Every acceptance run used a full copy outside C:\GitHub and real-ledger hashing before/after.
Every hash equals T002, including both ledger files and all backfill files; returns/ remains absent.
No production script changed. No Git, external network, or production research/backtest run occurred.
Windows asyncio's internal loopback socket pair is permitted; external connections are blocked in the child.
The concurrent GITHUB_SHA cleanup in test_033_trial_ledger.py was left untouched and excluded from this lane's counts.
Spec 044 and 041 artifacts were untouched; their uncommitted docs are excluded from counts.
See `scope-audit.json` and `review-units.md`. No marker/resolver or Phase 2 implementation was created.

## Exact failing node IDs

- `tests/test_043_enabled_control.py::test_record_trial_flag_records_complete_funded_trials`
- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E1]`
- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E2]`
- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E3]`
- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E4]`
- `tests/test_043_entry_points.py::test_default_entry_changes_no_ledger_bytes[E5]`
- `tests/test_043_incident.py::test_direct_baseline_call_changes_no_ledger_bytes`
- `tests/test_043_project_root.py::test_project_root_contract[override]`
- `tests/test_043_project_root.py::test_project_root_contract[invalid_override]`
- `tests/test_043_project_root.py::test_project_root_contract[file_marker]`
- `tests/test_043_project_root.py::test_project_root_contract[neither]`
- `tests/test_043_project_root.py::test_project_root_contract[wrong_nearer]`
- `tests/test_043_project_root.py::test_project_root_contract[foreign_cwd]`
- `tests/test_043_project_root.py::test_registry_root_survives_extra_depth`
