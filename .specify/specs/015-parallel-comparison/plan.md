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
