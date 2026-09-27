# Migration Inventory: `scripts/` to `src/qmb/` (Spec 040)

> **Inventory Scope**: Migration inventory and pre-flight analysis for packaging `Quant-ML-Bot` from a flat, unversioned `scripts/` directory (31 top-level modules, zero `__init__.py`, imported via `sys.path.insert` in `tests/context.py`) into an installable Python package at `src/qmb/` configured via `pyproject.toml`.
>
> **Completeness Guarantee**: Exhaustive codebase analysis covering all `.py` files, workflows, documentation, shell scripts, test assertions, and path constructions outside `venv/`, `.git/`, `node_modules/`, and `data/cache/`.

---

## Table of Contents
1. [Import Sites](#1-import-sites)
2. [Sys.path Manipulation & Import Behavior](#2-syspath-manipulation--import-behavior)
3. [Direct Script Invocations](#3-direct-script-invocations)
4. [Name Collision Risk](#4-name-collision-risk)
5. [Files That Would Move](#5-files-that-would-move)
6. [Surprises & Hidden Breakages](#6-surprises--hidden-breakages)

---

## 1. Import Sites

Every intra-project import in the repository where the target module is one of the 31 files in `scripts/`. Grouped by source file, with exact line numbers and statements.

**Summary Metrics**:
- **Total files importing `scripts/` modules**: 61 files
- **Total intra-project import statements**: 176 statements
- **Breakdown by directory**:
  - `scripts/`: 21 files, 54 import statements
  - `tests/`: 34 files, 100 import statements
  - `reports/`: 5 files, 11 import statements
  - `docs/`: 1 file, 11 import statements

### 1.1 `scripts/` Intra-Library Imports

#### `scripts/autocorrelation_check.py` (1 statement)
```python
scripts/autocorrelation_check.py:11: from data import download_market_data
```

#### `scripts/backtest_harness.py` (1 statement)
```python
scripts/backtest_harness.py:6: from metrics import validate_costs
```

#### `scripts/data_pipeline_sanity_check.py` (2 statements)
```python
scripts/data_pipeline_sanity_check.py:8: from data import cache_path, download_market_data, find_missing_bars
scripts/data_pipeline_sanity_check.py:9: from plotting import plt, save_figure
```

#### `scripts/estimators.py` (1 statement)
```python
scripts/estimators.py:35: from walk_forward_cv import walk_forward_splits
```

#### `scripts/feature_diagnostics.py` (2 statements)
```python
scripts/feature_diagnostics.py:36: from data import download_market_data
scripts/feature_diagnostics.py:37: from features import FEATURE_SETS, build_features, feature_columns
```

#### `scripts/feature_set_comparison.py` (5 statements)
```python
scripts/feature_set_comparison.py:77: from trial_runner import research_attempt, research_config
scripts/feature_set_comparison.py:94: from data import download_market_data
scripts/feature_set_comparison.py:95: from estimators import CLASSIFICATION, ESTIMATOR_REGISTRY, REGRESSION
scripts/feature_set_comparison.py:96: from features import build_features, feature_columns
scripts/feature_set_comparison.py:97: from model_cv import nested_walk_forward
```

#### `scripts/features.py` (2 statements)
```python
scripts/features.py:18: from signals import sma_crossover_signal
scripts/features.py:19: from targets import LABEL_COLUMN, build_target
```

#### `scripts/logistic_baseline.py` (6 statements)
```python
scripts/logistic_baseline.py:3: from trial_runner import research_attempt, research_config
scripts/logistic_baseline.py:8: from data import cache_path, download_market_data
scripts/logistic_baseline.py:9: from ma_crossover_backtest import baseline_results, mean_holding_bars
scripts/logistic_baseline.py:10: from signals import sma_crossover_signal
scripts/logistic_baseline.py:11: from backtest_harness import run_backtest, summarize_trades
scripts/logistic_baseline.py:12: from walk_forward_cv import walk_forward_splits
```

#### `scripts/ma_crossover_backtest.py` (5 statements)
```python
scripts/ma_crossover_backtest.py:7: from trial_runner import research_attempt, research_config
scripts/ma_crossover_backtest.py:12: from backtest_harness import run_backtest, summarize_trades
scripts/ma_crossover_backtest.py:13: from data import cache_path, download_market_data
scripts/ma_crossover_backtest.py:14: from plotting import plt, save_figure
scripts/ma_crossover_backtest.py:15: from signals import buy_and_hold_signal, random_signal, sma_crossover_signal
```

#### `scripts/metrics.py` (2 statements)
```python
scripts/metrics.py:17: from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
scripts/metrics.py:18: from cost_utils import risk_free_log_return, validate_costs
```

#### `scripts/ml_signal.py` (1 statement)
```python
scripts/ml_signal.py:47: from cost_utils import validate_costs
```

#### `scripts/model_cv.py` (3 statements)
```python
scripts/model_cv.py:33: from trial_runner import research_attempt, research_config
scripts/model_cv.py:41: from estimators import ( CLASSIFICATION, REGRESSION, TASKS, build_estimator, get_spec, model_row_masks, param_grid_points, )
scripts/model_cv.py:50: from walk_forward_cv import ( DEFAULT_INITIAL_TRAIN_MONTHS, DEFAULT_TEST_MONTHS, walk_forward_splits, )
```

#### `scripts/multi_ticker_comparison.py` (10 statements)
```python
scripts/multi_ticker_comparison.py:47: from trial_runner import research_attempt, research_config
scripts/multi_ticker_comparison.py:54: from data import cache_path, download_market_data
scripts/multi_ticker_comparison.py:55: from estimators import REGRESSION
scripts/multi_ticker_comparison.py:56: from features import build_features, feature_columns
scripts/multi_ticker_comparison.py:57: from ma_crossover_backtest import mean_holding_bars
scripts/multi_ticker_comparison.py:58: from backtest_harness import run_backtest
scripts/multi_ticker_comparison.py:59: from metrics import performance_summary
scripts/multi_ticker_comparison.py:60: from ml_signal import log_hurdle, positions_from_predicted_return, signal_from_positions
scripts/multi_ticker_comparison.py:61: from model_cv import nested_walk_forward
scripts/multi_ticker_comparison.py:62: from signals import buy_and_hold_signal, random_signal
```

#### `scripts/order_gateway.py` (1 statement)
```python
scripts/order_gateway.py:13: from live_safety_gate import ( ALLOW, BrokerSnapshot, GateDecision, LiveSafetyGate, OrderIntent, )
```

#### `scripts/portfolio_risk.py` (1 statement)
```python
scripts/portfolio_risk.py:46: from constants import TRADING_DAYS_PER_YEAR
```

#### `scripts/return_stats.py` (4 statements)
```python
scripts/return_stats.py:7: from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
scripts/return_stats.py:8: from cost_utils import risk_free_log_return
scripts/return_stats.py:9: from data import cache_path, download_market_data
scripts/return_stats.py:10: from plotting import plt, save_figure
```

#### `scripts/selection_bias.py` (3 statements)
```python
scripts/selection_bias.py:16: from constants import TRADING_DAYS_PER_YEAR, RISK_FREE_RATE_ANNUAL
scripts/selection_bias.py:17: from metrics import mean_log_return_se
scripts/selection_bias.py:18: from trial_registry import canonical_json, digest, validate_rows
```

#### `scripts/stationarity_check.py` (1 statement)
```python
scripts/stationarity_check.py:12: from data import download_market_data
```

#### `scripts/trial_backfill.py` (1 statement)
```python
scripts/trial_backfill.py:8: from trial_registry import canonical_json, digest, immutable_write
```

#### `scripts/trial_runner.py` (1 statement)
```python
scripts/trial_runner.py:13: from trial_registry import CONFIG_FIELDS, ROOT, TrialLedger, relative_path
```

#### `scripts/walk_forward_cv.py` (1 statement)
```python
scripts/walk_forward_cv.py:14: from data import download_market_data
```

### 1.2 `tests/` Test Suite Imports

#### `tests/spec033_pbo_profile.py` (1 statement)
```python
tests/spec033_pbo_profile.py:17: from selection_bias import matrix_pbo
```

#### `tests/test_019_calendar.py` (4 statements)
```python
tests/test_019_calendar.py:6: import features as ft
tests/test_019_calendar.py:7: import estimators as es
tests/test_019_calendar.py:8: import model_cv as cv
tests/test_019_calendar.py:9: import ml_signal as ms
```

#### `tests/test_019_conventions.py` (3 statements)
```python
tests/test_019_conventions.py:5: import metrics as mt
tests/test_019_conventions.py:6: import ml_signal as ms
tests/test_019_conventions.py:7: import backtest_harness as bt
```

#### `tests/test_019_ledger.py` (1 statement)
```python
tests/test_019_ledger.py:5: import backtest_harness as bt
```

#### `tests/test_019_metrics.py` (2 statements)
```python
tests/test_019_metrics.py:5: import metrics as mt
tests/test_019_metrics.py:6: import backtest_harness as bt
```

#### `tests/test_019_prices.py` (4 statements)
```python
tests/test_019_prices.py:5: import data as dt
tests/test_019_prices.py:6: import backtest_harness as bt
tests/test_019_prices.py:7: import metrics as mt
tests/test_019_prices.py:8: import targets as tg
```

#### `tests/test_019_targets.py` (1 statement)
```python
tests/test_019_targets.py:5: import targets as tg
```

#### `tests/test_020_unadjusted_price_data.py` (2 statements)
```python
tests/test_020_unadjusted_price_data.py:20: import data
tests/test_020_unadjusted_price_data.py:101: from backtest_harness import run_backtest
```

#### `tests/test_033_dsr.py` (1 statement)
```python
tests/test_033_dsr.py:10: from trial_registry import canonical_json
```

#### `tests/test_033_pbo.py` (1 statement)
```python
tests/test_033_pbo.py:12: from trial_registry import digest
```

#### `tests/test_033_trial_ledger.py` (3 statements)
```python
tests/test_033_trial_ledger.py:17: import trial_registry
tests/test_033_trial_ledger.py:157: from trial_runner import current_ledger
tests/test_033_trial_ledger.py:190: from trial_runner import current_ledger, injected_ledger
```

#### `tests/test_backtest_harness.py` (1 statement)
```python
tests/test_backtest_harness.py:8: from backtest_harness import run_backtest, summarize_trades
```

#### `tests/test_clean_clone_037.py` (3 statements)
```python
tests/test_clean_clone_037.py:11: import feature_set_comparison as fsc
tests/test_clean_clone_037.py:168: import multi_ticker_comparison as mtc
tests/test_clean_clone_037.py:190: import multi_ticker_comparison as mtc
```

#### `tests/test_cost_utils.py` (1 statement)
```python
tests/test_cost_utils.py:9: from cost_utils import risk_free_log_return, validate_costs
```

#### `tests/test_data.py` (2 statements)
```python
tests/test_data.py:20: import data
tests/test_data.py:21: from data import ( download_market_data, find_missing_bars, is_market_holiday, market_holidays, trading_days, )
```

#### `tests/test_data_pipeline_sanity_check.py` (2 statements)
```python
tests/test_data_pipeline_sanity_check.py:20: import data
tests/test_data_pipeline_sanity_check.py:21: from data_pipeline_sanity_check import MAX_GAPS_LISTED, report_calendar_gaps
```

#### `tests/test_estimators.py` (6 statements)
```python
tests/test_estimators.py:11: from estimators import ( CLASSIFICATION, ESTIMATOR_REGISTRY, MAX_GRID_POINTS, REGRESSION, build_estimator, fit_predict_walk_forward, final_estimator, fitted_scaler, get_spec, param_grid_points, )
tests/test_estimators.py:23: from features import SCALE_FREE_FEATURE_COLUMNS, build_features
tests/test_estimators.py:24: from logistic_baseline import FEATURE_COLUMNS as BASELINE_FEATURE_COLUMNS
tests/test_estimators.py:25: from logistic_baseline import walk_forward_predictions
tests/test_estimators.py:26: from walk_forward_cv import walk_forward_splits
tests/test_estimators.py:317: import estimators
```

#### `tests/test_feature_scaling.py` (9 statements)
```python
tests/test_feature_scaling.py:32: from estimators import ( CLASSIFICATION, REGRESSION, build_estimator, fit_predict_walk_forward, fitted_scaler, )
tests/test_feature_scaling.py:39: from feature_set_comparison import ( compare_classification, compare_regression, )
tests/test_feature_scaling.py:43: import estimators
tests/test_feature_scaling.py:44: import feature_set_comparison
tests/test_feature_scaling.py:45: from feature_diagnostics import ( condition_number, diagnose, format_report, max_abs_offdiagonal_correlation, variance_inflation_factors, )
tests/test_feature_scaling.py:52: from features import ( DERIVED_RATIO_COLUMNS, LEVEL_FEATURE_COLUMNS, SCALE_FREE_FEATURE_COLUMNS, build_features, feature_columns, )
tests/test_feature_scaling.py:59: from walk_forward_cv import walk_forward_splits
tests/test_feature_scaling.py:681: from estimators import param_grid_points
tests/test_feature_scaling.py:786: import model_cv
```

#### `tests/test_feature_set_comparison.py` (3 statements)
```python
tests/test_feature_set_comparison.py:43: import feature_set_comparison as fsc
tests/test_feature_set_comparison.py:44: from estimators import ESTIMATOR_REGISTRY
tests/test_feature_set_comparison.py:45: from feature_set_comparison import ( FEATURE_SET_A, FEATURE_SET_B, THREAD_LIMIT_VARS, ComparisonTask, _evaluate_feature_set_task, _pinned_thread_environment, _worker_init, build_tasks, compare_all_entries, compare_all_entries_parallel, format_report, pair_results, )
```

#### `tests/test_live_safety_gate.py` (2 statements)
```python
tests/test_live_safety_gate.py:20: import live_safety_gate as lsg
tests/test_live_safety_gate.py:21: from live_safety_gate import ( ACTION_BLOCK_NEW, ACTION_CANCEL_RISK_ADDING, ACTION_KILL_LATCHED, ACTION_REDUCE_ONLY, ALLOW, BrokerKillQuery, BrokerSnapshot, ConfigMismatchError, DENY, DENY_BROKER_STATUS, DENY_CLOCK_SKEW, DENY_DUPLICATE_ORDER, DENY_KILL_LATCHED, DENY_LOSS_HALT, DENY_MAX_GROSS_PCT, DENY_MAX_POSITION_PCT, DENY_NON_POSITIVE_EQUITY, DENY_PRICE_UNAVAILABLE, DENY_RECONCILIATION_HALT, DENY_SHORT_NOT_SUPPORTED, DENY_STALE_SNAPSHOT, KILL_BROKER_CANCEL_PENDING, KILL_BROKER_DISABLE_UNVERIFIED, KILL_CONFIRMED, KILL_LOCAL_BLOCKED, KILL_RECONCILING, OrderIntent, SafetyConfig, SafetyGate, new_client_order_id, )
```

#### `tests/test_logistic_baseline.py` (3 statements)
```python
tests/test_logistic_baseline.py:9: from logistic_baseline import ( FEATURE_COLUMNS, _signal_from_predictions, build_ml_signal, evaluate_walk_forward, walk_forward_predictions, )
tests/test_logistic_baseline.py:16: from walk_forward_cv import walk_forward_splits
tests/test_logistic_baseline.py:137: from backtest_harness import run_backtest
```

#### `tests/test_ma_crossover_backtest.py` (3 statements)
```python
tests/test_ma_crossover_backtest.py:14: from backtest_harness import run_backtest, summarize_trades
tests/test_ma_crossover_backtest.py:15: from ma_crossover_backtest import ( baseline_results, format_comparison, mean_holding_bars, )
tests/test_ma_crossover_backtest.py:20: from signals import sma_crossover_signal
```

#### `tests/test_metrics.py` (6 statements)
```python
tests/test_metrics.py:17: from backtest_harness import run_backtest
tests/test_metrics.py:18: from constants import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR
tests/test_metrics.py:19: from metrics import ( equity_curve, equity_log_returns, max_drawdown, performance_summary, sharpe_ratio, )
tests/test_metrics.py:534: import constants
tests/test_metrics.py:535: import return_stats
tests/test_metrics.py:545: import constants
```

#### `tests/test_ml_signal.py` (7 statements)
```python
tests/test_ml_signal.py:18: from backtest_harness import run_backtest
tests/test_ml_signal.py:19: from ml_signal import ( cost_hurdle, log_hurdle, positions_from_direction, positions_from_predicted_return, signal_from_positions, )
tests/test_ml_signal.py:657: from logistic_baseline import _signal_from_predictions
tests/test_ml_signal.py:766: from estimators import CLASSIFICATION, fit_predict_walk_forward
tests/test_ml_signal.py:767: from targets import DIRECTION, FORWARD_RETURN, build_target
tests/test_ml_signal.py:790: from estimators import CLASSIFICATION, ESTIMATOR_REGISTRY
tests/test_ml_signal.py:831: from estimators import ESTIMATOR_REGISTRY
```

#### `tests/test_model_cv.py` (7 statements)
```python
tests/test_model_cv.py:20: import estimators
tests/test_model_cv.py:21: from estimators import CLASSIFICATION, ESTIMATOR_REGISTRY, REGRESSION
tests/test_model_cv.py:22: from features import ( LEVEL_FEATURE_COLUMNS, SCALE_FREE_FEATURE_COLUMNS, build_features, )
tests/test_model_cv.py:27: from logistic_baseline import FEATURE_COLUMNS as BASELINE_FEATURE_COLUMNS
tests/test_model_cv.py:28: from model_cv import ( INNER_SCORE_COLUMNS, inner_splits_over, nested_walk_forward, score_fold, tune_on_fold, )
tests/test_model_cv.py:35: from walk_forward_cv import walk_forward_splits
tests/test_model_cv.py:38: import model_cv
```

#### `tests/test_multi_ticker_comparison.py` (1 statement)
```python
tests/test_multi_ticker_comparison.py:21: import multi_ticker_comparison as mtc
```

#### `tests/test_order_gateway.py` (2 statements)
```python
tests/test_order_gateway.py:11: from live_safety_gate import ACTION_BLOCK_NEW, ALLOW, DENY, GateDecision
tests/test_order_gateway.py:12: from order_gateway import OrderDeniedError, submit_order
```

#### `tests/test_portfolio_risk.py` (4 statements)
```python
tests/test_portfolio_risk.py:27: from constants import TRADING_DAYS_PER_YEAR
tests/test_portfolio_risk.py:28: from portfolio_risk import ( RECOMMENDED_CONFIG, LossCapGuard, RiskConfig, apply_entry_halt, apply_gross_cap, correlation_adjusted_weights, log_returns, loss_cap_history, position_overlap, realized_volatility, target_weights, trailing_correlation, volatility_target_weights, )
tests/test_portfolio_risk.py:1227: from multi_ticker_comparison import TICKER_UNIVERSE
tests/test_portfolio_risk.py:1302: from multi_ticker_comparison import TICKER_UNIVERSE
```

#### `tests/test_return_stats.py` (2 statements)
```python
tests/test_return_stats.py:11: import metrics
tests/test_return_stats.py:12: import return_stats
```

#### `tests/test_safety_router.py` (1 statement)
```python
tests/test_safety_router.py:14: from live_safety_gate import BrokerSnapshot, OrderIntent, SafetyConfig, SafetyGate
```

#### `tests/test_signals.py` (2 statements)
```python
tests/test_signals.py:8: from backtest_harness import run_backtest
tests/test_signals.py:9: from signals import buy_and_hold_signal, random_signal, sma_crossover_signal
```

#### `tests/test_targets.py` (7 statements)
```python
tests/test_targets.py:15: import features as features_module
tests/test_targets.py:16: import targets as targets_module
tests/test_targets.py:17: from features import ( LEVEL_FEATURE_COLUMNS, SCALE_FREE_FEATURE_COLUMNS, build_features, feature_columns, )
tests/test_targets.py:23: from targets import ( LABEL_COLUMN, build_target, direction_label, forward_log_return_label, )
tests/test_targets.py:495: from logistic_baseline import FEATURE_COLUMNS as baseline_columns
tests/test_targets.py:506: import logistic_baseline
tests/test_targets.py:547: import logistic_baseline
```

#### `tests/test_trial_registry.py` (1 statement)
```python
tests/test_trial_registry.py:3: import trial_registry
```

#### `tests/test_walk_forward_cv.py` (2 statements)
```python
tests/test_walk_forward_cv.py:12: from walk_forward_cv import walk_forward_splits # noqa: E402
tests/test_walk_forward_cv.py:284: from logistic_baseline import FEATURE_COLUMNS, evaluate_walk_forward
```

### 1.3 `reports/` API and Route Imports

#### `reports/api/routes/backtest.py` (5 statements)
```python
reports/api/routes/backtest.py:19: from backtest_harness import run_backtest, summarize_trades
reports/api/routes/backtest.py:20: from trial_runner import research_attempt, research_config
reports/api/routes/backtest.py:21: from ma_crossover_backtest import baseline_results, mean_holding_bars
reports/api/routes/backtest.py:22: from metrics import equity_curve, performance_summary
reports/api/routes/backtest.py:30: from signals import sma_crossover_signal
```

#### `reports/api/routes/data.py` (2 statements)
```python
reports/api/routes/data.py:19: from constants import TRADING_DAYS_PER_YEAR
reports/api/routes/data.py:20: from data import CACHE_DIR, find_missing_bars
```

#### `reports/api/routes/diagnostics.py` (2 statements)
```python
reports/api/routes/diagnostics.py:16: from feature_diagnostics import diagnose
reports/api/routes/diagnostics.py:17: from features import build_features, feature_columns
```

#### `reports/api/routes/ml_rundown.py` (1 statement)
```python
reports/api/routes/ml_rundown.py:24: from features import build_features
```

#### `reports/api/routes/safety.py` (1 statement)
```python
reports/api/routes/safety.py:15: from live_safety_gate import BrokerKillQuery, BrokerSnapshot, LiveSafetyGate
```

### 1.4 `docs/` Audit Probes Imports

#### `docs/audit-2026-09-12/probes.py` (11 statements)
```python
docs/audit-2026-09-12/probes.py:19: import data
docs/audit-2026-09-12/probes.py:20: import features
docs/audit-2026-09-12/probes.py:21: import feature_diagnostics as fd
docs/audit-2026-09-12/probes.py:22: import feature_set_comparison as fc
docs/audit-2026-09-12/probes.py:23: import metrics
docs/audit-2026-09-12/probes.py:24: import multi_ticker_comparison as mt
docs/audit-2026-09-12/probes.py:25: import model_cv
docs/audit-2026-09-12/probes.py:27: from walk_forward_cv import walk_forward_splits
docs/audit-2026-09-12/probes.py:28: import portfolio_risk as risk
docs/audit-2026-09-12/probes.py:29: from backtest_harness import run_backtest, summarize_trades
docs/audit-2026-09-12/probes.py:30: from targets import direction_label
```

### 1.6 Ambient Test Bootstrap Imports (`tests/context.py`)

In addition to direct imports of the 31 modules, **34 test files** import `tests/context.py` (either via `import context` or `from context import SCRIPTS_DIR`) solely to execute the `sys.path.insert(0, str(SCRIPTS_DIR))` side effect. Under an installed package, these 34 imports become obsolete and will be replaced by standard package imports (`from qmb import ...`).

| File | Line | Statement |
|---|---|---|
| `tests/api_fixtures.py` | 22 | `import context # noqa: F401 -- routes import scripts/ modules; see tests/context.py` |
| `tests/spec033_pbo_profile.py` | 15 | `from context import SCRIPTS_DIR` |
| `tests/test_019_calendar.py` | 5 | `import context` |
| `tests/test_019_conventions.py` | 4 | `import context` |
| `tests/test_019_ledger.py` | 4 | `import context` |
| `tests/test_019_metrics.py` | 4 | `import context` |
| `tests/test_019_prices.py` | 4 | `import context` |
| `tests/test_019_targets.py` | 4 | `import context` |
| `tests/test_033_backfill.py` | 5 | `from context import SCRIPTS_DIR` |
| `tests/test_033_dsr.py` | 8 | `from context import SCRIPTS_DIR` |
| `tests/test_033_trial_instrumentation.py` | 5 | `from context import SCRIPTS_DIR` |
| `tests/test_033_trial_ledger.py` | 16 | `from context import SCRIPTS_DIR` |
| `tests/test_backtest_harness.py` | 7 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_clean_clone_037.py` | 10 | `import context # noqa: F401` |
| `tests/test_cost_utils.py` | 8 | `import context # noqa: F401` |
| `tests/test_data.py` | 19 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_data_pipeline_sanity_check.py` | 19 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_estimators.py` | 10 | `from context import SCRIPTS_DIR` |
| `tests/test_feature_scaling.py` | 30 | `from context import SCRIPTS_DIR # noqa: F401` |
| `tests/test_feature_set_comparison.py` | 41 | `from context import SCRIPTS_DIR` |
| `tests/test_live_safety_gate.py` | 18 | `from context import SCRIPTS_DIR` |
| `tests/test_logistic_baseline.py` | 8 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_ma_crossover_backtest.py` | 13 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_metrics.py` | 16 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_ml_signal.py` | 17 | `from context import SCRIPTS_DIR` |
| `tests/test_model_cv.py` | 10 | `import contextlib` |
| `tests/test_model_cv.py` | 18 | `from context import SCRIPTS_DIR` |
| `tests/test_multi_ticker_comparison.py` | 19 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_order_gateway.py` | 10 | `import context # noqa: F401 -- makes scripts importable` |
| `tests/test_portfolio_risk.py` | 26 | `from context import SCRIPTS_DIR` |
| `tests/test_return_stats.py` | 10 | `import context # noqa: F401` |
| `tests/test_safety_router.py` | 13 | `import context # noqa: F401 -- makes scripts importable` |
| `tests/test_signals.py` | 7 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_targets.py` | 14 | `from context import SCRIPTS_DIR # noqa: F401 (import for the sys.path effect)` |
| `tests/test_trial_registry.py` | 2 | `from context import SCRIPTS_DIR` |

---

## 2. Sys.path Manipulation & Import Behavior

The repository currently mutates `sys.path` in multiple locations and relies on interpreter-dependent working directory behaviors to make flat modules importable. Here is the exhaustive inventory of all locations and mechanisms:

### 2.1 Explicit `sys.path.insert` / `sys.path.append` Call Sites

1. **`tests/context.py:11–13`** (Primary test suite bootstrap):
   ```python
   SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
   if str(SCRIPTS_DIR) not in sys.path:
       sys.path.insert(0, str(SCRIPTS_DIR))
   ```
   *Impact*: Executed as a side effect whenever `context` is imported by any test file.

2. **`tests/test_walk_forward_cv.py:10` & `tests/test_walk_forward_cv.py:281–283`** (Bypassed `context.py`):
   - Module preamble (line 10):
     ```python
     sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
     ```
   - Inside test method `test_evaluate_walk_forward_runs_without_error` (lines 281–283):
     ```python
     sys.path.insert(
         0, str(Path(__file__).resolve().parent.parent / "scripts")
     )
     from logistic_baseline import FEATURE_COLUMNS, evaluate_walk_forward
     ```
   *Impact*: Manual insertion written before `context.py` convention was adopted; contains redundant duplicate inside a test method.

3. **`tests/test_020_unadjusted_price_data.py:15–18`** (Bypassed `context.py`):
   ```python
   REPO_ROOT = Path(__file__).resolve().parents[1]
   SCRIPTS = REPO_ROOT / "scripts"
   if str(SCRIPTS) not in sys.path:
       sys.path.insert(0, str(SCRIPTS))
   ```
   *Impact*: Custom sys.path insertion without importing `context.py`.

4. **`reports/api/main.py:13–16`** (FastAPI entrypoint bootstrap):
   ```python
   REPO_ROOT = Path(__file__).resolve().parents[2]
   SCRIPTS_DIR = REPO_ROOT / "scripts"
   if str(SCRIPTS_DIR) not in sys.path:
       sys.path.insert(0, str(SCRIPTS_DIR))
   ```
   *Impact*: Injects `scripts/` so FastAPI application can import research modules at startup.

5. **`reports/api/routes/*.py`** (Route preambles with path resolution defects):
   - `reports/api/routes/backtest.py:14–17` (correct `parents[3]`):
     ```python
     REPO_ROOT = Path(__file__).resolve().parents[3]
     SCRIPTS_DIR = REPO_ROOT / "scripts"
     if str(SCRIPTS_DIR) not in sys.path: sys.path.insert(0, str(SCRIPTS_DIR))
     ```
   - `reports/api/routes/safety.py:10–13` (correct `parents[3]`):
     ```python
     REPO_ROOT = Path(__file__).resolve().parents[3]
     SCRIPTS_DIR = REPO_ROOT / "scripts"
     if str(SCRIPTS_DIR) not in sys.path: sys.path.insert(0, str(SCRIPTS_DIR))
     ```
   - `reports/api/routes/data.py:14–17` (**DEFECT**: uses `parents[2]`):
     ```python
     REPO_ROOT = Path(__file__).resolve().parents[2]  # Resolves to reports/, not repo root!
     SCRIPTS_DIR = REPO_ROOT / "scripts"             # Evaluates to reports/scripts/ (nonexistent)!
     if str(SCRIPTS_DIR) not in sys.path: sys.path.insert(0, str(SCRIPTS_DIR))
     ```
   - `reports/api/routes/diagnostics.py:11–14` (**DEFECT**: uses `parents[2]`):
     ```python
     REPO_ROOT = Path(__file__).resolve().parents[2]  # Same defect: points to reports/scripts
     SCRIPTS_DIR = REPO_ROOT / "scripts"
     if str(SCRIPTS_DIR) not in sys.path: sys.path.insert(0, str(SCRIPTS_DIR))
     ```
   - `reports/api/routes/ml_rundown.py:19–22` (**DEFECT**: uses `parents[2]`):
     ```python
     REPO_ROOT = Path(__file__).resolve().parents[2]  # Same defect: points to reports/scripts
     SCRIPTS_DIR = REPO_ROOT / "scripts"
     if str(SCRIPTS_DIR) not in sys.path: sys.path.insert(0, str(SCRIPTS_DIR))
     ```
   *Audit Finding 56*: These three routes only succeed because `reports/api/main.py` is loaded first, injecting the true `scripts/` directory before route modules are imported.

6. **`docs/audit-2026-09-12/probes.py:11–13`**:
   ```python
   ROOT = Path(__file__).resolve().parents[2]
   sys.path.insert(0, str(ROOT))
   sys.path.insert(0, str(ROOT / "scripts"))
   ```
   *Impact*: Adds both repo root (for `reports.api`) and `scripts/` (for research modules).

7. **`scripts/multi_ticker_comparison.py:399–402`** (Error message instruction string):
   ```python
   ./venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'scripts'); from data import download_market_data; download_market_data(...) "
   ```
   *Impact*: Instructions given to users explicitly instruct mutating sys.path in a one-liner.

### 2.2 Interpreter Default vs CWD-Relative Import Behaviors

1. **Direct execution of scripts (`python scripts/<name>.py`)**:
   - Python automatically prepends the directory containing the script (`scripts/`) to `sys.path[0]`.
   - This allows all 21 scripts that import other scripts (e.g. `from data import cache_path`) to work when run directly from the terminal or repo root, but *only* because of this interpreter default.

2. **Test runner invocations (`python -m pytest tests` vs `python -m unittest`)**:
   - When invoked as `python -m <runner>`, Python sets `sys.path[0]` to the Current Working Directory (the repo root).
   - `scripts/` is **not** on `sys.path`. Without `tests/context.py`, every intra-project import fails immediately.
   - Documented in `.specify/specs/017-position-sizing-risk/tasks.md:36`: `python -m unittest tests.test_portfolio_risk` failed because `tests/` was not on `sys.path`, failing before reaching the test module.

3. **CI Steps** (`.github/workflows/test.yml:19–20`, `.github/workflows/claude.yml:39–40`):
   - Steps run `pip install -r requirements.txt -r requirements-dev.txt` and `python -m pytest tests`.
   - Neither workflow runs `pip install -e .` or installs the project into the environment. Both rely completely on ambient cwd and `tests/context.py`.

4. **Shell Hooks** (`.claude/hooks/run-tests.ps1:1–2`):
   - Sets working directory to `(git rev-parse --show-toplevel)` and runs `python -m unittest discover -s tests`.

---

## 3. Direct Script Invocations

Every direct invocation pattern (`python scripts/<x>.py` or `python -m <x>`) across workflows, documentation, specs, shell files, and docstrings. These represent entry points that should be migrated to `[project.scripts]` in `pyproject.toml`.

### 3.1 Primary Documented CLI Scripts (`README.md:104–108`)
These are the user-facing entry points documented in the main README:

| Current Invocation | Proposed `[project.scripts]` Name | Target Function |
|---|---|---|
| `python scripts/data_pipeline_sanity_check.py` | `qmb-sanity` | `qmb.data_pipeline_sanity_check:main` |
| `python scripts/return_stats.py` | `qmb-return-stats` | `qmb.return_stats:main` |
| `python scripts/ma_crossover_backtest.py` | `qmb-ma-backtest` | `qmb.ma_crossover_backtest:main` |
| `python scripts/logistic_baseline.py` | `qmb-logistic-baseline` | `qmb.logistic_baseline:main` |
| `python scripts/multi_ticker_comparison.py` | `qmb-multi-ticker` | `qmb.multi_ticker_comparison:main` |

### 3.2 All Executable Scripts in `scripts/` (`if __name__ == '__main__':`)
Exhaustive list of all 12 modules in `scripts/` containing runnable `__main__` entry points:

| Module | Has Argparse | Entry Function | Role |
|---|---|---|---|
| `scripts/data_pipeline_sanity_check.py` | No | `main()` | Data pipeline sanity verification and plotting |
| `scripts/return_stats.py` | No | `main()` | Baseline descriptive statistics and Sharpe calculation |
| `scripts/ma_crossover_backtest.py` | No (sys.argv) | `main()` | Rule-based moving average crossover backtest |
| `scripts/logistic_baseline.py` | No | `main()` | Walk-forward logistic regression baseline |
| `scripts/multi_ticker_comparison.py` | Yes | `main()` | Five-ticker portfolio comparison across baselines |
| `scripts/feature_set_comparison.py` | Yes | `main()` | Parallel feature set A vs B comparison experiment |
| `scripts/feature_diagnostics.py` | No | `main()` | Collinearity, VIF, and condition number diagnostics |
| `scripts/stationarity_check.py` | No | `main()` | ADF and KPSS stationarity tests on raw and returns |
| `scripts/autocorrelation_check.py` | No | `main()` | Autocorrelation function and Ljung-Box test |
| `scripts/walk_forward_cv.py` | No | `main()` | Split generator visualization and sanity check |
| `scripts/scratch_aapl_correlations.py` | No | `main()` | Exploratory scratch script (AAPL correlations) |
| `scripts/scratch_multiticker_collinearity.py` | No | `main()` | Exploratory scratch script (Multi-ticker collinearity) |

### 3.3 Other Invocation Sites (API Server, Profilers, Mutation Runners)

1. **Reports Terminal API**:
   - `python -m reports.api.main` (or `uvicorn reports.api.main:app`)
   - Cited in: `reports/api/main.py:74`, `.specify/specs/018-terminal-truthfulness/quickstart.md:116`, `.specify/specs/018-terminal-truthfulness/research.md:183`
2. **Analytical Profilers & Tooling**:
   - `python tests/spec033_pbo_profile.py` (`tests/spec033_pbo_profile.py:1`)
3. **Mutation Test Drivers**:
   - `python tests/mutation/run_spec_018_mutants.py` (`tests/mutation/run_spec_018_mutants.py:3`)
   - `python tests/mutation/run_mutation_check.py` (`tests/mutation/run_mutation_check.py:84`)
4. **Test Runners**:
   - `python -m pytest tests` (Canonical command in `CLAUDE.md:156`, `README.md:114`, `.github/workflows/test.yml:20`)
   - `python -m unittest discover -s tests` (Legacy command in `.claude/hooks/run-tests.ps1:2`, older specs)

### 3.4 Exhaustive Invocation Citation Index

| Target | File | Line | Citation Text |
|---|---|---|---|
| `data_pipeline_sanity_check.py` | `README.md` | 104 | `python scripts/data_pipeline_sanity_check.py   # fetch, inspect, and plot one pr` |
| `return_stats.py` | `README.md` | 105 | `python scripts/return_stats.py                 # volatility, skew, kurtosis, dra` |
| `ma_crossover_backtest.py` | `README.md` | 106 | `python scripts/ma_crossover_backtest.py        # rule-based SMA crossover baseli` |
| `logistic_baseline.py` | `README.md` | 107 | `python scripts/logistic_baseline.py            # walk-forward logistic baseline` |
| `multi_ticker_comparison.py` | `README.md` | 108 | `python scripts/multi_ticker_comparison.py      # the five-ticker panel compariso` |
| `unittest` | `.specify/specs/018-terminal-truthfulness/quickstart.md` | 75 | `python -m unittest tests.test_feature_scaling tests.test_ma_crossover_backtest -` |
| `reports.api.main` | `.specify/specs/018-terminal-truthfulness/quickstart.md` | 116 | `python -m reports.api.main` |
| `reports.api.main` | `.specify/specs/018-terminal-truthfulness/research.md` | 183 | ``uvicorn reports.api.main:app` and `python -m reports.api.main` are` |
| `pytest` | `.specify/specs/021-finish-spec-019-migration/quickstart.md` | 52 | `| B | `python -m pytest tests/test_signals.py tests/test_ma_crossover_backtest.p` |
| `pytest` | `.specify/specs/021-finish-spec-019-migration/quickstart.md` | 76 | `python -m pytest tests/test_ma_crossover_backtest.py -k "baseline or random or s` |
| `ma_crossover_backtest.py` | `.specify/specs/021-finish-spec-019-migration/quickstart.md` | 132 | ``python scripts/ma_crossover_backtest.py` and `python scripts/logistic_baseline.` |
| `pytest` | `.specify/specs/021-finish-spec-019-migration/tasks.md` | 97 | `**Independent test.** `python -m pytest tests/test_signals.py tests/test_ma_cros` |
| `pytest` | `.specify/specs/021-finish-spec-019-migration/tasks.md` | 652 | `| SC-004: 20/20 seeds, buy-and-hold 1 trade, stated once | `python -m pytest tes` |
| `ma_crossover_backtest.py` | `.specify/specs/036-unadjusted-caller-wiring/quickstart.md` | 71 | `python scripts/ma_crossover_backtest.py ; echo "exit=$?"` |
| `ma_crossover_backtest.py` | `.specify/specs/036-unadjusted-caller-wiring/spec.md` | 326 | `Camden runs `python scripts/ma_crossover_backtest.py`. If a valid AAPL bundle` |
| `ma_crossover_backtest.py` | `.specify/specs/036-unadjusted-caller-wiring/tasks.md` | 83 | `Add a subprocess case: `python scripts/ma_crossover_backtest.py`, with its data ` |
| `pytest` | `.specify/specs/036-unadjusted-caller-wiring/tasks.md` | 216 | ``python -m pytest tests -q --junitxml=.specify/specs/036-unadjusted-caller-wirin` |
| `ma_crossover_backtest.py` | `.specify/specs/036-unadjusted-caller-wiring/contracts/cli-and-api.md` | 3 | `## 1. `python scripts/ma_crossover_backtest.py [--manifest PATH]`` |
| `reports.api.main.` | `reports/api/main.py` | 74 | `"""Entrypoint for running the API directly via python -m reports.api.main."""` |

---

## 4. Name Collision Risk

Assessment of the 31 module names against Python standard library modules, PyPI packages, and standard packaging conventions if installed as top-level modules in `site-packages`.

| Module Name | Risk Level | What It Shadows / Collision Reason |
|---|---|---|
| `data.py` | **CRITICAL / UNSAFE** | Shadows `data` on PyPI, ambient `data/` project directories on PYTHONPATH, and standard data namespaces (e.g. `torch.utils.data`, `nltk.data`). |
| `metrics.py` | **CRITICAL / UNSAFE** | Shadows `metrics` on PyPI and collides directly with `sklearn.metrics`, `torchmetrics`, and Prometheus metrics modules. |
| `signals.py` | **CRITICAL / UNSAFE** | Shadows `signals` on PyPI (event dispatchers like Blinker/Django), and is dangerously close to standard library `signal`. |
| `features.py` | **CRITICAL / UNSAFE** | Shadows `features` on PyPI (feature algebra/feature flags), and generic feature engineering modules. |
| `targets.py` | **HIGH / UNSAFE** | Shadows `targets` on PyPI (workflow/pipeline target management), and generic build target modules. |
| `constants.py` | **HIGH / UNSAFE** | Shadows `constants` on PyPI (environment/physical constants package), and common project-level configuration modules. |
| `plotting.py` | **HIGH / UNSAFE** | Shadows `plotting` on PyPI and collides with pandas/statsmodels internal plotting submodules. |
| `estimators.py` | **HIGH / UNSAFE** | Shadows `estimators` on PyPI and collides with scikit-learn / statsmodels estimator conventions. |
| `return_stats.py` | **MEDIUM / CAUTION** | Shadows `return-stats` on PyPI and generic financial return calculation packages. |
| `portfolio_risk.py` | **MEDIUM / CAUTION** | Generic financial risk term; conflicts with quantitative risk management packages on PyPI. |
| `cost_utils.py` | **MEDIUM / CAUTION** | Generic utility name; potential collision with cost accounting or financial utility packages. |
| `model_cv.py` | **MEDIUM / CAUTION** | Potential collision with cross-validation utility packages (`model-cv`). |
| `selection_bias.py` | **MEDIUM / CAUTION** | Academic statistical term; potential collision with econometric bias estimation packages. |
| `backtest_harness.py` | **LOW / SAFE** | Domain-specific, but generic backtesting terminology. |
| `order_gateway.py` | **LOW / SAFE** | Domain-specific execution seam; unlikely top-level collision. |
| `live_safety_gate.py` | **LOW / SAFE** | Project-specific safety gate implementation. |
| `walk_forward_cv.py` | **LOW / SAFE** | Domain-specific cross-validation methodology. |
| `trial_registry.py` | **LOW / SAFE** | Project-specific hash-chained ledger. |
| `trial_runner.py` | **LOW / SAFE** | Project-specific research attempt runner. |
| `trial_backfill.py` | **LOW / SAFE** | Project-specific trial backfill utility. |
| `logistic_baseline.py` | **LOW / SAFE** | Specific model baseline name. |
| `ma_crossover_backtest.py` | **LOW / SAFE** | Specific strategy backtest name. |
| `multi_ticker_comparison.py` | **LOW / SAFE** | Specific comparison experiment name. |
| `feature_set_comparison.py` | **LOW / SAFE** | Specific experiment comparison script. |
| `feature_diagnostics.py` | **LOW / SAFE** | Specific diagnostic script name. |
| `data_pipeline_sanity_check.py` | **LOW / SAFE** | Specific sanity-check utility name. |
| `stationarity_check.py` | **LOW / SAFE** | Specific time-series diagnostic script. |
| `autocorrelation_check.py` | **LOW / SAFE** | Specific time-series diagnostic script. |
| `ml_signal.py` | **LOW / SAFE** | Specific signal generation module. |
| `scratch_aapl_correlations.py` | **LOW / ABERRANT** | Exploratory scratch script; should not exist in production package. |
| `scratch_multiticker_collinearity.py` | **LOW / ABERRANT** | Exploratory scratch script; should not exist in production package. |

---

## 5. Files That Would Move

The full list of 31 modules moving from `scripts/` to `src/qmb/`, plus the new package root `src/qmb/__init__.py`:

| # | Current Path | Proposed `src/qmb/` Path | Architectural Role |
|---|---|---|---|
| 1 | `scripts/autocorrelation_check.py` | `src/qmb/autocorrelation_check.py` | Diagnostic script |
| 2 | `scripts/backtest_harness.py` | `src/qmb/backtest_harness.py` | Core execution & accounting |
| 3 | `scripts/constants.py` | `src/qmb/constants.py` | Project constants |
| 4 | `scripts/cost_utils.py` | `src/qmb/cost_utils.py` | Cost modeling & validation |
| 5 | `scripts/data.py` | `src/qmb/data.py` | Data fetching & caching |
| 6 | `scripts/data_pipeline_sanity_check.py` | `src/qmb/data_pipeline_sanity_check.py` | Data pipeline verification |
| 7 | `scripts/estimators.py` | `src/qmb/estimators.py` | Estimator registry & specs |
| 8 | `scripts/feature_diagnostics.py` | `src/qmb/feature_diagnostics.py` | Collinearity & VIF diagnostics |
| 9 | `scripts/feature_set_comparison.py` | `src/qmb/feature_set_comparison.py` | Feature set comparison harness |
| 10 | `scripts/features.py` | `src/qmb/features.py` | Point-in-time feature extraction |
| 11 | `scripts/live_safety_gate.py` | `src/qmb/live_safety_gate.py` | Execution safety gate |
| 12 | `scripts/logistic_baseline.py` | `src/qmb/logistic_baseline.py` | Walk-forward logistic baseline |
| 13 | `scripts/ma_crossover_backtest.py` | `src/qmb/ma_crossover_backtest.py` | Moving average baseline |
| 14 | `scripts/metrics.py` | `src/qmb/metrics.py` | Performance & statistics |
| 15 | `scripts/ml_signal.py` | `src/qmb/ml_signal.py` | ML hurdle & signal generation |
| 16 | `scripts/model_cv.py` | `src/qmb/model_cv.py` | Nested cross-validation & tuning |
| 17 | `scripts/multi_ticker_comparison.py` | `src/qmb/multi_ticker_comparison.py` | Five-ticker comparison harness |
| 18 | `scripts/order_gateway.py` | `src/qmb/order_gateway.py` | Pre-order gateway seam |
| 19 | `scripts/plotting.py` | `src/qmb/plotting.py` | Plotting utilities |
| 20 | `scripts/portfolio_risk.py` | `src/qmb/portfolio_risk.py` | Position sizing & risk guards |
| 21 | `scripts/return_stats.py` | `src/qmb/return_stats.py` | Descriptive statistics |
| 22 | `scripts/scratch_aapl_correlations.py` | `src/qmb/scratch_aapl_correlations.py` | Scratch correlation exploratory script |
| 23 | `scripts/scratch_multiticker_collinearity.py` | `src/qmb/scratch_multiticker_collinearity.py` | Scratch collinearity exploratory script |
| 24 | `scripts/selection_bias.py` | `src/qmb/selection_bias.py` | DSR & CSCV / PBO calculations |
| 25 | `scripts/signals.py` | `src/qmb/signals.py` | Rule-based signal generation |
| 26 | `scripts/stationarity_check.py` | `src/qmb/stationarity_check.py` | Stationarity diagnostics |
| 27 | `scripts/targets.py` | `src/qmb/targets.py` | Target labels & horizons |
| 28 | `scripts/trial_backfill.py` | `src/qmb/trial_backfill.py` | Trial ledger backfill utility |
| 29 | `scripts/trial_registry.py` | `src/qmb/trial_registry.py` | Lifetime trial ledger |
| 30 | `scripts/trial_runner.py` | `src/qmb/trial_runner.py` | Instrumented trial runner |
| 31 | `scripts/walk_forward_cv.py` | `src/qmb/walk_forward_cv.py` | Purged & embargoed splits |
| 32 | `[new]` | `src/qmb/__init__.py` | Package root |

> **Note on Scratch Modules**: `scripts/scratch_aapl_correlations.py` and `scripts/scratch_multiticker_collinearity.py` are legacy exploratory scripts. While included in the 31 files to preserve complete migration parity, the migration spec should evaluate moving them to a dedicated `scratch/` or `tools/` folder rather than shipping them inside `src/qmb/`.

---

## 6. Surprises & Hidden Breakages

This section documents every implicit dependency, hardcoded path assumption, dynamic import, and architectural seam that would silently break under an installed package even after a pure AST import rewrite (`import X` -> `from qmb import X`).

### 6.1 `Path(__file__).parents[N]` and Relative Path Construction
This is the single most common failure mode when converting flat script trees into installed packages.

1. **`scripts/data.py:52–53` (Cache Root Resolution)**:
   ```python
   PROJECT_ROOT = Path(__file__).resolve().parents[1]
   CACHE_DIR = PROJECT_ROOT / "data" / "cache"
   ```
   - *Failure*: In `scripts/`, `parents[1]` is the repo root. In `src/qmb/data.py`, `parents[1]` resolves to `src/`! If installed into `site-packages`, `parents[1]` resolves to `.../site-packages/` and attempts to create `site-packages/data/cache`.
   - *Remediation*: Cache directory resolution must not rely on `__file__`. It should default to `Path.cwd() / 'data' / 'cache'` or respect an environment variable (e.g. `QMB_DATA_DIR`).

2. **`scripts/feature_set_comparison.py:866–868` (Hardcoded Checkpoint Path)**:
   ```python
   CHECKPOINT_PATH = (
       Path(__file__).resolve().parents[1] / "data" / "cache" / "feature_set_comparison.json"
   )
   ```
   - *Failure*: Bypasses `data.CACHE_DIR` and duplicates `parents[1]`. Resolves to nonexistent `src/data/cache/` or crashes in site-packages.

3. **`scripts/trial_registry.py:19–20` (Lifetime Production Ledger Path)**:
   ```python
   ROOT = Path(__file__).resolve().parents[1]
   DEFAULT_TRIALS_PATH = ROOT / "docs/trials/trials.jsonl"
   ```
   - *Failure*: In `src/qmb/`, `parents[1]` is `src`. Under `site-packages`, `docs/trials/trials.jsonl` does not exist. All trial registry operations fail to locate the production ledger.

4. **`scripts/trial_runner.py:66–72` (`relative_path` Enforces Paths within `ROOT`)**:
   ```python
   if isinstance(value, Path):
       try:
           return relative_path(ROOT, value)
       except ValueError:
           if current_ledger().synthetic:
               return {"synthetic_path": value.name}
           raise
   ```
   - *Failure*: `relative_path` raises `ValueError("path outside repository; relative path required")` if any resolved `Path` argument is outside `ROOT`. If `ROOT` is mislocated, trial recording immediately crashes.

5. **`scripts/autocorrelation_check.py:14` & `scripts/stationarity_check.py:17` (Plots Directory)**:
   ```python
   PLOTS_DIRECTORY = Path(__file__).resolve().parent.parent / "plots"
   ```
   - *Failure*: Assumes `plots/` is sibling to parent directory. Resolves to `src/plots/` instead of repo root `plots/`.

6. **`scripts/scratch_aapl_correlations.py:11` & `scripts/scratch_multiticker_collinearity.py:20`**:
   ```python
   PROJECT_ROOT = Path(__file__).resolve().parents[1]
   ```
   - *Failure*: Assumes parent directory is repository root.

7. **`tests/conftest.py:24 & 37` (Fixture Verification of Production Ledger)**:
   ```python
   path = Path(__file__).resolve().parents[1] / "docs/trials/trials.jsonl"
   ```
   - *Note*: Operates in `tests/`, where `parents[1]` remains repo root as long as `tests/` stays at the top level.

### 6.2 Tests Asserting on `module.__file__` and Hardcoded AST Structure

1. **`tests/test_targets.py:605–643` (Strict AST Import Name Assertion)**:
   ```python
   def _imported_module_names(module) -> set[str]:
       with open(module.__file__, encoding="utf-8") as handle:
           tree = ast.parse(handle.read())
       names: set[str] = set()
       for node in ast.walk(tree):
           if isinstance(node, ast.Import):
               names.update(alias.name.split(".")[0] for alias in node.names)
           elif isinstance(node, ast.ImportFrom) and node.module:
               names.add(node.module.split(".")[0])
       return names

   def test_targets_imports_nothing_from_the_project(self):
       self.assertEqual(self._imported_module_names(targets_module), {"numpy", "pandas"})

   def test_features_imports_only_signals_and_targets(self):
       self.assertEqual(
           self._imported_module_names(features_module),
           {"numpy", "pandas", "signals", "targets"},
       )
   ```
   - **CRITICAL BREAKAGE**: This test opens `module.__file__` directly, parses its AST, and strictly asserts that `features.py` imports ONLY `{'numpy', 'pandas', 'signals', 'targets'}`.
   - If rewritten to package imports (`from qmb.signals import ...` or `from .signals import ...`), `names` extracts `{'numpy', 'pandas', 'qmb'}` or `{'numpy', 'pandas'}`. **This test will fail immediately upon import rewrite!**
   - In addition, `module.__file__` must exist as readable source on disk.

2. **`tests/test_order_gateway.py:33–49 & 135–147` (Hardcoded `scripts/` Directory Scan)**:
   ```python
   def test_production_broker_imports_always_import_live_gate(self):
       roots = [REPO_ROOT / "scripts", REPO_ROOT / "reports"]
       # ... scans roots ...
   ```
   - *Failure*: Hardcoded to scan `REPO_ROOT / 'scripts'`. When files move to `src/qmb/`, this guard completely stops scanning the project's bot modules unless updated to scan `src/qmb`.
   - Furthermore, `_imports()` checks:
     ```python
     if node.module in {"live_safety_gate", "scripts.live_safety_gate"}:
         imports_live_gate |= any(alias.name == "LiveSafetyGate" for alias in node.names)
     ```
     If rewritten to `from qmb.live_safety_gate import ...`, `node.module` is `'qmb.live_safety_gate'`, which is NOT in that set!

3. **`tests/test_033_trial_instrumentation.py:10–39` (Hardcoded Directory & Fixture Paths)**:
   ```python
   def bypasses(root):
       failures = []
       for folder in ("scripts", "reports/api"):
           for path in (root / folder).rglob("*.py"):
   ```
   - *Failure*: Walks `root / 'scripts'`. In `src/qmb/`, it will find zero files and silently become a no-op.
   - *Fixture failure*: Line 36 reads `tests/fixtures/spec_033/runner_inventory.json`, which contains 19 hardcoded calls referencing paths like `"path": "scripts/logistic_baseline.py"` and `"path": "scripts/feature_set_comparison.py"`.

4. **`tests/test_collection_guards.py:35–48` (Test Placement Guard)**:
   ```python
   def test_python_tests_live_under_tests():
       misplaced = [str(path.relative_to(REPO)) for path in python_test_files(REPO)
                    if not path.is_relative_to(TESTS)]
       assert not misplaced, "Python test files outside tests/:\n" + "\n".join(misplaced)
   ```
   - *Impact*: Any test helper or fixture placed inside `src/qmb/` matching `test*.py` or `*_test.py` will fail this suite guard.

### 6.3 Dynamic Imports and `importlib` Usage

1. **`tests/spec033_support.py:18–22` (`api()` Helper)**:
   ```python
   def api(module, name):
       assert importlib.util.find_spec(module), f"missing spec-033 behavior: {module}.{name}"
       obj = getattr(importlib.import_module(module), name, None)
       assert callable(obj), f"missing spec-033 behavior: {module}.{name}"
       return obj
   ```
   - *Failure*: Used across `tests/test_033_backfill.py`, `tests/test_033_dsr.py`, `tests/test_033_pbo.py`, and `tests/test_033_trial_ledger.py` with bare string arguments:
     - `api("trial_backfill", "calculate_backfill")`
     - `api("selection_bias", "build_matrix")`
     - `api("selection_bias", "deflated_sharpe")`
     - `api("selection_bias", "matrix_pbo")`
     - `api("trial_registry", "TrialLedger")`
     - `api("trial_runner", "run_trial")`
   - Because these are string literals passed to `importlib`, static AST rewrites of `import` statements will miss them entirely. `importlib.util.find_spec("trial_backfill")` will return `None` once the top-level name is `qmb.trial_backfill`.

### 6.4 In-Memory Source Mutation and `module.__file__` Compilation

1. **`tests/mutation_support_019.py:7–22` & `tests/mutation_support_032.py:13–28` (`killed()`)**:
   ```python
   def killed(module, old, new, oracle):
       path = Path(module.__file__)
       source = path.read_text()
       digest = hashlib.sha256(path.read_bytes()).digest()
       assert source.count(old) == 1, 'mutation must hit exactly one location'
       oracle()  # unmutated control must pass
       caught = False
       with patch.dict(module.__dict__):
           exec(compile(source.replace(old, new), str(path), 'exec'), module.__dict__)
   ```
   - *Impact*: Used in 8 test files (`test_019_calendar.py`, `test_019_conventions.py`, `test_019_ledger.py`, `test_019_metrics.py`, `test_019_prices.py`, `test_019_targets.py`, `test_clean_clone_037.py`, and `test_live_safety_gate.py`).
   - *Vulnerabilities*:
     1. **Source file must exist on disk**: If `module.__file__` points to a `.pyc` or inside a wheel archive, `read_text()` fails.
     2. **Exact target match required**: If code formatting, imports, or whitespace in the mutated modules change, `source.count(old) == 1` fails.
     3. **Module re-execution**: `exec(compile(...))` re-executes the *entire* module top-level code. Any imports in the module must succeed within the mutation execution context.

2. **`tests/mutation/run_mutation_check.py:51–63` (External Tree Copy)**:
   ```python
   shutil.copytree(REPO / "scripts", root / "scripts", ...)
   module = root / "scripts/data.py"
   ```
   - *Failure*: Directly copies `REPO / 'scripts'` and mutates `root / 'scripts/data.py'`. When `scripts/` is moved to `src/qmb/`, this script crashes.

3. **`tests/mutation/run_spec_018_mutants.py:22–26` (Hardcoded File Copy Tuple)**:
   ```python
   COPIED = (
       "scripts", "reports/__init__.py", "reports/api", "reports/web/src",
       "reports/requirements-ui.txt", "requirements-dev.txt", "tests/context.py", ...
   )
   ```
   - *Failure*: Hardcodes `"scripts"` and `"tests/context.py"` in its directory copy list.

### 6.5 Lifetime Ledger Trial Runner Identifiers

1. **`scripts/trial_runner.py:82–91` (`research_config`)**:
   - Runner strings passed to `research_config` are hardcoded across runner scripts:
     - `"scripts/ma_crossover_backtest.py:run_backtest"`
     - `"scripts/model_cv.py:grid_point"`
     - `"scripts/model_cv.py:tune_on_fold"`
     - `"scripts/multi_ticker_comparison.py:run_backtest"`
     - `"scripts/multi_ticker_comparison.py:nested_walk_forward"`
   - *Impact*: These runner strings are saved into `trials.jsonl` and included in configuration hashes. Changing them to `src/qmb/...` changes trial identity and historical reproducibility hashes.

### 6.6 Multiprocessing Worker Process Spawning

1. **`scripts/feature_set_comparison.py:840–880` (`compare_all_entries_parallel`)**:
   - Spawns worker processes using `concurrent.futures.ProcessPoolExecutor` with `_worker_init`.
   - On Windows, multiprocessing uses the `spawn` start method, launching a fresh Python interpreter.
   - In a packaged configuration, workers must find `qmb` via standard environment resolution (`site-packages` or `PYTHONPATH`), not via ephemeral `sys.path.insert` from a parent script.

### 6.7 Package-Data and Non-.py Dependencies

1. **`scripts/` Directory Contents**:
   - `scripts/` contains only `.py` files and `__pycache__`. There are zero non-.py files in `scripts/`.
2. **Runtime File System Dependencies**:
   - Modules expect read/write access to external directories located at the repository root:
     - `data/cache/` (market data cache and unadjusted bundles)
     - `data/cache/feature_set_comparison.json` (comparison checkpoint)
     - `docs/trials/trials.jsonl` (lifetime trial ledger)
     - `plots/` (figure output)
   - When packaged, `qmb` cannot assume it is executed from the repository root unless configured with explicit working-directory or environment overrides.
