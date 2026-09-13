import numpy as np
import pandas as pd
import pytest
import context
import metrics as mt
import backtest_harness as bt
from test_019_ledger import bars


def loss_curve():
    p = bars().assign(Open=50., Close=50., Buy_Next_Open=[True, False, False])
    log = bt.run_backtest(p, starting_capital=100., commission_per_trade=5.)
    return p, log, mt.equity_curve(p, log, starting_capital=100.,
                                  commission_per_trade=5., slippage_bps=0.)


def test_audit_first_fee_drawdown():
    _, _, curve = loss_curve()
    assert mt.max_drawdown(curve.Equity)[0] == pytest.approx(-.10)
    assert mt.max_drawdown(curve.Equity)[1:] == (-1, 2)
    assert curve.Equity.tolist() == [95., 95., 90.]
    np.testing.assert_allclose(mt.equity_log_returns(curve.Equity),
                               np.log([.95, 1., 90./95.]))


def test_funded_open_mark_and_quantity_metrics():
    p = bars().assign(Open=20., Close=[20., 21., 22.], Sell_Next_Open=False)
    log = bt.run_backtest(p, starting_capital=100., shares=3, commission_per_trade=1.)
    summary = mt.performance_summary(p, log, commission_per_trade=1., slippage_bps=0.)
    assert summary['total_pnl'] == 5.
    assert summary['total_return'] == .05
    assert summary['capital_base'] == 100.


def test_first_profit_flat_and_terminal_loss():
    for values, expected in [([105., 105.], 0.), ([100., 100.], 0.), ([105., 90.], 90/105-1)]:
        equity = pd.Series(values)
        equity.attrs['capital_base'] = 100.
        assert mt.max_drawdown(equity)[0] == pytest.approx(expected)
        assert mt.equity_log_returns(equity).iloc[0] == pytest.approx(np.log(values[0]/100))


def test_tampered_event_and_config_fail():
    p, log, _ = loss_curve()
    with pytest.raises(ValueError):
        mt.equity_curve(p, log, commission_per_trade=1., slippage_bps=0.)
    log.attrs['ledger'].loc[1, 'Cash'] += 1.
    with pytest.raises(ValueError):
        mt.equity_curve(p, log, commission_per_trade=5., slippage_bps=0.)


def test_insolvency_is_not_a_valid_log_return():
    equity = pd.Series([0., -1.])
    equity.attrs['capital_base'] = 100.
    assert mt.equity_log_returns(equity).isna().all()


def test_anchor_mutants():
    from test_019_mutation_support import killed
    killed(mt, 'anchored = "capital_base" in equity.attrs', 'anchored = False',
           test_audit_first_fee_drawdown)
    killed(mt, 'capital = equity.attrs.get("capital_base")', 'capital = None',
           test_first_profit_flat_and_terminal_loss)
