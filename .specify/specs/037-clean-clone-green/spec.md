# Feature Specification: Green from a clean clone

**Feature Branch**: `037-clean-clone-green` (name only; Camden owns Git)
**Created**: 2026-09-25
**Status**: Implemented and audited; full green gate NOT MET. Final: 886 passed, 1 failed, no skips/errors (see `artifacts/final-acceptance.json`). Spec 036 tearsheet decision pending.
**Evidence**: [failure-table.md](failure-table.md), [artifacts](artifacts/).
**Input**: Camden's clean-clone task, including the supplied Linux/Python 3.12.14 baseline.

## User Scenarios & Testing

### User Story 1 - Reproduce and repair the suite (Priority: P1)

A reviewer installs the exact pins into Python 3.12 and runs `python -m pytest tests`
from an export of committed HEAD, without machine-local artifacts.

**Why this priority**: A passing working directory is not evidence of reproducibility.
**Independent Test**: Full baseline and final runs with raw output, node IDs,
resolved distributions, source hashes, OS, CPU count and timestamp.

**Acceptance Scenarios**:
1. Given a clean HEAD export, installation and every failure are recorded before fixes.
2. Given HEAD plus the reviewed patch, the full suite passes without network or local caches.

### User Story 2 - Compare only observable outcomes (Priority: P1)

**Why this priority**: Fabricating missing labels corrupts paired statistics.
**Independent Test**: Synthetic known/unknown outcomes, exact paired counts,
classification and regression results, and an unsafe-cast in-memory mutant.

**Acceptance Scenarios**:
1. Unknown target rows do not contribute to either side of the paired statistic.
2. An empty scoreable sample fails explicitly; invalid finite class values and
non-finite predictions on scoreable rows cannot silently become class labels.
3. The original unsafe cast is killed, with an unmutated green control, using
`tests/mutation_support_019.py`.

### User Story 3 - Bounded, portable parallel verification (Priority: P2)

**Why this priority**: CI must terminate, and an environment variable is not proof
that a native thread pool uses one thread.
**Independent Test**: Real workers report effective thread counts; serial and
parallel prediction values, dtypes, indices, statistics and report text agree exactly.

**Acceptance Scenarios**:
1. Both workflow jobs have explicit timeouts.
2. Equivalence work is reduced without mocking away estimator fitting or the process boundary.
3. README setup states the effective pinned Python floor in one addition.

### Edge Cases

Unknown terminal and internal labels; unequal feature warmups; mismatched indices;
no scoreable pairs; missing/non-finite predictions; fractional class values;
worker initialization after native-library import; unavailable private OpenMP probe.

## Requirements

### Functional Requirements

- **FR-001**: Read-only HEAD export outside the repo; never invoke Git. Record
  baseline output before production/test fixes and categorize every failed/error node.
- **FR-002**: Answer (i)/(ii) below and fix the statistical boundary, without filling
  unknown targets with zero or relying on nullable casting to hide missing truth.
- **FR-003**: Reuse the existing in-memory mutation engine; no third harness.
- **FR-004**: Diagnose worker pinning without loosening the single-thread invariant.
- **FR-005**: Keep serial/parallel exact equivalence and bound both CI jobs.
- **FR-006**: Generate test inputs; no new network or gitignored-artifact dependency.
- **FR-007**: Preserve the named governance and module-ownership files byte-for-byte,
  except the single authorized README setup addition. No spec 035/036/038 work.

### Root-cause decision: (i), NaN is legitimate

`features.build_features` preserves the calendar and sets `Train_Eligible` separately
from `Inference_Eligible`. `estimators.model_row_masks` permits inference with an
unknown target; `model_cv.nested_walk_forward` returns covered inference positions,
including the terminal positions whose next-open outcome is not yet observable.
`_predictions_by_date` preserves those positions and their unknown labels.
Therefore NaN truth is legitimate at the comparison boundary; it is not an upstream
prediction-generation defect. Casting all labels to integer is incorrect. Scoring
must select the same observable-label rows on both sides, preserve pairing, and
report the resulting scored sample size. Regression needs the same boundary.
No change to inference eligibility, label construction, purge or embargo is authorized.

## Success Criteria

- **SC-001**: Full suite passes in an artifact-free HEAD-plus-patch export on Python 3.12;
  every skip has a named condition and reason, and platform limitations are explicit.
- **SC-002**: Unsafe-cast mutant fails the semantic oracle while its control passes.
- **SC-003**: Both jobs have timeouts; exact equivalence remains covered by real fits.
- **SC-004**: Failure table and final provenance are in this directory; protected
  file hashes match the initial snapshot, with only the authorized README delta.

## Assumptions

No strategy or financial performance claims are made. Synthetic values are test
inputs, not reported investment results. No new project dependency is planned.
Scratch export tooling (Dulwich) only reads the object store, supports packed objects,
and replaces neither project runtime code nor the human-owned Git workflow.

## Out of scope â€” for Camden's decision

There is no LICENSE file. A public repository without a license grants no general
reuse permission (all rights reserved), contrary to ADR 0001's public-framework intent.
Camden must choose the license; this spec does not add one.

There is no `pyproject.toml` or installable package. `scripts/` consists of flat
modules imported using `tests/context.py`'s `sys.path` insertion. The task and the current inventory both count
31 modules (2026-09-26 working tree; `Get-ChildItem scripts -Filter *.py -File`). Converting to `src/`
affects every test module's import path, standalone entry points, spawned-worker
imports, mutation loaders and CI invocation. No package conversion starts here.

## Measured follow-through and scope boundaries

The baseline is [fully categorized](failure-table.md): comparison failures are real
production defects; multi-ticker and tearsheet failures reflect the deliberate
Spec 019/020 funded-ledger contract change. Multi-ticker callers now require explicit
starting capital and terminal-liquidation policy and forward both unchanged to the
strategy and every baseline. Its synthetic tests declare their price basis, derive
purge/embargo from target metadata, and write CSV output only in temporary storage.
Real adjusted downloads remain rejected; this is not Spec 035/036 data-loader wiring.

The tearsheet success test requires the caller wiring owned by excluded Spec 036
(`docs/V1-FINISH-PLAN.md`, S2). Neither that route nor its existing test has been
changed. The option to retain the success assertions under a documented pending-036
skip plus an active rejection test was put to Camden; no approval has been inferred.
Until resolved, the suite cannot be claimed green.

The initialized-pool probe in `artifacts/initialized-pool.json` proves that a
native pool initialized at two threads remains at two after the initializer sets
OMP_NUM_THREADS=1. Starting the interpreter with the limit already set yields one.
Python 3.12's installed `multiprocessing/context.py` selects fork on non-macOS Unix;
explicit spawn prevents inheritance of initialized pools. The Windows worker tests
pass without relaxing their effective-one-thread invariant. Linux execution remains
unverified locally (no WSL or Docker runtime).

The equivalence fixture uses two real outer windows and two real orchestrator runs,
all registry entries and both feature sets. Pair-boundary spies capture actual
returned units without replacing model fits. Prediction comparisons explicitly use
`check_exact=True`; an adjacent-float perturbation proves that one ULP is rejected.
The alias and progress callback checks reuse the already computed runs. The AST
import guard distinguishes stdlib `multiprocessing` from third-party `multiprocess`
and is proven red for banned imports and aliases.

CI budgets are chosen operational limits: Python 20 minutes, web 10 minutes.
They are not measured performance claims. No project dependencies were added.

### Correction to the supplied install-floor evidence

The installed NumPy 2.5.2 wheel declares `Requires-Python: >=3.12`. Although pandas
3.0.5 and contourpy 1.3.3 require >=3.11, the complete current pins therefore need
**Python >=3.12**. The single README sentence states both facts. Evidence:
`artifacts/python-floor.json`, from the same environment as the baseline. Pins were
not relaxed to make Python 3.11 work.
