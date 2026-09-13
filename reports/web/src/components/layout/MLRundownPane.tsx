import React, { useState } from 'react';
import {
  Brain,
  ChevronRight,
  Compass,
  Cpu,
  HelpCircle,
} from 'lucide-react';
import type { MLRundownResponse } from '../../types/api';
import { NotComputedNotice } from '../common/NotComputedNotice';

interface MLRundownPaneProps {
  rundown: MLRundownResponse | null;
  loading: boolean;
  isOpen: boolean;
  onToggleOpen: () => void;
  colorblindMode: boolean;
}

export const MLRundownPane: React.FC<MLRundownPaneProps> = ({
  rundown,
  loading,
  isOpen,
  onToggleOpen,
  colorblindMode,
}) => {
  const [expandedInsight, setExpandedInsight] = useState<number | null>(1);

  if (!isOpen) {
    return (
      <button
        onClick={onToggleOpen}
        title="Open Indicator Readings Pane"
        className="fixed right-0 top-36 z-30 bg-[#0F131A] border-l border-y border-cyan-500/50 text-cyan-300 px-3 py-3 rounded-l-lg shadow-2xl flex flex-col items-center gap-2 font-mono text-xs hover:bg-[#151D2C] hover:text-white transition-all cursor-pointer"
      >
        <Brain className="w-5 h-5 text-cyan-400 animate-pulse" />
        <span className="[writing-mode:vertical-rl] tracking-widest font-bold uppercase text-[11px]">
          Indicator Readings
        </span>
      </button>
    );
  }

  return (
    <aside className="w-full lg:w-96 border-l border-[#1C2331] bg-[#0A0D13] flex flex-col h-full font-mono text-xs select-none">
      {/* Pane Top Header */}
      <div className="p-4 border-b border-[#1C2331] bg-[#0E131C] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-cyan-400" />
          <span className="font-bold text-white text-xs tracking-wide uppercase">
            Indicator Rule Readings
          </span>
        </div>

        <button
          onClick={onToggleOpen}
          className="p-1 rounded text-gray-400 hover:text-white hover:bg-[#161D29] transition-colors"
          title="Collapse Readings Pane"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Pane Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading || !rundown ? (
          <div className="p-8 text-center text-gray-500 flex flex-col items-center justify-center">
            <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-3" />
            Loading indicator readings...
          </div>
        ) : (
          <>
            {/* No fitted model is wired in (spec 018, finding 46) */}
            <NotComputedNotice label="Model forecast" reason={rundown.model_forecast.reason} />

            {/* Top Overall Rule Summary Card */}
            <div
              className={`p-3.5 rounded-lg border leading-relaxed ${
                rundown.verdict_status === 'bullish'
                  ? 'bg-emerald-950/25 border-emerald-700/40 text-emerald-200'
                  : rundown.verdict_status === 'bearish'
                  ? 'bg-rose-950/25 border-rose-700/40 text-rose-200'
                  : 'bg-amber-950/25 border-amber-700/40 text-amber-200'
              }`}
            >
              <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider mb-1 opacity-80">
                <span>Rule Summary</span>
                <span>As of {rundown.as_of_date}</span>
              </div>
              <div className="font-bold text-white text-xs mt-0.5">
                {rundown.summary_verdict}
              </div>
            </div>

            {/* Instruction Callout for Camden */}
            <div className="bg-[#121622] p-2.5 rounded border border-[#1E2638] text-[11px] text-gray-300">
              <span className="text-cyan-400 font-bold">🎓 Quick Guide: </span>
              These readings apply fixed indicator rules to the latest bar. They are not a model's output, and none of them measures whether its rule predicts returns.
            </div>

            {/* 5-Item Rundown */}
            <div className="space-y-3">
              {rundown.insights.map((item) => {
                const isExpanded = expandedInsight === item.rank;
                const statusColor =
                  item.status === 'bullish'
                    ? colorblindMode ? 'text-cyan-400 border-cyan-500/50 bg-cyan-950/40' : 'text-emerald-400 border-emerald-500/50 bg-emerald-950/40'
                    : item.status === 'bearish'
                    ? colorblindMode ? 'text-amber-400 border-amber-500/50 bg-amber-950/40' : 'text-rose-400 border-rose-500/50 bg-rose-950/40'
                    : item.status === 'caution'
                    ? 'text-amber-400 border-amber-500/50 bg-amber-950/40'
                    : 'text-gray-300 border-gray-700 bg-gray-900';

                return (
                  <div
                    key={item.rank}
                    className="rounded-lg border border-[#1C2331] bg-[#0E131C] overflow-hidden hover:border-[#2C384F] transition-all"
                  >
                    {/* Item Card Header */}
                    <div
                      onClick={() => setExpandedInsight(isExpanded ? null : item.rank)}
                      className="p-3 cursor-pointer flex items-center justify-between gap-2 hover:bg-[#131924] transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded bg-[#161D2B] border border-[#232F45] text-cyan-400 font-bold flex items-center justify-center text-[10px]">
                          0{item.rank}
                        </span>
                        <div>
                          <div className="text-[10px] uppercase font-semibold text-gray-400 tracking-wider">
                            {item.category}
                          </div>
                          <div className="font-bold text-white text-xs tracking-tight">
                            {item.headline}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded border font-bold ${statusColor}`}>
                          {item.status}
                        </span>
                      </div>
                    </div>

                    {/* Expandable Breakdown Body */}
                    {isExpanded && (
                      <div className="px-3.5 pb-3.5 pt-1 space-y-2.5 border-t border-[#161D29] bg-[#0B0E15]">
                        {/* Technical Reading */}
                        <div>
                          <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider flex items-center gap-1">
                            <Cpu className="w-3 h-3 text-cyan-400" />
                            <span>1. Technical Reading:</span>
                          </div>
                          <div className="mt-0.5 px-2 py-1 rounded bg-[#121622] border border-[#1A2233] text-cyan-300 text-[11px] font-mono">
                            {item.technical_reading}
                          </div>
                        </div>

                        {/* Plain English */}
                        <div>
                          <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider flex items-center gap-1">
                            <HelpCircle className="w-3 h-3 text-amber-400" />
                            <span>2. Plain English Translation:</span>
                          </div>
                          <p className="mt-0.5 text-gray-200 text-xs leading-relaxed">
                            {item.plain_english}
                          </p>
                        </div>

                        {/* Limits of the reading */}
                        <div>
                          <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider flex items-center gap-1">
                            <Compass className="w-3 h-3 text-emerald-400" />
                            <span>3. Limits of This Reading:</span>
                          </div>
                          <p className="mt-0.5 text-emerald-300 text-xs leading-relaxed bg-emerald-950/20 p-2 rounded border border-emerald-900/30">
                            {item.how_to_plan}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </aside>
  );
};
