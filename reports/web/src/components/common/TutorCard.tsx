import React, { useState } from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  Compass,
  GraduationCap,
  Lightbulb,
  Scale,
} from 'lucide-react';

interface TutorCardProps {
  title: string;
  badge?: string;
  whatItMeans: string;
  whatItRepresents: string;
  howToInterpret: string;
  howToPlan: string;
  defaultExpanded?: boolean;
}

export const TutorCard: React.FC<TutorCardProps> = ({
  title,
  badge = 'QUANT TUTOR DECODER',
  whatItMeans,
  whatItRepresents,
  howToInterpret,
  howToPlan,
  defaultExpanded = true,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [activeTab, setActiveTab] = useState<'plain' | 'math' | 'interpret' | 'plan'>('plain');

  return (
    <div className="bg-[#0C1017] border border-cyan-900/40 rounded-lg overflow-hidden font-mono text-xs shadow-lg shadow-cyan-950/10">
      {/* Header Bar */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-4 py-2.5 bg-gradient-to-r from-[#101726] to-[#0A0D14] border-b border-[#1C2331] flex items-center justify-between cursor-pointer select-none hover:bg-[#141C2E] transition-colors"
      >
        <div className="flex items-center gap-2">
          <GraduationCap className="w-4 h-4 text-cyan-400" />
          <span className="font-bold text-white tracking-wide text-xs">{title}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950/70 border border-cyan-500/40 text-cyan-300 font-semibold uppercase">
            {badge}
          </span>
        </div>

        <button className="text-gray-400 hover:text-white transition-colors">
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {isExpanded && (
        <div className="p-4 space-y-3">
          {/* Navigation Tabs */}
          <div className="flex gap-1 border-b border-[#1C2331] pb-2 overflow-x-auto">
            <button
              onClick={() => setActiveTab('plain')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                activeTab === 'plain'
                  ? 'bg-cyan-500 text-black font-bold'
                  : 'bg-[#121620] text-gray-400 hover:text-gray-200'
              }`}
            >
              <Lightbulb className="w-3.5 h-3.5" />
              <span>1. Plain English</span>
            </button>

            <button
              onClick={() => setActiveTab('math')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                activeTab === 'math'
                  ? 'bg-cyan-500 text-black font-bold'
                  : 'bg-[#121620] text-gray-400 hover:text-gray-200'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>2. Quant Representation</span>
            </button>

            <button
              onClick={() => setActiveTab('interpret')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                activeTab === 'interpret'
                  ? 'bg-cyan-500 text-black font-bold'
                  : 'bg-[#121620] text-gray-400 hover:text-gray-200'
              }`}
            >
              <Scale className="w-3.5 h-3.5" />
              <span>3. How to Interpret</span>
            </button>

            <button
              onClick={() => setActiveTab('plan')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                activeTab === 'plan'
                  ? 'bg-cyan-500 text-black font-bold'
                  : 'bg-[#121620] text-gray-400 hover:text-gray-200'
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>4. How to Plan & Act</span>
            </button>
          </div>

          {/* Active Tab Content */}
          <div className="bg-[#121722] p-3.5 rounded border border-[#1C2538] text-gray-200 leading-relaxed text-xs">
            {activeTab === 'plain' && (
              <div className="space-y-1">
                <div className="text-cyan-400 font-bold text-[11px] flex items-center gap-1">
                  <Lightbulb className="w-3.5 h-3.5" />
                  <span>PLAIN ENGLISH TRANSLATION:</span>
                </div>
                <p>{whatItMeans}</p>
              </div>
            )}

            {activeTab === 'math' && (
              <div className="space-y-1">
                <div className="text-cyan-400 font-bold text-[11px] flex items-center gap-1">
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>QUANT MATHEMATICS & SYSTEM MECHANISM:</span>
                </div>
                <p>{whatItRepresents}</p>
              </div>
            )}

            {activeTab === 'interpret' && (
              <div className="space-y-1">
                <div className="text-cyan-400 font-bold text-[11px] flex items-center gap-1">
                  <Scale className="w-3.5 h-3.5" />
                  <span>BENCHMARKS & INTERPRETATION GUIDE:</span>
                </div>
                <p>{howToInterpret}</p>
              </div>
            )}

            {activeTab === 'plan' && (
              <div className="space-y-1">
                <div className="text-cyan-400 font-bold text-[11px] flex items-center gap-1">
                  <Compass className="w-3.5 h-3.5" />
                  <span>ACTIONABLE QUANT PLAYBOOK:</span>
                </div>
                <p>{howToPlan}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
