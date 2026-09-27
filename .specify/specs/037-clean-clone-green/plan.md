# Implementation Plan: Green from a clean clone

**Branch**: `037-clean-clone-green` (human-owned) | **Date**: 2026-09-25
**Spec**: [spec.md](spec.md)
**Input**: Spec 037, authored from `.specify/templates/spec-template.md`.

## Summary

Measure committed HEAD separately from the working directory, establish red tests,
repair observable-outcome scoring and any measured in-scope residuals, then verify
the entire suite in a fresh HEAD-plus-patch export. Preserve raw evidence.

## Technical Context

**Language/Version**: Python 3.12 verification; effective pinned minimum Python 3.12 (NumPy wheel metadata).
**Primary Dependencies**: Existing pinned pandas, NumPy, scipy, statsmodels,
scikit-learn and pytest; no project dependency additions.
**Storage**: Synthetic temporary fixtures and spec-local text/JSON evidence.
**Testing**: `python -m pytest tests`; focused regressions and existing mutation helper.
**Target Platform**: CI Ubuntu/Python 3.12; available execution host Windows.
**Project Type**: Standalone research modules and reports API.
**Performance Goals**: Finite CI budgets; remove redundant equivalence fits.
**Constraints**: No Git commands, market-data downloads, protected-file edits or
cross-spec ownership changes. Camden reviews and merges.
**Scale/Scope**: Only clean-clone reproducibility and the supplied comparison defects.

## Constitution Check

- Rules 1/2/5: Do not alter target eligibility, time alignment or CV geometry;
  test scoring with unknown outcomes and asymmetric coverage.
- Rules 6/8: No new project dependencies, strategy or accounting-layer redesign.
- Rules 7/9/10: No execution/credential access or version-control commands; human merge gate.
- Rules 11/12: Stamp evidence; measure red first and kill the original cast mutant.
- Rules 13–16: No investment results are generated or claimed by this work.

## Project Structure

```text
.specify/specs/037-clean-clone-green/
  spec.md, plan.md, tasks.md, failure-table.md, artifacts/
scripts/feature_set_comparison.py
tests/test_feature_set_comparison.py
tests/test_clean_clone_037.py
scripts/multi_ticker_comparison.py
tests/test_multi_ticker_comparison.py
.github/workflows/test.yml
README.md (setup addition only)
```

Additional failing files may be repaired only after evidence categorizes them and
the fix stays within this spec's explicit ownership boundaries.

## Execution

1. Snapshot protected hashes; read committed objects into scratch without Git.
2. Install requirements into isolated Python 3.12; capture full baseline plus packages.
3. Categorize every failure/error by exact node ID, distinguishing supplied Linux
   evidence from locally measured Windows evidence.
4. Write regression oracles and run them red before changing production.
5. Implement paired scoring, proven pinning repair and minimal equivalence workload.
6. Run focused green and mutation proofs, then the canonical full suite in a fresh export.
7. Verify protected hashes and README delta; finalize failure table and handoff evidence.

## Complexity Tracking

No constitutional exception requested. Read-only scratch export uses Dulwich because
stdlib does not decode packed repository objects; it is not a project dependency.
