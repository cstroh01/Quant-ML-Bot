import numpy as np
import pandas as pd
import pytest
import context
import backtest_harness as bt


def bars():
    frame = pd.DataFrame({'Date': pd.to_datetime(['2026-09-03', '2026-09-04', '2026-09-08']),
                          'Open': [100., 200., 200.], 'Close': [100., 200., 200.],
                          'Buy_Next_Open': [False, True, False],
                          'Sell_Next_Open': [False, False, True]})
    frame.attrs['price_basis'] = 'unadjusted_dollars'
    return frame


def test_audit_100_cannot_fund_201_10():
    trades = bt.run_backtest(bars(), starting_capital=100., commission_per_trade=1., slippage_bps=5.)
    assert trades.empty, 'A $100 account accepted a $201.10 entry'
    assert trades.attrs['ledger'].Event.tolist().count('rejected') == 1


def test_cash_and_quantity_oracle():
    p = bars().assign(Open=[20., 20., 22.], Close=[20., 21., 22.])
    log = bt.run_backtest(p, starting_capital=100., shares=3,
                          commission_per_trade=1., slippage_bps=0.)
    ledger = log.attrs['ledger']
    marks = ledger[ledger.Event == 'mark']
    assert marks.Cash.tolist() == [100., 39., 104.]
    assert marks.Quantity.tolist() == [0., 3., 0.]
    assert marks.Equity.tolist() == [100., 102., 104.]
    np.testing.assert_allclose(ledger.Equity, ledger.Cash + ledger.Quantity * ledger.Price)
    assert log['P&L'].tolist() == [4.]
    assert ledger.Event_ID.is_unique


@pytest.mark.parametrize('column,value', [('Open', np.nan), ('Close', 0.),
                                         ('Buy_Next_Open', 'False')])
def test_invalid_bars_fail(column, value):
    p = bars()
    p[column] = value
    with pytest.raises(ValueError):
        bt.run_backtest(p, starting_capital=100.)


@pytest.mark.parametrize('kwargs', [{'commission_per_trade': np.nan},
                                    {'slippage_bps': np.inf}, {'slippage_bps': 10000.}])
def test_invalid_costs_fail(kwargs):
    with pytest.raises(ValueError):
        bt.run_backtest(bars(), starting_capital=100., **kwargs)


def test_open_position_is_marked_not_sold_and_prefix_is_stable():
    p = bars().assign(Open=20., Close=[20., 21., 22.], Sell_Next_Open=False)
    short = bt.run_backtest(p.iloc[:2], starting_capital=100., commission_per_trade=1.)
    full = bt.run_backtest(p, starting_capital=100., commission_per_trade=1.)
    assert short.empty and full.empty
    pd.testing.assert_frame_equal(short.attrs['ledger'], full.attrs['ledger'].iloc[:len(short.attrs['ledger'])])
    liquidated = bt.run_backtest(p, starting_capital=100., commission_per_trade=1., liquidate=True)
    assert liquidated['P&L'].tolist() == [0.]
    assert 'liquidation' in liquidated.attrs['ledger'].Event.tolist()


def test_invalid_chronology_and_conflicting_signals():
    for p in [bars().iloc[::-1], bars().assign(Date=pd.Timestamp('2026-09-03')),
              bars().assign(Buy_Next_Open=True, Sell_Next_Open=True)]:
        with pytest.raises(ValueError):
            bt.run_backtest(p, starting_capital=100.)


def test_ledger_mutants():
    from test_019_mutation_support import killed
    killed(bt, 'if required > cash:', 'if False:', test_audit_100_cannot_fund_201_10)
    killed(bt, 'cash -= required', 'cash -= required - commission_per_trade',
           test_cash_and_quantity_oracle)
    killed(bt, 'if quantity and liquidate:', 'if quantity:',
           test_open_position_is_marked_not_sold_and_prefix_is_stable)
