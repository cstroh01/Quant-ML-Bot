import React from 'react';
import { Info, ShieldAlert } from 'lucide-react';
import { TutorCard } from '../common/TutorCard';

interface CrossValidationViewProps {
  tutorMode?: boolean;
}

export const CrossValidationView: React.FC<CrossValidationViewProps> = ({ tutorMode = true }) => {
  // Representative walk-forward folds from scripts/walk_forward_cv.py
  const folds = [
    { fold: 1, trainMonths: 'M1 - M6', purgeDays: '1 bar', testMonth: 'M7', embargoDays: '1 bar' },
    { fold: 2, trainMonths: 'M1 - M7', purgeDays: '1 bar', testMonth: 'M8', embargoDays: '1 bar' },
    { fold: 3, trainMonths: 'M1 - M8', purgeDays: '1 bar', testMonth: 'M9', embargoDays: '1 bar' },
    { fold: 4, trainMonths: 'M1 - M9', purgeDays: '1 bar', testMonth: 'M10', embargoDays: '1 bar' },
    { fold: 5, trainMonths: 'M1 - M10', purgeDays: '1 bar', testMonth: 'M11', embargoDays: '1 bar' },
    { fold: 6, trainMonths: 'M1 - M11', purgeDays: '1 bar', testMonth: 'M12', embargoDays: '1 bar' },
  ];

  return (
    <div className="space-y-6">
      {/* Top Banner explaining AFML Purged & Embargoed Cross-Validation */}
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/40 text-emerald-400 font-semibold">
            Constitution Rule 2
          </span>
          <span className="text-xs font-mono text-gray-400">López de Prado (AFML) Standard</span>
        </div>
        <h2 className="text-lg font-bold text-white tracking-tight">
          Purged & Embargoed Walk-Forward Cross-Validation
        </h2>
        <p className="text-xs text-gray-300 mt-1 max-w-3xl">
          Random k-fold and standard contiguous splits leak information across time because financial returns are serially correlated. For any label spanning horizon <span className="font-mono text-cyan-300">h</span>, observations within <span className="font-mono text-cyan-300">h</span> bars of the test boundary are purged, and an embargo gap is enforced before training resumes.
        </p>
      </div>

      {/* Tutor Decoder */}
      {tutorMode && (
        <TutorCard
          title="AFML Purging, Embargoing & Leakage Prevention"
          badge="QUANT DECODER: TIME-SERIES SPLITTING"
          whatItMeans="In normal AI (like recognizing photos of cats), you can shuffle data randomly. But in financial markets, you can never shuffle! What happened on Tuesday is tied to Monday. If a trading label spans 5 days into the future, and your training data touches those 5 days, your model cheats by reading tomorrow's newspaper. Purging and embargoing cut out those overlap zones so tests are completely honest."
          whatItRepresents="For an event label spanning horizon h bars: Purging removes all training samples whose event horizons overlap with the out-of-sample test window. Embargo removes e bars of training data immediately succeeding the test window to counter serial autoregression. Folds strictly expand forward in time (Walk-Forward)."
          howToInterpret="Notice the timeline below: the training window (emerald) expands forward. The amber buffer (purge) prevents forward-looking bias. The cyan bar is the strictly untouched out-of-sample test month. If a model's Sharpe drops significantly when moving from in-sample to these walk-forward folds, the model was overfitted."
          howToPlan="1. Always set your purge window h equal to or greater than your longest holding period. 2. Enforce a minimum 1-bar embargo gap. 3. Tune all model hyperparameters inside the inner folds (Nested CV) so test data never influences model tuning."
        />
      )}

      {/* Visual Timeline Folds Breakdown */}
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
              Expanding Window Split Architecture
            </h3>
            <p className="text-xs text-gray-400">
              Each outer fold fits models strictly on past data and evaluates strictly on future unseen bars.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded bg-emerald-600/60 border border-emerald-500" />
              <span className="text-gray-300">Training Window</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded bg-amber-500/70 border border-amber-400" />
              <span className="text-gray-300">Purge & Embargo</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded bg-cyan-500/70 border border-cyan-400" />
              <span className="text-gray-300">OOS Test Window</span>
            </div>
          </div>
        </div>

        {/* Horizontal Timeline Bars */}
        <div className="space-y-3 font-mono text-xs">
          {folds.map((f, i) => {
            const trainWidth = 35 + i * 8;
            return (
              <div key={f.fold} className="p-3 bg-[#131822] rounded border border-[#1C2331] flex items-center gap-4">
                <span className="w-16 font-bold text-gray-300">Fold {f.fold}</span>

                <div className="flex-1 flex h-7 rounded overflow-hidden bg-[#0A0D12] border border-[#1F2737] relative">
                  {/* Expanding Train */}
                  <div
                    style={{ width: `${trainWidth}%` }}
                    className="bg-emerald-900/50 border-r border-emerald-600/50 flex items-center justify-center text-[10px] text-emerald-200 font-medium px-2"
                  >
                    Train ({f.trainMonths})
                  </div>

                  {/* Purge Buffer */}
                  <div className="w-3 bg-amber-500/80 border-r border-amber-400/80" title="Purge window (h bars)" />

                  {/* Out of Sample Test Window */}
                  <div className="w-20 bg-cyan-600/60 border-r border-cyan-400/60 flex items-center justify-center text-[10px] text-cyan-200 font-semibold">
                    Test ({f.testMonth})
                  </div>

                  {/* Embargo Gap */}
                  <div className="w-3 bg-amber-600/60" title="Embargo window (e bars)" />
                </div>

                <div className="text-[11px] text-gray-400 w-32 text-right">
                  Test: <span className="text-cyan-300 font-semibold">{f.testMonth}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Rule 2 & Spec 006 Core Principles Callout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="flex items-center gap-2 text-cyan-400 font-semibold mb-2">
            <Info className="w-4 h-4" />
            <span>Nested Hyperparameter Search (Spec 011)</span>
          </div>
          <p className="text-gray-300 leading-relaxed">
            Hyperparameters are tuned strictly inside outer folds. The inner splitter builds sub-frames from outer train indices alone, ensuring zero information from the test set ever influences parameter selection.
          </p>
        </div>

        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-4">
          <div className="flex items-center gap-2 text-amber-400 font-semibold mb-2">
            <ShieldAlert className="w-4 h-4" />
            <span>Persistent Embargo Semantics (Spec 006)</span>
          </div>
          <p className="text-gray-300 leading-relaxed">
            Embargo gaps stay excluded permanently in a persistent ledger. A later fold's training data never touches an earlier fold's embargo zone, preventing serial correlation leaks across non-contiguous windows.
          </p>
        </div>
      </div>
    </div>
  );
};
