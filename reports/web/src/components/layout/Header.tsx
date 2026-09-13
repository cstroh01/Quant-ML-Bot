import React from 'react';
import {
  Brain,
  Eye,
  GraduationCap,
  Keyboard,
} from 'lucide-react';
import type { NotComputed } from '../../types/api';

interface HeaderProps {
  currentTicker: string;
  tickers: string[];
  onSelectTicker: (ticker: string) => void;
  colorblindMode: boolean;
  onToggleColorblind: () => void;
  onOpenShortcuts: () => void;
  tutorMode: boolean;
  onToggleTutorMode: () => void;
  isMLPaneOpen: boolean;
  onToggleMLPane: () => void;
  testRun: NotComputed | null;
}

export const Header: React.FC<HeaderProps> = ({
  currentTicker,
  tickers,
  onSelectTicker,
  colorblindMode,
  onToggleColorblind,
  onOpenShortcuts,
  tutorMode,
  onToggleTutorMode,
  isMLPaneOpen,
  onToggleMLPane,
  testRun,
}) => {
  return (
    <header className="border-b border-[#1C2331] bg-[#0A0D12] px-6 py-3 flex flex-wrap items-center justify-between gap-4 select-none">
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
      <div className="flex items-center gap-2.5">
        {/* Tutor / Beginner Mode Toggle */}
        <button
          onClick={onToggleTutorMode}
          title="Toggle Beginner / Tutor Mode (Explains concepts in plain English)"
          className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-mono font-bold border transition-all ${
            tutorMode
              ? 'bg-cyan-500 text-black border-cyan-400 shadow-lg shadow-cyan-500/25'
              : 'bg-[#121721] border-[#1C2331] text-gray-400 hover:text-white'
          }`}
        >
          <GraduationCap className="w-4 h-4" />
          <span>{tutorMode ? '🎓 TUTOR MODE: ON' : '🎓 Tutor Mode'}</span>
        </button>

        {/* Indicator Readings Pane Toggle (rule readings, not model output: spec 018, finding 46) */}
        <button
          onClick={onToggleMLPane}
          title="Toggle Right-Side Indicator Readings Pane"
          className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-mono font-bold border transition-all ${
            isMLPaneOpen
              ? 'bg-purple-950/60 border-purple-500/60 text-purple-300 shadow-lg shadow-purple-900/20'
              : 'bg-[#121721] border-[#1C2331] text-gray-400 hover:text-white'
          }`}
        >
          <Brain className="w-4 h-4 text-purple-400" />
          <span>ML Rundown</span>
        </button>

        {/* Test status: the API reads no CI result, so no count or pass state is shown (spec 018, finding 47) */}
        <div
          title={testRun?.reason ?? 'Test status not reported'}
          className="hidden xl:flex items-center gap-2 px-2.5 py-1 rounded bg-[#121721] border border-[#1C2331] text-[11px] font-mono"
        >
          <span className="h-2 w-2 rounded-full bg-gray-600" />
          <span className="text-gray-400">TESTS: NOT REPORTED</span>
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
          <span>{colorblindMode ? 'CB P&L' : 'P&L'}</span>
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
