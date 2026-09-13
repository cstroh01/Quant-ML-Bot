import numpy as np
import pandas as pd
import pytest
import context
import targets as tg


def prices():
    return pd.DataFrame({'Date': pd.to_datetime(['2026-09-03', '2026-09-04',
                                                '2026-09-08', '2026-09-09']),
                         'Open': [100., 200., 200., 220.],
                         'Close': [100., 200., 200., 220.]}, index=[3, 8, 10, 15])


def test_overnight_move_is_not_earned_before_entry():
    label, task, availability = tg.build_target(prices(), kind='return', horizon=1)
    assert label.iloc[0] == 0., 'overnight gain occurred before executable entry'
    assert label.iloc[1] == pytest.approx(np.log(1.1))
    assert label.iloc[-2:].isna().all()
    assert availability == 2 and task == 'regression'
    assert label.index.equals(prices().index)


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf, 0., -1.])
@pytest.mark.parametrize('endpoint', [1, 2])
def test_invalid_endpoint_is_unknown(bad, endpoint):
    p = prices()
    p.iloc[endpoint, p.columns.get_loc('Open')] = bad
    assert pd.isna(tg.direction_label(p, horizon=1).iloc[0])
    assert pd.isna(tg.forward_log_return_label(p, horizon=1).iloc[0])


def test_only_entry_and_exit_opens_define_target():
    p = prices()
    control = tg.forward_log_return_label(p, horizon=1)
    changed = p.copy()
    changed['Close'] *= 50
    changed.iloc[3, changed.columns.get_loc('Open')] *= 2
    assert tg.forward_log_return_label(changed, horizon=1).iloc[0] == control.iloc[0]
    assert tg.build_target(p, kind='direction', horizon=2)[2] == 3
    assert tg.forward_log_return_label(p.iloc[:2], horizon=1).isna().all()


def test_panel_cannot_shift_across_tickers():
    p = prices().assign(Ticker=['A', 'A', 'B', 'B'])
    with pytest.raises(ValueError, match='instrument'):
        tg.build_target(p, kind='return', horizon=1)


def test_target_mutants():
    from test_019_mutation_support import killed
    killed(tg, 'prices.Open.shift(-1)', 'prices.Open',
           test_overnight_move_is_not_earned_before_entry)
    killed(tg, '_TASK_FOR_KIND[kind], horizon + 1', '_TASK_FOR_KIND[kind], horizon',
           test_overnight_move_is_not_earned_before_entry)
    killed(tg, 'label[returns.isna()] = pd.NA', 'label[returns.isna()] = 0',
           lambda: test_invalid_endpoint_is_unknown(np.nan, 1))
