"""EXAMPLE - NOT A RESULT. T023 lifecycle regression; fake in-memory receipt sink only."""
from pathlib import Path
import json
import socket
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
import numpy as np
import pandas as pd
import pytest
import trial_registry as registry
import trial_runner
import ma_crossover_backtest as sma
import logistic_baseline as logistic
import feature_set_comparison as features
import multi_ticker_comparison as multi
import model_cv
from test_033_trial_instrumentation import bypasses


class StopProbe(RuntimeError):
    pass


class Sink:
    synthetic = False  # role-policy spy only; not a TrialLedger and never writes a ledger

    def __init__(self):
        self.events, self.active, self.configs = [], set(), []

    def start(self, config, **kw):
        identity = str(len(self.configs) + 1)
        self.active.add(identity)
        self.configs.append(config)
        self.events.append({'event': 'started', 'id': identity, 'role': kw['role'], 'runner': kw['runner'],
                            'config_hash': registry.digest(config),
                            'resolved_argument_keys': sorted(config.get('resolved_arguments', {})),
                            'missing_canonical_fields': sorted(k for k in registry.CONFIG_FIELDS if config.get(k) is None)})
        return identity

    def finish(self, identity, outcome, **kw):
        self.active.remove(identity)
        self.events.append({'event': outcome, 'id': identity})
        return {'trial_id': identity}

    def callback(self, name, *, stop=False):
        self.events.append({'event': name, 'active_receipts': len(self.active)})
        if stop:
            raise StopProbe(name)


@pytest.fixture
def sink(monkeypatch):
    state = Sink()
    monkeypatch.setattr(trial_runner, 'current_ledger', lambda *a, **k: state)
    def forbidden(*a, **k):
        raise AssertionError('AUDIT refuses real ledger writes or network')
    monkeypatch.setattr(registry.TrialLedger, 'start', forbidden)
    monkeypatch.setattr(registry.TrialLedger, 'finish', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(registry, 'source_identity', lambda: {'git_sha': 'a' * 40, 'workspace_state': 'unknown', 'source_tree_hash': 'b' * 64})
    yield state


def frame():
    value = pd.DataFrame({'Date': pd.bdate_range('2024-01-02', periods=8), 'Close': np.arange(100., 108.), 'Label': [0, 1] * 4})
    for name in logistic.FEATURE_COLUMNS:
        if name not in value:
            value[name] = np.arange(1., 9.)
    value.attrs.update(source_manifest_sha256='d' * 64, label_horizon=1)
    return value


def test_feature_comparison_records_before_nested_fit(sink, monkeypatch):
    monkeypatch.setattr(features, 'build_features', lambda *a, **k: (frame(), 'regression', 1))
    monkeypatch.setattr(features, 'feature_columns', lambda *a: ['Close'])
    monkeypatch.setattr(features, 'nested_walk_forward', lambda *a, **k: sink.callback('nested_fit', stop=True))
    with pytest.raises(StopProbe):
        features._predictions_by_date(frame(), name='ridge', task='regression', feature_set='levels')
    assert sink.events[0]['role'] == 'candidate' and sink.events[1]['active_receipts'] == 1
    assert sink.events[-1]['event'] == 'errored'


def test_feature_snapshot_binds_an_explicit_seed_change(sink, monkeypatch):
    monkeypatch.setattr(features, 'build_features', lambda *a, **k: (frame(), 'regression', 1))
    monkeypatch.setattr(features, 'feature_columns', lambda *a: ['Close'])
    monkeypatch.setattr(features, 'nested_walk_forward', lambda *a, **k: sink.callback('nested_fit', stop=True))
    for seed in (42, 43):
        with pytest.raises(StopProbe):
            features._predictions_by_date(frame(), name='ridge', task='regression', feature_set='levels', random_state=seed)
    assert [c['resolved_arguments']['random_state'] for c in sink.configs] == [42, 43]
    assert registry.digest(sink.configs[0]) != registry.digest(sink.configs[1])


def test_sma_candidate_records_before_backtest(sink, monkeypatch, tmp_path):
    monkeypatch.setattr(sma, 'load_unadjusted_for_ticker', lambda *a, **k: frame())
    monkeypatch.setattr(sma, 'research_close_signal', lambda *a, **k: frame())
    monkeypatch.setattr(sma, 'run_backtest', lambda *a, **k: sink.callback('backtest', stop=True))
    args = SimpleNamespace(ticker='AAPL', short_window=2, long_window=3, commission=1., slippage_bps=5., manifest=None)
    with pytest.raises(StopProbe):
        sma._run_main(args, tmp_path)
    assert sink.events[0]['role'] == 'candidate' and sink.events[1]['active_receipts'] == 1


@pytest.mark.parametrize('module', [sma, multi], ids=['sma', 'multi'])
def test_required_baselines_keep_roles_before_callbacks(sink, monkeypatch, module):
    def run(*a, **k):
        sink.callback('backtest')
        return pd.DataFrame()
    summary = dict(total_trades=1, total_pnl=0., win_rate=0., total_return=0., sharpe_ratio=0., max_drawdown=0., capital_base=10000.)
    monkeypatch.setattr(module, 'run_backtest', run)
    monkeypatch.setattr(module, 'buy_and_hold_signal', lambda x: x.copy())
    monkeypatch.setattr(module, 'random_signal', lambda x, *a: x.copy())
    if module is sma:
        monkeypatch.setattr(sma, 'summarize_trades', lambda *a, **k: summary.copy())
        sma.baseline_results(frame(), n_trades=1, holding_bars=1, seed_count=2,
                             commission_per_trade=1., slippage_bps=5., starting_capital=10000., liquidate=True)
    else:
        monkeypatch.setattr(multi, 'mean_holding_bars', lambda *a: 1)
        monkeypatch.setattr(multi, 'performance_summary', lambda *a, **k: summary.copy())
        multi._baseline_rows('AAPL', frame(), pd.DataFrame([{'P&L': 0.}]), seed_count=2,
                             commission_per_trade=1., slippage_bps=5., starting_capital=10000., liquidate=True)
    assert [e['role'] for e in sink.events if e['event'] == 'started'] == ['buy_and_hold_baseline', 'random_signal_baseline', 'random_signal_baseline']
    assert all(e['active_receipts'] == 1 for e in sink.events if e['event'] == 'backtest')


def test_multi_candidate_records_before_nested_fit(sink, monkeypatch):
    monkeypatch.setattr(multi, 'download_market_data', lambda *a, **k: frame())
    monkeypatch.setattr(multi, 'build_features', lambda *a, **k: (frame(), 'regression', 1))
    monkeypatch.setattr(multi, 'feature_columns', lambda: ['Close'])
    monkeypatch.setattr(multi, 'nested_walk_forward', lambda *a, **k: sink.callback('nested_fit', stop=True))
    result = multi.run_one_ticker('AAPL', starting_capital=10000., liquidate=True)
    assert isinstance(result, multi.ComparisonFailure)
    assert sink.events[0]['role'] == 'candidate' and sink.events[1]['active_receipts'] == 1
    assert sink.events[-1]['event'] == 'errored'


@pytest.mark.parametrize('failure', ['fit', 'predict', 'backtest', 'clean'])
def test_logistic_refit_receipt_covers_fit_and_account(sink, monkeypatch, tmp_path, failure):
    monkeypatch.setattr(trial_runner, 'ROOT', tmp_path)
    monkeypatch.setattr(logistic, 'download_market_data', lambda *a, **k: frame().assign(Ticker='AAPL'))
    monkeypatch.setattr(logistic, 'build_features', lambda *a, **k: frame())
    monkeypatch.setattr(logistic, 'evaluate_walk_forward', lambda *a: pd.DataFrame({'Fold': [1]}))
    monkeypatch.setattr(logistic, 'cache_path', lambda name: tmp_path / name)
    monkeypatch.setattr(logistic, 'walk_forward_splits', lambda *a, **k: iter([(np.array([0, 1]), np.array([2, 3]))]))
    class Classifier:
        def __init__(self, **kw): pass
        def fit(self, *a, **k): sink.callback('fit', stop=failure == 'fit')
        def predict(self, x):
            sink.callback('predict', stop=failure == 'predict')
            return np.ones(len(x), dtype=int)
    monkeypatch.setattr(logistic, 'LogisticRegression', Classifier)
    def backtest(live, **kw):
        sink.callback('backtest', stop=failure == 'backtest')
        assert list(live.Date) == list(frame().Date.iloc[2:])
        assert kw == dict(commission_per_trade=logistic.COMMISSION_PER_TRADE,
                          slippage_bps=logistic.SLIPPAGE_BPS,
                          starting_capital=logistic.STARTING_CAPITAL, liquidate=logistic.LIQUIDATE_AT_END)
        return pd.DataFrame()
    monkeypatch.setattr(logistic, 'run_backtest', backtest)
    monkeypatch.setattr(trial_runner.Attempt, 'account', lambda *a, **k: sink.callback('account'))
    monkeypatch.setattr(logistic, 'summarize_trades', lambda *a, **k: {'total_trades': 0})
    monkeypatch.setattr(logistic, 'mean_holding_bars', lambda *a: 1)
    monkeypatch.setattr(logistic, 'baseline_results', lambda *a, **k: {})
    monkeypatch.setattr(logistic, '_format_ml_comparison', lambda *a, **k: '')
    if failure == 'clean':
        logistic._run_main()
    else:
        with pytest.raises(StopProbe): logistic._run_main()
    callbacks = [e for e in sink.events if 'active_receipts' in e]
    assert callbacks and all(e['active_receipts'] == 1 for e in callbacks)
    assert [e['role'] for e in sink.events if e['event'] == 'started'] == ['candidate', 'candidate']
    assert sink.events[-1]['event'] == ('rejected' if failure == 'clean' else 'errored')
    assert not sink.active


def test_model_cv_grid_records_each_point_before_fit(sink, monkeypatch):
    monkeypatch.setattr(model_cv, 'param_grid_points', lambda *a, **k: [{'alpha': 1.}, {'alpha': 2.}])
    monkeypatch.setattr(model_cv, 'model_row_masks', lambda *a, **k: (np.ones(8, dtype=bool), np.ones(8, dtype=bool)))
    monkeypatch.setattr(model_cv, 'inner_splits_over', lambda *a, **k: iter([(np.array([0, 1]), np.array([2, 3]))]))
    class Estimator:
        def fit(self, *a):
            sink.callback('grid_fit')
        def predict(self, x):
            return np.zeros(len(x))
    monkeypatch.setattr(model_cv, 'build_estimator', lambda *a, **k: Estimator())
    model_cv.tune_on_fold(frame(), np.arange(6), name='ridge', task='regression', feature_columns=['Close'],
                          label_column='Label', label_horizon=1, embargo_bars=1, random_state=42)
    assert [e['role'] for e in sink.events if e['event'] == 'started'] == ['candidate', 'candidate']
    assert all(e['active_receipts'] == 1 for e in sink.events if e['event'] == 'grid_fit')
    assert [c['resolved_arguments']['params'] for c in sink.configs] == [{'alpha': 1.}, {'alpha': 2.}]


@pytest.mark.parametrize('failure', ['fit', 'predict', 'clean'])
def test_model_cv_final_fit_lifecycle(sink, monkeypatch, failure):
    monkeypatch.setattr(model_cv, 'model_row_masks', lambda *a, **k: (np.ones(8, dtype=bool), np.ones(8, dtype=bool)))
    monkeypatch.setattr(model_cv, 'walk_forward_splits', lambda *a, **k: iter([(np.array([0, 1]), np.array([2, 3]))]))
    monkeypatch.setattr(model_cv, 'tune_on_fold', lambda *a, **k: ({'alpha': 1.}, False, pd.DataFrame()))
    class Estimator:
        def fit(self, *a): sink.callback('fit', stop=failure == 'fit')
        def predict(self, x):
            sink.callback('predict', stop=failure == 'predict')
            return np.array([0.25, 0.75])
    monkeypatch.setattr(model_cv, 'build_estimator', lambda *a, **k: Estimator())
    def run():
        return model_cv.nested_walk_forward(frame(), name='ridge', task='regression', feature_columns=['Close'],
                                           label_column='Label', label_horizon=1, embargo_bars=1, random_state=42)
    if failure == 'clean':
        predictions, covered, folds = run()
        assert covered.tolist() == [2, 3]
        assert predictions.iloc[[2, 3]].tolist() == [0.25, 0.75]
        assert predictions.drop(index=[2, 3]).isna().all()
        assert len(folds) == 1 and folds.iloc[0]['Params'] == {'alpha': 1.}
        assert folds.iloc[0]['Train_End'] < folds.iloc[0]['Test_Start']
    else:
        with pytest.raises(StopProbe): run()
    assert all(e['active_receipts'] == 1 for e in sink.events if 'active_receipts' in e)
    assert [e['role'] for e in sink.events if e['event'] == 'started'] == ['candidate']
    assert sink.events[-1]['event'] == ('rejected' if failure == 'clean' else 'errored')
    assert not sink.active
