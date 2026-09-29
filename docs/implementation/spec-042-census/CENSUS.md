# Census: Source-Text, Regex, and AST Dependencies in Tests and Mutations

## 1. Scope, File Set, and Search Methodology

### 1.1 Context and Scope
This census provides a read-only inventory of every test, mutant, and mutation driver in `Quant-ML-Bot` whose pass/fail status depends on the exact text of a source file (exact substring match, regex, or AST). 

The census addresses two key operational failure modes:
1. **Whole-file formatting fragility**: Reformatting via tools such as `black` or `ruff format` modifies whitespace, indentation, line breaks, and quote styles, causing exact-count substring assertions (e.g. `source.count(old) == 1`) to fail without any semantic defect.
2. **Packaging migration fragility**: Shifting modules to `src/qmb/` alters import syntax (e.g., `from qmb.signals import ...`), directory layout, and module boundary checks.

### 1.2 File Set Scanned
The scan covered all files within the repository boundaries under:
- `tests/` (including `tests/mutation/`, helpers, and fixtures)
- `scripts/`
- `reports/` (including `reports/api/` and `reports/web/src/`)

Excluded directories: `.git/`, `.pytest_cache/`, `__pycache__/`, `node_modules/`, `reports/web/dist/`, and virtual environment directories.

### 1.3 Exact Search Patterns Used
The following patterns were scanned exhaustively across the target tree:
- `killed\(` — Invocations of `mutation_support_019.killed` and `mutation_support_032.killed`
- `\.count\(` — String count assertions (e.g. `source.count(old) == 1`)
- `\.replace\(` — String mutations (e.g. `source.replace(old, new)`)
- `re\.(sub|search|match|findall|compile)` — Regular expression patterns evaluating source or configuration text
- `ast\.parse` — Abstract Syntax Tree parsing of Python source code
- `read_text` / `read_bytes` — Direct filesystem reads targeting source, test, or requirements files
- `inspect\.getsource` / `inspect\.getsourcelines` / `inspect\.currentframe` — Runtime reflection on source code
- `open\(` — Direct file descriptor operations targeting scripts or module source paths
- `research_config\(` — Hardcoded runner identification strings in research entrypoints
- `source_identity` / `source_tree_hash` — Production source tree hashing and metadata tracking

---

## 2. Master Census Table

The table below catalogs every identified test, mutant, and mutation driver.

Columns:
- **File**: Test or mutation driver file containing the check.
- **Test / Function**: Function or test case defining the check or mutant.
- **Target Source File**: File whose text, AST, or structure is evaluated.
- **Mechanism**: Detection mechanism (`exact substring incl. whitespace`, `AST node`, `AST node + regex`, or `regex`).
- **Fragile to Reformat (Y/N)**: Whether whole-file code formatting (e.g. `ruff`, `black`, `prettier`) risks altering the target text and breaking the check.
- **Fragile to Import Shift (Y/N)**: Whether shifting import statements, reordering, or qualifying imports (e.g. `from qmb...`) risks breaking the check.
- **Why**: Rationale explaining the classification.

| # | File | Test / Function | Target Source File | Mechanism | Fragile to Reformat | Fragile to Import Shift | Why |
|---|---|---|---|---|:---:|:---:|---|
| 1 | `tests/test_019_calendar.py` | `test_calendar_mutants` (mutant 1) | `scripts/features.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'return features, task, label_availability_span'` fails if return tuple formatting changes. |
| 2 | `tests/test_019_calendar.py` | `test_calendar_mutants` (mutant 2) | `scripts/ml_signal.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'desired[i] = long'` fails if spacing around assignment operator changes. |
| 3 | `tests/test_019_calendar.py` | `test_calendar_mutants` (mutant 3) | `scripts/estimators.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'train_indices = train_indices[train_ok[train_indices]]'` fails if indexing expression line wraps. |
| 4 | `tests/test_019_conventions.py` | `test_metric_convention_mutants` (mutant 1) | `scripts/metrics.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'(annualized_return - annual_risk_free_log_return)'` fails if parentheses or spacing change. |
| 5 | `tests/test_019_conventions.py` | `test_metric_convention_mutants` (mutant 2) | `scripts/metrics.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'variance += 2 * (1 - lag / (lags + 1)) * covariance'` fails if arithmetic spacing or wrapping changes. |
| 6 | `tests/test_019_conventions.py` | `test_metric_convention_mutants` (mutant 3) | `scripts/metrics.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'hac_lags = max(horizon - 1, min(len(returns) - 1, effective_bw))'` fails if nested call wraps across lines. |
| 7 | `tests/test_019_ledger.py` | `test_ledger_mutants` (mutant 1) | `scripts/backtest_harness.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'if required > cash:'` fails if `if` condition spacing changes. |
| 8 | `tests/test_019_ledger.py` | `test_ledger_mutants` (mutant 2) | `scripts/backtest_harness.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'cash -= required'` fails if assignment operator spacing changes. |
| 9 | `tests/test_019_ledger.py` | `test_ledger_mutants` (mutant 3) | `scripts/backtest_harness.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'if quantity and liquidate:'` fails if boolean condition line wraps or formatting shifts. |
| 10 | `tests/test_019_metrics.py` | `test_anchor_mutants` (mutant 1) | `scripts/metrics.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'anchored = "capital_base" in equity.attrs'` fails if formatter changes double quotes to single quotes. |
| 11 | `tests/test_019_metrics.py` | `test_anchor_mutants` (mutant 2) | `scripts/metrics.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'capital = equity.attrs.get("capital_base")'` fails if formatter changes double quotes to single quotes. |
| 12 | `tests/test_019_prices.py` | `test_price_action_mutants` (mutant 1) | `scripts/backtest_harness.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'quantity *= row.Split'` fails if assignment operator spacing changes. |
| 13 | `tests/test_019_prices.py` | `test_price_action_mutants` (mutant 2) | `scripts/backtest_harness.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'receivable += income'` fails if assignment operator spacing changes. |
| 14 | `tests/test_019_prices.py` | `test_price_action_mutants` (mutant 3) | `scripts/data.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'result.Close.iloc[0] * gross.cumprod()'` fails if operator spacing or wrapping changes. |
| 15 | `tests/test_019_targets.py` | `test_target_mutants` (mutant 1) | `scripts/targets.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'prices.Open.shift(-1)'` fails if method call formatting or wrapping changes. |
| 16 | `tests/test_019_targets.py` | `test_target_mutants` (mutant 2) | `scripts/targets.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'_TASK_FOR_KIND[kind], horizon + 1'` fails if argument list spacing changes. |
| 17 | `tests/test_019_targets.py` | `test_target_mutants` (mutant 3) | `scripts/targets.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'label[returns.isna()] = pd.NA'` fails if indexing expression spacing changes. |
| 18 | `tests/test_clean_clone_037.py` | `test_unsafe_cast_mutant_is_killed` | `scripts/feature_set_comparison.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on leading 4 spaces and trailing newline fails if indentation or line wrapping changes. |
| 19 | `tests/test_clean_clone_037.py` | `test_implicit_fork_context_mutant_is_killed` | `scripts/feature_set_comparison.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on 12 leading spaces and trailing newline fails if call keyword arguments are reformatted. |
| 20 | `tests/test_clean_clone_037.py` | `test_changed_baseline_funding_mutant_is_killed` | `scripts/multi_ticker_comparison.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on 6-line multiline block with 12 leading spaces fails on any whitespace/newline reformat (active bug). |
| 21 | `tests/test_live_safety_gate.py` | `test_inclusive_position_boundary_is_actually_enforced` | `scripts/live_safety_gate.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` fails if comparison operator spacing, double quotes on `["instrument_notional"]`, or line breaks shift. |
| 22 | `tests/test_live_safety_gate.py` | `test_nonpositive_equity_guard_is_actually_before_any_division` | `scripts/live_safety_gate.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'if not math.isfinite(snapshot.equity) or snapshot.equity <= 0.0:'` fails if boolean condition line wraps. |
| 23 | `tests/test_live_safety_gate.py` | `test_kill_latch_is_actually_checked` | `scripts/live_safety_gate.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on multiline string with 12 leading spaces fails if indentation or line wrap changes. |
| 24 | `tests/test_live_safety_gate.py` | `test_pending_orders_are_actually_aggregated_into_exposure` | `scripts/live_safety_gate.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on dictionary comprehension fails if formatted across multiple lines. |
| 25 | `tests/test_live_safety_gate.py` | `test_reduce_only_is_actually_exempted_from_a_loss_halt` | `scripts/live_safety_gate.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on `'if halted and not is_reduce_only:'` fails if condition formatting changes. |
| 26 | `tests/test_live_safety_gate.py` | `test_restart_actually_reloads_the_kill_latch_from_disk` | `scripts/live_safety_gate.py` | exact substring incl. whitespace | Y | N | `source.count(old) == 1` on dictionary comprehension fails if line wraps or spacing changes. |
| 27 | `tests/mutation/run_mutation_check.py` | `main` (spec 020 price bundle mutant) | `scripts/data.py` | exact substring incl. whitespace | Y | N | `source.count(ORIGINAL) != 1` on 3-line block with 4-space indent fails if indentation or call wrapping changes. |
| 28 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[0]` (finding 45) | `reports/api/routes/diagnostics.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'reason=SIGNIFICANCE_NOT_COMPUTED)'` fails if keyword argument wraps across lines. |
| 29 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[1]` (finding 45) | `reports/api/routes/diagnostics.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'"No saved experiment run'` fails if quote normalization converts double quotes to single quotes. |
| 30 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[2]` (finding 45) | `reports/web/src/components/views/FeatureDiagnosticsView.tsx` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'reason={significance.reason}'` fails if Prettier wraps JSX props. |
| 31 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[3]` (finding 47) | `reports/api/routes/capital_gate.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on multiline string with 12 leading spaces fails if indentation or argument wrapping changes. |
| 32 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[4]` (finding 47) | `reports/api/routes/capital_gate.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` fails if quote normalization or docstring/string formatting alters double quotes. |
| 33 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[5]` (finding 47) | `reports/api/schemas.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'if self.status != "unknown" and not self.evidence:'` fails if quote style or condition line breaks change. |
| 34 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[6]` (finding 47) | `reports/web/src/components/layout/Header.tsx` | exact substring incl. whitespace | N | N | Isolated plain text string in JSX; not altered by line-level reformatting unless text content is edited. |
| 35 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[7]` (finding 47) | `reports/web/src/components/views/CapitalGateView.tsx` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'of {gateStatus.gates.length} Gates'` fails if JSX formatter changes spacing inside `{}`. |
| 36 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[8]` (finding 46) | `reports/api/routes/ml_rundown.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'forecast_title = "Both Trend Rules Read Down"\n'` fails if quote style or trailing newline changes. |
| 37 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[9]` (finding 46) | `reports/api/routes/ml_rundown.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'NotComputed(reason=FORECAST_NOT_COMPUTED)'` fails if constructor arguments wrap across lines. |
| 38 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[10]` (finding 46) | `reports/api/routes/ml_rundown.py` | exact substring incl. whitespace | N | N | Isolated substring inside string literal; immune to structural whitespace changes unless text itself changes. |
| 39 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[11]` (finding 46) | `reports/web/src/components/layout/MLRundownPane.tsx` | exact substring incl. whitespace | N | N | Isolated text literal in TSX component; immune to code layout changes. |
| 40 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[12]` (finding 57) | `reports/api/routes/data.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'without network access."""\n'` fails if docstring quote style or trailing newline changes. |
| 41 | `tests/mutation/run_spec_018_mutants.py` | `MUTANTS[13]` (finding 57) | `reports/api/main.py` | exact substring incl. whitespace | Y | N | `text.count(find) != 1` on `'StaticFiles(directory=str(dist_dir)'` fails if argument call formatting wraps lines. |
| 42 | `tests/mutation/run_unadjusted_wiring_mutants.py` | `MUTANTS[0]` (`adjusted fallback`) | `scripts/ma_crossover_backtest.py` | exact substring incl. whitespace | Y | N | `content.count(find) != 1` on leading 4 spaces and trailing newline fails if line wraps or indentation changes. |
| 43 | `tests/mutation/run_unadjusted_wiring_mutants.py` | `MUTANTS[1]` (`ambiguous selection`) | `scripts/data.py` | exact substring incl. whitespace | Y | N | `content.count(find) != 1` on multiline string with 4 and 8 spaces and double quotes fails on reformatting. |
| 44 | `tests/mutation/run_unadjusted_wiring_mutants.py` | `MUTANTS[2]` (`broad ticker prefix`) | `scripts/data.py` | exact substring incl. whitespace | Y | N | `content.count(find) != 1` on `'pattern.fullmatch(path.name)'` fails if argument spacing changes. |
| 45 | `tests/mutation/run_unadjusted_wiring_mutants.py` | `MUTANTS[3]` (`nominal split signal`) | `scripts/ma_crossover_backtest.py` | exact substring incl. whitespace | Y | N | `content.count(find) != 1` on leading 4 spaces and double quotes fails if quotes normalize or indentation shifts. |
| 46 | `tests/mutation/run_unadjusted_wiring_mutants.py` | `MUTANTS[4]` (`trial before load`) | `scripts/ma_crossover_backtest.py` | exact substring incl. whitespace | Y | N | `content.count(find) != 1` on leading 4 spaces and trailing newline fails if line is wrapped or reformatted. |
| 47 | `tests/mutation/run_unadjusted_wiring_mutants.py` | `MUTANTS[5]` (`missing 503 mapping`) | `reports/api/routes/backtest.py` | exact substring incl. whitespace | Y | N | `content.count(find) != 1` on leading 4 spaces fails if indentation or exception clause formatting changes. |
| 48 | `tests/mutation/run_unadjusted_wiring_mutants.py` | `MUTANTS[6]` (`baseline funding omitted`) | `reports/api/routes/backtest.py` | exact substring incl. whitespace | Y | N | `content.count(find) != 1` on multiline string with 8 leading spaces and trailing comma fails if call arguments wrap differently. |
| 49 | `tests/test_estimators.py` | `TestModuleBoundaries.test_estimators_imports_only_walk_forward_cv_and_sklearn` | `scripts/estimators.py` | AST node | N | Y | Asserts exact set of imported module names: `{"__future__", "itertools", "collections", "dataclasses", "typing", "numpy", "pandas", "sklearn", "walk_forward_cv"}`; packaging migration shifts module names to `qmb`. |
| 50 | `tests/test_estimators.py` | `TestModuleBoundaries.test_estimators_imports_no_forbidden_project_module` | `scripts/estimators.py` | AST node | N | N | Asserts AST import set does not intersect forbidden project modules (immune to whitespace; but vulnerable to silent pass under packaging). |
| 51 | `tests/test_feature_set_comparison.py` | `ParallelComparisonContractTests.test_no_external_parallelism_library_is_imported` | `scripts/feature_set_comparison.py` | AST node | N | N | Asserts AST import set does not intersect forbidden parallelism modules (`joblib`, `dask`, etc.). |
| 52 | `tests/test_ml_signal.py` | `TestModuleBoundaries.test_ml_signal_imports_only_numpy_and_pandas` | `scripts/ml_signal.py` | AST node | N | Y | Asserts exact imported module set: `{"__future__", "numpy", "pandas", "cost_utils"}`; fails if imports or packaging shift to `qmb`. |
| 53 | `tests/test_ml_signal.py` | `TestModuleBoundaries.test_ml_signal_imports_no_forbidden_project_module` | `scripts/ml_signal.py` | AST node | N | N | Asserts AST import set does not intersect forbidden modules (`backtest_harness`, `estimators`, `sklearn`, etc.). |
| 54 | `tests/test_model_cv.py` | `TestModuleBoundaries.test_model_cv_imports_exactly_the_declared_set` | `scripts/model_cv.py` | AST node | N | Y | Asserts exact imported module set: `{"__future__", "collections", "typing", "numpy", "pandas", "sklearn", "estimators", "walk_forward_cv", "trial_runner"}`; fails under packaging migration. |
| 55 | `tests/test_model_cv.py` | `TestModuleBoundaries.test_model_cv_imports_no_forbidden_project_module` | `scripts/model_cv.py` | AST node | N | N | Asserts AST import set does not intersect forbidden project modules. |
| 56 | `tests/test_portfolio_risk.py` | `ModuleBoundaryTests.test_the_import_set_is_exactly_the_declared_one` | `scripts/portfolio_risk.py` | AST node | N | Y | Asserts exact imported module set: `{"__future__", "dataclasses", "numpy", "pandas", "constants"}`; fails under packaging migration. |
| 57 | `tests/test_portfolio_risk.py` | `ModuleBoundaryTests.test_no_signal_accounting_or_data_module_is_imported` | `scripts/portfolio_risk.py` | AST node | N | N | Asserts AST import set does not intersect forbidden modules. |
| 58 | `tests/test_portfolio_risk.py` | `NoKellyTests.test_no_identifier_in_the_module_is_a_kelly_anything` | `scripts/portfolio_risk.py` | AST node | N | N | Walks AST identifier names asserting none contains "kelly" (immune to formatting and import shifts). |
| 59 | `tests/test_targets.py` | `TestModuleBoundaries.test_neither_module_imports_the_harness` | `scripts/targets.py`, `scripts/features.py` | AST node | N | N | Asserts AST import sets do not intersect forbidden modules (`backtest_harness`, `plotting`, `data`, `yfinance`). |
| 60 | `tests/test_targets.py` | `TestModuleBoundaries.test_targets_imports_nothing_from_the_project` | `scripts/targets.py` | AST node | N | Y | Asserts exact imported module set: `{"numpy", "pandas"}`; fails if imports or packaging shift to `qmb`. |
| 61 | `tests/test_targets.py` | `TestModuleBoundaries.test_features_imports_only_signals_and_targets` | `scripts/features.py` | AST node | N | Y | Asserts exact imported module set: `{"numpy", "pandas", "signals", "targets"}`; fails under packaging migration to `qmb`. |
| 62 | `tests/test_unadjusted_caller_wiring.py` | `test_cli_source_contains_no_legacy_download_reference` | `scripts/ma_crossover_backtest.py` | AST node | N | N | Asserts AST contains no `Name(id="download_market_data")` or `ImportFrom` alias `"download_market_data"`. |
| 63 | `tests/test_order_gateway.py` | `BrokerImportGuardTests.test_production_broker_imports_always_import_live_gate` | `scripts/*.py`, `reports/**/*.py`, `exec/**/*.py` | AST node | N | Y | Asserts broker modules import `LiveSafetyGate` specifically from `live_safety_gate` or `scripts.live_safety_gate`; fails on packaging to `qmb`. |
| 64 | `tests/test_033_trial_instrumentation.py` | `test_inventory_and_production_guard` | `scripts/*.py`, `reports/api/**/*.py` | AST node | N | Y | `bypasses()` resolves aliases exclusively from `ast.ImportFrom` and scans hardcoded `scripts/` directory; fails if folder moves. |
| 65 | `tests/test_033_trial_instrumentation.py` | `test_api_strategy_is_candidate_not_required_random_baseline` | `reports/api/routes/backtest.py` | AST node | N | N | Asserts `research_attempt` AST call contains keyword argument `role="candidate"`. |
| 66 | `tests/test_no_fabricated_values.py` | `FabricatedSourceTests.test_route_modules_carry_no_fabricated_literal` | `reports/api/routes/*.py` | AST node + regex | N | N | Walks AST `Constant` string nodes matching against forbidden metric regexes; AST string evaluation is whitespace-invariant. |
| 67 | `tests/test_no_fabricated_values.py` | `FabricatedSourceTests.test_terminal_components_carry_no_fabricated_literal` | `reports/web/src/**/*.ts*` | regex | N | N | Scans lines of TS/TSX source matching forbidden literal regexes; immune to formatting unless a literal is split across tokens. |
| 68 | `tests/test_reports_api.py` | `test_dev_requirements_match_declared_ui_pins` | `requirements-dev.txt`, `reports/requirements-ui.txt` | regex | Y | N | Scans requirements with `^([A-Za-z0-9_.-]+)==(\S+)$`; fails if dependency line spacing or formatting shifts. |

---

## 3. Floor Inventory: Hardcoded Runner Strings

An earlier inventory undercounted runner strings (5 vs 12). The undercount occurred because runner invocations exist across 5 distinct script files, but there are **12 distinct call sites** in `scripts/` (plus 1 in `reports/api/`, 1 embedded in a mutant string, and 1 static fixture inventory).

When migrating to `src/qmb/`, every runner string hardcoding `scripts/<module>.py:<runner>` will become misaligned unless updated or derived dynamically.

### 3.1 Inventory Table of Runner Strings

| # | Source File | Line | Hardcoded Runner String | Function Context | Role |
|---|---|---|---|---|---|
| 1 | `scripts/feature_set_comparison.py` | 167 | `"scripts/feature_set_comparison.py:nested_walk_forward"` | `nested_walk_forward` | `candidate` |
| 2 | `scripts/logistic_baseline.py` | 318 | `"scripts/logistic_baseline.py:evaluate_walk_forward"` | `evaluate_walk_forward` | `candidate` |
| 3 | `scripts/logistic_baseline.py` | 332 | `"scripts/logistic_baseline.py:run_backtest"` | `run_backtest` | `candidate` |
| 4 | `scripts/ma_crossover_backtest.py` | 123 | `"scripts/ma_crossover_backtest.py:run_backtest"` | `_baseline_rows` | `buy_and_hold_baseline` |
| 5 | `scripts/ma_crossover_backtest.py` | 135 | `"scripts/ma_crossover_backtest.py:run_backtest"` | `_baseline_rows` | `random_signal_baseline` |
| 6 | `scripts/ma_crossover_backtest.py` | 250 | `"scripts/ma_crossover_backtest.py:run_backtest"` | `main` | `candidate` |
| 7 | `scripts/model_cv.py` | 330 | `"scripts/model_cv.py:grid_point"` | `tune_on_fold` | *(default)* |
| 8 | `scripts/model_cv.py` | 461 | `"scripts/model_cv.py:tune_on_fold"` | `fit_predict_walk_forward` | `candidate` |
| 9 | `scripts/multi_ticker_comparison.py` | 138 | `"scripts/multi_ticker_comparison.py:run_backtest"` | `_baseline_rows` | `buy_and_hold_baseline` |
| 10 | `scripts/multi_ticker_comparison.py` | 157 | `"scripts/multi_ticker_comparison.py:run_backtest"` | `_baseline_rows` | `random_signal_baseline` |
| 11 | `scripts/multi_ticker_comparison.py` | 284 | `"scripts/multi_ticker_comparison.py:nested_walk_forward"` | `_run_ml_candidate` | `candidate` |
| 12 | `scripts/multi_ticker_comparison.py` | 322 | `"scripts/multi_ticker_comparison.py:run_backtest"` | `_run_ml_candidate` | `candidate` |
| 13 | `reports/api/routes/backtest.py` | 60 | `"reports/api/routes/backtest.py:run_backtest"` | `backtest_tearsheet` | `candidate` |
| 14 | `tests/mutation/run_unadjusted_wiring_mutants.py` | 47 | `"scripts/ma_crossover_backtest.py:run_backtest"` | Mutant 5 (`trial before load`) | `candidate` |

---

## 4. Totals per Mechanism

| Mechanism | Description | Count | Fragile to Reformat | Fragile to Import Shift |
|---|---|:---:|:---:|:---:|
| **exact substring incl. whitespace** | String pattern matching with `.count()`, `.replace()`, or `killed()` | 48 | 45 | 0 |
| **AST node** | Structural syntax tree inspection via `ast.parse` and node visitors | 17 | 0 | 8 |
| **AST node + regex** | Combined AST string literal extraction and regular expression matching | 1 | 0 | 0 |
| **regex** | Line-by-line or multiline regular expression matching against file text | 2 | 1 | 0 |
| **TOTAL** | All source-dependent tests, mutants, and drivers | **68** | **46** | **8** |

### Breakdown of the 48 Exact Substring Mutants:
- In-suite tests using `mutation_support_019.killed`: **20**
- In-suite tests using `mutation_support_032.killed`: **6**
- Standalone runner `tests/mutation/run_mutation_check.py`: **1**
- Standalone runner `tests/mutation/run_spec_018_mutants.py`: **14**
- Standalone runner `tests/mutation/run_unadjusted_wiring_mutants.py`: **7**

---

## 5. Suites Sharing `mutation_support_019` and `mutation_support_032`

### 5.1 Suite Inventory
- **Suites using `tests/mutation_support_019.py`** (7 test suites, 20 mutants):
  1. `tests/test_019_calendar.py` (3 mutants)
  2. `tests/test_019_conventions.py` (3 mutants)
  3. `tests/test_019_ledger.py` (3 mutants)
  4. `tests/test_019_metrics.py` (2 mutants)
  5. `tests/test_019_prices.py` (3 mutants)
  6. `tests/test_019_targets.py` (3 mutants)
  7. `tests/test_clean_clone_037.py` (3 mutants)
- **Suites using `tests/mutation_support_032.py`** (1 test suite, 6 mutants):
  1. `tests/test_live_safety_gate.py` (6 mutants)

### 5.2 Implementation Duplication & Architecture
- `mutation_support_032.py` is an exact clone of `mutation_support_019.py` (differing only in docstring wording). It was created to comply with the project's historical "one helper per spec" convention.
- Both helpers enforce the exact same three guarantees:
  1. Target string is unambiguous: `assert source.count(old) == 1, 'mutation must hit exactly one location'`
  2. Unmutated control passes: `oracle()`
  3. Mutant is caught via `AssertionError`: `assert caught, 'semantic mutant survived'`
  4. Source integrity is validated before and after: `assert hashlib.sha256(path.read_bytes()).digest() == digest`
- **Migration Impact**: Both helpers read `Path(module.__file__).read_text()`. If packaging moves `scripts/` to `src/qmb/`, `module.__file__` automatically resolves to the new location, but every single `old` target string containing exact whitespace remains vulnerable to any formatting normalization applied during packaging.

---

## 6. Silent Failure Analysis: Assertions That Could Always Pass

A critical vulnerability category identified in this census is tests whose assertions **pass silently** (returning green) even when the underlying contract is violated or when files are moved or refactored.

### 6.1 Forbidden Module Boundary Checks Under Package Qualification
- **Vulnerable Sites**:
  - `tests/test_estimators.py`: `test_estimators_imports_no_forbidden_project_module`
  - `tests/test_ml_signal.py`: `test_ml_signal_imports_no_forbidden_project_module`
  - `tests/test_model_cv.py`: `test_model_cv_imports_no_forbidden_project_module`
  - `tests/test_portfolio_risk.py`: `test_no_signal_accounting_or_data_module_is_imported`
  - `tests/test_targets.py`: `test_neither_module_imports_the_harness`
  - `tests/test_feature_set_comparison.py`: `test_no_external_parallelism_library_is_imported`
- **Silent Mechanism**:
  In each of these suites, the AST inspection helper extracts imported names as:
  ```python
  if isinstance(node, ast.Import):
      modules.update(alias.name.split(".")[0] for alias in node.names)
  elif isinstance(node, ast.ImportFrom) and node.module:
      modules.add(node.module.split(".")[0])
  ```
  And then asserts:
  ```python
  self.assertEqual(modules & forbidden, set())
  ```
  1. **Package qualification bypass**: When migrated to `src/qmb/`, an import written as `from qmb.signals import ...` or `import qmb.signals` yields `node.module.split(".")[0] == "qmb"`. Because `"qmb"` is not in `forbidden` (which expects `"signals"`), `modules & forbidden` is `set()`. The test **passes silently** despite importing a forbidden module.
  2. **Relative import omission**: For `from . import signals` or `from .signals import ...`, if `node.module` is `None` (relative import without module name), `elif isinstance(node, ast.ImportFrom) and node.module:` evaluates to `False`. The import is completely skipped and never added to `modules`, passing silently.

### 6.2 Broker Import Guard Over Empty Matches
- **Vulnerable Site**:
  - `tests/test_order_gateway.py`: `BrokerImportGuardTests.test_production_broker_imports_always_import_live_gate`
- **Silent Mechanism**:
  The test collects offenders by walking hardcoded directory roots:
  ```python
  roots = [REPO_ROOT / "scripts", REPO_ROOT / "reports"]
  offenders = [
      path.relative_to(REPO_ROOT).as_posix()
      for root in roots
      for path in root.rglob("*.py")
      if broker_import_without_gate(path)
  ]
  self.assertEqual(offenders, [], f"broker modules missing LiveSafetyGate: {offenders}")
  ```
  Currently, there are **0 files** in the repository importing any broker library from `BROKER_CLIENT_ROOTS`. The list `offenders` is empty (`[]`), and `self.assertEqual(offenders, [])` passes trivially. If a broker adapter is added outside `scripts/` or `reports/` (e.g. in `src/qmb/` or `adapters/`), or if `scripts` is moved, the loop scans zero matching files and **passes silently**. Furthermore, `_imports(path)` checks `if node.module in {"live_safety_gate", "scripts.live_safety_gate"}`; if imported as `from qmb.live_safety_gate import LiveSafetyGate`, `imports_live_gate` remains `False`.

### 6.3 Research Call Bypass Guard Directory Hardcoding
- **Vulnerable Site**:
  - `tests/test_033_trial_instrumentation.py`: `test_inventory_and_production_guard` calling `bypasses(ROOT)`
- **Silent Mechanism**:
  `bypasses()` hardcodes:
  ```python
  for folder in ("scripts", "reports/api"):
      for path in (root / folder).rglob("*.py"):
  ```
  If `scripts` is migrated to `src/qmb`, `(root / "scripts").rglob("*.py")` generates an empty sequence without error. `bypasses(ROOT)` returns `[]`, and:
  ```python
  assert not bypasses(ROOT), "uninstrumented research calls: " + "; ".join(bypasses(ROOT))
  ```
  **passes silently** with zero files evaluated.
  Additionally, `bypasses()` only extracts aliases from `ast.ImportFrom`. If a primitive is imported via `import backtest_harness as bt` and called as `bt.run_backtest`, or aliased via assignment `run = run_backtest`, the alias dictionary does not resolve it, allowing uninstrumented calls to pass undetected.

### 6.4 Static Fixture Existence Assertion
- **Vulnerable Site**:
  - `tests/test_033_trial_instrumentation.py`: `test_inventory_and_production_guard`
- **Silent Mechanism**:
  ```python
  data = json.loads((ROOT / "tests/fixtures/spec_033/runner_inventory.json").read_text(encoding="utf-8"))
  assert data["calls"]
  ```
  This assertion evaluates a committed static JSON fixture file, not live code. It will always pass regardless of whether the actual production code contains uninstrumented runners or changed paths.

### 6.5 Glob-Based Source Tests Against Moved Directories
- **Vulnerable Sites**:
  - `tests/test_no_fabricated_values.py`: `test_route_modules_carry_no_fabricated_literal`
  - `tests/test_no_fabricated_values.py`: `test_terminal_components_carry_no_fabricated_literal`
- **Silent Mechanism**:
  Both tests initialize `found = []` and iterate over `ROUTES_DIR.glob("*.py")` and `WEB_SRC.rglob("*.ts*")`. If directory paths change or files move during a frontend/backend reorganization, the glob returns `[]`, `found` remains empty, and `self.assertEqual(found, [])` **passes silently** without inspecting any files.
