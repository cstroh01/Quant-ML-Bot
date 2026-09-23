# Canonical Suite Triage — Spec 033 Phase 7 Checkpoint

_Date: 2026-09-22_  
_Status: Triage-only — no production or test fixes applied (Rule 10 / human-owned scope)_  
_Sources:_
- `docs/implementation/spec-033/suite-comparison-phase7.json`
- `docs/implementation/spec-033/canonical-phase7.txt`
- `docs/implementation/spec-033/T001-baseline.txt` (start of Spec 033: 18 failed, 9 errors, 723 passed)
- `docs/audit-2026-09-12/UNIFIED_FAILURES.md` (2026-09-14 post-019 run: 161 failed, 9 errors)
- `docs/PROJECT_CONTEXT.md` (2026-09-18 Spec 032 completion: 18 failed, 9 errors, 723 passed)

---

## Executive Summary

| Total Red Nodes | Pre-Existing & Known | New / Uninvestigated | Action Required for Spec 033 |
|:---:|:---:|:---:|:---:|
| **27** (18 failed, 9 errors) | **27** (100%) | **0** (0%) | **None** (flag for dedicated remediation specs) |

Every single one of the 18 failures and 9 errors present at the Spec 033 Phase 7 checkpoint is **pre-existing and historically documented**. Comparison against the pre-spec-033 baseline (`T001-baseline.txt`), the Spec 032 completion checkpoint (`docs/PROJECT_CONTEXT.md:102-111`), and the 2026-09-14 unified blast-radius diff (`docs/audit-2026-09-12/UNIFIED_FAILURES.md`) confirms:
1. **Zero new failures or errors** were introduced by Spec 033 (all 28 added PBO tests pass cleanly, 817/844 passed).
2. All 27 reds are localized to the same five files: `test_feature_set_comparison.py`, `test_model_cv.py`, `test_multi_ticker_comparison.py`, `test_reports_api.py`, and `test_targets.py`.
3. The root causes trace directly to two historical transitions:
   - **Pandas 2.0+ `IntCastingNaNError`** when calling `.astype(int)` on arrays containing NaNs in `feature_set_comparison.py` (3 failures, 9 errors).
   - **Spec 019 / 020 Funded Ledger & Unadjusted Price Basis Migration** which updated `backtest_harness.py`, `estimators.py`, and `targets.py` to enforce unadjusted dollar prices and 2-bar execution timing, leaving legacy test fixtures and callers in `multi_ticker_comparison.py`, `model_cv.py`, `targets.py`, and `reports/api/routes/backtest.py` unmigrated (15 failures).

---

## Node-by-Node Categorization

| # | Test Node ID | Outcome | Category | Historical Baseline Source | Root Cause Mechanism |
|---|---|:---:|:---:|---|---|
| 1 | `tests/test_feature_set_comparison.py::TestParentSideThreadPinning::test_the_orchestrator_leaves_this_process_unpinned` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:77` | `feature_set_comparison.py:369` `labels.astype(int)` raises `IntCastingNaNError` |
| 2 | `tests/test_feature_set_comparison.py::TestSynchronousPathCreatesNoProcesses::test_no_executor_is_constructed` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:79` | `feature_set_comparison.py:369` `labels.astype(int)` raises `IntCastingNaNError` |
| 3 | `tests/test_feature_set_comparison.py::TestSynchronousPathCreatesNoProcesses::test_the_synchronous_path_runs_in_the_calling_process` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:80` | `feature_set_comparison.py:369` `labels.astype(int)` raises `IntCastingNaNError` |
| 4 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_discordant_counts_and_p_values_are_equal` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:179` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 5 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_formatted_reports_match_character_for_character` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:180` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 6 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_on_pair_reports_completed_comparisons_in_report_order` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:181` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 7 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_orchestrator_results_match_key_for_key_and_bit_for_bit` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:182` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 8 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_pairing_the_two_unit_sets_gives_identical_statistics` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:183` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 9 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_prediction_dtypes_and_index_survive_the_process_boundary` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:184` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 10 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_prediction_series_are_identical` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:185` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 11 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_result_order_is_the_registry_order_in_both_modes` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:186` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 12 | `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_the_fr_007_alias_produces_the_same_results` | ERROR | Pre-existing & known | `UNIFIED_FAILURES.md:187` | `setUpClass` crashes on `feature_set_comparison.py:369` `IntCastingNaNError` |
| 13 | `tests/test_model_cv.py::TestEquivalenceWithLogisticBaseline::test_null_placement_matches_too` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:138` | `logistic_baseline.py:166` passes unmasked NaNs to `LogisticRegression.fit` |
| 14 | `tests/test_model_cv.py::TestEquivalenceWithLogisticBaseline::test_one_outer_fit_per_fold_on_top_of_the_tuning_fits` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:139` | `estimators.py:280` raises `ValueError: purge/embargo shorter than label availability span` (span=2 vs horizon=1) |
| 15 | `tests/test_model_cv.py::TestEquivalenceWithLogisticBaseline::test_single_point_grid_reproduces_the_baseline_element_for_element` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:140` | `logistic_baseline.py:166` passes unmasked NaNs to `LogisticRegression.fit` |
| 16 | `tests/test_model_cv.py::TestEquivalenceWithLogisticBaseline::test_the_fixture_discriminates_between_folds` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:141` | `logistic_baseline.py:166` passes unmasked NaNs to `LogisticRegression.fit` |
| 17 | `tests/test_multi_ticker_comparison.py::TestIsolatedFailure::test_the_short_ticker_fails_by_name_and_the_others_complete` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:142` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 18 | `tests/test_multi_ticker_comparison.py::TestAllSucceed::test_every_ticker_produces_exactly_three_rows` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:143` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 19 | `tests/test_multi_ticker_comparison.py::TestCostParameterConsistency::test_commission_and_slippage_match_across_tickers_and_strategies` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:144` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 20 | `tests/test_multi_ticker_comparison.py::TestCostParameterConsistency::test_isolated_failure_still_matches_costs_for_completed_tickers` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:145` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 21 | `tests/test_multi_ticker_comparison.py::TestHonestyColumns::test_baseline_rows_carry_nan_for_the_ml_only_columns` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:146` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 22 | `tests/test_multi_ticker_comparison.py::TestHonestyColumns::test_ml_row_carries_hurdle_and_prediction_columns_and_fold_geometry` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:147` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 23 | `tests/test_multi_ticker_comparison.py::TestCsvRoundTrip::test_round_trip_preserves_shape` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:148` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 24 | `tests/test_multi_ticker_comparison.py::TestMutations::test_dropping_a_baseline_is_caught_by_the_strategy_set_assertion` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:149` | `backtest_harness.py:38` raises `ValueError: funded ledger requires declared unadjusted dollar prices` |
| 25 | `tests/test_reports_api.py::TestReportsApi::test_backtest_tearsheet` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:150` (Audit Finding 57) | `/api/backtest/tearsheet` calls `run_backtest` without unadjusted price basis |
| 26 | `tests/test_targets.py::TestEquivalenceWithLogisticBaseline::test_build_features_reproduces_the_baseline_frame` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:177` | Horizon mismatch: `build_features` returns span=2 under spec 019; legacy test asserts 1 |
| 27 | `tests/test_targets.py::TestEquivalenceWithLogisticBaseline::test_direction_label_matches_the_baseline_label` | FAILED | Pre-existing & known | `UNIFIED_FAILURES.md:178` | NA mask mismatch (0.59%) due to spec 019 open-basis shift conventions |

---

## Detailed Root Cause Analysis by Module

### 1. `tests/test_feature_set_comparison.py` (3 Failed, 9 Errors)

- **Failure / Error Signature**:
  ```text
  pandas.errors.IntCastingNaNError: Cannot convert non-finite values (NA or inf) to integer.
  Replace or remove non-finite values or cast to an integer type that supports these values (e.g. 'Int64')
  ```
- **Callsite**: `scripts/feature_set_comparison.py:369` inside `compare_classification`:
  ```python
  truth = labels.astype(int).to_numpy()
  ```
- **Mechanism**:
  Walk-forward CV produces unobservable / warm-up / tail rows containing `NaN` / `pd.NA`. In modern pandas, `.astype(int)` strictly refuses to cast floats or nullable integers with missing values to native int.
  In `TestSerialParallelEquivalence`, `compare_all_entries_parallel` runs in `@classmethod setUpClass`, causing all 9 test methods to terminate in `ERROR` during setup. In `TestParentSideThreadPinning` and `TestSynchronousPathCreatesNoProcesses`, it is called directly within the test body, yielding 3 `FAILED` results on the same line.
- **Triage Assessment**: Pre-existing defect. Logged on 2026-09-14 in `UNIFIED_FAILURES.md:77, 79, 80, 179-187`.

### 2. `tests/test_model_cv.py` (4 Failed)

- **Failure Signatures**:
  1. `ValueError: Input X contains NaN. LogisticRegression does not accept missing values encoded as NaN natively.` (`test_null_placement_matches_too`, `test_single_point_grid_reproduces_the_baseline_element_for_element`, `test_the_fixture_discriminates_between_folds`).
  2. `ValueError: purge/embargo shorter than label availability span` (`test_one_outer_fit_per_fold_on_top_of_the_tuning_fits`).
- **Callsites**:
  - `scripts/logistic_baseline.py:166` inside `walk_forward_predictions`.
  - `scripts/estimators.py:280` inside `model_row_masks`.
- **Mechanism**:
  - The first three tests call legacy `walk_forward_predictions(self.frame)`. After spec 019 changed feature computation boundaries, unmasked NaN rows reach `model.fit`.
  - The fourth test asserts equivalence with nested tuning splits using `label_horizon=1, embargo_bars=1`. However, `self.frame` carries `attrs["label_availability_span"] = 2` from the spec 019 next-open entry model. `model_row_masks` enforces `horizon >= label_availability_span`, raising `ValueError`.
- **Triage Assessment**: Pre-existing defect. Logged on 2026-09-14 in `UNIFIED_FAILURES.md:138-141`.

### 3. `tests/test_multi_ticker_comparison.py` (8 Failed)

- **Failure Signature**:
  ```text
  AssertionError: Lists differ: [ComparisonFailure(ticker='A', reason='funded ledger requires declared unadjusted dollar prices')] != []
  KeyError: 'Strategy' / KeyError: 'commission_per_trade'
  ```
- **Callsite**: `scripts/backtest_harness.py:38` inside `run_backtest`.
- **Mechanism**:
  Spec 019 and Spec 020 made unadjusted dollar prices mandatory in the backtest harness:
  ```python
  if prices.attrs.get("price_basis") != "unadjusted_dollars":
      raise ValueError("funded ledger requires declared unadjusted dollar prices")
  ```
  The synthetic price fixtures in `tests/test_multi_ticker_comparison.py` (`_long_history`) produce prices with default attributes (`price_basis = "research_adjusted"` or missing). `run_one_ticker` catches the exception and records a `ComparisonFailure`. Every ticker fails, resulting in empty results frames that fail downstream assertions.
- **Triage Assessment**: Pre-existing defect. Spec 021 was scoped to migrate accounting consumers, but `multi_ticker_comparison.py` was left pending. Logged on 2026-09-14 in `UNIFIED_FAILURES.md:142-149`.

### 4. `tests/test_reports_api.py` (1 Failed)

- **Failure Signature**:
  ```text
  ValueError: funded ledger requires declared unadjusted dollar prices
  ```
- **Callsite**: `reports/api/routes/backtest.py:55` inside `get_backtest_tearsheet`.
- **Mechanism**:
  The FastAPI endpoint `/api/backtest/tearsheet` loads cached market data via `get_cached_ticker_data` and feeds it to `run_backtest`. The cached ticker data lacks `attrs["price_basis"] == "unadjusted_dollars"`, triggering the harness guard.
- **Triage Assessment**: Pre-existing defect. Identical to 2026-09-12 Audit Finding 57 ("a clean checkout does not reproduce: 11 API tests run, 7 failed") and logged on 2026-09-14 in `UNIFIED_FAILURES.md:150`.

### 5. `tests/test_targets.py` (2 Failed)

- **Failure Signatures**:
  1. `AssertionError: Tuples differ: ('classification', 2) != ('classification', 1)` (`test_build_features_reproduces_the_baseline_frame`).
  2. `AssertionError: Series NA mask values are different (0.59172 %)` (`test_direction_label_matches_the_baseline_label`).
- **Callsites**:
  - `tests/test_targets.py:544`
  - `tests/test_targets.py:523`
- **Mechanism**:
  In Spec 019, `direction_label` and `build_target` were updated to reflect next-open execution timing, resulting in an effective label horizon/span of 2 bars. Legacy baseline equivalence tests written in Spec 009 pinned the old 1-bar horizon and old NA mask layout.
- **Triage Assessment**: Pre-existing defect. Logged on 2026-09-14 in `UNIFIED_FAILURES.md:177-178`.

---

## Conclusion & Follow-up Plan

1. **No Spec 033 Regression**: Spec 033 Phase 7 (PBO matrix calculations, CSCV block partitioning, DSR target correction) introduced zero new test failures or errors.
2. **No Fixes Applied**: In accordance with the prompt's instructions and repo policy, no code fixes were applied during this triage.
3. **Follow-up Tasks**:
   - **Task A (Feature Set Comparison)**: In `scripts/feature_set_comparison.py`, fix `labels.astype(int)` to drop or mask `NaN`/`pd.NA` rows prior to casting, or cast to pandas `Int64` nullable array (resolves 3 failures + 9 errors).
   - **Task B (Spec 021 Phase 2 Migration)**: Complete the migration of `tests/test_multi_ticker_comparison.py`, `tests/test_model_cv.py`, `tests/test_targets.py`, and `reports/api/routes/backtest.py` to declare `price_basis = "unadjusted_dollars"` and align with the 2-bar execution timing contract (resolves the remaining 15 failures).
