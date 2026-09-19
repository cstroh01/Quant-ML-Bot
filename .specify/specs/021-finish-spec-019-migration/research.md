# Research: Finish the Spec 019 Migration (Consumer Side)

**Phase 0 output for** [plan.md](plan.md). Every open question in the plan's
Technical Context is resolved here.

Each decision is written as **Decision / Rationale / Alternatives considered**.
The evidence comes from four suite runs and three in-process probes, taken on
2026-09-18 between 16:20 and 16:45 EDT. Nothing was written to the repository.
The scratch files lived in the session scratchpad.

---

## R-1 — Per-test inventory

**Decision.** 128 unique failing test functions. 107 are in scope and are
assigned to lanes A–E below; 6 of those 107 are gated and move to lane G. 21
are residual.

**Method.**

1. `python -m pytest tests --junitxml=…` was run on the tree at 16:34:38 EDT.
   No file changed during the run; this was checked with `find -newer`.
2. The JUnit report gives each test's ID paired with its first error.
3. Second-layer errors come from in-process probes (R-2).
4. A scratch script generated the table and asserted two things:
   - every failing ID is classified;
   - every classified ID is failing.

   Both held: `MISSING: []`, `CLASSIFIED BUT NOT IN FAILING SET: []`.

**Columns.**

- **First**: the delta behind the error the test raises today.
- **Second**: the delta a test hits once the first is fixed.
- `C6-random` is the `random_signal` defect.
- `C1-semantic` is a capital-base expectation, as opposed to a missing
  argument.
- "Gated" rows move to lane G ([plan.md](plan.md) → Lanes).

#### Lane A (41)

| File | Test | First | Second | Change |
|---|---|---|---|---|
| `test_backtest_harness` | `CostTests::test_commission_is_charged_once_per_fill_not_once_per_round_trip` | C1 | - | capital |
| `test_backtest_harness` | `CostTests::test_costs_apply_to_the_end_of_data_close_exit` | C1 | C5 | liquidate=True explicit; assert costs on the `liquidation` exit |
| `test_backtest_harness` | `CostTests::test_defaults_reproduce_the_uncosted_arithmetic_exactly` | C1 | - | capital |
| `test_backtest_harness` | `CostTests::test_enough_slippage_turns_a_winner_into_a_loser` | C1 | - | capital |
| `test_backtest_harness` | `CostTests::test_hand_computed_costs_match_exactly` | C1 | - | capital |
| `test_backtest_harness` | `CostTests::test_slippage_worsens_both_sides_of_a_losing_trade_too` | C1 | - | capital |
| `test_backtest_harness` | `RunBacktestTests::test_cumulative_pnl_accumulates_across_trades` | C1 | - | capital |
| `test_backtest_harness` | `RunBacktestTests::test_empty_result_keeps_the_full_column_layout` | C1 | - | capital |
| `test_backtest_harness` | `RunBacktestTests::test_open_position_is_marked_to_the_final_close` | C1 | C5 | split: mark-only (0 closed trades, final Equity = marked close) + liquidate=True (1 trade, ledger `liquidation` event) |
| `test_backtest_harness` | `RunBacktestTests::test_repeated_buy_signals_do_not_stack_a_position` | C1 | - | capital |
| `test_backtest_harness` | `RunBacktestTests::test_round_trip_is_filled_at_the_open_on_both_sides` | C1 | - | capital |
| `test_backtest_harness` | `RunBacktestTests::test_sell_while_flat_does_nothing` | C1 | - | capital |
| `test_metrics` | `TestAttributionOffByOne::test_commission_is_charged_on_the_entry_and_exit_bars` | C1 | - | capital |
| `test_metrics` | `TestAttributionOffByOne::test_one_bar_hold_puts_pnl_on_exactly_two_bars` | C1 | - | capital |
| `test_metrics` | `TestAttributionOffByOne::test_position_is_one_from_entry_up_to_but_not_including_exit` | C1 | - | capital |
| `test_metrics` | `TestBoundaries::test_entry_on_bar_zero` | C1 | - | capital |
| `test_metrics` | `TestBoundaries::test_equity_is_anchored_so_a_bar_zero_drawdown_is_captured` | C1 | - | capital = the 100.0 it already passes to `equity_curve` (`:230`) |
| `test_metrics` | `TestBoundaries::test_position_still_open_on_the_final_bar_marks_to_its_close` | C1 | C5 | choose per intent: mark-only assertion or liquidate=True; state which |
| `test_metrics` | `TestBoundaries::test_same_bar_round_trip` | C1 | C5 | choose per intent: mark-only assertion or liquidate=True; state which |
| `test_metrics` | `TestEmptyTradeLog::test_curve_is_flat_at_the_capital_base` | C1 | C1-semantic | Equity == declared capital, not first Close (11.0) |
| `test_metrics` | `TestEmptyTradeLog::test_drawdown_is_a_genuine_zero` | C1 | - | capital |
| `test_metrics` | `TestEmptyTradeLog::test_performance_summary_has_every_key` | C1 | C7 | expected key set = 019 unit 6 schema |
| `test_metrics` | `TestEmptyTradeLog::test_sharpe_is_nan_not_zero` | C1 | - | capital |
| `test_metrics` | `TestGapCase::test_a_missing_session_does_not_change_the_bar_count` | C1 | - | capital |
| `test_metrics` | `TestReconciliation::test_bar_pnl_sums_to_trade_log_pnl` | C1 | C5 | liquidate=True so sum(Bar P&L) = sum(closed P&L) holds; docstring says why |
| `test_metrics` | `TestReconciliation::test_curve_has_one_row_per_bar` | C1 | - | capital |
| `test_metrics` | `TestReconciliation::test_reconciliation_holds_without_costs_too` | C1 | C5 | liquidate=True so sum(Bar P&L) = sum(closed P&L) holds; docstring says why |
| `test_metrics` | `TestSharpeConventions::test_costs_reach_the_metric` | C1 | - | capital |
| `test_metrics` | `TestValidation::test_a_trade_date_absent_from_prices_raises` | C1 | - | capital |
| `test_metrics` | `TestValidation::test_duplicate_dates_raise` | C1 | - | capital |
| `test_metrics` | `TestValidation::test_empty_price_frame_raises` | C1 | - | capital |
| `test_metrics` | `TestValidation::test_negative_costs_raise` | C1 | - | capital |
| `test_metrics` | `TestValidation::test_non_range_index_raises` | C1 | C4-index | invert: non-RangeIndex accepted, curve equals RangeIndex twin; rename |
| `test_metrics` | `TestValidation::test_unsorted_dates_raise` | C1 | - | capital |
| `test_ml_signal` | `EstimatorAgnosticTests::test_every_registry_entry_produces_a_signal_through_one_path` | C3 | FR-004 | add Open to `_synthetic_frame`; purge/embargo from `build_target` span, not `1, 1` |
| `test_ml_signal` | `HarnessReconciliationTests::test_break_even_reconciles_within_floating_point_tolerance` | C6 | C1 if absent | declare price_basis on the synthetic frame; capital |
| `test_ml_signal` | `HarnessReconciliationTests::test_it_reconciles_across_several_cost_settings` | C6 | C1 if absent | declare price_basis on the synthetic frame; capital |
| `test_ml_signal` | `HarnessReconciliationTests::test_the_first_order_hurdle_would_not_have_reconciled` | C6 | C1 if absent | declare price_basis on the synthetic frame; capital |
| `test_ml_signal` | `HysteresisTests::test_a_still_long_final_bar_is_forced_flat` | C5 | - | rewrite: final bar keeps its decision; rename |
| `test_ml_signal` | `NullPredictionTests::test_a_null_exits_an_open_position` | C5 | - | final element True (0.0 is not < exit 0.0); null-exit at [2] still asserted |
| `test_ml_signal` | `OrderingTests::test_the_decision_pairs_each_prediction_with_its_own_rows_hurdle` | C5 | - | final element per its own decision, not forced flat |

#### Lane B (17)

| File | Test | First | Second | Change |
|---|---|---|---|---|
| `test_logistic_baseline` | `TestBuildMlSignalEndToEnd::test_runs_without_error_and_pnl_is_finite` | C1 | - | capital (+ D-3 policy) |
| `test_ma_crossover_backtest` | `BaselineResultsTests::test_an_infeasible_random_baseline_is_reported_not_swallowed` | C1 | - | capital + policy args |
| `test_ma_crossover_backtest` | `BaselineResultsTests::test_both_baselines_report_the_costs_they_were_run_with` | C1 | C6-random | needs `random_signal` fix (FR-011) |
| `test_ma_crossover_backtest` | `BaselineResultsTests::test_buy_and_hold_holds_exactly_one_position` | C1 | C5 | liquidate=True via D-3 |
| `test_ma_crossover_backtest` | `BaselineResultsTests::test_seeds_produce_a_spread_rather_than_one_repeated_number` | C1 | C6-random | needs `random_signal` fix |
| `test_ma_crossover_backtest` | `BaselineResultsTests::test_the_random_baseline_matches_the_strategys_trade_count` | C1 | C6-random | would go green vacuously once C1 is fixed (loops over []); assert 20 summaries first (FR-012) |
| `test_ma_crossover_backtest` | `FormatComparisonTests::test_a_strategy_with_no_trades_still_produces_a_report` | C1 | - | capital + policy args |
| `test_ma_crossover_backtest` | `FormatComparisonTests::test_an_infeasible_random_baseline_says_so_in_the_report` | C1 | - | capital + policy args |
| `test_ma_crossover_backtest` | `FormatComparisonTests::test_cost_parameters_are_stated_once_not_per_row` | C1 | - | extend: capital and policy stated once |
| `test_ma_crossover_backtest` | `FormatComparisonTests::test_the_random_row_reports_dispersion_beside_the_mean` | C1 | C6-random | needs `random_signal` fix |
| `test_ma_crossover_backtest` | `FormatComparisonTests::test_three_rows_are_reported_side_by_side` | C1 | - | capital + policy args |
| `test_ma_crossover_backtest` | `MeanHoldingBarsTests::test_holding_period_is_counted_in_rows_not_calendar_days` | C6 | C1 | call site uses strictly positive closes; capital |
| `test_signals` | `BuyAndHoldSignalTests::test_a_single_row_frame_produces_no_trade_rather_than_crashing` | C1 | - | capital |
| `test_signals` | `BuyAndHoldSignalTests::test_an_empty_frame_produces_no_trade_rather_than_crashing` | C6 | - | signal layer: no entry; harness: named refusal; rename |
| `test_signals` | `BuyAndHoldSignalTests::test_the_harness_closes_the_position_at_the_final_close` | C1 | C5 | liquidate=True explicit (or mark-only); rename to say which |
| `test_signals` | `RandomSignalTests::test_the_harness_records_exactly_the_requested_number_of_trades` | C6 | C1 | strictly positive prices at the call site (fixture frozen); capital |
| `test_signals` | `RandomSignalTests::test_zero_trades_is_a_valid_request_not_a_division_by_zero` | C6 | C1 | strictly positive prices at the call site (fixture frozen); capital |

#### Lane C (13)

| File | Test | First | Second | Change |
|---|---|---|---|---|
| `test_targets` | `TestBoundaries::test_exactly_the_last_horizon_rows_are_null` | C2 | - | h+1 rows null (4 subtests) |
| `test_targets` | `TestBoundaries::test_over_long_horizon_yields_an_empty_feature_frame_not_an_error` | C2+C4 | - | all rows kept, none Train_Eligible, span 301; rename |
| `test_targets` | `TestBuildTargetContract::test_direction_is_a_classification_task` | C2 | - | third value == h+1; add REVIEW_019 R-10 test (span passed as horizon differs) |
| `test_targets` | `TestBuildTargetContract::test_return_is_a_regression_task` | C2 | - | third value == h+1; add REVIEW_019 R-10 test (span passed as horizon differs) |
| `test_targets` | `TestBuildTargetContract::test_the_returned_horizon_is_what_was_asked_for` | C2 | - | third value == h+1; add REVIEW_019 R-10 test (span passed as horizon differs) |
| `test_targets` | `TestDirectionLabel::test_dtype_is_nullable_so_the_tail_cannot_become_false` | C2 | - | tail is h+1 = 4 nulls |
| `test_targets` | `TestDirectionLabel::test_label_at_t_compares_against_close_at_t_plus_horizon` | C3 | - | re-derive from opens by hand; rename |
| `test_targets` | `TestEquivalenceWithLogisticBaseline::test_build_features_reproduces_the_baseline_frame` | D-2 | - | GATED: re-anchor per D-2 (lane G) |
| `test_targets` | `TestEquivalenceWithLogisticBaseline::test_direction_label_matches_the_baseline_label` | D-2 | - | GATED: re-anchor per D-2 (lane G) |
| `test_targets` | `TestForwardLogReturnLabel::test_non_positive_close_is_nan_not_negative_infinity` | C3 | - | zero an endpoint *Open*; rename |
| `test_targets` | `TestForwardLogReturnLabel::test_value_is_the_log_ratio_over_the_horizon` | C3 | - | log(Open[t+h+1]/Open[t+1]) by hand |
| `test_targets` | `TestGapCase::test_label_spans_rows_not_calendar_days` | C3 | - | positional property on opens; re-derive |
| `test_targets` | `TestValidation::test_missing_close_column_raises` | C3 | - | required column is Open: a frame without Open raises; rename |

#### Lane D (17)

| File | Test | First | Second | Change |
|---|---|---|---|---|
| `test_feature_scaling` | `TestCollinearity::test_no_scale_free_column_is_badly_collinear` | C4 | - | pass complete rows of the set explicitly (test helper); primitives now name non-finite input instead of failing in the SVD |
| `test_feature_scaling` | `TestCollinearity::test_the_two_ratios_have_acceptable_vif` | C4 | - | pass complete rows of the set explicitly (test helper); primitives now name non-finite input instead of failing in the SVD |
| `test_feature_scaling` | `TestCollinearity::test_the_worst_scale_free_pair_beats_the_worst_level_pair` | C4 | - | pass complete rows of the set explicitly (test helper); primitives now name non-finite input instead of failing in the SVD |
| `test_feature_scaling` | `TestConditioning::test_max_vif_drops` | C4 | - | pass complete rows of the set explicitly (test helper); primitives now name non-finite input instead of failing in the SVD |
| `test_feature_scaling` | `TestConditioning::test_standardizing_alone_does_not_fix_the_level_set` | C4 | - | pass complete rows of the set explicitly (test helper); primitives now name non-finite input instead of failing in the SVD |
| `test_feature_scaling` | `TestConditioning::test_the_scale_free_matrix_is_better_conditioned` | C4 | - | pass complete rows of the set explicitly (test helper); primitives now name non-finite input instead of failing in the SVD |
| `test_feature_scaling` | `TestNonFiniteGuard::test_a_level_run_keeps_those_rows` | C4 | - | control: rows eligible under levels, ineligible under scale_free |
| `test_feature_scaling` | `TestNonFiniteGuard::test_zero_volume_rows_are_dropped_rather_than_infinite` | C4 | - | assert NaN-not-inf + ineligible (FR-008); rename |
| `test_feature_scaling` | `TestRatioDefinitions::test_rel_volume_is_volume_over_its_trailing_mean` | C4 | - | compare on eligible rows of the full-calendar frame |
| `test_feature_scaling` | `TestRatioDefinitions::test_volume_window_is_configurable_and_defaults_to_long_window` | C4 | - | row counts are now equal; assert eligible counts differ |
| `test_feature_scaling` | `TestScaleReachesEveryFit::test_every_fit_receives_the_same_scale` | C2 | - | purge = embargo = returned span |
| `test_feature_scaling` | `TestScaleReachesEveryFit::test_the_default_reaches_every_fit_as_none` | C2 | - | purge = embargo = returned span |
| `test_feature_scaling` | `TestScalerIsFitOnTrainingRowsOnly::test_later_folds_see_different_statistics` | C4 | C2 | fit on train-eligible rows of each fold; splits sized by span; whole-frame control kept |
| `test_feature_scaling` | `TestScalerIsFitOnTrainingRowsOnly::test_scaler_statistics_are_the_training_slice_statistics` | C4 | C2 | fit on train-eligible rows of each fold; splits sized by span; whole-frame control kept |
| `test_feature_scaling` | `TestScalerIsFitOnTrainingRowsOnly::test_scaler_statistics_differ_from_the_whole_frame` | C4 | C2 | fit on train-eligible rows of each fold; splits sized by span; whole-frame control kept |
| `test_feature_scaling` | `TestScalingChangesTheAnswer::test_hgb_predictions_do_not_move` | C2 | - | purge = embargo = returned span |
| `test_feature_scaling` | `TestScalingChangesTheAnswer::test_ridge_predictions_move_when_the_scaler_is_applied` | C2 | - | purge = embargo = returned span |

#### Lane E (19)

| File | Test | First | Second | Change |
|---|---|---|---|---|
| `test_estimators` | `TestDeterminism::test_different_params_change_the_answer` | C2 | - | purge = embargo = returned span |
| `test_estimators` | `TestDeterminism::test_repeated_runs_agree` | C2 | - | purge = embargo = returned span |
| `test_estimators` | `TestGradientBoosting::test_hgb_classification_runs_and_predicts_labels` | C2 | - | purge = embargo = returned span |
| `test_estimators` | `TestGradientBoosting::test_hgb_regression_runs_and_differs_from_ridge` | C2 | - | purge = embargo = returned span |
| `test_estimators` | `TestOneFitPerFold::test_each_fold_sees_a_freshly_fitted_model` | C2 | - | purge = embargo = returned span |
| `test_estimators` | `TestRegressionPath::test_predictions_are_finite_floats_where_covered` | C2 | - | purge = embargo = returned span |
| `test_estimators` | `TestRegressionPath::test_rows_before_the_first_fold_are_null` | C2 | - | purge = embargo = returned span |
| `test_estimators` | `TestRegressionPath::test_task_and_horizon_come_through_from_build_features` | C2 | - | assert span == 2 for h=1; rename |
| `test_model_cv` | `TestDeterminism::test_repeated_nested_runs_agree` | C2 | - | purge = embargo = returned span |
| `test_model_cv` | `TestDeterminism::test_repeated_tuning_selects_the_same_candidate` | C2 | - | purge = embargo = returned span |
| `test_model_cv` | `TestEquivalenceWithLogisticBaseline::test_null_placement_matches_too` | D-2/C4 | - | GATED: re-anchor to `fit_predict_walk_forward` (D-2); fixture guard fits eligible rows (lane G) |
| `test_model_cv` | `TestEquivalenceWithLogisticBaseline::test_one_outer_fit_per_fold_on_top_of_the_tuning_fits` | C2 | D-2 | GATED with its class (lane G) |
| `test_model_cv` | `TestEquivalenceWithLogisticBaseline::test_single_point_grid_reproduces_the_baseline_element_for_element` | D-2/C4 | - | GATED: re-anchor to `fit_predict_walk_forward` (D-2); fixture guard fits eligible rows (lane G) |
| `test_model_cv` | `TestEquivalenceWithLogisticBaseline::test_the_fixture_discriminates_between_folds` | D-2/C4 | - | GATED: re-anchor to `fit_predict_walk_forward` (D-2); fixture guard fits eligible rows (lane G) |
| `test_model_cv` | `TestNestedWalkForward::test_regression_path_produces_finite_floats` | C2 | - | purge = embargo = returned span |
| `test_model_cv` | `TestSelectionActuallySelects::test_scores_differ_across_candidates` | C2 | - | purge = embargo = returned span |
| `test_model_cv` | `TestSelectionActuallySelects::test_the_winner_has_the_lowest_mean_inner_score` | C2 | - | purge = embargo = returned span |
| `test_model_cv` | `TestTuneOnFoldIsolation::test_selection_is_unchanged_by_corrupting_every_outside_row` | C2 | C4 | span; `_corrupted` flips only known labels (keeps the visibility control) |
| `test_model_cv` | `TestTuneOnFoldIsolation::test_the_corruption_would_be_visible_if_it_leaked` | C2 | C4 | span; `_corrupted` flips only known labels (keeps the visibility control) |

#### Residual — not 021 (21)

| File | Test | First error |
|---|---|---|
| `test_feature_set_comparison` | `TestParentSideThreadPinning::test_the_orchestrator_leaves_this_process_unpinned` | pandas.errors.IntCastingNaNError: Cannot convert non-finite values (NA or inf) t |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_discordant_counts_and_p_values_are_equal` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_formatted_reports_match_character_for_character` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_on_pair_reports_completed_comparisons_in_report_order` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_orchestrator_results_match_key_for_key_and_bit_for_bit` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_pairing_the_two_unit_sets_gives_identical_statistics` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_prediction_dtypes_and_index_survive_the_process_boundary` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_prediction_series_are_identical` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_result_order_is_the_registry_order_in_both_modes` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSerialParallelEquivalence::test_the_fr_007_alias_produces_the_same_results` | failed on setup with "pandas.errors.IntCastingNaNError: Cannot convert non-finit |
| `test_feature_set_comparison` | `TestSynchronousPathCreatesNoProcesses::test_no_executor_is_constructed` | pandas.errors.IntCastingNaNError: Cannot convert non-finite values (NA or inf) t |
| `test_feature_set_comparison` | `TestSynchronousPathCreatesNoProcesses::test_the_synchronous_path_runs_in_the_calling_process` | pandas.errors.IntCastingNaNError: Cannot convert non-finite values (NA or inf) t |
| `test_multi_ticker_comparison` | `TestAllSucceed::test_every_ticker_produces_exactly_three_rows` | AssertionError: Lists differ: [ComparisonFailure(ticker='A', reason='fun[149 cha |
| `test_multi_ticker_comparison` | `TestCostParameterConsistency::test_commission_and_slippage_match_across_tickers_and_strategies` | AssertionError: Lists differ: [ComparisonFailure(ticker='A', reason='fun[149 cha |
| `test_multi_ticker_comparison` | `TestCostParameterConsistency::test_isolated_failure_still_matches_costs_for_completed_tickers` | KeyError: 'commission_per_trade' |
| `test_multi_ticker_comparison` | `TestCsvRoundTrip::test_round_trip_preserves_shape` | AssertionError: Lists differ: [ComparisonFailure(ticker='A', reason='fun[149 cha |
| `test_multi_ticker_comparison` | `TestHonestyColumns::test_baseline_rows_carry_nan_for_the_ml_only_columns` | KeyError: 'Strategy' |
| `test_multi_ticker_comparison` | `TestHonestyColumns::test_ml_row_carries_hurdle_and_prediction_columns_and_fold_geometry` | AssertionError: Lists differ: [ComparisonFailure(ticker='A', reason='fun[51 char |
| `test_multi_ticker_comparison` | `TestIsolatedFailure::test_the_short_ticker_fails_by_name_and_the_others_complete` | AssertionError: Lists differ: ['GOOD1', 'BAD', 'GOOD2'] != ['BAD'] |
| `test_multi_ticker_comparison` | `TestMutations::test_dropping_a_baseline_is_caught_by_the_strategy_set_assertion` | AssertionError: Lists differ: [ComparisonFailure(ticker='A', reason='fun[51 char |
| `test_reports_api` | `TestReportsApi::test_backtest_tearsheet` | ValueError: funded ledger requires declared unadjusted dollar prices |

**How the residual fails, and why it stays residual.**

- **`feature_set_comparison.py` (12).** `compare_classification` runs
  `labels.astype(int)` at `:367` over covered rows. Under C4 those rows include
  the final `h+1` sessions, whose labels are unknown. The cast is in the frozen
  production file, and no test-side change fixes it without hiding it.
- **`multi_ticker_comparison.py` (8).** The first error is 020's
  "funded ledger requires declared unadjusted dollar prices", caused by
  `download_market_data` at `:230`. Behind it, `run_backtest` has no capital at
  `:133`, `:141` and `:269`, all in the frozen file. The test fixture could
  declare `price_basis`, and the next error would still be in the frozen file.
- **`test_backtest_tearsheet` (1).** Owned by spec 018 T024 (`018/tasks.md:95`).

---

## R-2 — Probes: how the second layer was found

**Decision.** Second-layer failures were found with scratch-only pytest plugins
that changed one library default in memory, for one process. The repository
was never edited.

| Probe | Changes, in process only | Files run | Result |
|---|---|---|---|
| A | `run_backtest` `starting_capital` default = 1e6 | the 6 files that consume the harness | 33 failed / 110 passed |
| B | A, plus `liquidate` default = True | same | 25 failed / 118 passed |
| S | `model_row_masks` lifts purge and embargo to the frame's declared span | `test_estimators`, `test_feature_scaling`, `test_model_cv` | 47 failed / 104 passed |

**What each probe showed.**

- **A → B, 8 tests turn green.** These fail on C5 alone:
  - `test_backtest_harness` ×2;
  - `test_metrics` ×4;
  - `test_ma_crossover_backtest::test_buy_and_hold_holds_exactly_one_position`;
  - `test_signals::test_the_harness_closes_the_position_at_the_final_close`.
- **Still failing under B** are the C5 policy-layer tests in `ml_signal`, C6
  (price basis, non-positive prices, empty frame), C7, the capital-base test,
  the `RangeIndex` test, and three `random_signal` tests.
- **The `random_signal` root cause** was reproduced directly on the sawtooth
  fixture: `baseline_results` returned `random_error = "conflicting buy and
  sell signals"` and zero summaries.
- **Probe S** separated pure-C2 tests, which pass once the span is lifted, from
  C2 + C4 tests (`TestTuneOnFoldIsolation._corrupted` casts `<NA>`) and from
  tests that pass the span as purge but keep `embargo_bars=1`. `walk_forward_splits`
  rejects that last group itself.

**Hidden-vacuity scan.** Probe A was also run over the whole suite, minus the
slow frozen `test_feature_set_comparison.py`. The question was which tests
pass today only *because* capital is missing, since the capital error is a
`ValueError` and could satisfy an `assertRaises(ValueError)` meant for
something else.

Result: exactly one test newly fails under the probe,
`test_019_conventions.py::test_capital_must_be_chosen_before_the_first_open`.
That is the C1 gate itself failing because the probe removed what it guards,
which is the correct outcome. **No test in the current tree passes by
accident on the capital error.**

Migrated tests that assert a `ValueError` still pin the message with
`assertRaisesRegex`, so the 019 errors (capital, basis, empty frame) cannot
satisfy them in the future. See tasks T013, T016, T018 and T027(d).

**Why probes rather than trusting first errors.** 47 tests stop at "starting_capital
is required". A first-error triage would size lane A as 47 one-line edits. The
probes show 11 of them need a semantic decision (C5, C7, capital base, index).
That changes the lane's review profile, not only its line count.

---

## R-3 — Absorb or defer the rename (D-1)

**Decision.** Defer to a follow-on spec, proposed `022-purge-span-rename`.

**Rationale.**

1. **The rename can't be done without touching frozen files.** Both frozen
   files call `build_features(label_horizon=)` and
   `nested_walk_forward(label_horizon=)`:
   `feature_set_comparison.py:153-172` and `multi_ticker_comparison.py:234-250`.
   A hard rename breaks them. A dual-keyword shim adds library surface to
   modules 019 declared done, and then needs its own removal later.
2. **The name means two things.** `build_features(label_horizon=)` is the
   forecast horizon `h`, and a correct call passes `1`.
   `walk_forward_splits(label_horizon=)`, `inner_splits_over`, `tune_on_fold`,
   `nested_walk_forward` and `fit_predict_walk_forward` use the same name for
   the purge width, which after 019 is `h+1`. One rename cannot fix both.
   - The first becomes `horizon=`, matching `targets.build_target(horizon=)`.
   - The second becomes `purge_bars=`, or `label_availability_span=`, which is
     019's own term.
   - Choosing between those names is the follow-on's first decision.
3. **Keeping value changes and name changes in different PRs is what makes
   either one explainable (Rule 9).** In 021, a line like
   `label_horizon=1, embargo_bars=1` → `label_horizon=span, embargo_bars=span`
   is a value change that a reviewer must check against the label. In the
   follow-on, `label_horizon=span` → `purge_bars=span` is a pure rename that a
   reviewer can skim. Doing both at once turns every line into both.

**Mitigation, so deferring costs nothing.** FR-003 and FR-004: every migrated
call site passes a *variable* holding the span. After 021 the rename is purely
mechanical. `grep -n "label_horizon=[0-9]"` over the migrated files returns
only exempted splitter hunks (SC-002).

**Alternatives considered.**

- *Absorb the rename in 021, shim included.* Rejected: it edits five library
  modules and both frozen call paths, and it pushes lanes A–E past the 400-line
  budget.
- *Absorb only the `attrs` key cleanup,* that is, remove the
  `frame.attrs.get("label_horizon", …)` fallbacks. Rejected: two of the three
  fallbacks are in the frozen files, and the third (`estimators.py:278`) is
  library.

**What the follow-on inherits.**

- The two renames above, and the guard's error message.
- The three legacy `attrs` fallbacks.
- The library docstrings (`targets.py:11-18`, `features.py:125-129`,
  `walk_forward_cv.py:32-50`, `model_cv.py`).
- `walk_forward_cv.main()`'s `label_horizon=1, embargo_bars=1` demo.
- Making `model_row_masks` unbypassable for frames without the span in `attrs`
  (spec: Flagged, not fixed, item 1).
- `logistic_baseline.py:65,:149`, depending on how D-2 is decided.

---

## R-4 — The `random_signal` fix (FR-011)

**Decision.** Space consecutive trips so that entry *i+1* comes at least one
row after exit *i*.

- **Spacing.** `spread = avg_holding_days` instead of `avg_holding_days - 1`
  (`signals.py:126`).
- **Capacity bound.** With first entry row 1 and trips of length *h* separated
  by one-row gaps, trip *k* exits at row `1 + (k-1)(h+1) + h`. That must be
  ≤ `n-1`, so `n ≥ n_trades·(h+1) + 1`. The error message quotes that figure;
  the old one quoted `n_trades·h + 2`.
- **Preserved.**
  - the exact trade count;
  - the exact holding length;
  - non-overlap;
  - seeded determinism (`default_rng(seed)`);
  - the `n_trades == 0` early return;
  - the named infeasibility error.
- **Worked check, 30-row infeasibility fixture** (4 trips × 10 bars): it needs
  45 rows under the new bound and had needed 42 under the old one. It stays
  infeasible, so `test_an_infeasible_random_baseline_*` keeps its meaning.

**Rationale.**

- 019's harness rejects a row carrying both signals (`backtest_harness.py:63-64`),
  and 021 edits no library module.
- A same-open sell-then-buy is also economically empty: two fills, two
  commissions, two slippage charges, and no change in position. The old
  behavior was a cost artifact, not a baseline.
- The signal layer owns "when to trade" (CLAUDE.md module table), so the fix
  belongs there (Rule 8).

**Rule 5 tests, which must ship in the same PR.**

- *Off-by-one.* For every seed in a sweep, no row has both flags, and every
  entry after the first is at least *h + 1* rows after the previous entry.
- *Boundary.* The first entry is ≥ row 1. The last exit is ≤ row `n-1`. A frame
  of exactly `n_trades·(h+1)+1` rows is feasible; one row fewer raises.
- *Gap case.* The function is positional, so calendar gaps do not enter it. A
  business-day frame with a holiday hole gives row-identical signals to a
  frame without the hole but with the same row count.

**Rule 12 red evidence.** Plant `spread = avg_holding_days - 1` in a copy. The
off-by-one test must fail, naming the row with both flags. The unmutated
control must pass.

**Alternatives considered.**

- *Change the harness to allow sell-then-buy on one row.* Rejected: it is a
  library change, and it reopens a 019 decision.
- *Drop the conflicting trips and redraw.* Rejected: it loses the determinism
  contract and complicates the capacity reasoning.
- *Keep the old spacing and filter same-row pairs.* Rejected: that changes the
  trade count, which breaks frequency matching (Rule 4).

**Downstream effect on frozen code, stated rather than hidden.**
`multi_ticker_comparison._baseline_rows` imports `random_signal`. Its random
baseline will stop failing for this reason, without the frozen file changing.
Its tests stay red because of the capital and 020 issues (R-1, Residual).

---

## R-5 — End-of-data policy in reports (D-3)

**Decision.** `liquidate=True` explicitly, the same on all three rows. The
report says so once.

**Rationale.**

- `run_backtest(liquidate=True)` sells at the final session's close, charging
  commission and slippage, and records a distinct `liquidation` ledger event
  (`backtest_harness.py:90-104`, `:143-144`).
- Before 019, reports closed the position at the end-of-data close with costs
  applied. `test_costs_apply_to_the_end_of_data_close_exit` asserted exactly
  that. So the closed-trade numbers keep their meaning, and the terminal exit
  becomes visible.
- `mean_holding_bars` maps the liquidation's `Exit Date`, which is a real
  session, so it needs no change.

**Alternatives considered.**

- *Mark-only, with P&L columns from ledger equity (`performance_summary`).*
  More faithful to 019's "end of batch is not an exit", but it changes report
  columns. It belongs with 018 T029, which already owns report-figure honesty,
  or with work order 3.
- *Mark-only, keeping `summarize_trades`.* Rejected: buy-and-hold becomes 0
  trades and $0, which is a silently broken Rule 4 baseline.

---

## R-6 — Starting capital (D-4)

**Decision.**

- **Production.** `STARTING_CAPITAL = 10_000.0` beside the cost model in
  `ma_crossover_backtest.py`, restated in `logistic_baseline.py` the way that
  file restates its cost model (`logistic_baseline.py:26-31`). It is printed
  in the report header as an assumption. **Camden sets the final value.**
  `10_000.0` is a proposal.
- **Tests.** One constant per test module, for example
  `STARTING_CAPITAL = 1_000_000.0`. It must be large enough that no fixture's
  entry is rejected unless the test is about rejection.

**Rationale.**

- No capital constant exists anywhere in the repository today; checked with a
  grep for `CAPITAL` over `scripts/`. So there is nothing to reuse.
- At one share, capital changes no closed-trade P&L. It changes
  capital-relative metrics (`total_return`, equity log returns, drawdown %),
  and that is why it is declared and printed, like commission.
- Tests that assert equity use the constant symbolically, never a literal
  (FR-002).
- `test_metrics.py:230` passes `100.0` on purpose, for its drawdown arithmetic.
  It keeps `100.0`, and `run_backtest` gets the same `100.0`.

**Alternatives considered.**

- *`constants.STARTING_CAPITAL`.* `constants.py` holds *comparison*
  denominators (`constants.py:1-11`), and capital is arguably one. Rejected
  for 021 because it would add a fifth production file and an import into a
  module that is deliberately importless. The follow-on can promote it if
  cross-script return comparisons are ever made.
- *A default in the harness.* Forbidden by 019.

---

## R-7 — Diagnostics on a full-calendar frame (FR-007)

**Decision.**

1. **The primitives refuse non-finite input.** `standardized_matrix` raises a
   `ValueError` that names the columns and the count of non-finite rows. It
   also says: pass the set's complete rows. The three measures built on it
   (`condition_number`, `variance_inflation_factors`,
   `max_abs_offdiagonal_correlation` / `correlation_frame`) inherit the
   refusal. Today they die in LAPACK ("SVD did not converge") or return `nan`.
2. **`diagnose(frame, feature_set)`** restricts to rows where the set's columns
   are all finite. It reports `rows` (used) and a new `rows_excluded`.
   `format_report` prints both.
3. **Tests** in `test_feature_scaling.py` pass complete rows through one local
   helper.

**Rationale.**

- A silent row drop inside a primitive would hide how much of the frame a
  number describes.
- The one production caller that could forget, `routes/diagnostics.py:50-51`,
  already filters (018 T008), so its behavior does not change.
- `diagnose` is the entry point that knows the set, so it is the right place
  to mask and count.

**Rule 12.** The primitive's refusal is a new gate. Red: feed one NaN row and
assert the named error. Control: complete rows measure without error.

**Alternatives considered.**

- *Mask inside `standardized_matrix`.* Rejected: it is silent, and it
  duplicates the route's filter.
- *Mask only in `diagnose`.* Rejected: the six failing tests call the
  primitives directly (`test_feature_scaling.py:44-48`), so they would stay red.

---

## R-8 — Re-anchoring the `logistic_baseline` equivalence (D-2, gated)

**Decision.**

- **`test_targets.py`.**
  - The level-feature equivalence (five columns, rows matched by `Date`) is
    kept.
  - `test_direction_label_matches_the_baseline_label` becomes
    `test_label_divergence_from_the_pre_019_control_is_exactly_the_open_basis`.
    It uses a hand-worked frame where `Close[t+1] > Close[t]` but
    `Open[t+2] < Open[t+1]`, and asserts the two labels disagree on that row
    and nowhere the arithmetic says they should agree.
  - `test_build_features_reproduces_the_baseline_frame` becomes
    `test_baseline_rows_are_a_date_subset_of_the_full_calendar_frame`. The
    shared level columns must be equal on those rows.
- **`test_model_cv.py`.**
  - The reference moves from `logistic_baseline.walk_forward_predictions` to
    `estimators.fit_predict_walk_forward`. Same frame (`levels`, `scale=False`),
    grid point `C = 1.0`, and span-sized purge and embargo.
  - `test_the_fixture_discriminates_between_folds` fits train-eligible rows.
  - `test_one_outer_fit_per_fold_on_top_of_the_tuning_fits` uses the span.

**Rationale.** The property spec 011 T015 cares about is "tuning is the only
source of divergence", and it is fully preserved against the in-contract
untuned loop. The link from the untuned loop to the control survives in
`test_estimators.py:212` (`test_matches_logistic_baseline_element_for_element`),
which runs on label-agnostic synthetic frames and passes today. The chain to
the committed control is re-routed, not cut.

**Why this needs sign-off.** It retires spec 009 SC-001/SC-002 as written (the
label and frame equivalence) and replaces them with a pinned divergence.
`DIAGNOSIS_HORIZON_OFFBYONE.md` already recorded this as Camden's call.

**Alternative considered.** Migrate `logistic_baseline.py` to 019. That moves
the committed Phase 2 control. It needs its own spec with Rule 4 baselines and
Rule 11 regeneration of the AAPL figures in `PROJECT_CONTEXT.md` (`:441-446`).

---

## R-9 — Exemptions from FR-003 and FR-004

**Decision.** Literal purge and embargo values stay legal in two places. Each
exempt hunk carries a one-line comment saying why.

1. **Splitter unit tests on label-free frames** (`test_walk_forward_cv.py`,
   which is not failing and not edited). They test the splitter's arithmetic
   for a given width, not a label.
2. **Tests on `_synthetic_features`** (`test_logistic_baseline.py:19-35`). Its
   `Label` is alternating integers, not a function of prices, so it has no
   horizon. Those tests pass today and are not edited.

**Not exempt:** `test_ml_signal.py::EstimatorAgnosticTests`. It builds real
`direction_label` and `forward_log_return_label` targets with `horizon=1`, so
it must take the span from `build_target` (FR-004).

---

## R-10 — Gates touched, and their red evidence (Rule 12)

| Gate (test) | Field the gate reads | Planted defect (in a copy, never committed) | Control |
|---|---|---|---|
| `TestOffByOne` pair (`test_targets.py:214-280`) | `Open` | Already re-armed. **Do not regress.** Lane C re-runs `TestOffByOneGuardsFireOnARealBug` | Unmutated `targets.py` passes |
| `TestScalerIsFitOnTrainingRowsOnly` | scaler `mean_` / `scale_` of train-eligible rows | Fit the scaler on the whole frame | Per-fold fit passes. `…_differ_from_the_whole_frame` stays as the internal control |
| `TestTuneOnFoldIsolation` | labels and features outside `outer_train_indices` | Let `inner_splits_over` see one outside row | `…_would_be_visible_if_it_leaked` stays green |
| `TestNonFiniteGuard` | `Rel_Volume` on zero-volume rows | Stop the ±inf → NaN replacement (`features.py:174-175`) | `levels` keeps the rows eligible |
| `feature_diagnostics` non-finite refusal (new) | `standardized_matrix` input | Feed one NaN row | Complete rows measure |
| `random_signal` same-row guard (new) | `Buy_Next_Open` & `Sell_Next_Open` per row | `spread = h - 1` | Unmutated passes |
| Random-baseline count guard (FR-012) | `len(random_summaries)` | Make `random_signal` raise for every seed | Unmutated gives 20 |
| `test_cost_parameters_are_stated_once_not_per_row` (extended) | report text | Print capital or policy per row | Unmutated has exactly one of each |

Red evidence follows the 019 plan's method: mutate a source copy in memory,
patch temporarily, run the unmutated control, and never overwrite shared
source. `tests/mutation_support_019.py` already provides `killed(...)` for this.

---

## R-11 — Shared fixtures and shared modules (the parallel-lane hazard)

**Decision.** For the whole of 021, each shared fixture's signature and output
are frozen (FR-020). Fixes go at call sites. So lanes that import another
lane's fixture never need to wait for it.

| Fixture (owner lane) | Region | Imported by |
|---|---|---|
| `test_backtest_harness.make_signalled_prices` (A) | `:11-26` | `test_metrics.py:26` (A) |
| `test_ma_crossover_backtest.COSTS`, `make_prices`, `sawtooth_prices` (B) | `:22-42` | `test_metrics.py:27` (A); `test_targets.py:30` (C) |
| `test_logistic_baseline._synthetic_features` (B) | `:19-35` | `test_estimators.py:26`, `test_model_cv.py:37` (E) |

| Shared production module (owner lane) | Region owned | Read by other lanes |
|---|---|---|
| `scripts/logistic_baseline.py` (B) | `main()` (`:297-347`), `_format_ml_comparison` (`:229-294`), cost constants (`:26-33`) | `build_features`, `walk_forward_predictions` and `FEATURE_COLUMNS` are read by E, G and C. **Frozen.** |
| `scripts/ma_crossover_backtest.py` (B) | whole file | `baseline_results` / `mean_holding_bars` are imported by `routes/backtest.py` (018 T024) and `multi_ticker_comparison.py` (frozen). The interface is fixed in [contracts/consumer-interfaces.md](contracts/consumer-interfaces.md). |
| `scripts/signals.py` (B) | `random_signal`, `buy_and_hold_signal` docstring | `multi_ticker_comparison.py` (frozen) imports `random_signal` |
| `scripts/feature_diagnostics.py` (D) | whole file | `routes/diagnostics.py` imports `diagnose` |

**Why a fixture change would break a parallel lane silently.**
`test_targets.py` re-derives label expectations from `make_prices`'s
`Open = Close + 1` relation. If lane B changed that fixture, lane C's
hand-derived numbers would go wrong without any merge conflict. The freeze is
what makes the lanes independent. It is a real constraint, not a convenience.

---

## R-12 — Concurrent lane (D-6)

**Decision.** Lane A starts after the cost_utils lane lands.

**Observed.** Files changed at 16:29:52–16:30:39 EDT:

- new: `scripts/cost_utils.py`, `tests/test_cost_utils.py`,
  `tests/test_return_stats.py`;
- modified: `scripts/metrics.py`, `scripts/ml_signal.py`,
  `scripts/return_stats.py`, `tests/test_019_conventions.py`,
  `tests/test_metrics.py`, `tests/test_ml_signal.py`.

Its content does not overlap 019's migration. It moves `validate_costs` and
`risk_free_log_return`, and adds Sharpe regression coverage. Its *files*
overlap lane A in two places: `test_metrics.py` and `test_ml_signal.py`.

**Also noted.** `backtest_harness.py:6` still imports `validate_costs` from
`metrics`, so that lane may not be finished. 021 edits neither
`backtest_harness.py` nor `metrics.py` either way.

**Alternative considered.** Have lane A edit around the other lane's hunks.
Rejected: two uncommitted edit streams in one file cannot be reviewed as
separate PRs without `git` operations that agents may not run.
