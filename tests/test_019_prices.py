import numpy as np
import pandas as pd
import pytest
import context
import data as dt
import backtest_harness as bt
import metrics as mt
import targets as tg
from test_019_ledger import bars


def action_bars():
    p = bars().assign(Open=[50., 25., 24.], Close=[50., 25., 24.],
                      Buy_Next_Open=[True, False, False], Sell_Next_Open=False,
                      Split=[1., 2., 1.], Dividend=[0., 0., 1.],
                      Dividend_Pay_Date=pd.to_datetime([None, None, '2026-09-09']))
    return p


def test_adjusted_and_undeclared_prices_cannot_fund_account():
    for basis in ('research_adjusted', None):
        p = bars()
        p.attrs['price_basis'] = basis
        with pytest.raises(ValueError, match='unadjusted'):
            bt.run_backtest(p)


def test_split_and_dividend_oracle():
    p = action_bars()
    extra = p.iloc[[-1]].copy().assign(Date=pd.Timestamp('2026-09-09'), Dividend=0.,
                                     Dividend_Pay_Date=pd.NaT, Sell_Next_Open=True)
    p = pd.concat([p, extra], ignore_index=True)
    log = bt.run_backtest(p, starting_capital=101., commission_per_trade=1.)
    marks = log.attrs['ledger'].query("Event == 'mark'")
    assert marks.Quantity.tolist() == [1., 2., 2., 0.]
    assert marks.Cash.tolist() == [50., 50., 50., 99.]
    assert marks.Receivable.tolist() == [0., 0., 2., 0.]
    assert marks.Equity.tolist() == [100., 100., 100., 99.]
    assert log['P&L'].tolist() == [-2.]
    curve = mt.equity_curve(p, log, commission_per_trade=1., slippage_bps=0.)
    assert curve.Equity.tolist() == [100., 100., 100., 99.]


def test_ex_date_buyer_does_not_receive_prior_dividend():
    p = action_bars().assign(Buy_Next_Open=[False, False, True])
    log = bt.run_backtest(p, starting_capital=100., commission_per_trade=1.)
    assert log.attrs['ledger'].iloc[-1].Equity == 99.
    assert log.attrs['ledger'].iloc[-1].Receivable == 0.


def test_causal_research_prices_and_no_cache_relabel():
    p = action_bars().assign(Ticker='A', High=lambda x:x.Close, Low=lambda x:x.Close, Volume=100.)
    assert hasattr(dt, 'execution_price_frame'), 'missing raw-dollar input boundary'
    raw = dt.execution_price_frame(p)
    assert raw.Close.tolist() == [50., 25., 24.]
    assert raw.Research_Close.tolist() == [50., 50., 50.]
    prefix = dt.execution_price_frame(p.iloc[:2])
    pd.testing.assert_series_equal(prefix.Research_Close, raw.Research_Close.iloc[:2])
    legacy = dt._tidy(p, ['A'])
    assert legacy.attrs['price_basis'] == 'research_adjusted'


def test_action_spanning_label_is_unavailable():
    p = action_bars()
    assert pd.isna(tg.forward_log_return_label(p, horizon=1).iloc[0])


def test_missing_pay_date_and_invalid_split_fail():
    for p in (action_bars().assign(Dividend_Pay_Date=pd.NaT), action_bars().assign(Split=0.)):
        with pytest.raises(ValueError):
            bt.run_backtest(p)


def test_price_action_mutants():
    from test_019_mutation_support import killed
    killed(bt, 'quantity *= row.Split', 'quantity *= 1.', test_split_and_dividend_oracle)
    killed(bt, 'receivable += income', 'cash += income; receivable += 0.',
           test_split_and_dividend_oracle)
    killed(dt, 'result.Close.iloc[0] * gross.cumprod()', 'result.Close.copy()',
           test_causal_research_prices_and_no_cache_relabel)
