# Implementation Plan: Ledger write guard

**Branch**: `043-ledger-write-guard` (human-owned) | **Date**: 2026-09-28
**Spec**: [spec.md](spec.md) | **Note**: [NOTE-for-ledger-write-guard-spec.md](NOTE-for-ledger-write-guard-spec.md)
**Preconditions**: D-1 to D-5 decided by Camden; the production ledger at its
known state (spec, hard precondition 2); implemented **before** spec 040.

## Summary

Make production the non-default. First build a copy-based harness that runs
every entry point, and the incident's library call, against a full repository
copy outside `C:\GitHub`. Observe it red on today's code: each run writes the
copy's ledger. Then add:
- marker-based root resolution;
- a two-layer refusal: at the write layer before any lock, `mkdir` or append,
  and early, before data loading or fitting;
- the D-1 enablement mechanism;
- the D-2 route behaviour;
- the D-4 driver isolation;
- the D-3 scope items.

The real ledger is never exposed to a run. It is hashed before and after as a
tripwire.

## Technical Context

**Language/Version**: Python ≥ 3.12 (CI 3.12; local 3.13.14). Stdlib `tomllib` for the marker.
**Dependencies**: none added (Rule 6).
**Testing**: `python -m pytest tests`, plus copy-based subprocess tests driven from pytest. No network: data access in the child is replaced with labelled synthetic frames.
**Constraints**:
- No Git.
- No byte under the real `docs/trials/` changes, and no run targets it.
- Refusal precedes the first `serialized()` / `mkdir` / `immutable_write` / `_append`.

**Scale**: about 8 source files touched (`trial_runner.py`, `trial_registry.py`,
`trial_backfill.py`, four entry-point `main`s, the backtest route), plus
`scripts/_project.py` and `pyproject.toml` (new, D-5a), `tests/conftest.py`,
`tests/spec033_support.py`, 3 mutation drivers and about 4 new test and helper
modules. Split into review units (below).

## Constitution Check

| Rule | How this spec satisfies it |
|---|---|
| 1–5, 13, 14 | Not engaged. No feature, label, CV, cost or data computation changes |
| 6 Dependencies | None. `tomllib` is stdlib |
| 8 Layers | The guard lives in the recording layer (`trial_runner`, `trial_registry`). Entry points gain only a flag or preflight (D-1). No signal, fill or accounting code changes |
| 9 Merge gate | Six review units, each explainable alone. The write layer is about 20 lines |
| 10 Git | The agent runs no Git. Camden restores anything, and nothing should need restoring |
| 11 Provenance | The ledger's history is byte-identical (AC-4). D-3(b) keeps Rule 11's label text exact |
| 12 Red proof | AC-1, AC-2 and AC-10 are red on pre-043 code. The write layer is red-proven independently of the early layer. AC-3 is the green control against a guard stuck closed. AC-4, AC-5, AC-7, AC-8 and AC-9 have planted defects |
| 15 DSR | Stops N from being inflated by accident or by page views (D-2). `N_current`'s definition is untouched (FR-007); D-2 B's conflict with spec 033 FR-026 is raised, not resolved |
| 16 Limitations | Not engaged. No result surface changes |

## Project Structure (after)

```text
pyproject.toml                         new, minimal marker (D-5a)
scripts/_project.py                    new: project_root(), ProjectRootNotFound (moved by 040 T016)
scripts/trial_registry.py              ROOT = project_root(); write-layer refusal
scripts/trial_runner.py                refusal in current_ledger/research_attempt; D-1 enablement; D-3(b) constant
scripts/trial_backfill.py              write-layer refusal for the production root
scripts/{ma_crossover_backtest,logistic_baseline,multi_ticker_comparison,feature_set_comparison}.py
                                       early preflight + D-1 flag; E4 passes the enable token to workers (if D-1 B)
reports/api/routes/backtest.py         D-2
tests/conftest.py                      FR-008 whole-tree manifest guard; imports the D-3(b) constant
tests/spec033_support.py               imports the D-3(b) constant
tests/mutation/*.py                    D-4 (shared helper)
tests/ledger_copy_support.py           new: copy builder, manifest, tripwire (helper name, not a test name)
tests/ledger_guard_child.py            new: child harness that patches data access and runs E1–E5
tests/test_043_*.py                    new: AC-1 to AC-10
docs/trials/**                         UNCHANGED
```

## Review units (one PR, reviewed in order; split into PRs if Camden prefers)

1. **U1 Root**: `pyproject.toml`, `_project.py`, `ROOT`, and AC-5.
2. **U2 Write guard**: FR-001 to FR-005 at both layers; AC-1 to AC-3.
3. **U3 Route**: D-2 and AC-10.
4. **U4 Drivers and conftest**: FR-008, D-4, AC-6 guard proof and AC-8.
5. **U5 Marker**: D-3(b) and AC-7.
6. **U6 Alias bypass**: D-3(a) and AC-9. Omitted if D-3(a) is 2 or 3.

## Rollback

Every change is additive to code paths or confined to tests, and no ledger
byte changes. Camden discards the working tree if a gate fails. Nothing under
`docs/trials/` can need restoring, because AC-4 and the tripwire prove it was
never touched.

## Complexity Tracking

| Item | Why it is needed | Simpler alternative rejected |
|---|---|---|
| Two refusal layers | The write layer catches library calls (the incident). The early layer avoids unrecorded compute and wasted runs | Entry-point checks only: would not have stopped 2026-09-28 |
| Copy-based harness | ACs must run entry points with the variable unset, and the real ledger must never be exposed | Running entry points in the real repository: that is exactly how the incident happened |
| Child harness that patches data access | E2–E4 call `download_market_data`, and tests allow no network. Without reachability, AC-1 passes vacuously for any entry point that fails on data first | Relying on missing data: a false green (Rule 12) |
| Minimal `pyproject.toml` now | FR-006's marker must exist before 040 | Depth-based root until 040: the failure 040 L1 names |
