import React from 'react';
import {
  CheckCircle2,
  Clock,
  Lock,
  Shield,
} from 'lucide-react';
import type { CapitalGateStatusResponse } from '../../types/api';
import { TutorCard } from '../common/TutorCard';

interface CapitalGateViewProps {
  gateStatus: CapitalGateStatusResponse | null;
  loading: boolean;
  tutorMode?: boolean;
}

export const CapitalGateView: React.FC<CapitalGateViewProps> = ({ gateStatus, loading, tutorMode = true }) => {
  if (loading || !gateStatus) {
    return (
      <div className="p-12 flex flex-col items-center justify-center text-gray-500 font-mono text-sm">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
        Auditing Capital Gate readiness status...
      </div>
    );
  }

  const passedCount = gateStatus.gates.filter((g) => g.status === 'passed').length;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-[#111927] to-[#0A0E17] border border-[#1C2331] rounded-lg p-5">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-cyan-400" />
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-cyan-400">
              Project Instructions §12 Capital Gate
            </span>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-[#161D29] border border-[#263145] text-white">
            {passedCount} of 5 Gates Passed
          </span>
        </div>

        <h2 className="text-xl font-bold text-white tracking-tight">
          Pre-Live Capital Allocation Checklist
        </h2>
        <p className="text-xs text-gray-300 mt-1 max-w-3xl">
          The money goal is gated, not asserted. Most retail algo/ML trading strategies lose money due to overfitting. This checklist must pass in order before any dollar of real capital touches live broker routing.
        </p>

        {/* Readiness Meter */}
        <div className="mt-4 pt-3 border-t border-[#1C2331] flex items-center justify-between text-xs font-mono">
          <span className="text-gray-400">Current Readiness Stage:</span>
          <span className="text-cyan-300 font-semibold">{gateStatus.overall_readiness}</span>
        </div>
      </div>

      {/* Tutor Decoder */}
      {tutorMode && (
        <TutorCard
          title="Understanding The 5 Capital Gates: From Idea to Institutional Fund"
          badge="QUANT DECODER: CAPITAL GATES"
          whatItMeans="The number one mistake retail traders make is deploying real money immediately after seeing one attractive backtest chart. In reality, backtests without friction, leakage checks, or live forward testing are financial illusions. The 5 Capital Gates are non-negotiable gates that prove your algorithmic system is robust before risking a single dollar."
          whatItRepresents="Gate 1 verifies clean, split/dividend adjusted historical data. Gate 2 enforces well-conditioned, scale-free features with low collinearity. Gate 3 requires leak-free purged/embargoed walk-forward cross-validation. Gate 4 mandates realistic execution friction modeling (commissions + slippage). Gate 5 requires paper-trading forward testing to match simulated returns."
          howToInterpret="Passed gates (green checkmark) are mathematically verified and audited. In-Progress gates (spinning cyan indicator) are where the engineering focus currently sits. Pending gates (gray lock) cannot be unlocked out-of-order. This guarantees disciplined founder execution and prevents capital catastrophe."
          howToPlan="1. Treat the gates as your engineering roadmap — never skip a gate. 2. Currently, focus on finishing Gate 4 and establishing Gate 5 paper trading infrastructure. 3. Remember §12: the software framework is open-source and professional, while the money goal is gated and earned through rigorous validation."
        />
      )}

      {/* 5-Gate Accordion / Checklist Cards */}
      <div className="space-y-3 font-mono text-xs">
        {gateStatus.gates.map((gate) => {
          const isPassed = gate.status === 'passed';
          const isInProgress = gate.status === 'in_progress';

          return (
            <div
              key={gate.gate_number}
              className={`p-5 rounded-lg border transition-all ${
                isPassed
                  ? 'bg-[#0E1520] border-emerald-900/40'
                  : isInProgress
                  ? 'bg-[#121620] border-cyan-800/50 shadow-lg shadow-cyan-950/20'
                  : 'bg-[#0C0F16] border-[#1C2331] opacity-75'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">
                    {isPassed ? (
                      <div className="h-6 w-6 rounded-full bg-emerald-950/60 border border-emerald-500/50 flex items-center justify-center text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      </div>
                    ) : isInProgress ? (
                      <div className="h-6 w-6 rounded-full bg-cyan-950/60 border border-cyan-500/50 flex items-center justify-center text-cyan-400">
                        <Clock className="w-3.5 h-3.5 animate-spin" />
                      </div>
                    ) : (
                      <div className="h-6 w-6 rounded-full bg-gray-900 border border-gray-700 flex items-center justify-center text-gray-500">
                        <Lock className="w-3.5 h-3.5" />
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold text-gray-500 uppercase">
                        Gate 0{gate.gate_number}
                      </span>
                      <h3 className="text-sm font-bold text-white tracking-wide">
                        {gate.title}
                      </h3>
                    </div>
                    <p className="text-gray-300 mt-1 leading-relaxed text-xs">
                      {gate.description}
                    </p>
                  </div>
                </div>

                <div>
                  {isPassed ? (
                    <span className="px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 font-semibold text-[11px]">
                      PASSED
                    </span>
                  ) : isInProgress ? (
                    <span className="px-2.5 py-1 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-700/40 font-semibold text-[11px]">
                      IN PROGRESS
                    </span>
                  ) : (
                    <span className="px-2.5 py-1 rounded bg-gray-900 text-gray-500 border border-gray-800 font-medium text-[11px]">
                      PENDING
                    </span>
                  )}
                </div>
              </div>

              {/* Details & Verification Evidence */}
              <div className="mt-3 pt-3 border-t border-[#1C2331] text-[11px] space-y-1">
                <div className="text-gray-400">
                  <span className="text-gray-500">Audit Status: </span>
                  <span className={isPassed ? 'text-emerald-300' : 'text-gray-300'}>
                    {gate.details}
                  </span>
                </div>
                {gate.evidence && (
                  <div className="text-gray-400">
                    <span className="text-gray-500">Evidence: </span>
                    <span className="text-cyan-300">{gate.evidence}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
