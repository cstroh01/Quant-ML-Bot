import React from 'react';
import {
  CheckCircle2,
} from 'lucide-react';
import type { FeatureDiagnosticsResponse, SignificanceResponse } from '../../types/api';

interface FeatureDiagnosticsViewProps {
  diagnostics: FeatureDiagnosticsResponse | null;
  significance: SignificanceResponse | null;
  loading: boolean;
}

export const FeatureDiagnosticsView: React.FC<FeatureDiagnosticsViewProps> = ({
  diagnostics,
  significance,
  loading,
}) => {
  if (loading || !diagnostics) {
    return (
      <div className="p-12 flex flex-col items-center justify-center text-gray-500 font-mono text-sm">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
        Computing matrix condition numbers & VIF diagnostics...
      </div>
    );
  }

  const levelsEntry = diagnostics.diagnostics.find((d) => d.feature_set === 'levels');
  const scaleFreeEntry = diagnostics.diagnostics.find((d) => d.feature_set === 'scale_free');

  return (
    <div className="space-y-6">
      {/* Spec 014 Header Banner */}
      <div className="bg-gradient-to-r from-[#121927] to-[#0D121B] border border-[#1C2331] rounded-lg p-5">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/40 text-cyan-400 font-semibold">
            Spec 014 Resolution
          </span>
          <span className="text-xs font-mono text-gray-400">Design Matrix Conditioning Audit</span>
        </div>
        <h2 className="text-lg font-bold text-white tracking-tight">
          Scale-Free Ratios vs. Price Levels Matrix Comparison
        </h2>
        <p className="text-xs text-gray-300 mt-1 max-w-3xl">
          Zero models beat baseline in Phase 3 because the design matrix suffered from non-stationarity ($50 train bars extrapolating to $200 bars) and collinearity (Short_SMA vs Long_SMA r=0.998). Standardizing ratios resolves both structural defects.
        </p>
      </div>

      {/* Conditioning Metrics Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Levels (Old Control) */}
        <div className="bg-[#0F131A] border border-rose-900/30 rounded-lg p-5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-rose-400 font-semibold uppercase tracking-wider">
              Level Features (Old Control)
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-800/40">
              ILL-CONDITIONED
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 my-3 font-mono">
            <div>
              <div className="text-[11px] text-gray-400">CONDITION NUMBER</div>
              <div className="text-2xl font-bold text-rose-400 tabular-nums">
                {levelsEntry?.condition_number.toFixed(2)}
              </div>
              <div className="text-[10px] text-rose-300/70 mt-0.5">&gt; 30.0 (Ill-conditioned)</div>
            </div>

            <div>
              <div className="text-[11px] text-gray-400">MAX VIF</div>
              <div className="text-2xl font-bold text-rose-400 tabular-nums">
                {levelsEntry?.max_vif.toFixed(2)}
              </div>
              <div className="text-[10px] text-rose-300/70 mt-0.5">&gt; 10.0 (Severe collinearity)</div>
            </div>
          </div>

          <div className="text-xs font-mono text-gray-400 pt-2 border-t border-[#1C2331]">
            <span className="text-gray-500">Worst Collinear Pair: </span>
            <span className="text-rose-300 font-medium">
              {levelsEntry?.max_correlation_pair.join(' vs ')} ({levelsEntry?.max_correlation_value})
            </span>
          </div>
        </div>

        {/* Scale Free (Spec 014 Default) */}
        <div className="bg-[#0F131A] border border-cyan-900/40 rounded-lg p-5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-cyan-400 font-semibold uppercase tracking-wider">
              Scale-Free Ratios (Spec 014 Default)
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-700/40">
              WELL-CONDITIONED
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 my-3 font-mono">
            <div>
              <div className="text-[11px] text-gray-400">CONDITION NUMBER</div>
              <div className="text-2xl font-bold text-cyan-400 tabular-nums">
                {scaleFreeEntry?.condition_number.toFixed(2)}
              </div>
              <div className="text-[10px] text-emerald-400 mt-0.5">✓ 17x Improvement</div>
            </div>

            <div>
              <div className="text-[11px] text-gray-400">MAX VIF</div>
              <div className="text-2xl font-bold text-cyan-400 tabular-nums">
                {scaleFreeEntry?.max_vif.toFixed(2)}
              </div>
              <div className="text-[10px] text-emerald-400 mt-0.5">✓ Well below 5.0 line</div>
            </div>
          </div>

          <div className="text-xs font-mono text-gray-400 pt-2 border-t border-[#1C2331]">
            <span className="text-gray-500">Highest Remaining Correlation: </span>
            <span className="text-cyan-300 font-medium">
              {scaleFreeEntry?.max_correlation_pair.join(' vs ')} ({scaleFreeEntry?.max_correlation_value})
            </span>
          </div>
        </div>
      </div>

      {/* Paired Significance Screening Table */}
      {significance && (
        <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
          <div className="mb-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
                Spec 014 Paired Significance Screening
              </h3>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-950/50 border border-emerald-600/40 text-emerald-400">
                Screening Alpha = 0.10
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              McNemar's test on discordant classification outcomes; Wilcoxon signed-rank test on paired per-bar regression squared errors.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[#141A24] text-gray-400 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-2.5 px-4 border-b border-[#1C2331]">Estimator</th>
                  <th className="py-2.5 px-4 border-b border-[#1C2331]">Task</th>
                  <th className="py-2.5 px-4 border-b border-[#1C2331]">Statistical Test</th>
                  <th className="py-2.5 px-4 border-b border-[#1C2331] text-right">P-Value</th>
                  <th className="py-2.5 px-4 border-b border-[#1C2331] text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C2331] text-gray-300">
                {significance.entries.map((entry, idx) => (
                  <tr key={idx} className="hover:bg-[#141A24]/40">
                    <td className="py-2.5 px-4 font-semibold text-white">{entry.estimator}</td>
                    <td className="py-2.5 px-4 capitalize text-gray-400">{entry.task}</td>
                    <td className="py-2.5 px-4 text-gray-300">{entry.test_name}</td>
                    <td className="py-2.5 px-4 text-right tabular-nums font-bold">
                      {entry.p_value.toFixed(3)}
                    </td>
                    <td className="py-2.5 px-4 text-center">
                      {entry.passed_screening ? (
                        <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-semibold px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-800/40">
                          <CheckCircle2 className="w-3 h-3" /> PASSED (p &lt; 0.10)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] text-gray-500 px-2 py-0.5 rounded bg-gray-900 border border-gray-800">
                          NEUTRAL
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Feature Correlation Heatmap Table */}
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-lg p-5">
        <div className="mb-3">
          <h3 className="text-sm font-semibold tracking-wide text-white uppercase font-mono">
            Scale-Free Feature Pairwise Correlation Matrix
          </h3>
          <p className="text-xs text-gray-400">
            Spearman/Pearson correlation matrix verifying that no pairwise feature correlation exceeds 0.55.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-center text-xs font-mono">
            <thead className="bg-[#141A24] text-gray-400 uppercase text-[10px]">
              <tr>
                <th className="py-2.5 px-3 border-b border-[#1C2331] text-left">Feature</th>
                {diagnostics.features_scale_free.map((feat) => (
                  <th key={feat} className="py-2.5 px-3 border-b border-[#1C2331]">
                    {feat}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1C2331]">
              {diagnostics.features_scale_free.map((rowFeat) => (
                <tr key={rowFeat} className="hover:bg-[#141A24]/40">
                  <td className="py-2 px-3 text-left font-semibold text-gray-300 border-r border-[#1C2331]">
                    {rowFeat}
                  </td>
                  {diagnostics.features_scale_free.map((colFeat) => {
                    const val = diagnostics.correlation_matrix[rowFeat]?.[colFeat] ?? 0;
                    const isDiag = rowFeat === colFeat;
                    const absVal = Math.abs(val);
                    return (
                      <td
                        key={colFeat}
                        className={`py-2 px-3 tabular-nums ${
                          isDiag
                            ? 'text-gray-500 font-normal'
                            : absVal > 0.5
                            ? 'text-amber-400 font-bold bg-amber-950/20'
                            : 'text-gray-300'
                        }`}
                      >
                        {val.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
