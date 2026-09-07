# Tasks — 015 Parallelized Feature-Set Comparison

Dependency-ordered. `[P]` = parallelizable with the task above it.

---

## Phase 1 — Worker Architecture & Environment Pinning

- [ ] **T001** Define `ComparisonTask` dataclass in `scripts/feature_set_comparison.py` holding `(name, task, feature_set, random_state)`. (FR-004)
- [ ] **T002** Implement `_worker_init()` in `scripts/feature_set_comparison.py` setting environment variables `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `VECLIB_MAXIMUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`. (FR-002)
- [ ] **T003** Extract `_evaluate_feature_set_task()` as a module-level, picklable worker function returning `(name, task, feature_set, predicted, labels, outer_folds)`. (FR-003)

---

## Phase 2 — Parallel Orchestration & Collation

- [ ] **T004** Implement `compare_all_entries_parallel(prices, max_workers=None, random_state=42)` in `scripts/feature_set_comparison.py`. Use `concurrent.futures.ProcessPoolExecutor(max_workers=max_workers, initializer=_worker_init)`. (FR-001, FR-007)
- [ ] **T005** Implement synchronous fallback path in `compare_all_entries_parallel` when `max_workers=1` to bypass process creation for debugging. (FR-007)
- [ ] **T006** Collate completed futures into a dictionary keyed by `(name, task, feature_set)`, then assemble paired comparisons in deterministic order sorted by `(name, task)`. (FR-006)
- [ ] **T007** Update `main()` in `scripts/feature_set_comparison.py` to parse an optional `--workers` CLI argument (default `None`) and delegate to `compare_all_entries_parallel()`. (FR-007)

---

## Phase 3 — Verification & Equivalence Testing

- [ ] **T008** Create `tests/test_feature_set_comparison.py` with synthetic data fixtures (no network download). (Rule 5)
- [ ] **T009** Add test asserting bit-for-bit equivalence between `max_workers=1` (serial) and `max_workers=2` (parallel) on prediction series, labels, and statistical test outputs. (FR-005, SC-002)
- [ ] **T010** Add test verifying error propagation: if a worker encounters an invalid model or exception, the executor surfaces the error cleanly with task identification.
- [ ] **T011** Verify on the real cached AAPL dataset that `feature_set_comparison.py` achieves target speedup without memory leaks. (SC-001, SC-003, SC-004)
