---
description: "Task list for spec 021: finish the spec 019 migration (consumer side)"
---

# Tasks: Finish the Spec 019 Migration (Consumer Side)

**Input**: [spec.md](spec.md) · [plan.md](plan.md) · [research.md](research.md)
(R-1 is the per-test inventory) · [contracts/consumer-interfaces.md](contracts/consumer-interfaces.md) ·
[data-model.md](data-model.md) · [quickstart.md](quickstart.md)

**Tests**: Required. This spec *is* a test migration, and Rules 5 and 12
demand new tests for the two new gates. Where a task adds a gate, the test is
written first and shown failing on the current code.

**Organization: lanes, not stories.** You asked that implementation run in
parallel lanes where no two agents touch the same file. User stories cut
across files: one test file carries both US1 and US2 work. So phases here are
**lanes, one PR each**, and every task carries the `[USn]` story it serves.
The story view is rebuilt in [Story → task map](#story--task-map).

**Rules for every task.**

- **No `git`** (Rule 10). Camden commits.
- Edit **only** the files your lane owns (plan.md → Lanes).
- **Never** edit a frozen fixture region, frozen function, library module,
  frozen production file, `routes/backtest.py`, `requirements*.txt` or
  `docs/PROJECT_CONTEXT.md` (FR-019, FR-020).
- Expected values are **derived by hand**, with the arithmetic in a comment.
  Never paste a value printed by the code under test (FR-005).
- Line counts use `diff -u` against the lane snapshot from T003.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel with the other tasks in its phase. That means a
  different file and no dependency on an unfinished task.
- **[USn]**: the user story in spec.md that the task serves.
- **Lanes A–E never share a file**, so any two lanes' tasks can run in
  parallel once their preconditions hold.

---

## Phase 1: Setup (shared, before any lane)

- [ ] T001 Re-baseline the suite, following quickstart.md §1: `python -m pytest tests -q --tb=no --junitxml=<scratch>/baseline.xml`. Extract the unique failing test IDs and diff them against research.md R-1, which lists 128 IDs. Record in [Evidence → T001](#t001-re-baseline):
  - the summary line;
  - the unique-failure count;
  - every ID added or removed, with the cause.

  An ID not in R-1 is *not* 021's to fix. Record it and name the lane or spec that introduced it.
- [ ] T002 Record four preconditions in [Evidence → T002](#t002-preconditions):
  - **(a) The concurrent cost_utils lane has landed or been abandoned.** Ask Camden; do not infer it. `scripts/backtest_harness.py:6` still importing `validate_costs` from `metrics` suggests that lane is unfinished. **Lane A is blocked until (a) holds.**
  - **(b) D-2's sign-off status** in spec.md. **Lane G is blocked until it is signed.**
  - **(c) D-3 and D-4** accepted as written, or amended in spec.md. **Lane B is blocked until one of those holds.**
  - **(d) Spec 018 T024's state** (open or not). This matters because of the shared `tests/test_reports_api.py`.
- [ ] T003 [P] For each lane about to start, copy every file it owns (plan.md → Lanes) to `<scratch>/snap-<lane>/`, keeping relative paths. Do this before the lane's first edit (quickstart.md §2). Lane G snapshots only after PR-C and PR-E merge.
- [ ] T004 [P] Write a scratch-only fingerprint script (never in the repository) and record its output in [Evidence → T004](#t004-frozen-fingerprints). It takes the SHA-256 of two kinds of thing:
  - **(i) The exact source text of every frozen region**, obtained with `ast.get_source_segment`:
    - `tests/test_backtest_harness.py::make_signalled_prices`;
    - `tests/test_ma_crossover_backtest.py::{COSTS, make_prices, sawtooth_prices}`;
    - `tests/test_logistic_baseline.py::_synthetic_features`;
    - `scripts/logistic_baseline.py::{FEATURE_COLUMNS, SHORT_WINDOW, LONG_WINDOW, VOLATILITY_WINDOW, build_features, evaluate_walk_forward, walk_forward_predictions, _signal_from_predictions, build_ml_signal}`.
  - **(ii) Whole files:**
    - `scripts/{backtest_harness,targets,features,estimators,model_cv,walk_forward_cv,metrics,ml_signal,feature_set_comparison,multi_ticker_comparison}.py`;
    - `reports/api/routes/backtest.py`;
    - `requirements.txt` and `requirements-dev.txt`;
    - `docs/PROJECT_CONTEXT.md`.

  Take `metrics.py` and `ml_signal.py` *after* T002(a) holds.

---

## Phase 2: Foundational (conventions every lane applies; no code)

**No shared helper module is created.** A helper imported by several test
files would be a file that no lane owns, which is exactly the conflict this
plan avoids. Each lane applies these conventions locally instead.

- **Capital.** Each test module declares one constant, for example `STARTING_CAPITAL = 1_000_000.0`, with a comment citing 019 C1 and D-4. It is large enough that no entry is rejected unless rejection is the test's subject. Assertions on equity use the constant, never a literal.
- **End of data.** Every test that touches end-of-data behavior says in its docstring whether it asserts *mark-only* (019 default) or *terminal liquidation* (`liquidate=True`), and why (FR-009).
- **Span.** Purge and embargo come from a variable holding the span: `build_features(...)[2]`, `build_target(...)[2]` or `frame.attrs["label_availability_span"]` (FR-003, FR-004). The exemptions are in research.md R-9, and each exempt edited hunk carries a one-line comment.
- **Error pins.** A migrated test that asserts a `ValueError` uses `assertRaisesRegex`/`pytest.raises(match=...)`, so no 019 error (capital, basis, empty frame) can satisfy it by accident (research.md R-2).
- **Renames.** A test whose *name* asserts pre-019 behavior is renamed to the property it now checks, and its docstring says what changed in 019. No test is deleted without a named replacement in the same PR (SC-006).
- **Evidence.** Red evidence follows research.md R-10: plant the defect in memory with `tests/mutation_support_019.killed(...)`, which the 019 precedent uses. Never write a mutant to disk. Always run the unmutated control.

**Checkpoint**: once T001–T004 are recorded, lanes whose preconditions hold may start.

---

## Phase 3: Lane B, accounting consumers (PR-B) · User Story 3 (P2)

**Goal.** The Phase 0 comparison has three real rows:

- the strategy, buy-and-hold, and a random baseline that runs for every seed;
- identical capital, costs and end-of-data policy on all three;
- each of those stated once in the report.

**Independent test.** `python -m pytest tests/test_signals.py tests/test_ma_crossover_backtest.py tests/test_logistic_baseline.py`
passes, and SC-004 holds (quickstart.md §4).

**Owns.**

- `scripts/signals.py`;
- `scripts/ma_crossover_backtest.py`;
- `scripts/logistic_baseline.py`, reporting hunks only: `main()`, `_format_ml_comparison` and the cost-model constants at `:26-33`;
- `tests/test_signals.py`;
- `tests/test_ma_crossover_backtest.py`, except `:22-42`;
- `tests/test_logistic_baseline.py`, except `:19-35`.

**Precondition:** T002(c).

### New gate first (Rules 5 and 12)

- [ ] T005 [P] [US3] In `tests/test_signals.py`, add a class `RandomSignalSpacingTests` with the three tests research.md R-4 describes. Build frames with the file's local `make_prices` over **strictly positive** closes (`range(1, n + 1)`). All three are row-positional.
  - **`test_no_row_carries_both_flags_for_any_seed`**:
    - a 200-row frame, `n_trades=8`, `avg_holding_days=10`, seeds 0–49;
    - assert `not (Buy_Next_Open & Sell_Next_Open).any()`;
    - assert consecutive entry rows differ by ≥ 11.
  - **`test_the_tightest_feasible_frame_is_accepted_and_one_row_less_raises`**:
    - with `n = n_trades*(avg_holding_days+1)+1`, the call succeeds, the first entry row is ≥ 1, and the last exit row is ≤ `n-1`;
    - with `n-1` it raises `ValueError`, and the message contains the number `n`.
  - **`test_calendar_holes_do_not_move_row_positions`**: two frames with the same row count, one with a missing business day, give identical signal columns.

  Run the class on the **current** `scripts/signals.py`. The first two tests must FAIL. Paste both failures into [Evidence → PR-B](#pr-b-lane-b).
- [ ] T006 [US3] In `scripts/signals.py::random_signal`, implement contracts §3, G4 and G7. Keep everything else as it is.
  - **Change:**
    - `spread = avg_holding_days` (was `avg_holding_days - 1`, at `:126`);
    - the capacity check;
    - the error message now names the bound `n_trades*(avg_holding_days+1)+1`;
    - the docstring explains the one-row gap: the 019 harness rejects a row with both flags, and a same-open sell-then-buy is two costed fills with no position change.
  - **Keep:** the signature, determinism, `n_trades == 0`, and exact `bool` dtype.
  - **Then:** T005 passes, and the existing `RandomSignalTests` determinism and seed tests still pass.
- [ ] T007 [US4] Red evidence for T005. Use `mutation_support_019.killed(signals, 'spread = avg_holding_days', 'spread = avg_holding_days - 1', <test_no_row_carries_both_flags_for_any_seed>)`. The mutant must be killed and the control must pass. Record in [Evidence → PR-B](#pr-b-lane-b).
- [ ] T008 [US5] In `scripts/signals.py::buy_and_hold_signal`, fix the docstring at `:47-53`. The harness *marks* a still-open position at the final close. A closed round trip exists only when the accounting caller passes `liquidate=True` (019 C5). Keep the rationale for emitting no exit signal. Depends on T006, same file.

### Production: the report consumers

- [ ] T009 [P] [US3] In `scripts/ma_crossover_backtest.py`, implement contracts §1 and §2.
  - **Constants, beside the cost model (`:20-24`):**
    - `STARTING_CAPITAL = 10_000.0`, commented as a D-4 *assumption* whose value Camden sets;
    - `LIQUIDATE_AT_END = True`, commented with D-3's reason.
  - **`baseline_results`:** gains required keyword-only `starting_capital` and `liquidate`, forwarded to both `run_backtest` calls (`:81`, `:92`).
  - **`main()`:** passes both to `run_backtest` (`:186`) and to `baseline_results` (`:206-212`).
  - **`format_comparison`:** prints capital once and the end-of-data policy once, inside the cost-model block, read from the same module constants.
  - Do not change `mean_holding_bars`.
- [ ] T010 [US3] In `scripts/logistic_baseline.py`, reporting hunks only:
  - restate `STARTING_CAPITAL` and `LIQUIDATE_AT_END` in the cost-model block (`:26-33`), with the same restatement comment the block already carries;
  - `main()` passes both to `run_backtest` (`:314`) and to `baseline_results` (`:334-340`);
  - `_format_ml_comparison` states both once in its cost block.
  - **Do not** touch any function T004 fingerprinted.

  Depends on T009, because it uses the new `baseline_results` signature.

### Tests

- [ ] T011 [US3] In `tests/test_ma_crossover_backtest.py`, outside `:22-42`:
  - Add module constants `STARTING_CAPITAL = 1_000_000.0` and `LIQUIDATE = True`, commented.
  - Pass them to every `run_backtest` call (`:54`, `:109`, `:158`) and every `baseline_results` call (7).
  - In `test_holding_period_is_counted_in_rows_not_calendar_days`, use closes `range(1, 11)` at the call site. The expected value is still 5: entry row 1, exit row 6.
  - In `test_buy_and_hold_holds_exactly_one_position`, say in the docstring that the 1 comes from D-3's terminal liquidation.
  - **FR-012:** `test_the_random_baseline_matches_the_strategys_trade_count` and `test_seeds_produce_a_spread_rather_than_one_repeated_number` must `assertEqual(len(results["random_summaries"]), 20)` *before* looping.
  - Extend `test_cost_parameters_are_stated_once_not_per_row` so the capital line and the end-of-data line each appear exactly once.

  Depends on T006 and T009.
- [ ] T012 [US4] Red evidence, recorded in [Evidence → PR-B](#pr-b-lane-b):
  - **(a) Count guard.** Mutant: in `ma_crossover_backtest.baseline_results`, replace `random_signal(prices, n_trades, holding_bars, seed)` with `random_signal(prices, n_trades, len(prices), seed)`. Every seed then becomes infeasible. The FR-012 test must fail on the count, and the control must pass.
  - **(b) Stated once.** Mutant: duplicate the capital line in `format_comparison`. The extended test must fail.
- [ ] T013 [US3] In `tests/test_signals.py`, after T005:
  - Add a module `STARTING_CAPITAL` constant and pass it on every `run_backtest` call.
  - `RandomSignalTests.price_frame` uses `range(1, n_bars + 1)`.
  - Rename `test_the_harness_closes_the_position_at_the_final_close` to `test_liquidation_closes_the_position_at_the_final_close` and pass `liquidate=True`. The hand-derived values: entry fill 120.0, exit fill 40.0, with Open = Close + 100 and zero costs.
  - Add `test_without_liquidation_the_position_is_marked_not_closed`: the trade log is empty, and the ledger's last `mark` event has `Quantity == 1` and `Price == 40.0`.
  - Rename `test_an_empty_frame_produces_no_trade_rather_than_crashing` to `test_an_empty_frame_yields_no_entry_and_the_harness_refuses_it`. Assert no entry signal, and `assertRaisesRegex(ValueError, "nonempty")`.
  - Fix the comment at `:98-99`.
- [ ] T014 [P] [US3] In `tests/test_logistic_baseline.py`, `TestBuildMlSignalEndToEnd` (`:139`) passes `starting_capital` and `liquidate`. Do not touch `:19-35`.
- [ ] T015 [US3] **PR-B close-out.**
  - Run quickstart.md §3 for lane B, which must be green.
  - Run the full suite (quickstart.md §5). The failing IDs must be the T001 baseline minus lane B's 17 R-1 rows, and nothing new.
  - The T004 fingerprints must be unchanged.
  - Line count ≤ 400.
  - Draft the PR description from plan.md's template. It must state:
    - the one-row gap in `random_signal`, and that no baseline figure is quoted;
    - that the frozen `multi_ticker_comparison.py` inherits G4 through its import;
    - the D-3 and D-4 values.

**Checkpoint**: SC-004 holds. US3 is independently verifiable.

---

## Phase 4: Lane A, ledger tests (PR-A) · User Story 1 (P1)

**Goal.** Every harness, metrics and policy-layer test reflects C1, C5, C6
and C7.

**Independent test.** `python -m pytest tests/test_backtest_harness.py tests/test_metrics.py tests/test_ml_signal.py` passes.

**Owns.**

- `tests/test_backtest_harness.py`, except `:11-26`;
- `tests/test_metrics.py`;
- `tests/test_ml_signal.py`.

**Precondition:** T002(a). **Can run in parallel with B, C, D and E.**

- [ ] T016 [P] [US1] In `tests/test_backtest_harness.py`:
  - Add a module `STARTING_CAPITAL` and pass it on every `run_backtest` call.
  - `test_missing_signal_columns_fail_loudly`: use `assertRaisesRegex(ValueError, "missing columns")`.
  - The negative-cost asserts at `:229-231`: pin `commission_per_trade` and `slippage_bps` respectively.
- [ ] T017 [US1] In `tests/test_backtest_harness.py`, the C5 tests. Hand-derive every value in comments.
  - **Split `test_open_position_is_marked_to_the_final_close` into two tests:**
    - `test_an_open_position_is_marked_not_closed`: default, empty trade log. The final ledger `mark` has `Price == 25.0` and `Quantity == 1`.
    - `test_liquidation_closes_it_at_the_final_close`: `liquidate=True`. One trade with `Exit Price == 25.0`, and exactly one ledger event named `liquidation`, on the final date.
  - **Rename `test_costs_apply_to_the_end_of_data_close_exit` to `test_costs_apply_to_the_terminal_liquidation`:**
    - pass `liquidate=True`;
    - assert exit fill = `Close × (1 − s)`;
    - assert the commission is charged on that event.

  Depends on T016, same file.
- [ ] T018 [P] [US1] In `tests/test_metrics.py`, C1:
  - Add a module `STARTING_CAPITAL` and a local `RUN = {**COSTS, "starting_capital": STARTING_CAPITAL}`. `COSTS` is imported and frozen.
  - Use `RUN` on every `run_backtest` call. `equity_curve` and `performance_summary` keep `**COSTS`.
  - `test_equity_is_anchored_so_a_bar_zero_drawdown_is_captured`: `run_backtest(..., starting_capital=100.0)`, matching `:230`.
  - The `TestValidation` asserts: pin each expected message with `assertRaisesRegex`.
- [ ] T019 [US1] In `tests/test_metrics.py`, the C5 tests. Depends on T018.
  - `test_bar_pnl_sums_to_trade_log_pnl` and `test_reconciliation_holds_without_costs_too`:
    - pass `liquidate=True`;
    - the docstring says Σ Bar P&L = Σ closed P&L holds only for a run that ends flat.
  - `test_position_still_open_on_the_final_bar_marks_to_its_close`: assert mark-only.
    - The trade log is empty.
    - The final curve `Equity` equals cash plus the marked close.
    - Σ Bar P&L equals final equity minus capital.
  - `test_same_bar_round_trip`: read its intent, choose mark-only or liquidation, and say which in the docstring.
- [ ] T020 [US1] In `tests/test_metrics.py`, the semantic tests. Depends on T019.
  - `test_curve_is_flat_at_the_capital_base`: `Equity == STARTING_CAPITAL`. The old `11.0` was the price-derived capital that 019 removed.
  - `test_performance_summary_has_every_key`: the expected set is the 20 keys at `scripts/metrics.py:351-374`, namely:
    - `annualized_mean_log_return`, `cagr_252_sessions`, `mean_log_return_se_hac`, `hac_lags`;
    - `cash_interest_rate_annual`, `risk_free_rate_annual`, `interpretation`, `liquidation`;
    - `total_trades`, `total_pnl`, `total_return`, `sharpe_ratio`, `max_drawdown`;
    - `drawdown_peak_bar`, `drawdown_trough_bar`, `bars`, `bars_in_market`;
    - `capital_base`, `commission_per_trade`, `slippage_bps`.
  - Rename `test_non_range_index_raises` to `test_a_non_range_index_is_preserved_and_changes_nothing`. The same prices with an offset index (for example `index*3+7`, as in `test_019_calendar.py:16`) give `Equity` values equal to the `RangeIndex` twin.
- [ ] T021 [P] [US1] In `tests/test_ml_signal.py`, the C5 tests.
  - `NullPredictionTests.test_a_null_exits_an_open_position`: expect `[True, True, False, True, True]`, with the comment "0.0 is not < exit 0.0; the batch end is not a decision". The null exit at index 2 is still asserted.
  - Rename `HysteresisTests.test_a_still_long_final_bar_is_forced_flat` to `test_a_still_long_final_bar_keeps_its_decision`, and `assertTrue`.
  - `OrderingTests.test_the_decision_pairs_each_prediction_with_its_own_rows_hurdle`: re-derive the final element from its own row's decision.
- [ ] T022 [US1] In `tests/test_ml_signal.py`, the C6 tests. The two synthetic frames in `HarnessReconciliationTests` (around `:496-503` and `:537-544`) set `attrs["price_basis"] = "unadjusted_dollars"`, and their `run_backtest` calls pass `STARTING_CAPITAL`. This is test-only, per 019 R-04. Depends on T021.
- [ ] T023 [US2] In `tests/test_ml_signal.py::EstimatorAgnosticTests`, which is FR-004 and not exempt (research.md R-9):
  - `_synthetic_frame` gains a strictly positive `Open` column.
  - `_predictions` takes `span = build_target(self.frame, kind=..., horizon=1)[2]` and passes `label_horizon=span, embargo_bars=span`.
  - Drop both `dropna` calls. `model_row_masks` masks after splitting (FR-007).
  - Assert that the prediction index equals the frame index.

  Depends on T022.
- [ ] T024 [US1] **PR-A close-out.** Same checks as T015, with lane A's 41 R-1 rows. Also confirm that the cost_utils lane's hunks in `test_metrics.py` and `test_ml_signal.py` are untouched: diff the T003 snapshot, and every hunk must be yours.

**Checkpoint**: lane A's 41 rows are green.

---

## Phase 5: Lane C, targets (PR-C) · User Story 2 (P1)

**Goal.** Label tests assert the open-to-open label and the `h+1` span, with
hand-derived values.

**Independent test.** `python -m pytest tests/test_targets.py` passes, except the two gated `TestEquivalenceWithLogisticBaseline` tests.

**Owns.** `tests/test_targets.py`, except `TestEquivalenceWithLogisticBaseline` and the module docstring, which are lane G's.

**Precondition:** none. `make_prices` is imported from lane B's file and is frozen.

- [ ] T025 [P] [US2] In `tests/test_targets.py`, the span tests:
  - The three `TestBuildTargetContract` tests assert the third value is `h+1`. Rename `test_the_returned_horizon_is_what_was_asked_for` to `test_the_third_value_is_the_availability_span`.
  - `test_dtype_is_nullable_so_the_tail_cannot_become_false`: 4 nulls at h = 3.
  - `test_exactly_the_last_horizon_rows_are_null`: `h+1` rows. Rename it to match.
  - Add `test_passing_the_span_back_as_horizon_builds_a_different_label` (REVIEW_019 R-10): `build_target(p, kind=k, horizon=span)[0]` differs from the `horizon=1` label on at least one known row, for both kinds.
- [ ] T026 [US2] In `tests/test_targets.py`, rename `test_over_long_horizon_yields_an_empty_feature_frame_not_an_error` to `test_an_over_long_horizon_keeps_every_row_and_trains_on_none`. Assert:
  - `len(frame) == 60`;
  - `not frame.Train_Eligible.any()`;
  - `(task, span) == ("classification", 301)`.

  Depends on T025.
- [ ] T027 [US1] In `tests/test_targets.py`, the C3 re-derivations. `make_prices` gives Open = Close + 1. Put every value's arithmetic in a comment. Depends on T026.
  - **(a)** Rename `test_label_at_t_compares_against_close_at_t_plus_horizon` to `test_label_compares_the_exit_open_against_the_entry_open`. For closes `[10, 12, 11, 15, 14]` the opens are `[11, 13, 12, 16, 15]`.
    - h = 1: `[0, 1, 0, <NA>, <NA>]`, from 12 > 13, 16 > 12, 15 > 16.
    - h = 2: `[1, 1, <NA>, <NA>, <NA>]`, from 16 > 13 and 15 > 12.
  - **(b)** `test_value_is_the_log_ratio_over_the_horizon`: extend the closes to `[100, 110, 121, 133.1]`, so the opens are `[101, 111, 122, 134.1]`.
    - h = 1: `label[0] = log(122/111)` and `label[1] = log(134.1/122)`. The last 2 rows are NaN.
    - h = 2: `label[0] = log(134.1/111)`. The last 3 rows are NaN.
  - **(c)** Rename `test_non_positive_close_is_nan_not_negative_infinity` to `test_a_non_positive_open_endpoint_is_nan_not_infinite`. Zero an entry-endpoint *Open*.
  - **(d)** Rename `test_missing_close_column_raises` to `test_missing_open_column_raises`. Use `pd.DataFrame({"Close": [1., 2.]})` and `assertRaisesRegex(ValueError, "Open")`.
  - **(e)** `TestGapCase`: choose opens so that a calendar-day reading and a row reading give different signs. Assert the row reading: `label[0] = log(Open[2]/Open[1])` across the five-day gap.
- [ ] T028 [US4] Run `TestOffByOne` and `TestOffByOneGuardsFireOnARealBug` (`:214-280`, already re-armed to `Open`), and confirm both pass. Then kill the target mutant `killed(targets, 'prices.Open.shift(-(horizon + 1))', 'prices.Open.shift(-(horizon + 2))', <TestOffByOne blindness test>)`. Record in [Evidence → PR-C](#pr-c-lane-c). This proves research.md R-10's "do not regress".
- [ ] T029 [US5] In `tests/test_targets.py`, fix the `_walk` docstring (`:37-38`, "`build_features` drops on it") and the class docstrings of every test T025–T027 renamed.
- [ ] T030 [US2] **PR-C close-out.** Same checks as T015, with lane C's 11 non-gated R-1 rows.

---

## Phase 6: Lane D, features and diagnostics (PR-D) · User Story 1 (P1)

**Goal.**

- Diagnostics measure complete rows and say how many.
- Primitives refuse non-finite input by name.
- The zero-volume guard is asserted as ineligibility.
- The rundown's final session is pinned.

**Independent test.** `python -m pytest tests/test_feature_scaling.py tests/test_reports_api.py -k "not backtest_tearsheet"` passes.

**Owns.**

- `scripts/feature_diagnostics.py`;
- `tests/test_feature_scaling.py`;
- `tests/test_reports_api.py`: **only** the `test_ml_rundown` hunk. It is shared with 018 T024 (plan.md → flagged exceptions, item 2).

**Precondition:** none.

- [ ] T031 [P] [US1] In `tests/test_feature_scaling.py`, add `test_a_non_finite_row_is_refused_by_name`. Put one NaN in a scale-free column, then call `condition_number` and `variance_inflation_factors`. Each must raise `ValueError` matching both the column name and `complete rows`. Run it on the current code: it must FAIL, because today the error is LinAlgError or a `nan`. Record the failure.
- [ ] T032 [US1] In `scripts/feature_diagnostics.py`, implement contracts §4:
  - `standardized_matrix` refuses non-finite input with the named `ValueError`;
  - `diagnose` masks to the set's complete rows and returns `rows` (measured) and `rows_excluded`;
  - `format_report` prints both;
  - fix the `main()` comment at `:206-210`.

  Then T031 passes. Depends on T031.
- [ ] T033 [US4] Red evidence for T031, recorded in [Evidence → PR-D](#pr-d-lane-d). An in-memory mutant removes the refusal from `standardized_matrix`. The test must fail. The control, complete rows, must measure without error.
- [ ] T034 [US1] In `tests/test_feature_scaling.py`, the C4 tests. Depends on T031, same file.
  - **The `_complete(frame, columns)` helper.** Add it to return rows where `columns` are all finite. `TestCollinearity` and `TestConditioning` measure on `_complete(frame, set_columns)`.
  - **`TestNonFiniteGuard`** (FR-008). Rename `test_zero_volume_rows_are_dropped_rather_than_infinite` to `test_zero_volume_rows_are_nan_and_ineligible_not_infinite`. On the zero-volume rows:
    - `Rel_Volume` is NaN and never ±inf;
    - `Inference_Eligible` is False under `scale_free`.
  - **`test_a_level_run_keeps_those_rows`** becomes the control: the same rows are `Inference_Eligible` under `levels`.
  - **`TestRatioDefinitions` (2).** Compare on eligible rows of the full-calendar frame. The volume-window test asserts that the *eligible* counts differ, since row counts are now equal.
  - **`TestScalerIsFitOnTrainingRowsOnly` (3).**
    - Splits are sized by the span.
    - Each fold's scaler is fitted on that fold's train-eligible rows.
    - `test_scaler_statistics_differ_from_the_whole_frame` stays as the internal control.
- [ ] T035 [US2] In `tests/test_feature_scaling.py`, the C2 tests: the four in `TestScalingChangesTheAnswer` and `TestScaleReachesEveryFit`. Take the span from `frame.attrs["label_availability_span"]`; the local `_frame` helper may also return it. Pass it as purge and embargo. Depends on T034.
- [ ] T036 [US4] Red evidence, recorded in [Evidence → PR-D](#pr-d-lane-d):
  - **(a) `TestNonFiniteGuard`.** An in-memory mutant of `features.py` drops the ±inf → NaN replacement at `:174-175`. The guard fails and the `levels` control passes.
  - **(b) `TestScalerIsFitOnTrainingRowsOnly`.** The planted defect fits the scaler on the whole frame. The gate fails.
- [ ] T037 [US1] In `tests/test_reports_api.py::test_ml_rundown` only, closing finding 23's consumer half (FR-018):
  - Assert `data["as_of_date"]` equals the last `Date` of the fixture panel's AAPL rows, formatted `YYYY-MM-DD`.
  - Red evidence: an in-memory mutant of `reports/api/routes/ml_rundown.py` reads `features_df.iloc[-2]`. The assertion fails. The route source is not edited.
- [ ] T038 [US1] **PR-D close-out.** Same checks as T015, with lane D's 17 R-1 rows. Also confirm the `test_reports_api.py` diff contains only `test_ml_rundown` lines. If 018 T024 landed in the meantime, re-snapshot and re-diff.

---

## Phase 7: Lane E, CV consumers (PR-E) · User Story 2 (P1)

**Goal.** Every CV test on a `build_features` frame sizes purge and embargo
from the span. The isolation gate corrupts only rows whose labels exist.

**Independent test.** `python -m pytest tests/test_estimators.py tests/test_model_cv.py` passes, except the four gated tests in `test_model_cv.py::TestEquivalenceWithLogisticBaseline`.

**Owns.** `tests/test_estimators.py`, and `tests/test_model_cv.py` except `TestEquivalenceWithLogisticBaseline`, which is lane G's. `_synthetic_features` is imported from lane B's file and is frozen.

**Precondition:** none.

- [ ] T039 [P] [US2] In `tests/test_estimators.py`, the 8 failing tests (R-1):
  - Take `span` from `build_features(...)[2]` and pass `label_horizon=span, embargo_bars=span`.
  - The direct splitter call at `:302` becomes `embargo_bars=horizon`, where `horizon` is the span variable.
  - Rename `test_task_and_horizon_come_through_from_build_features` to `test_task_and_span_come_through_from_build_features`, asserting span == 2 at h = 1.
  - Tests on `_synthetic_features` are exempt (research.md R-9) and not edited.
- [ ] T040 [P] [US2] In `tests/test_model_cv.py`, the 7 failing C2 tests outside the equivalence class:
  - `TestSelectionActuallySelects` ×2;
  - `TestNestedWalkForward` ×1;
  - `TestDeterminism` ×2;
  - `TestTuneOnFoldIsolation` ×2.

  Where the frame comes from `_learnable_frame`, pass `frame.attrs["label_availability_span"]` as purge and embargo. Tests on `_synthetic_features` are exempt and not edited.
- [ ] T041 [US1] In `tests/test_model_cv.py::TestTuneOnFoldIsolation._corrupted` (`:460-473`), the label flip applies only to outside rows whose label is known (`notna`). Feature corruption still covers every outside row. `test_the_corruption_would_be_visible_if_it_leaked` stays as the control. Depends on T040.
- [ ] T042 [US4] Red evidence, recorded in [Evidence → PR-E](#pr-e-lane-e). An in-memory mutant of `model_cv._inner_splits` adds one position outside `positions` to each inner training set. `test_selection_is_unchanged_by_corrupting_every_outside_row` must fail, and the visibility control must pass.
- [ ] T043 [US2] **PR-E close-out.** Same checks as T015, with lane E's 15 non-gated R-1 rows.

---

## Phase 8: Lane G, re-anchoring the control (PR-G) · User Story 1 (P1) · **GATED**

**Goal.** The pre-019 control stays frozen, and the equivalence tests are
re-anchored per research.md R-8.

**Independent test.** Both `TestEquivalenceWithLogisticBaseline` classes pass.

**Owns.**

- `tests/test_targets.py::TestEquivalenceWithLogisticBaseline` and that file's module docstring (`:1-7`);
- `tests/test_model_cv.py::TestEquivalenceWithLogisticBaseline`.

**Flagged:** lane G re-enters files lanes C and E own. It is **sequential
only**.

**Precondition:** T002(b), D-2 signed, **and** PR-C and PR-E both merged.

- [ ] T044 [US1] Re-read spec.md D-2 as signed.
  - If Camden amended it, stop and update research.md R-8 and this phase before editing.
  - Snapshot the two files (T003).
- [ ] T045 [US1] In `tests/test_targets.py::TestEquivalenceWithLogisticBaseline`, per R-8:
  - Keep `test_level_feature_columns_match` and `test_the_default_feature_set_is_not_the_level_set`.
  - Replace `test_direction_label_matches_the_baseline_label` with `test_label_divergence_from_the_pre_019_control_is_exactly_the_open_basis`. Use a hand-worked frame with a row where `Close[t+1] > Close[t]` but `Open[t+2] < Open[t+1]`.
  - Replace `test_build_features_reproduces_the_baseline_frame` with `test_baseline_rows_are_a_date_subset_of_the_full_calendar_frame`. The shared level columns must be equal on those rows.
  - Rewrite the class docstring and the module docstring: the control is frozen pre-019, and the divergence is pinned.
- [ ] T046 [US1] In `tests/test_model_cv.py::TestEquivalenceWithLogisticBaseline`, per R-8:
  - The reference becomes `estimators.fit_predict_walk_forward(name="logistic", task=CLASSIFICATION, params={"C": 1.0}, scale=False, label_horizon=span, embargo_bars=span, random_state=42)`.
  - The fixture-discrimination guard fits train-eligible rows.
  - `test_one_outer_fit_per_fold_on_top_of_the_tuning_fits` uses the span.
  - Rewrite the class docstring. It names the chain via `test_estimators.py:212`, and drops the claim that it pins `logistic_baseline.walk_forward_predictions` directly.
- [ ] T047 [US4] Red evidence, recorded in [Evidence → PR-G](#pr-g-lane-g):
  - **(a) Divergence.** An in-memory mutant of `targets._executable_endpoints` returns close-based endpoints. The divergence test fails.
  - **(b) Tuner equivalence.** An in-memory mutant of `model_cv.tune_on_fold` returns `{"C": 0.5}`. The equivalence test fails.
  - The controls pass for both.
- [ ] T048 [US1] **PR-G close-out.** Same checks as T015, with lane G's 6 R-1 rows.

---

## Phase 9: The gate (SC-001 to SC-007) · User Story 1 (P1)

**Goal.** The suite fails on exactly the residual list, and every structural
criterion holds.

**Precondition:** every PR-A to PR-G merged.

- [ ] T049 [US1] Run quickstart.md §5. The failing IDs in `final.xml` must equal the 21 residual IDs in research.md R-1, with zero errors outside them (SC-001).
  - Any extra ID is a 021 defect. Fix it in the owning lane's file.
  - Any residual ID that is now passing: record which owner landed it.
- [ ] T050 [P] [US2] Run quickstart.md §4's grep (SC-002). Every hit must carry an exemption comment.
- [ ] T051 [P] [US1] Check the collected count (SC-006). It must be ≥ the T001 count, minus the D-2 replacements, plus the new tests. List every rename and replacement from lanes A–G in [Evidence → Gate](#gate).
- [ ] T052 [P] [US1] Re-run the T004 fingerprints. Every digest must be unchanged (FR-019, FR-020).
- [ ] T053 [P] [US4] Confirm the Evidence section has a red outcome and a green control for every gate in research.md R-10 (SC-003).
- [ ] T054 [P] [US5] Re-read every docstring and comment in the touched files against C1–C7 (FR-017).

---

## Phase 10: Polish and handoff

- [ ] T055 In [Evidence → Handoff](#handoff), record the inputs for the follow-ons, so each starts from facts rather than re-triage. **Do not create those specs.** Camden assigns numbers.
  - **Rename** (research.md R-3, "What the follow-on inherits"): the call sites, now all span variables, and the three legacy `attrs` fallbacks.
  - **Frozen files** (spec D-5): the `:367` and `:428` NaN-label scoring; `multi_ticker_comparison`'s capital and policy gap at `:133`, `:141` and `:269`; its 020 loader at `:230`.
  - **Docs and Rule 11** (spec D-7): the `PROJECT_CONTEXT.md` passages.
  - **020 wiring:** the two entry points that now stop on 020's named reason.
- [ ] T056 Update spec.md's **Status** line. Name the merged PRs, the final baseline numbers, and the residual count.

---

## Dependencies and execution order

```text
T001─T004 (setup, recorded)
   ├── Lane B  T005→T006→T007, T006→T008, T009→T010, {T006,T009}→T011→T012, T005→T013, T014 ─→ T015 (PR-B)
   ├── Lane A  [needs T002a]  T016→T017, T018→T019→T020, T021→T022→T023 ─→ T024 (PR-A)
   ├── Lane C  T025→T026→T027, T028, T029 ─→ T030 (PR-C) ─┐
   ├── Lane D  T031→T032→T033, T031→T034→T035→T036, T037 ─→ T038 (PR-D)
   └── Lane E  T039, T040→T041→T042 ─→ T043 (PR-E) ───────┤
                                                          ▼
                     [needs T002b: D-2 signed]  Lane G  T044→T045, T044→T046, →T047 ─→ T048 (PR-G)
                                                          ▼
                                    Gate T049 · T050–T054 [P] ─→ Handoff T055 → T056
```

- **Across lanes:** A, B, C, D and E are fully parallel. They share no file,
  and the fixtures they read are frozen (FR-020, research.md R-11). A waits
  only on the concurrent lane (T002a). G waits on D-2 **and** on PR-C and
  PR-E.
- **Within a lane:** tasks on the same file are sequential, in ID order. A
  test that adds a gate comes before the code it gates: T005→T006 and
  T031→T032.
- **Suggested review order:** PR-B first. It is the only production behavior
  change with Rule 4 consequences, and it fixes the D-3/D-4 conventions the
  test lanes mirror.

### Where exclusive ownership breaks, and how it is contained

| Shared file | Holders | Containment |
|---|---|---|
| `tests/test_targets.py` | C, then G | Sequential. G starts after PR-C merges. The split is by class. |
| `tests/test_model_cv.py` | E, then G | Sequential. G starts after PR-E merges. The split is by class. |
| `tests/test_reports_api.py` | D and spec 018 T024 | The split is by hunk (`test_ml_rundown` against `test_backtest_tearsheet`). Whichever lands second re-snapshots (T038). |
| `tests/test_metrics.py`, `tests/test_ml_signal.py` | A and the concurrent cost_utils lane | A waits (T002a). T024 verifies that no foreign hunk moved. |
| Fixtures in B's files, read by A, C and E | B owns them; all may read | Frozen (FR-020). T004 and T052 prove it. |
| `scripts/logistic_baseline.py` | B (reporting hunks); C, E and G read the frozen functions | Frozen functions are fingerprinted (T004 and T052). |

## Parallel examples

```text
# After T001–T004, with T002(a) and T002(c) satisfied, five agents in five lanes:
Agent 1 (B): T005 in tests/test_signals.py  ‖  T009 in scripts/ma_crossover_backtest.py  ‖  T014 in tests/test_logistic_baseline.py
Agent 2 (A): T016 in tests/test_backtest_harness.py  ‖  T018 in tests/test_metrics.py  ‖  T021 in tests/test_ml_signal.py
Agent 3 (C): T025 in tests/test_targets.py
Agent 4 (D): T031 in tests/test_feature_scaling.py
Agent 5 (E): T039 in tests/test_estimators.py  ‖  T040 in tests/test_model_cv.py

# After every PR merges, the gate checks run side by side:
T050 ‖ T051 ‖ T052 ‖ T053 ‖ T054
```

## Implementation strategy

- **First reviewable increment: PR-B.** It is not an MVP of US1, which by
  definition needs every lane. It is the smallest PR that repairs a live
  production defect: the random baseline silently not running. Review it
  first, and confirm D-3 and D-4 on it.
- **Then B, A, C, D and E in any order.** Each is independently green on its
  own focused run, and each strictly shrinks the full suite's failing set.
  The failing set never grows, and no PR may add an ID outside R-1.
- **G last, when Camden signs D-2.** If D-2 is rejected in favor of migrating
  `logistic_baseline.py`, lane G is replaced by a new spec. The rest of 021
  still lands, and the 6 gated tests join the residual list with that spec as
  their owner.
- **The gate (Phase 9)** is the only point where US1 is claimed.

## Story → task map

| Story | Priority | Tasks |
|---|---|---|
| US1: every red test has a name and an owner | P1 | T016–T020, T022, T024, T027, T031–T032, T034, T037–T038, T041, T044–T046, T048, T049, T051–T052 |
| US2: the purge came from the label | P1 | T023, T025–T026, T030, T035, T039–T040, T043, T050 |
| US3: the Phase 0 comparison has three real rows | P2 | T005–T006, T009–T011, T013–T015 |
| US4: migrated gates can still go red | P2 | T007, T012, T028, T033, T036, T042, T047, T053 |
| US5: no touched file describes the old contract | P3 | T008, T029, T054 |

---

## Evidence

This section is filled in during implementation. Paste each command and its
real output; never summarize a run you did not make.

### T001 re-baseline

| Field | Value |
|---|---|
| Date/time | |
| Summary line | |
| Unique failing | |
| IDs added vs R-1 (cause) | |
| IDs removed vs R-1 (cause) | |

### T002 preconditions

| Precondition | State | Recorded by / date |
|---|---|---|
| (a) cost_utils lane landed or abandoned | | |
| (b) D-2 signed | | |
| (c) D-3 / D-4 accepted or amended | | |
| (d) 018 T024 state | | |

### T004 frozen fingerprints

| Region / file | SHA-256 at T004 | SHA-256 at T052 |
|---|---|---|

### PR-B (lane B)

| Gate / check | Red (planted defect → outcome) | Green control | Lines |
|---|---|---|---|

### PR-A (lane A)

| Check | Result | Lines |
|---|---|---|

### PR-C (lane C)

| Gate / check | Red | Green control | Lines |
|---|---|---|---|

### PR-D (lane D)

| Gate / check | Red | Green control | Lines |
|---|---|---|---|

### PR-E (lane E)

| Gate / check | Red | Green control | Lines |
|---|---|---|---|

### PR-G (lane G)

| Gate / check | Red | Green control | Lines |
|---|---|---|---|

### Gate

| Criterion | Result |
|---|---|
| SC-001: failing set = residual (21) | |
| SC-002: grep hits all exempt | |
| SC-003: every R-10 gate has red and green | |
| SC-004: 20/20 seeds, buy-and-hold 1 trade, stated once | |
| SC-005: every PR ≤ 400 lines | |
| SC-006: collected count, with renames and replacements listed | |
| SC-007: no metric quoted in any PR | |

### Handoff

(T055)
