import React from 'react';
import {
  CheckCircle2,
} from 'lucide-react';
import type { BarData, GapsResponse, MarketStatsResponse, TradeRecord } from '../../types/api';
import { CandlestickChart } from '../charts/CandlestickChart';
import { TutorCard } from '../common/TutorCard';

interface MarketDataViewProps {
  ticker: string;
  ohlcv: BarData[];
  trades?: TradeRecord[];
  stats: MarketStatsResponse | null;
  gaps: GapsResponse | null;
  loading: boolean;
  colorblindMode: boolean;
  tutorMode?: boolean;
}

export const MarketDataView: React.FC<MarketDataViewProps> = ({
  ticker,
  ohlcv,
  trades = [],
  stats,
  gaps,
  loading,
  colorblindMode,
  tutorMode = true,
}) => {
  if (loading || !stats) {
    return (
      <div className="p-12 flex flex-col items-center justify-center text-gray-500 font-mono text-sm">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
        Loading cached OHLCV market bars & calendar diagnostics...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Return Statistics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="text-xs text-gray-400 font-mono mb-1">ANNUAL VOLATILITY</div>
          <div className="text-xl font-bold font-mono text-white tabular-nums">
            {(stats.annual_volatility * 100).toFixed(2)}%
          </div>
          <div className="text-[11px] text-gray-500 mt-1 font-mono">252-day annualized</div>
        </div>

        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="text-xs text-gray-400 font-mono mb-1">EXCESS KURTOSIS</div>
          <div className="text-xl font-bold font-mono text-amber-400 tabular-nums">
            {stats.excess_kurtosis.toFixed(2)}
          </div>
          <div className="text-[11px] text-gray-400 mt-1 font-mono">Fat tails (3.0 - 12.0)</div>
        </div>

        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="text-xs text-gray-400 font-mono mb-1">RETURN SKEWNESS</div>
          <div className="text-xl font-bold font-mono text-white tabular-nums">
            {stats.skewness.toFixed(3)}
          </div>
          <div className="text-[11px] text-gray-500 mt-1 font-mono">Lopsidedness metric</div>
        </div>

        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="text-xs text-gray-400 font-mono mb-1">MAX HISTORICAL DRAWDOWN</div>
          <div className={`text-xl font-bold font-mono tabular-nums ${colorblindMode ? 'text-amber-400' : 'text-rose-400'}`}>
            {(stats.max_drawdown * 100).toFixed(2)}%
          </div>
          <div className="text-[11px] text-gray-500 mt-1 font-mono truncate">
            {stats.peak_date} → {stats.trough_date}
          </div>
        </div>
      </div>

      {/* Tutor Decoder */}
      {tutorMode && (
        <TutorCard
          title="Market Data Dynamics: Volatility, Fat Tails & Exchange Calendars"
          badge="QUANT DECODER: MARKET DISTRIBUTIONS"
          whatItMeans="Stock markets do not behave like textbook bell curves. Freak crashes, flash crashes, and parabolic rallies occur far more often than naive probability calculates. This is called 'fat tails'. Volatility also clusters — a wild day is almost always followed by more wild days."
          whatItRepresents="Excess Kurtosis (Normal distribution = 0.0) quantifies the thickness of return tails. A kurtosis of 4 to 10+ represents high tail risk. Annualized Volatility is σ × √252. NYSE calendar gap detection ensures our time series has zero missing trading sessions without forward-filling synthetic prices."
          howToInterpret="If Excess Kurtosis is above 3.0, your stop losses will be hit by sudden gaps more often than Gaussian risk models predict. If Volatility is above 35%, expect wide whipsaws. When inspecting the NYSE Gap table below, ensure 'Zero Unexplained Gaps' is confirmed — missing sessions distort indicators and lead to spurious signals."
          howToPlan="1. In high-kurtosis regimes, downsize your trade allocations (use fractional Kelly sizing or ATR-based position sizing). 2. Never forward-fill missing market dates; fix data pipelines at the source. 3. Look at historical drawdown peak-to-trough dates to ensure your strategy survives historical market stress periods (e.g. 2020 crash, 2022 rate hikes)."
        />
      )}

      {/* Main Candlestick Chart */}
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              {ticker} Adjusted OHLCV & Volume Series
            </h3>
            <p className="text-xs text-gray-400">
              Split/dividend adjusted daily bars. Timezone-naive, midnight-normalized session convention.
            </p>
          </div>
          <span className="text-xs font-mono text-cyan-400 px-2 py-0.5 rounded bg-cyan-950/40 border border-cyan-800/40">
            {ohlcv.length} Sessions Loaded
          </span>
        </div>

        <CandlestickChart
          data={ohlcv}
          trades={trades}
          colorblindMode={colorblindMode}
          height={420}
        />
      </div>

      {/* NYSE Calendar Gaps Inspector (FR-009) */}
      {gaps && (
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
                  NYSE Calendar Gap Inspector (FR-009)
                </h3>
                {gaps.total_missing_bars === 0 ? (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/50 border border-emerald-600/40 text-emerald-400">
                    ZERO UNEXPLAINED GAPS
                  </span>
                ) : (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/50 border border-amber-600/40 text-amber-400">
                    {gaps.total_missing_bars} MISSING SESSIONS DETECTED
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Examines NYSE sessions with no observed bar against federal market holidays. Gaps are inspected, never forward or backward filled (Rule 1).
              </p>
            </div>
          </div>

          {gaps.total_missing_bars > 0 ? (
            <div className="bg-[#121721] rounded p-3 border border-[#1C2331] text-xs font-mono text-gray-300">
              <div className="text-[11px] text-gray-400 mb-1">SAMPLE UNEXPLAINED SESSIONS:</div>
              <div className="flex flex-wrap gap-2">
                {gaps.sample_dates.map((date) => (
                  <span key={date} className="px-2 py-1 rounded bg-[#161D2A] border border-[#232F42] text-amber-300">
                    {date}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-xs font-mono text-emerald-400 flex items-center gap-1.5 pt-1">
              <CheckCircle2 className="w-4 h-4" />
              <span>All expected trading sessions present in observed history.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
