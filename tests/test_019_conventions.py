import numpy as np
import pandas as pd
import pytest
import context
import metrics as mt
import ml_signal as ms
import backtest_harness as bt
from test_019_ledger import bars


def test_effective_annual_hurdle_uses_log_units():
    r = pd.Series([.01, .02, -.01])
    expected = (r.mean()*252 - np.log1p(.1)) / (r.std()*np.sqrt(252))
    assert mt.sharpe_ratio(r, risk_free_rate_annual=.1) == pytest.approx(expected)


def test_dependent_mean_uncertainty_has_hand_oracle():
    r = pd.Series([.01, .02, .03, .04])
    assert hasattr(mt, 'mean_log_return_se'), 'missing autocovariance-aware uncertainty'
    # deviations [-.015,-.005,.005,.015]; gamma0=.000125,
    # gamma1=.00003125, Bartlett weight=.5 => LRV=.00015625.
    assert mt.mean_log_return_se(r, lags=1) == pytest.approx(np.sqrt(.00015625/4))
    assert np.isnan(mt.mean_log_return_se(pd.Series([.1, np.nan]), lags=0))


def test_growth_and_interest_conventions_recorded():
    p = bars().assign(Open=20., Close=[20., 21., 22.], Sell_Next_Open=False)
    log = bt.run_backtest(p, starting_capital=100., commission_per_trade=1.)
    s = mt.performance_summary(p, log, commission_per_trade=1., slippage_bps=0.)
    assert s.get('cash_interest_rate_annual') == 0., 'cash interest assumption absent'
    assert s['annualized_mean_log_return'] == pytest.approx(np.log(1.01)*252/3)
    assert s['cagr_252_sessions'] == pytest.approx(1.01**(252/3)-1)
    assert s['risk_free_rate_annual'] > 0
    assert 'research' in s['interpretation']


@pytest.mark.parametrize('kwargs', [{'commission_per_trade': np.nan}, {'slippage_bps': np.inf}])
def test_signal_costs_reject_nonfinite(kwargs):
    params = dict(commission_per_trade=1., slippage_bps=5.)
    params.update(kwargs)
    with pytest.raises(ValueError):
        ms.cost_hurdle(pd.Series([100.]), **params)


def test_threshold_infinity_is_invalid():
    with pytest.raises(ValueError):
        ms.positions_from_predicted_return(pd.Series([.1]), .01, exit_threshold=np.inf)


def test_trade_log_tampering_is_not_a_successful_summary():
    p = bars().assign(Open=20., Close=20.)
    log = bt.run_backtest(p, starting_capital=100., commission_per_trade=1.)
    log.loc[0, 'P&L'] = 123.
    with pytest.raises(ValueError):
        mt.performance_summary(p, log, commission_per_trade=1., slippage_bps=0.)


@pytest.mark.parametrize('column', ['Quantity', 'Entry Quantity', 'Entry Cost',
                                    'Dividend Income', 'Cumulative P&L'])
def test_trade_metadata_reconciles(column):
    p = bars().assign(Open=20., Close=20.)
    log = bt.run_backtest(p, starting_capital=100., commission_per_trade=1.)
    log.loc[0, column] = 999.
    with pytest.raises(ValueError):
        mt.equity_curve(p, log, commission_per_trade=1., slippage_bps=0.)


def test_a_single_invalid_phase_fails_even_if_balances_reconcile():
    p = bars().assign(Open=20., Close=20.)
    log = bt.run_backtest(p, starting_capital=100., commission_per_trade=1.)
    ledger = log.attrs['ledger']
    ledger.loc[ledger.Event == 'buy', 'Phase'] = 'close'
    with pytest.raises(ValueError):
        mt.equity_curve(p, log, commission_per_trade=1., slippage_bps=0.)


def test_invalid_terminal_equity_is_not_hidden():
    eq = pd.Series([100., np.nan])
    assert np.isnan(mt.max_drawdown(eq)[0])


def test_capital_must_be_chosen_before_the_first_open():
    with pytest.raises(ValueError, match='starting_capital'):
        bt.run_backtest(bars().assign(Close=99999.))


def test_total_loss_has_no_partial_annualized_log_statistic():
    p = bars().assign(Open=[20., 20., 1.], Close=[20., 20., 1.])
    log = bt.run_backtest(p, starting_capital=21., commission_per_trade=1.)
    s = mt.performance_summary(p, log, commission_per_trade=1., slippage_bps=0.)
    assert s['total_return'] == -1.
    assert np.isnan(s['annualized_mean_log_return'])


def test_payment_cannot_be_moved_ahead_of_source_pay_date():
    from test_019_prices import action_bars
    p = action_bars().assign(Dividend_Pay_Date=pd.Timestamp('2026-09-08'))
    log = bt.run_backtest(p, starting_capital=101., commission_per_trade=1.)
    source = p.assign(Dividend_Pay_Date=pd.Timestamp('2026-09-09'))
    with pytest.raises(ValueError):
        mt.equity_curve(source, log, commission_per_trade=1., slippage_bps=0.)


def test_dividend_event_cannot_invent_shares():
    from test_019_prices import action_bars
    p = action_bars()
    log = bt.run_backtest(p, starting_capital=101., commission_per_trade=1.)
    ledger = log.attrs['ledger']
    ledger.loc[ledger.Date == p.Date.iloc[-1], 'Quantity'] += 1
    ledger['Equity'] = ledger.Cash + ledger.Quantity * ledger.Price + ledger.Receivable
    with pytest.raises(ValueError):
        mt.equity_curve(p, log, commission_per_trade=1., slippage_bps=0.)


def test_metric_convention_mutants():
    from test_019_mutation_support import killed
    killed(mt, '(annualized_return - np.log1p(risk_free_rate_annual))',
           '(annualized_return - risk_free_rate_annual)',
           test_effective_annual_hurdle_uses_log_units)
    killed(mt, 'variance += 2 * (1 - lag / (lags + 1)) * covariance',
           'variance += 0 * covariance', test_dependent_mean_uncertainty_has_hand_oracle)


def test_same_period_costed_baselines(capsys):
    # Mechanics only: no trained model or claim of a strategy's economic edge.
    x = np.arange(8, dtype=float)
    p = pd.DataFrame({'Date': pd.bdate_range('2026-08-24', periods=8),
                      'Open': 20 + x, 'Close': 20.2 + x})
    p.attrs['price_basis'] = 'unadjusted_dollars'
    records = {}
    for name, desired in [('policy', [True, True, False, False, False, False, False, False]),
                          ('buy_hold', [True]*8)]:
        buy, sell = ms.signal_from_positions(pd.Series(desired))
        prices = p.assign(Buy_Next_Open=buy, Sell_Next_Open=sell)
        log = bt.run_backtest(prices, starting_capital=100., commission_per_trade=1.,
                              slippage_bps=5., liquidate=True)
        records[name] = mt.performance_summary(prices, log, commission_per_trade=1., slippage_bps=5.)
    random_pnl = []
    for seed in range(20):
        desired = np.zeros(8, dtype=bool)
        start = np.random.default_rng(seed).integers(0, 5)
        desired[start:start+2] = True
        buy, sell = ms.signal_from_positions(pd.Series(desired))
        prices = p.assign(Buy_Next_Open=buy, Sell_Next_Open=sell)
        log = bt.run_backtest(prices, starting_capital=100., commission_per_trade=1., slippage_bps=5., liquidate=True)
        assert len(log) == records['policy']['total_trades'] == 1
        random_pnl.append(float(log['P&L'].sum()))
    assert all(r['bars'] == 8 and r['capital_base'] == 100. for r in records.values())
    with capsys.disabled():
        print('Synthetic baseline P&L:', {k:r['total_pnl'] for k,r in records.items()},
              'random mean/std:', np.mean(random_pnl), np.std(random_pnl, ddof=1))
