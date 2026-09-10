# Implementation Plan — 015 Parallelized Feature-Set Comparison

**Spec**: `.specify/specs/015-parallel-comparison/spec.md`

---

## Scope

- `scripts/feature_set_comparison.py` — **modified**.
  - Extract worker execution into a top-level picklable function `_evaluate_feature_set_task()`.
  - Add `_worker_init()` to isolate thread environment variables (`OMP_NUM_THREADS=1`, etc.).
  - Implement `compare_all_entries_parallel()` using `concurrent.futures.ProcessPoolExecutor`.
  - Provide a fallback/synchronous path when `max_workers=1`.
  - Add `--workers` CLI argument support to `main()`.
- `tests/test_feature_set_comparison.py` — **new**.
  - Test worker execution in isolation.
  - Test determinism: `max_workers=1` vs `max_workers=2` equivalence on synthetic data fixture.
  - Test exception handling: child process errors propagate cleanly with informative context.
  - Test result ordering: results are assembled deterministically regardless of completion order.

Explicitly **not** touched:
- `scripts/estimators.py`, `scripts/model_cv.py`, `scripts/features.py`, `scripts/data.py` (Rule 8: caller layer does not mutate model/signal layers).
- `data/cache/` (read-only).
- No new dependencies added to `requirements.txt` (Rule 6).

---

## Constitution Check

| Rule | Bearing on this plan |
|---|---|
| 1 — Point-in-time correctness | Unchanged. Parallelization strictly partitions independent estimator/feature-set runs. No cross-sample or cross-bar communication exists. |
| 2 — Purge/embargo | Unchanged. `model_cv.nested_walk_forward` is called unmodified within each worker. |
| 3 — Costs | Not applicable. `feature_set_comparison.py` evaluates statistical predictive accuracy (McNemar/Wilcoxon), not backtested P&L. |
| 4 — Baselines | The comparison baseline remains the paired control (`levels` vs `scale_free`), run on identical bars and splits. |
| 5 — Tests | Unit tests verify equivalence between serial and parallel execution modes over synthetic data fixtures. |
| 6 — Dependencies | **No new dependencies**. Replaces serial loop with standard library `concurrent.futures.ProcessPoolExecutor`. Specifically avoids `joblib` to prevent unnecessary dependency creep. |
| 8 — Layer separation | `feature_set_comparison.py` sits at the diagnostic level. It consumes `estimators`, `model_cv`, `features`, and `data` as an orchestrator and modifies none of them. |
| 9 — The merge gate | Clear explanation of the thread oversubscription problem and why process-level thread pinning is necessary. |
| 10 — Version control | No `git` commands run. Local review only. |

---

## Architectural Design

### 1. The Work Unit
Each task submitted to the executor is defined as:
```python
@dataclass(frozen=True)
class ComparisonTask:
    name: str
    task: str
    feature_set: str
    random_state: int
```

The worker entry point:
```python
def _evaluate_feature_set_task(
    prices: pd.DataFrame,
    task_spec: ComparisonTask,
) -> tuple[str, str, str, pd.Series, pd.Series, int]:
    """Top-level function executed in worker process."""
    predicted, labels, outer_folds = _predictions_by_date(
        prices,
        name=task_spec.name,
        task=task_spec.task,
        feature_set=task_spec.feature_set,
        random_state=task_spec.random_state,
    )
    return (
        task_spec.name,
        task_spec.task,
        task_spec.feature_set,
        predicted,
        labels,
        outer_folds,
    )
```

### 2. Thread Pinning in Worker Initialization
To guarantee that neither NumPy BLAS routines nor `HistGradientBoosting` spawn
uncontrolled threads:
```python
def _worker_init() -> None:
    import os
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
```

### 3. Gathering and Pairing Results
After `ProcessPoolExecutor.as_completed()` yields all 8 tasks:
1. Index results in a dictionary by `(name, task, feature_set)`.
2. For each `(name, task)` in `sorted(ESTIMATOR_REGISTRY)`:
   - Extract predictions for `FEATURE_SET_A` (`levels`) and `FEATURE_SET_B` (`scale_free`).
   - Intersect `Date` indices.
   - Run `compare_classification` or `compare_regression`.
   - Record the structured result dictionary.
3. Pass the gathered results to `format_report()`.

Because results are sorted by `(name, task)` before reporting, the output order is
strictly deterministic and identical to the serial script.

---

## Implementation Correction (2026-09-09)

Design Constraint 2 above (`_worker_init()` setting thread-limit env vars inside
the worker) does not achieve its stated goal on Windows. This section records
why, and what actually ships instead, so the next agent reading this plan does
not re-derive the same bug from scratch.

**What was wrong.** On Windows, `ProcessPoolExecutor` workers are created via
`spawn`, not `fork`. A `spawn`ed child's first act is unpickling the submitted
task, which imports `numpy`/`scipy`/`sklearn` as a side effect of unpickling
the task's arguments — and NumPy's BLAS backend and `HistGradientBoosting`'s
own thread pool are both committed at import time, before `_worker_init()` on
the executor ever runs. `_worker_init()` arrives too late to matter.

**Measured impact.** With `_worker_init()` alone, workers ran at ~2.8 cores
each instead of the intended 1.0 — worse than doing nothing. Setting
`OMP_NUM_THREADS` late, after sklearn has already read the environment, reads
to sklearn as deliberate operator configuration and disables its own
core-count heuristic: effective thread count came out at 16 with the
initializer versus 8 without it. This was caught by measuring actual effective
thread count during execution, not by reading the env var back afterward
(the env var reads `"1"` in both the broken and fixed versions — reading it
back proves nothing).

**The fix.** `_pinned_thread_environment()`, a context manager, sets the five
thread-limit env vars (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`MKL_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS`) in the
**parent** process before `ProcessPoolExecutor` is constructed, and restores
the parent's original environment on exit. A `spawn`ed child inherits the
parent's environment at spawn time — ahead of its own first import — so the
limits are in place before NumPy/sklearn ever read them. `_worker_init()` is
retained as-is and still runs; it is now the fallback for the `fork` start
method (Linux/macOS default), where it was never actually broken. Design
Constraint 2's code above is superseded by this context manager wrapping the
pool's lifetime; `_worker_init()` is not removed.

**Verification.** Five new tests in `tests/test_feature_set_comparison.py`
guard this specifically: effective thread count under the pool matches the
pin (not just the env var string), and parent environment is provably
restored after the pool exits.

**Status.** Implemented and tested by Claude Code during spec 015 work,
ratified as a clearly-correct fix (not a tradeoff) rather than a spec
deviation requiring a new round of Camden review — the spec's literal
mechanism defeated its own SC-001 goal, so following it literally would have
shipped a regression. Not yet committed to git (Rule 10 — Camden commits).
