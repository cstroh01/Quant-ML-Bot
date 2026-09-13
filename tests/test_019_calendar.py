import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch
import context
import features as ft
import estimators as es
import model_cv as cv
import ml_signal as ms


def panel(n=180):
    x = np.arange(n, dtype=float)
    return pd.DataFrame({'Date': pd.bdate_range(end='2026-09-04', periods=n),
                         'Ticker': 'A', 'Open': 100 + x, 'Close': 100 + x + np.sin(x),
                         'Volume': 1000.}, index=np.arange(n)*3+7)


def build(p):
    return ft.build_features(p, target_kind='return', label_horizon=1,
                             short_window=2, long_window=3, volatility_window=2)


def test_freshest_row_and_internal_gap_preserved():
    p = panel(15)
    p.iloc[8, p.columns.get_loc('Volume')] = np.nan
    frame, _, h = build(p)
    assert frame.index.equals(p.index), 'feature construction compressed the session calendar'
    assert frame.Date.iloc[-1] == pd.Timestamp('2026-09-04')
    assert frame.Label.iloc[-2:].isna().all()
    assert frame.Train_Eligible.iloc[-1] == False
    assert frame.Inference_Eligible.iloc[-1] == True
    assert h == 2
    prefix, _, _ = build(p.iloc[:10])
    pd.testing.assert_frame_equal(prefix[ft.feature_columns()], frame[ft.feature_columns()].iloc[:10])


def test_batch_end_is_not_a_decision():
    pred = pd.Series([.2, .2, .2], index=pd.to_datetime(['2026-09-03','2026-09-04','2026-09-08']))
    short = ms.positions_from_predicted_return(pred.iloc[:2], .01, exit_threshold=0.)
    full = ms.positions_from_predicted_return(pred, .01, exit_threshold=0.)
    assert short.tolist() == [True, True]
    pd.testing.assert_series_equal(short, full.iloc[:2])
    buy, sell = ms.signal_from_positions(full)
    assert buy.tolist() == [False, True, False]
    assert not sell.any()


class SpyModel:
    fits = []
    def fit(self, x, y):
        assert np.isfinite(x.to_numpy(dtype=float)).all(), 'warmup/gap reached estimator fit'
        assert np.isfinite(y.to_numpy(dtype=float)).all(), 'unknown label reached estimator fit'
        self.fits.append((x.index.copy(), y.copy()))
        return self
    def predict(self, x):
        assert np.isfinite(x.to_numpy(dtype=float)).all(), 'invalid inference features'
        return np.full(len(x), .01)


@pytest.mark.parametrize('nested', [False, True])
def test_cv_masks_after_splitting_and_keeps_unknown_tail(nested):
    # Explicit raw calendar tests the CV boundary independently of build_features.
    frame = panel().assign(x=1., Label=.01)
    frame.iloc[0, frame.columns.get_loc('x')] = np.nan
    frame.iloc[-8, frame.columns.get_loc('x')] = np.nan
    frame.iloc[-2:, frame.columns.get_loc('Label')] = np.nan
    kwargs = dict(name='ridge', task='regression', feature_columns=['x'], label_column='Label',
                  label_horizon=2, embargo_bars=2, random_state=42,
                  initial_train_months=2, test_months=1)
    SpyModel.fits = []
    module = cv if nested else es
    with patch.object(module, 'build_estimator', side_effect=lambda *a, **k: SpyModel()):
        result = (cv.nested_walk_forward(frame, inner_initial_train_months=1,
                                         inner_test_months=1, **kwargs) if nested
                  else es.fit_predict_walk_forward(frame, **kwargs))
    pred = result[0] if nested else result
    assert pred.index.equals(frame.index)
    assert pd.isna(pred.iloc[-8])
    assert pred.iloc[-1] == .01
    assert SpyModel.fits
    if nested:
        assert len(frame)-8 not in result[1]


def test_short_purge_cannot_override_target_metadata():
    frame, task, _ = build(panel())
    with pytest.raises(ValueError, match='horizon'):
        es.fit_predict_walk_forward(frame, name='ridge', task=task,
                                    feature_columns=ft.feature_columns(), label_column='Label',
                                    label_horizon=1, embargo_bars=1, random_state=42)


def test_future_perturbation_does_not_change_earlier_oos_predictions():
    p = panel()
    a, task, h = build(p)
    changed = p.copy()
    changed.iloc[145:, changed.columns.get_loc('Close')] *= 2
    changed.iloc[145:, changed.columns.get_loc('Open')] *= 3
    b, _, _ = build(changed)
    for nested in (False, True):
        kwargs = dict(name='ridge', task=task, feature_columns=ft.feature_columns(),
                      label_column='Label', label_horizon=h, embargo_bars=h,
                      random_state=42, initial_train_months=2, test_months=1)
        runner = cv.nested_walk_forward if nested else es.fit_predict_walk_forward
        pa, pb = runner(a, **kwargs), runner(b, **kwargs)
        if nested:
            pa, pb = pa[0], pb[0]
        assert pa.iloc[:145].notna().any()
        pd.testing.assert_series_equal(pa.iloc[:145], pb.iloc[:145])


def test_calendar_mutants():
    from test_019_mutation_support import killed
    killed(ft, 'return features, task, horizon',
           'return features.dropna(subset=[LABEL_COLUMN]), task, horizon',
           test_freshest_row_and_internal_gap_preserved)
    killed(ms, 'desired[i] = long', 'desired[i] = long if i < len(predicted)-1 else False',
           test_batch_end_is_not_a_decision)
    killed(es, 'train_indices = train_indices[train_ok[train_indices]]',
           'train_indices = train_indices',
           lambda: test_cv_masks_after_splitting_and_keeps_unknown_tail(False))
