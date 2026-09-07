import React from 'react';
import {
  BarChart3,
  CheckCircle2,
  GitBranch,
  Layers,
  LineChart,
} from 'lucide-react';

export type TerminalTab = 'backtest' | 'diagnostics' | 'cv' | 'market' | 'capital_gate';

interface TabNavigationProps {
  activeTab: TerminalTab;
  onSelectTab: (tab: TerminalTab) => void;
}

export const TabNavigation: React.FC<TabNavigationProps> = ({ activeTab, onSelectTab }) => {
  const tabs: { id: TerminalTab; label: string; shortcut: string; icon: React.ReactNode }[] = [
    {
      id: 'backtest',
      label: 'Backtest & Tearsheet',
      shortcut: 'g b',
      icon: <LineChart className="w-4 h-4" />,
    },
    {
      id: 'diagnostics',
      label: 'Feature Diagnostics (VIF / Matrix)',
      shortcut: 'g f',
      icon: <Layers className="w-4 h-4" />,
    },
    {
      id: 'cv',
      label: 'Walk-Forward CV Studio',
      shortcut: 'g c',
      icon: <GitBranch className="w-4 h-4" />,
    },
    {
      id: 'market',
      label: 'Market Data & Calendar Gaps',
      shortcut: 'g d',
      icon: <BarChart3 className="w-4 h-4" />,
    },
    {
      id: 'capital_gate',
      label: 'Capital Gate Cockpit (§12)',
      shortcut: 'g g',
      icon: <CheckCircle2 className="w-4 h-4" />,
    },
  ];

  return (
    <nav className="border-b border-[#1C2331] bg-[#0C1017] px-6 flex overflow-x-auto select-none no-scrollbar">
      <div className="flex gap-1">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`flex items-center gap-2 py-3 px-3.5 border-b-2 text-xs font-medium transition-all whitespace-nowrap ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 bg-[#141A24]/60'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-700'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
              <span className="text-[10px] font-mono text-gray-500 bg-[#161D29] px-1.5 py-0.5 rounded border border-[#212B3B]">
                {tab.shortcut}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
