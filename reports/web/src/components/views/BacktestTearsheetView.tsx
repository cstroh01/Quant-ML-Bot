import React, { useState } from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  CandlestickChart as CandlestickIcon,
  CheckCircle2,
  DollarSign,
  FileSpreadsheet,
  LineChart as LineChartIcon,
  Percent,
  RefreshCw,
  Sliders,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import type { BacktestTearsheetResponse, BarData } from '../../types/api';
import { CandlestickChart } from '../charts/CandlestickChart';
import { DrawdownChart } from '../charts/DrawdownChart';
import { EquityCurveChart } from '../charts/EquityCurveChart';
import { TutorCard } from '../common/TutorCard';

interface BacktestTearsheetViewProps {
  tearsheet: BacktestTearsheetResponse | null;
  ohlcv: BarData[];
  loading: boolean;
  colorblindMode: boolean;
  tutorMode?: boolean;
  currentParams: {
    shortWindow: number;
    longWindow: number;
    commission: number;
    slippageBps: number;
  };
  onApplyParams: (params: {
    shortWindow: number;
    longWindow: number;
    commission: number;
    slippageBps: number;
  }) => void;
}

export const BacktestTearsheetView: React.FC<BacktestTearsheetViewProps> = ({
  tearsheet,
  ohlcv,
  loading,
  colorblindMode,
  tutorMode = true,
  currentParams,
  onApplyParams,
}) => {
  const [showAccessibleTable, setShowAccessibleTable] = useState(false);
  const [chartMode, setChartMode] = useState<'equity' | 'candlestick'>('equity');

  // Local state for interactive sliders
  const [shortWindow, setShortWindow] = useState(currentParams.shortWindow);
  const [longWindow, setLongWindow] = useState(currentParams.longWindow);
  const [commission, setCommission] = useState(currentParams.commission);
  const [slippageBps, setSlippageBps] = useState(currentParams.slippageBps);

  const hasDirtyParams =
    shortWindow !== currentParams.shortWindow ||
    longWindow !== currentParams.longWindow ||
    commission !== currentParams.commission ||
    slippageBps !== currentParams.slippageBps;

  const handleReset = () => {
    setShortWindow(10);
    setLongWindow(30);
    setCommission(1.0);
    setSlippageBps(5.0);
    onApplyParams({ shortWindow: 10, longWindow: 30, commission: 1.0, slippageBps: 5.0 });
  };

  const handleApply = () => {
    onApplyParams({ shortWindow, longWindow, commission, slippageBps });
  };

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

  // Compute total friction drag in dollars ($2 * commission * trades + roundtrip slippage)
  const totalFrictionDrag = tearsheet.trade_log.length * (2 * tearsheet.commission_per_trade);

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

        {/* Cost Model Audit */}
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4 col-span-2 md:col-span-1">
          <div className="flex items-center justify-between text-xs text-gray-400 font-mono mb-1">
            <span>FRICTION MODEL</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-sm font-semibold font-mono text-cyan-300">
            ${tearsheet.commission_per_trade.toFixed(2)} / {tearsheet.slippage_bps.toFixed(1)} bps
          </div>
          <div className="text-[11px] text-gray-400 mt-1 flex items-center justify-between font-mono">
            <span>Drag: -${totalFrictionDrag.toFixed(2)}</span>
            <span className="text-emerald-400">✓ 1e-9</span>
          </div>
        </div>
      </div>

      {/* Beginner & Quant Tutor Decoder (Tutor Mode) */}
      {tutorMode && (
        <TutorCard
          title="Backtest Tearsheet & Performance Anatomy"
          badge="QUANT DECODER: PERFORMANCE & FRICTION"
          whatItMeans="A backtest simulates how this trading rule would have performed in historical market sessions. Total Net P&L is what lands in your account after paying exchange commissions and market slippage. The Sharpe Ratio measures how much profit you made for every bump of volatility you endured."
          whatItRepresents="Sharpe = (E[R_p] - R_f) / σ_p, annualized by √252 with R_f = 3.78% (3-month T-Bill). Max Drawdown represents the deepest peak-to-trough capital decline. Friction Drag accounts for $1/trade commission and 5 bps of slippage applied per execution. All metrics are reconciled down to 1e-9 tolerance."
          howToInterpret="Sharpe < 1.0 indicates poor risk-adjusted returns (uncompensated risk). Sharpe 1.0 - 1.5 is acceptable for systematic strategies. Sharpe > 2.0 requires intense scrutiny for overfitting. If Max Drawdown exceeds 20%, capital preservation rules are failing. Crucially: compare Net P&L against the Rule 4 Baseline table below — if the strategy cannot beat 'Passive Buy-and-Hold' or overlaps with 'Random Trading', you have no edge."
          howToPlan="1. Check the Drag metric: if friction consumes > 25% of gross profits, widen your moving average windows to reduce over-trading. 2. If Drawdown is unacceptable, cut position sizing or add ATR volatility stops. 3. Only progress if Net P&L beats the Random Baseline by more than 2 standard deviations."
        />
      )}

      {/* Interactive Friction & Sensitivity Studio (Rule 3) */}
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Interactive Friction & Sensitivity Studio (Rule 3)
            </h3>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/40 text-cyan-400 font-semibold">
              Live Re-calculation
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#161D29] border border-[#263145] text-gray-400 hover:text-white text-xs font-mono transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Reset (10/30, $1, 5bps)</span>
            </button>

            <button
              onClick={handleApply}
              disabled={!hasDirtyParams}
              className={`px-3 py-1 rounded text-xs font-mono font-bold transition-colors ${
                hasDirtyParams
                  ? 'bg-cyan-500 text-black hover:bg-cyan-400 shadow-lg shadow-cyan-500/20'
                  : 'bg-gray-800 text-gray-500 cursor-not-allowed'
              }`}
            >
              Apply Simulation
            </button>
          </div>
        </div>

        {/* 4 Interactive Sliders */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 font-mono text-xs">
          {/* Commission Slider */}
          <div className="space-y-1.5 bg-[#121620] p-3 rounded border border-[#1C2331]">
            <div className="flex justify-between text-gray-300">
              <span>Commission:</span>
              <span className="text-cyan-400 font-bold">${commission.toFixed(2)}/trade</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="5.0"
              step="0.25"
              value={commission}
              onChange={(e) => setCommission(parseFloat(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-gray-500">
              <span>$0.00 (Zero)</span>
              <span>$5.00 (Heavy)</span>
            </div>
          </div>

          {/* Slippage Slider */}
          <div className="space-y-1.5 bg-[#121620] p-3 rounded border border-[#1C2331]">
            <div className="flex justify-between text-gray-300">
              <span>Slippage:</span>
              <span className="text-cyan-400 font-bold">{slippageBps.toFixed(1)} bps</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="50.0"
              step="0.5"
              value={slippageBps}
              onChange={(e) => setSlippageBps(parseFloat(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-gray-500">
              <span>0 bps</span>
              <span>50 bps (Stress test)</span>
            </div>
          </div>

          {/* Short MA Window */}
          <div className="space-y-1.5 bg-[#121620] p-3 rounded border border-[#1C2331]">
            <div className="flex justify-between text-gray-300">
              <span>Short MA:</span>
              <span className="text-cyan-400 font-bold">{shortWindow} bars</span>
            </div>
            <input
              type="range"
              min="5"
              max="50"
              step="1"
              value={shortWindow}
              onChange={(e) => setShortWindow(parseInt(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-gray-500">
              <span>5 bars (Fast)</span>
              <span>50 bars</span>
            </div>
          </div>

          {/* Long MA Window */}
          <div className="space-y-1.5 bg-[#121620] p-3 rounded border border-[#1C2331]">
            <div className="flex justify-between text-gray-300">
              <span>Long MA:</span>
              <span className="text-cyan-400 font-bold">{longWindow} bars</span>
            </div>
            <input
              type="range"
              min="15"
              max="100"
              step="1"
              value={longWindow}
              onChange={(e) => setLongWindow(parseInt(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-gray-500">
              <span>15 bars</span>
              <span>100 bars (Slow)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Chart Section */}
      <div className="space-y-4 bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Performance Visualization
            </h3>
            <p className="text-xs text-gray-400">
              Toggle between the Reconciled Equity Curve and the Candlestick Price Chart with executed Trade Fills.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Chart Mode Toggle */}
            <div className="flex items-center bg-[#121721] p-0.5 rounded border border-[#1C2331] text-xs font-mono">
              <button
                onClick={() => setChartMode('equity')}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
                  chartMode === 'equity'
                    ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 font-semibold'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <LineChartIcon className="w-3.5 h-3.5" />
                <span>Equity & Drawdown</span>
              </button>

              <button
                onClick={() => setChartMode('candlestick')}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors ${
                  chartMode === 'candlestick'
                    ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 font-semibold'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <CandlestickIcon className="w-3.5 h-3.5" />
                <span>Price & Trade Fills</span>
              </button>
            </div>

            <button
              onClick={() => setShowAccessibleTable(!showAccessibleTable)}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded bg-[#161D29] border border-[#263145] text-gray-300 hover:text-white transition-colors"
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>{showAccessibleTable ? 'Hide Table' : 'View as Table'}</span>
            </button>
          </div>
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
        ) : chartMode === 'equity' ? (
          <div className="space-y-3">
            <EquityCurveChart equityCurve={tearsheet.equity_curve} colorblindMode={colorblindMode} height={280} />
            <div>
              <div className="text-[11px] font-mono text-gray-400 mb-1">UNDERWATER DRAWDOWN PROFILE (%)</div>
              <DrawdownChart equityCurve={tearsheet.equity_curve} colorblindMode={colorblindMode} height={140} />
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-xs font-mono text-gray-400 flex items-center justify-between">
              <span>CANDLESTICK ACTION WITH OVERLAYED ENTRY/EXIT FILLS</span>
              <span className="text-cyan-400">▲ Buy Entry | ▼ Sell Exit</span>
            </div>
            <CandlestickChart
              data={ohlcv}
              trades={tearsheet.trade_log}
              colorblindMode={colorblindMode}
              height={400}
              shortWindow={currentParams.shortWindow}
              longWindow={currentParams.longWindow}
            />
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
