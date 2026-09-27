# Categorized clean-HEAD baseline

Run `spec037-20260925-baseline`, HEAD `54e6e0bca572cfc96a477308fa0a3d71414fdd42`, 2026-09-26 UTC (2026-09-25 local). Windows 11 x86_64, Python 3.12.13, 16 logical CPUs, inherited OMP_NUM_THREADS=16. Exact resolved distributions and times: [environment](artifacts/baseline-environment.json); [raw output](artifacts/baseline.txt); [JUnit](artifacts/baseline.xml); [source hashes](artifacts/initial-provenance.json).

Canonical full-suite baseline: **12 failed, 840 passed, 9 errors**, no skips; pytest 411.99 seconds, supervisor 415.22 seconds. Every failing/error node follows.

| Node | Outcome | Category | Evidence / cause |
|---|---|---|---|
| `tests/test_feature_set_comparison.py::TestParentSideThreadPinning::test_the_orchestrator_leaves_this_process_unpinned` | failure | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSynchronousPathCreatesNoProcesses::test_no_executor_is_constructed` | failure | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSynchronousPathCreatesNoProcesses::test_the_synchronous_path_runs_in_the_calling_process` | failure | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_discordant_counts_and_p_values_are_equal` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_formatted_reports_match_character_for_character` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_on_pair_reports_completed_comparisons_in_report_order` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_orchestrator_results_match_key_for_key_and_bit_for_bit` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_pairing_the_two_unit_sets_gives_identical_statistics` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_prediction_dtypes_and_index_survive_the_process_boundary` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_prediction_series_are_identical` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_result_order_is_the_registry_order_in_both_modes` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_feature_set_comparison.py::TestSerialParallelEquivalence::test_the_fr_007_alias_produces_the_same_results` | error | real defect in production code | Unknown observable-outcome boundary: NaN labels cast to integer (A). |
| `tests/test_multi_ticker_comparison.py::TestIsolatedFailure::test_the_short_ticker_fails_by_name_and_the_others_complete` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_multi_ticker_comparison.py::TestAllSucceed::test_every_ticker_produces_exactly_three_rows` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_multi_ticker_comparison.py::TestCostParameterConsistency::test_commission_and_slippage_match_across_tickers_and_strategies` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_multi_ticker_comparison.py::TestCostParameterConsistency::test_isolated_failure_still_matches_costs_for_completed_tickers` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_multi_ticker_comparison.py::TestHonestyColumns::test_baseline_rows_carry_nan_for_the_ml_only_columns` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_multi_ticker_comparison.py::TestHonestyColumns::test_ml_row_carries_hurdle_and_prediction_columns_and_fold_geometry` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_multi_ticker_comparison.py::TestCsvRoundTrip::test_round_trip_preserves_shape` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_multi_ticker_comparison.py::TestMutations::test_dropping_a_baseline_is_caught_by_the_strategy_set_assertion` | failure | churn from a deliberate contract change | Spec 019/020 funded ledger rejects undeclared price basis; caller also omits explicit funding/end policy; old test geometry refers to retired EMBARGO_BARS. |
| `tests/test_reports_api.py::TestReportsApi::test_backtest_tearsheet` | failure | churn from a deliberate contract change | CSV loses price-basis metadata; tearsheet still uses pre-funded-ledger contract. Caller wiring belongs to excluded Spec 036. |

No measured failures depend on gitignored artifacts; none remain uncategorized. The supplied Linux pinning failure is a production defect conditioned on the start method, not a reason to relax the one-thread invariant. It does not reproduce with Windows spawn; [initialized-pool probe](artifacts/initialized-pool.json) reproduces ineffective late environment changes. Linux execution is unavailable on this host.

## Final comparison

Run `spec037-20260925-final`, 2026-09-26 UTC: **886 passed, 1 failed, 0 errors,
0 skips**, 887 collected, pytest 619.53 seconds (supervisor 623.36 seconds).
[Raw output](artifacts/final.txt), [JUnit](artifacts/final.xml),
[environment](artifacts/final-environment.json), [exact differential](artifacts/final-acceptance.json).
All 20 other baseline failure/error IDs are resolved; there are no unexpected failures.

| Baseline category/group | Baseline failing/error nodes | Final disposition |
|---|---:|---|
| Real production defect: feature comparison | 12 (3 failures + 9 errors) | All pass |
| Deliberate contract change: multi-ticker funding/fixtures | 8 failures | All pass |
| Deliberate contract change: tearsheet caller | 1 failure | Still fails; excluded Spec 036 wiring |
| Environment-only, gitignored artifact, uncategorized | 0 locally measured failures | None |

The separate supplied Linux worker failure is discussed above; the Windows pinning
control passes and explicit spawn removes the inherited-pool mechanism. This is not
an executed Linux CI result. The known Starlette/httpx deprecation warning remains;
no pinned dependency was changed to suppress it.

**The green-from-clean-clone definition of done is not met.** The remaining node is
`tests/test_reports_api.py::TestReportsApi::test_backtest_tearsheet`, which raises
`ValueError: funded ledger requires declared unadjusted dollar prices`. No test was
skipped or weakened to hide it, and the Spec 036-owned route was not changed.
