import React, { useEffect, useState } from 'react';
import { Header } from './components/layout/Header';
import { TabNavigation, type TerminalTab } from './components/layout/TabNavigation';
import { BacktestTearsheetView } from './components/views/BacktestTearsheetView';
import { CapitalGateView } from './components/views/CapitalGateView';
import { CrossValidationView } from './components/views/CrossValidationView';
import { FeatureDiagnosticsView } from './components/views/FeatureDiagnosticsView';
import { MarketDataView } from './components/views/MarketDataView';
import { KeyboardShortcutsModal } from './components/common/KeyboardShortcutsModal';
import {
  fetchBacktestTearsheet,
  fetchCapitalGateStatus,
  fetchCollinearity,
  fetchGaps,
  fetchMarketStats,
  fetchOhlcv,
  fetchSignificance,
  fetchTickers,
} from './services/api';
import type {
  BacktestTearsheetResponse,
  BarData,
  CapitalGateStatusResponse,
  FeatureDiagnosticsResponse,
  GapsResponse,
  MarketStatsResponse,
  SignificanceResponse,
} from './types/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TerminalTab>('backtest');
  const [currentTicker, setCurrentTicker] = useState<string>('AAPL');
  const [tickers, setTickers] = useState<string[]>(['AAPL', 'AMZN', 'GOOGL', 'MSFT', 'NVDA']);
  
  // Accessibility: Colorblind-Safe P&L mode
  const [colorblindMode, setColorblindMode] = useState<boolean>(() => {
    return localStorage.getItem('quant_terminal_cb_mode') === 'true';
  });

  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);

  // Data States
  const [ohlcv, setOhlcv] = useState<BarData[]>([]);
  const [stats, setStats] = useState<MarketStatsResponse | null>(null);
  const [gaps, setGaps] = useState<GapsResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<FeatureDiagnosticsResponse | null>(null);
  const [significance, setSignificance] = useState<SignificanceResponse | null>(null);
  const [tearsheet, setTearsheet] = useState<BacktestTearsheetResponse | null>(null);
  const [capitalGate, setCapitalGate] = useState<CapitalGateStatusResponse | null>(null);

  const [loading, setLoading] = useState<boolean>(true);

  // Toggle Colorblind Palette
  const toggleColorblind = () => {
    const next = !colorblindMode;
    setColorblindMode(next);
    localStorage.setItem('quant_terminal_cb_mode', String(next));
  };

  // Initial Load: Tickers and Capital Gate
  useEffect(() => {
    fetchTickers()
      .then((t) => {
        if (t.length > 0) setTickers(t);
      })
      .catch((err) => console.warn('Using default tickers fallback', err));

    fetchCapitalGateStatus()
      .then((gate) => setCapitalGate(gate))
      .catch((err) => console.warn('Using default capital gate fallback', err));
  }, []);

  // Load Ticker-specific Data
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchOhlcv(currentTicker).catch(() => []),
      fetchMarketStats(currentTicker).catch(() => null),
      fetchGaps(currentTicker).catch(() => null),
      fetchCollinearity(currentTicker).catch(() => null),
      fetchSignificance(currentTicker).catch(() => null),
      fetchBacktestTearsheet(currentTicker).catch(() => null),
    ]).then(([ohlcvData, statsData, gapsData, diagData, sigData, tsData]) => {
      setOhlcv(ohlcvData);
      setStats(statsData);
      setGaps(gapsData);
      setDiagnostics(diagData);
      setSignificance(sigData);
      setTearsheet(tsData);
      setLoading(false);
    });
  }, [currentTicker]);

  // Global Keyboard Shortcuts (g b, g f, g c, g d, g g, ?)
  useEffect(() => {
    let lastKey = '';
    let keyTimeout: ReturnType<typeof setTimeout> | null = null;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        return;
      }

      if (e.key === '?') {
        e.preventDefault();
        setIsShortcutsOpen((prev) => !prev);
        return;
      }

      if (e.key === 'Escape') {
        setIsShortcutsOpen(false);
        return;
      }

      if (lastKey === 'g') {
        if (e.key === 'b') setActiveTab('backtest');
        if (e.key === 'f') setActiveTab('diagnostics');
        if (e.key === 'c') setActiveTab('cv');
        if (e.key === 'd') setActiveTab('market');
        if (e.key === 'g') setActiveTab('capital_gate');
        lastKey = '';
        if (keyTimeout) clearTimeout(keyTimeout);
        return;
      }

      if (e.key === 'g') {
        lastKey = 'g';
        keyTimeout = setTimeout(() => {
          lastKey = '';
        }, 800);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      if (keyTimeout) clearTimeout(keyTimeout);
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#080A0E] text-gray-100 flex flex-col font-sans">
      {/* Header */}
      <Header
        currentTicker={currentTicker}
        tickers={tickers}
        onSelectTicker={setCurrentTicker}
        colorblindMode={colorblindMode}
        onToggleColorblind={toggleColorblind}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
      />

      {/* Tab Navigation */}
      <TabNavigation activeTab={activeTab} onSelectTab={setActiveTab} />

      {/* Main Terminal Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {activeTab === 'backtest' && (
          <BacktestTearsheetView
            tearsheet={tearsheet}
            loading={loading}
            colorblindMode={colorblindMode}
          />
        )}

        {activeTab === 'diagnostics' && (
          <FeatureDiagnosticsView
            diagnostics={diagnostics}
            significance={significance}
            loading={loading}
          />
        )}

        {activeTab === 'cv' && <CrossValidationView />}

        {activeTab === 'market' && (
          <MarketDataView
            ticker={currentTicker}
            ohlcv={ohlcv}
            stats={stats}
            gaps={gaps}
            loading={loading}
            colorblindMode={colorblindMode}
          />
        )}

        {activeTab === 'capital_gate' && (
          <CapitalGateView gateStatus={capitalGate} loading={loading} />
        )}
      </main>

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />
    </div>
  );
};

export default App;
