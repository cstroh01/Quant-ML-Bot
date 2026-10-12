// Spec 047 U1b fixture. EXAMPLE — NOT A RESULT. Synthetic response; no market data.
// Two closed trades plus an open entry: the old view formula, 2 * $1.00 * 2 trades = $4.00,
// disagrees with the charged commission_total ($3.00), and slippage_total is non-zero.
import type { BacktestTearsheetResponse } from '../../types/api'

export const tearsheet047: BacktestTearsheetResponse = {
  ticker: 'SYN',
  strategy_name: 'EXAMPLE — NOT A RESULT',
  commission_per_trade: 1.0,
  slippage_bps: 5.0,
  commission_total: 3.0,
  slippage_total: 0.47,
  capital_base: 1000,
  total_return: 1.5,
  total_pnl: 15,
  sharpe_ratio: 0.5,
  max_drawdown: 2.0,
  reconciliation_passed: true,
  equity_curve: [
    { time: '2024-03-07', equity: 1000, drawdown: 0, position: 0, bar_pnl: 0 },
    { time: '2024-03-08', equity: 1015, drawdown: 0, position: 1, bar_pnl: 15 },
  ],
  trade_log: [
    { entry_date: '2024-03-01', entry_price: 10, exit_date: '2024-03-04', exit_price: 11, pnl: 8, cumulative_pnl: 8, holding_bars: 1 },
    { entry_date: '2024-03-05', entry_price: 11, exit_date: '2024-03-06', exit_price: 12, pnl: 7, cumulative_pnl: 15, holding_bars: 1 },
  ],
  comparison_table: [],
}
