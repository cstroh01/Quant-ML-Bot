import React from 'react';
import { X } from 'lucide-react';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const shortcuts = [
    { key: 'g b', description: 'Jump to Backtest & Tearsheet' },
    { key: 'g f', description: 'Jump to Feature Diagnostics (VIF / Matrix)' },
    { key: 'g c', description: 'Jump to Walk-Forward CV Studio' },
    { key: 'g d', description: 'Jump to Market Data & Calendar Gaps' },
    { key: 'g g', description: 'Jump to Capital Gate Cockpit (§12)' },
    { key: '?', description: 'Toggle Keyboard Shortcuts Modal' },
    { key: 'Esc', description: 'Close Modal' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-[#0F131A] border border-[#1C2331] rounded-xl max-w-md w-full p-6 shadow-2xl font-mono text-xs">
        <div className="flex items-center justify-between pb-3 border-b border-[#1C2331] mb-4">
          <h3 className="text-sm font-bold text-white tracking-wide uppercase">
            Terminal Keyboard Shortcuts
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 rounded hover:bg-[#161D29] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-2.5">
          {shortcuts.map((s) => (
            <div key={s.key} className="flex items-center justify-between py-1">
              <span className="text-gray-300">{s.description}</span>
              <kbd className="px-2 py-1 rounded bg-[#161D29] border border-[#212B3B] text-cyan-300 font-bold">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="mt-5 pt-3 border-t border-[#1C2331] text-[11px] text-gray-500 text-center">
          Press <kbd className="text-gray-400">Esc</kbd> or click outside to dismiss
        </div>
      </div>
    </div>
  );
};
