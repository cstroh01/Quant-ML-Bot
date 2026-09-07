import React, { useState } from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  DollarSign,
  FileSpreadsheet,
  Percent,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { BacktestTearsheetResponse } from '../../types/api';
import { DrawdownChart } from '../charts/DrawdownChart';
import { EquityCurveChart } from '../charts/EquityCurveChart';

interface BacktestTearsheetViewProps {
  tearsheet: BacktestTearsheetResponse | null;
  loading: boolean;
  colorblindMode: boolean;
}

export const BacktestTearsheetView: React.FC<BacktestTearsheetViewProps> = ({
  tearsheet,
  loading,
  colorblindMode,
}) => {
  const [showAccessibleTable, setShowAccessibleTable] = useState(false);

  if (loading || !tearsheet) {
    return (
      <div className="p-12 flex flex-col items-center justify-center text-gray-500 font-mono text-sm">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
        Computing reconciled backtest & 3-way baseline comparisons...
      </div>
    );
  }

  const isPositiveReturn = tearsheet.total_return >= 0;
  const returnColor = isPositiveReturn
    ? colorblindMode ? 'text-cyan-400' : 'text-emerald-400'
    : colorblindMode ? 'text-amber-400' : 'text-rose-400';

  return (
    <div className="space-y-6">
      {/* Top Metric Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
        {/* Total Net P&L */}
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="flex items-center justify-between text-xs text-gray-400 font-mono mb-1">
            <span>TOTAL NET P&L</span>
            <DollarSign className="w-3.5 h-3.5 text-gray-500" />
          </div>
          <div className={`text-xl font-bold font-mono tabular-nums ${returnColor}`}>
            ${tearsheet.total_pnl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-gray-500 mt-1 font-mono">Net of slippage & comm.</div>
        </div>

        {/* Total Return % */}
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="flex items-center justify-between text-xs text-gray-400 font-mono mb-1">
            <span>TOTAL RETURN</span>
            <Percent className="w-3.5 h-3.5 text-gray-500" />
          </div>
          <div className={`text-xl font-bold font-mono tabular-nums flex items-center gap-1 ${returnColor}`}>
            {isPositiveReturn ? <ArrowUpRight className="w-5 h-5" /> : <ArrowDownRight className="w-5 h-5" />}
            {tearsheet.total_return.toFixed(2)}%
          </div>
          <div className="text-[11px] text-gray-500 mt-1 font-mono">Base: ${tearsheet.capital_base.toFixed(2)}</div>
        </div>

        {/* Annualized Sharpe Ratio */}
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="flex items-center justify-between text-xs text-gray-400 font-mono mb-1">
            <span>SHARPE RATIO</span>
            <TrendingUp className="w-3.5 h-3.5 text-gray-500" />
          </div>
          <div className="text-xl font-bold font-mono tabular-nums text-white">
            {tearsheet.sharpe_ratio !== null ? tearsheet.sharpe_ratio.toFixed(2) : 'N/A'}
          </div>
          <div className="text-[11px] text-gray-500 mt-1 font-mono">Rf = 3.78% (3m T-Bill)</div>
        </div>

        {/* Max Drawdown */}
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="flex items-center justify-between text-xs text-gray-400 font-mono mb-1">
            <span>MAX DRAWDOWN</span>
            <TrendingDown className="w-3.5 h-3.5 text-gray-500" />
          </div>
          <div className={`text-xl font-bold font-mono tabular-nums ${colorblindMode ? 'text-amber-400' : 'text-rose-400'}`}>
            {tearsheet.max_drawdown !== null ? `${tearsheet.max_drawdown.toFixed(2)}%` : '0.00%'}
          </div>
          <div className="text-[11px] text-gray-500 mt-1 font-mono">Strict peak-to-trough</div>
        </div>

        {/* Friction Model Audit */}
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4 col-span-2 md:col-span-1">
          <div className="flex items-center justify-between text-xs text-gray-400 font-mono mb-1">
            <span>COST MODEL</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-sm font-semibold font-mono text-cyan-300">
            ${tearsheet.commission_per_trade.toFixed(2)} / 5.0 bps
          </div>
          <div className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1 font-mono">
            <span>✓ Reconciled (1e-9)</span>
          </div>
        </div>
      </div>

      {/* Chart Section */}
      <div className="space-y-4 bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Per-Bar Equity Growth & Underwater Drawdown
            </h3>
            <p className="text-xs text-gray-400">
              Reconciles bit-for-bit to harness trade log P&L. Initial capital anchored at first close.
            </p>
          </div>

          <button
            onClick={() => setShowAccessibleTable(!showAccessibleTable)}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded bg-[#161D29] border border-[#263145] text-gray-300 hover:text-white transition-colors"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span>{showAccessibleTable ? 'Hide Tabular Data' : 'View as Accessible Table'}</span>
          </button>
        </div>

        {showAccessibleTable ? (
          <div className="max-h-72 overflow-y-auto border border-[#1C2331] rounded text-xs font-mono">
            <table className="w-full text-left">
              <thead className="bg-[#141A24] text-gray-400 sticky top-0">
                <tr>
                  <th className="p-2 border-b border-[#1C2331]">Date</th>
                  <th className="p-2 border-b border-[#1C2331]">Position</th>
                  <th className="p-2 border-b border-[#1C2331]">Bar P&L</th>
                  <th className="p-2 border-b border-[#1C2331]">Equity</th>
                  <th className="p-2 border-b border-[#1C2331]">Drawdown</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C2331] text-gray-300">
                {tearsheet.equity_curve.slice(0, 100).map((pt, idx) => (
                  <tr key={idx} className="hover:bg-[#151C28]">
                    <td className="p-2">{pt.time}</td>
                    <td className="p-2">{pt.position}</td>
                    <td className="p-2">${pt.bar_pnl.toFixed(2)}</td>
                    <td className="p-2">${pt.equity.toFixed(2)}</td>
                    <td className="p-2">{pt.drawdown.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="space-y-3">
            <EquityCurveChart equityCurve={tearsheet.equity_curve} colorblindMode={colorblindMode} height={280} />
            <div>
              <div className="text-[11px] font-mono text-gray-400 mb-1">UNDERWATER DRAWDOWN PROFILE (%)</div>
              <DrawdownChart equityCurve={tearsheet.equity_curve} colorblindMode={colorblindMode} height={140} />
            </div>
          </div>
        )}
      </div>

      {/* Mandatory 3-Way Baseline Comparison Table (Rule 4) */}
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="mb-4">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Rule 4 Mandatory Baseline Comparison
            </h3>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-600/40 text-amber-400">
              Mandatory PR Gate
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            Evaluated over the identical period, with identical ${tearsheet.commission_per_trade.toFixed(2)}/trade commission and {tearsheet.slippage_bps.toFixed(1)} bps slippage applied to all three rows.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#141A24] text-gray-400 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-2.5 px-4 border-b border-[#1C2331]">Strategy / Baseline</th>
                <th className="py-2.5 px-4 border-b border-[#1C2331] text-right">Trades</th>
                <th className="py-2.5 px-4 border-b border-[#1C2331] text-right">Net P&L ($)</th>
                <th className="py-2.5 px-4 border-b border-[#1C2331] text-right">Win Rate</th>
                <th className="py-2.5 px-4 border-b border-[#1C2331] text-right">Sharpe Ratio</th>
                <th className="py-2.5 px-4 border-b border-[#1C2331] text-right">Max Drawdown</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1C2331] text-gray-200">
              {tearsheet.comparison_table.map((row, idx) => (
                <tr key={idx} className={idx === 0 ? 'bg-cyan-950/20 font-semibold' : 'hover:bg-[#141A24]/40'}>
                  <td className="py-3 px-4 flex items-center gap-2">
                    {idx === 0 && <span className="h-2 w-2 rounded-full bg-cyan-400" />}
                    <span>{row.strategy_name}</span>
                  </td>
                  <td className="py-3 px-4 text-right tabular-nums">{row.total_trades}</td>
                  <td className={`py-3 px-4 text-right tabular-nums font-bold ${
                    row.net_pnl >= 0
                      ? colorblindMode ? 'text-cyan-400' : 'text-emerald-400'
                      : colorblindMode ? 'text-amber-400' : 'text-rose-400'
                  }`}>
                    ${row.net_pnl.toFixed(2)}
                    {row.std_pnl !== null && (
                      <span className="text-gray-400 font-normal text-[10px] ml-1">
                        (±${row.std_pnl.toFixed(2)})
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-right tabular-nums">
                    {row.win_rate !== null ? `${row.win_rate.toFixed(1)}%` : '—'}
                  </td>
                  <td className="py-3 px-4 text-right tabular-nums">
                    {row.sharpe_ratio !== null ? row.sharpe_ratio.toFixed(2) : '—'}
                  </td>
                  <td className="py-3 px-4 text-right tabular-nums">
                    {row.max_drawdown !== null ? `${row.max_drawdown.toFixed(2)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Trade Log Ledger */}
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Executed Trades Ledger
            </h3>
            <p className="text-xs text-gray-400">
              Recorded next-open fills, slipped prices, and trade P&L net of commissions.
            </p>
          </div>
          <span className="text-xs font-mono text-gray-400">
            {tearsheet.trade_log.length} Completed Trades
          </span>
        </div>

        <div className="max-h-72 overflow-y-auto border border-[#1C2331] rounded">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#141A24] text-gray-400 sticky top-0 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-2.5 px-3.5 border-b border-[#1C2331]">Entry Date</th>
                <th className="py-2.5 px-3.5 border-b border-[#1C2331] text-right">Entry Price</th>
                <th className="py-2.5 px-3.5 border-b border-[#1C2331]">Exit Date</th>
                <th className="py-2.5 px-3.5 border-b border-[#1C2331] text-right">Exit Price</th>
                <th className="py-2.5 px-3.5 border-b border-[#1C2331] text-right">Trade P&L</th>
                <th className="py-2.5 px-3.5 border-b border-[#1C2331] text-right">Cumulative P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1C2331] text-gray-300">
              {tearsheet.trade_log.map((trade, idx) => {
                const isWinner = trade.pnl >= 0;
                return (
                  <tr key={idx} className="hover:bg-[#141A24]/60">
                    <td className="py-2 px-3.5 text-gray-300">{trade.entry_date}</td>
                    <td className="py-2 px-3.5 text-right tabular-nums">${trade.entry_price.toFixed(2)}</td>
                    <td className="py-2 px-3.5 text-gray-300">{trade.exit_date}</td>
                    <td className="py-2 px-3.5 text-right tabular-nums">${trade.exit_price.toFixed(2)}</td>
                    <td className={`py-2 px-3.5 text-right tabular-nums font-semibold ${
                      isWinner
                        ? colorblindMode ? 'text-cyan-400' : 'text-emerald-400'
                        : colorblindMode ? 'text-amber-400' : 'text-rose-400'
                    }`}>
                      ${trade.pnl.toFixed(2)}
                    </td>
                    <td className="py-2 px-3.5 text-right tabular-nums text-white">
                      ${trade.cumulative_pnl.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
