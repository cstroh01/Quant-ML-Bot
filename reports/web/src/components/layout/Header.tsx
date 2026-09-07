import React from 'react';
import { Eye, Keyboard, ShieldCheck } from 'lucide-react';

interface HeaderProps {
  currentTicker: string;
  tickers: string[];
  onSelectTicker: (ticker: string) => void;
  colorblindMode: boolean;
  onToggleColorblind: () => void;
  onOpenShortcuts: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentTicker,
  tickers,
  onSelectTicker,
  colorblindMode,
  onToggleColorblind,
  onOpenShortcuts,
}) => {
  return (
    <header className="border-b border-[#1C2331] bg-[#0A0D12] px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 select-none">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
            Q
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold tracking-tight text-white text-base">QUANT-ML-BOT</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-[#1C2331] text-cyan-400 font-medium">
                v2.1 §12 Terminal
              </span>
            </div>
            <p className="text-[11px] text-gray-400">Institutional Quant & AFML Research Console</p>
          </div>
        </div>

        <div className="h-5 w-px bg-[#1C2331] mx-1 hidden sm:block" />

        {/* Ticker Selector */}
        <div className="flex items-center gap-2">
          <label htmlFor="ticker-select" className="text-xs font-mono text-gray-400 uppercase">
            Asset:
          </label>
          <select
            id="ticker-select"
            value={currentTicker}
            onChange={(e) => onSelectTicker(e.target.value)}
            className="bg-[#121721] border border-[#1C2331] hover:border-[#2E384D] text-white text-sm font-mono font-semibold rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors cursor-pointer"
          >
            {tickers.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Right Action Items */}
      <div className="flex items-center gap-3">
        {/* Engine Status Badge */}
        <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded bg-[#121721] border border-[#1C2331] text-[11px] font-mono">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-gray-300">CORE: CONNECTED</span>
          <span className="text-gray-500">|</span>
          <span className="text-emerald-400 flex items-center gap-1 font-semibold">
            <ShieldCheck className="w-3.5 h-3.5" /> 310/310 PASS
          </span>
        </div>

        {/* Colorblind Palette Toggle */}
        <button
          onClick={onToggleColorblind}
          title="Toggle Colorblind-Safe P&L Palette (Cyan/Amber vs Emerald/Rose)"
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
            colorblindMode
              ? 'bg-amber-950/40 border-amber-600/50 text-amber-300'
              : 'bg-[#121721] border-[#1C2331] text-gray-300 hover:text-white hover:border-[#2E384D]'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          <span>{colorblindMode ? 'Colorblind P&L: ON' : 'Colorblind P&L'}</span>
        </button>

        {/* Shortcuts Help */}
        <button
          onClick={onOpenShortcuts}
          title="View Keyboard Shortcuts (?)"
          className="p-1.5 rounded bg-[#121721] border border-[#1C2331] text-gray-400 hover:text-white hover:border-[#2E384D] transition-colors"
        >
          <Keyboard className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
