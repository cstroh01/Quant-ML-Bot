import React, { useEffect, useState } from 'react';
import { Header } from './components/layout/Header';
import { MLRundownPane } from './components/layout/MLRundownPane';
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
  fetchMLRundown,
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
  MLRundownResponse,
  SignificanceResponse,
} from './types/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TerminalTab>('backtest');
  const [currentTicker, setCurrentTicker] = useState<string>('AAPL');
  const [tickers, setTickers] = useState<string[]>(['AAPL', 'AMZN', 'GOOGL', 'MSFT', 'NVDA']);
  
  // Backtest Simulation Parameters
  const [backtestParams, setBacktestParams] = useState({
    shortWindow: 10,
    longWindow: 30,
    commission: 1.0,
    slippageBps: 5.0,
  });

  // Accessibility: Colorblind-Safe P&L mode
  const [colorblindMode, setColorblindMode] = useState<boolean>(() => {
    return localStorage.getItem('quant_terminal_cb_mode') === 'true';
  });

  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);

  // Tutor / Beginner Mode (default ON to bridge high-level finance to plain English)
  const [tutorMode, setTutorMode] = useState<boolean>(true);

  // Right-Side ML Model Decision Rundown Pane (default ON)
  const [isMLPaneOpen, setIsMLPaneOpen] = useState<boolean>(true);

  // Data States
  const [ohlcv, setOhlcv] = useState<BarData[]>([]);
  const [stats, setStats] = useState<MarketStatsResponse | null>(null);
  const [gaps, setGaps] = useState<GapsResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<FeatureDiagnosticsResponse | null>(null);
  const [significance, setSignificance] = useState<SignificanceResponse | null>(null);
  const [tearsheet, setTearsheet] = useState<BacktestTearsheetResponse | null>(null);
  const [capitalGate, setCapitalGate] = useState<CapitalGateStatusResponse | null>(null);
  const [mlRundown, setMlRundown] = useState<MLRundownResponse | null>(null);

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
      fetchBacktestTearsheet(
        currentTicker,
        backtestParams.shortWindow,
        backtestParams.longWindow,
        backtestParams.commission,
        backtestParams.slippageBps
      ).catch(() => null),
      fetchMLRundown(currentTicker).catch(() => null),
    ]).then(([ohlcvData, statsData, gapsData, diagData, sigData, tsData, mlData]) => {
      setOhlcv(ohlcvData);
      setStats(statsData);
      setGaps(gapsData);
      setDiagnostics(diagData);
      setSignificance(sigData);
      setTearsheet(tsData);
      setMlRundown(mlData);
      setLoading(false);
    });
  }, [currentTicker, backtestParams]);

  const handleApplyParams = (newParams: typeof backtestParams) => {
    setBacktestParams(newParams);
  };

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
        tutorMode={tutorMode}
        onToggleTutorMode={() => setTutorMode((prev) => !prev)}
        isMLPaneOpen={isMLPaneOpen}
        onToggleMLPane={() => setIsMLPaneOpen((prev) => !prev)}
      />

      {/* Tab Navigation */}
      <TabNavigation activeTab={activeTab} onSelectTab={setActiveTab} />

      {/* Main Terminal Body with Side-by-Side ML Rundown Pane */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden w-full">
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
          {activeTab === 'backtest' && (
            <BacktestTearsheetView
              tearsheet={tearsheet}
              ohlcv={ohlcv}
              loading={loading}
              colorblindMode={colorblindMode}
              tutorMode={tutorMode}
              currentParams={backtestParams}
              onApplyParams={handleApplyParams}
            />
          )}

          {activeTab === 'diagnostics' && (
            <FeatureDiagnosticsView
              diagnostics={diagnostics}
              significance={significance}
              loading={loading}
              tutorMode={tutorMode}
            />
          )}

          {activeTab === 'cv' && <CrossValidationView tutorMode={tutorMode} />}

          {activeTab === 'market' && (
            <MarketDataView
              ticker={currentTicker}
              ohlcv={ohlcv}
              trades={tearsheet?.trade_log}
              stats={stats}
              gaps={gaps}
              loading={loading}
              colorblindMode={colorblindMode}
              tutorMode={tutorMode}
            />
          )}

          {activeTab === 'capital_gate' && (
            <CapitalGateView
              gateStatus={capitalGate}
              loading={loading}
              tutorMode={tutorMode}
            />
          )}
        </main>

        {/* 5-Item ML Rundown Right-Side Pane */}
        <MLRundownPane
          rundown={mlRundown}
          loading={loading}
          isOpen={isMLPaneOpen}
          onToggleOpen={() => setIsMLPaneOpen((prev) => !prev)}
          colorblindMode={colorblindMode}
        />
      </div>

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />
    </div>
  );
};

export default App;
