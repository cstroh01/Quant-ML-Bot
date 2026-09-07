# Feature Specification: Parallelized Feature-Set Comparison

**Feature Branch**: `015-parallel-comparison`

**Created**: 2026-09-06

**Status**: Draft

**Input**: Spec 014 introduced `scripts/feature_set_comparison.py` to run nested
walk-forward cross-validation across all 4 estimator registry entries under
both the `levels` control set and the `scale_free` ratio set, performing paired
significance testing (McNemar for classification, Wilcoxon signed-rank for
regression). Currently, this comparison executes completely serially:
4 estimator entries × 2 feature sets = 8 walk-forward runs. Each run evaluates
~113 outer folds, with each outer fold evaluating inner folds across 4 grid
points, totaling over 37,000 model fits. On AAPL alone, this serial loop
requires 2 to 3 hours. Spec 013 (multi-ticker comparison across AAPL, AMZN,
GOOGL, MSFT, NVDA) is blocked on this runtime: evaluating 5 tickers serially
would require 10 to 15 hours.

**Owns / must not know about** (per CLAUDE.md's module table):
`scripts/feature_set_comparison.py` owns diagnostic comparison execution and
reporting. It imports `data`, `features`, `estimators`, and `model_cv`. It must
know nothing about signals, trade fills, positions, or P&L (Rule 8). It does
not modify `estimators.py`, `features.py`, or `model_cv.py`.

---

## Background

The nested walk-forward evaluation in `scripts/feature_set_comparison.py` has a
multiplicative computational profile:

$$\text{Fits} = E \times F \times O \times (1 + I \times G)$$

Where:
- $E = 4$ registered estimators (`logistic/classification`, `hgb/classification`,
  `ridge/regression`, `hgb/regression`)
- $F = 2$ feature sets (`levels`, `scale_free`)
- $O \approx 113$ outer folds (over 10 years of data with 1-month test steps)
- $I \approx 10$ inner folds per outer fold
- $G = 4$ hyperparameter grid points per entry

This produces approximately 4,600 fits per $(E, F)$ pair, or ~37,000 fits for
one ticker. Because the outer loop iterates sequentially over the 8
$(E, F)$ combinations, the execution is purely serial, with one problematic
exception: `HistGradientBoosting` internally leverages OpenMP to parallelize
histogram binning across all available CPU cores.

### The Oversubscription Trap
If multiple worker processes are spawned without controlling OpenMP, each
worker process attempts to consume all available physical cores. On an 8-core
machine, 8 worker processes each attempting to run 8 threads results in 64
active threads competing for 8 cores. The resulting cache eviction, CPU
pipeline thrashing, and OS context-switching overhead causes oversubscribed
parallel runs to execute *slower* than single-threaded serial runs.

To achieve linear scaling across CPU cores, thread affinity and concurrency must
be bounded at the process level:
1. Each worker process is restricted to a single thread for linear algebra and
   OpenMP operations (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
   `MKL_NUM_THREADS=1`, `VECLIB_MAXIMUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`).
2. Parallelism is extracted at the embarrassingly parallel $(E, F)$ job level
   using Python's standard library `concurrent.futures.ProcessPoolExecutor`.

### Why `ProcessPoolExecutor` and Not `joblib`
Rule 6 states: *"No dependency is added without a one-line justification in the
PR description naming what it does that the standard library and the existing
dependencies cannot."*
Python's standard library `concurrent.futures.ProcessPoolExecutor` handles
multiprocess distribution natively without adding `joblib` or any other external
dependency to `requirements.txt`.

---

## Design Constraints

### 1. Work Unit Granularity
The atomic unit of parallelization is a single feature-set prediction run:
$$(name, task, feature\_set, seed)$$

There are 8 such units for a single ticker (and 40 when generalized to 5
tickers in spec 013). Parallelizing at this top-level granularity minimizes
inter-process communication (IPC) overhead:
- **Input**: Lightweight configuration tuple and read-only price dataframe.
- **Output**: Serialized predictions series, true labels series, and outer fold
  count.
- Inner folds and grid search remain localized within each worker process,
  requiring zero cross-process synchronization.

### 2. Worker Initialization and OpenMP Isolation
On Windows, Python's `multiprocessing` uses `spawn`. Environment variables
governing thread pools must be set before runtime libraries (NumPy, SciPy,
OpenBLAS, MKL) initialize their thread pools:
```python
def _worker_init() -> None:
    import os
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
```
The `ProcessPoolExecutor` is instantiated with `initializer=_worker_init`.

### 3. Bit-for-Bit Determinism
Rule 5 / CLAUDE.md (*Conventions → Determinism*) dictates: *"Every stochastic
operation takes an explicit seed parameter. No implicit global random state."*
- Each work unit receives an explicit `random_state: int`.
- Because work units are executed in isolated processes and results are gathered
  and sorted deterministically by `(name, task, feature_set)`, the output of the
  parallel run is bit-for-bit identical to the serial implementation.

### 4. Windows Process Spawn Compatibility
All worker target functions must be top-level functions defined at the module
level in `scripts/feature_set_comparison.py`, not local closures or lambda
functions, ensuring compatibility with Windows `pickle` and `spawn`.

---

## User Scenarios & Testing

### User Story 1 - Fast Diagnostic Execution on Multi-Core Workstations (Priority: P1)
As the project owner, I need `feature_set_comparison.py` to evaluate the 8
estimator/feature-set combinations concurrently across available CPU cores, so
the diagnostic completes in ~20–30 minutes rather than 2–3 hours.

**Acceptance**: Running `feature_set_comparison.py` with `max_workers=None` (or
`--workers N`) on an 8-core machine completes in under 35 minutes on the 10-year
AAPL dataset.

### User Story 2 - Bit-for-Bit Equivalence with Serial Execution (Priority: P1)
As a developer reviewing model comparisons, I need the parallel implementation
to produce the exact same predictions, p-values, and test statistics as the
serial implementation.

**Acceptance**: A test running both the serial execution and parallel execution
over a synthetic test fixture asserts:
1. Predictions for each `(name, task, feature_set)` match to machine precision.
2. McNemar contingency tables and Wilcoxon signed-rank statistics match
   identically.
3. Formatted comparison reports match character-for-character.

### User Story 3 - Controllable Concurrency and Debuggability (Priority: P2)
As a developer debugging a model failure, I need to be able to force serial
execution (`workers=1`) to obtain clean tracebacks without multiprocessing IPC.

**Acceptance**: `main(max_workers: int | None = None)` accepts an optional worker
count. Setting `max_workers=1` bypasses process pool creation and runs
serially in the main process.

---

## Requirements

### Functional Requirements

- **FR-001**: `scripts/feature_set_comparison.py` MUST parallelize the evaluation
  of the `(estimator_name, task, feature_set)` product using
  `concurrent.futures.ProcessPoolExecutor`.
- **FR-002**: Worker processes MUST initialize with single-threaded thread limits
  (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
  `VECLIB_MAXIMUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`) to prevent CPU core
  oversubscription.
- **FR-003**: Worker target functions MUST be picklable module-level functions
  compatible with the Windows `multiprocessing` `spawn` start method.
- **FR-004**: Each parallel task MUST take an explicit `random_state` parameter,
  ensuring no worker relies on global or inherited random state.
- **FR-005**: Parallel execution MUST produce bit-for-bit identical prediction
  series, discordant pair counts, and p-values to the existing serial loop.
- **FR-006**: The parallel orchestrator MUST collect results into a deterministic
  order (`(name, task)`) matching the existing report layout regardless of which
  process completes first.
- **FR-007**: `compare_all_entries()` MUST accept an optional `max_workers`
  parameter (defaulting to `None`, which uses all available logical cores). When
  `max_workers=1`, it MUST execute synchronously in the calling process without
  spawning child processes.
- **FR-008** *(Rule 6)*: The implementation MUST NOT introduce any new dependency.
  It MUST rely exclusively on standard library `concurrent.futures`, `os`, and
  `multiprocessing`.

---

## Success Criteria

- **SC-001**: Running `feature_set_comparison.py` across all 8 configurations on
  a machine with at least 4 physical cores achieves at least a 3.0x wall-clock
  speedup compared to serial execution.
- **SC-002**: On the standard test fixture, running with `max_workers=1` and
  `max_workers=4` produces identical prediction series (asserted with
  `pd.testing.assert_series_equal`).
- **SC-003**: The 4 p-values reported for AAPL match the spec 014 baseline
  figures exactly.
- **SC-004**: Memory usage remains stable; each worker exits cleanly upon task
  completion without dangling zombie processes or memory leaks.
