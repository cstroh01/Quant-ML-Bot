# Implementation Plan: Installable package (`scripts/` → `src/qmb/`)

**Branch**: `040-installable-package` (human-owned) | **Date**: 2026-09-27
**Spec**: [spec.md](spec.md) | **Evidence**: [MIGRATION-INVENTORY.md](../../../docs/implementation/spec-040/MIGRATION-INVENTORY.md)
**Preconditions**: specs 036 and 041 merged; no other lane open; green suite at `PRE`.

## Summary

Build the verification tooling first: the AC-1 filter, the junit comparator, and
the ledger boundary and installability tests, each red-proven. Then close the
allowlist. Then perform the whole migration as **one atomic working-tree change**
and gate it with AC-1 to AC-6. The ledger is never rewritten. A single mapping
file marks the era boundary by record hash.

## Technical Context

**Language/Version**: Python ≥ 3.12 (declared in `requires-python`). CI runs 3.12; the local venv runs 3.13.14.
**Build**: setuptools ≥ 77 through PEP 517/660. A build-time requirement only; no runtime dependency is added.
**Testing**: `python -m pytest tests` (AC-2), plus the out-of-tree AC-3 procedure, which becomes a permanent CI step.
**Constraints**: no Git (Camden runs the Git form of AC-1); no network in tests; no byte change under `docs/trials/` except the new mapping file.
**Scale**: 31 files moved; about 60 files with import rewrites; about 40 enumerated non-import edits; 5 new source or test files.

## Constitution Check

| Rule | How this spec satisfies it |
|---|---|
| 6 Dependencies | None at runtime. The setuptools justification is in spec §4 |
| 8 Layers / module boundaries | Module contents are unchanged apart from import lines and the enumerated path lines. `_project.py` owns only root location |
| 9 Merge gate | AC-1 makes about 176 import edits mechanically reviewable. The human review surface is the allowlist, `pyproject.toml`, `_project.py`, the mapping file and the new tests (target ≤ 600 lines) |
| 10 Git | The agent never runs Git. It compares against a read-only export of `PRE`. Camden runs the Git form of AC-1 and owns rollback and tagging |
| 11 Provenance | L1, L2 and L3 fixed. Runner strings name real files. The mapping file records the era boundary |
| 12 Red proof | Every gate has a planted-defect case plus a control: AC-1 (5 cases), AC-4 (R-4a/b/c), AC-5 (flat import), and the non-vacuity assertions on every scanning guard |
| 15 DSR | The lifetime count is pinned by AC-4b and 4c. The L1 fork of the ledger is prevented by marker-based root resolution |
| 1–5, 13, 14, 16 | Not engaged. No computation, data or result changes |

## Project Structure (after)

```text
pyproject.toml                      new
src/qmb/__init__.py                 new (docstring only)
src/qmb/_project.py                 new (project_root, ProjectRootNotFound)
src/qmb/<29 modules>.py             moved from scripts/
scratch/<2 scratch modules>.py      moved byte-identical
docs/trials/runner-renames.json     new; everything else under docs/trials/ byte-identical
tests/repo_paths.py                 new (REPO_ROOT, PACKAGE_DIR; no sys.path)
tests/test_040_*.py                 new (3 modules)
tests/context.py                    deleted
.specify/specs/040-installable-package/
  ac1-allowlist.json, tools/ac1_filter.py, tools/compare_junit.py, artifacts/
```

## Why one atomic unit

A half-migrated tree is red everywhere and gives no signal. Every module that
still imports flat fails the moment its first dependency has moved, and every
test fails at collection. An incremental landing would also leave `main` in a
state where neither `tests/context.py` nor the installed package works. So the
tooling lands and is proven *before* the migration, and the migration itself
lands in one change, gated as a whole.

## Rollback

The rollback point is `PRE`: the commit on `main` recorded at T003, after 036
and 041 have merged. If any AC fails and cannot be fixed within the same unit,
Camden discards the working-tree change (or reverts the single migration
commit) back to `PRE`. The agent does neither; Rule 10 applies. Nothing under
`docs/trials/` can need restoring, because AC-4a proves it was never touched.

**Camden tags `v1.0` only after AC-1 to AC-5 have passed** (AC-6 as well, which
is recorded alongside them), and after the other `SCOPE-V1.md` §3 items hold.
`pyproject.toml` `version = "1.0.0"` must match that tag.

## Complexity Tracking

| Item | Why it is needed | Simpler alternative rejected |
|---|---|---|
| `_project.py` (one new module) | L1: a depth-based root silently forks the ledger | `parents[2]`: passes an editable install, then fails a wheel install |
| `pytest pythonpath = ["."]` | `reports/` is not packaged, but tests import `reports.api` from any cwd | Packaging `reports`: scope creep, and a generic top-level name |
| AC-1 filter as spec-local tooling | Reviewability is a hard constraint (CLAUDE.md) | Reading the diff: not feasible at 176 edits |
