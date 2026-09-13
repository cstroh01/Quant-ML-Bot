import React from 'react';
import { Ban } from 'lucide-react';

interface NotComputedNoticeProps {
  label: string;
  reason: string;
}

/**
 * A value no computation produced (spec 018). Neutral grey on purpose: no
 * spinner, no pulse and no pass/fail colour, so it cannot read as loading,
 * passed or failed.
 */
export const NotComputedNotice: React.FC<NotComputedNoticeProps> = ({ label, reason }) => (
  <div className="flex items-start gap-2 rounded border border-gray-800 bg-gray-900/60 p-3 text-xs font-mono text-gray-400">
    <Ban className="w-3.5 h-3.5 mt-0.5 shrink-0 text-gray-500" />
    <div>
      <div className="font-semibold uppercase tracking-wider text-gray-300">{label}: not computed</div>
      <p className="mt-0.5 leading-relaxed">{reason}</p>
    </div>
  </div>
);
