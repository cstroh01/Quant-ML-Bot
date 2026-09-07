import type {
  BacktestTearsheetResponse,
  BarData,
  CapitalGateStatusResponse,
  FeatureDiagnosticsResponse,
  GapsResponse,
  MarketStatsResponse,
  SignificanceResponse,
} from '../types/api';

const API_BASE = '/api';

export async function fetchTickers(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/data/tickers`);
  if (!res.ok) throw new Error(`Failed to fetch tickers: ${res.statusText}`);
  return res.json();
}

export async function fetchOhlcv(ticker: string): Promise<BarData[]> {
  const res = await fetch(`${API_BASE}/data/ohlcv?ticker=${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to fetch OHLCV: ${res.statusText}`);
  return res.json();
}

export async function fetchMarketStats(ticker: string): Promise<MarketStatsResponse> {
  const res = await fetch(`${API_BASE}/data/stats?ticker=${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.statusText}`);
  return res.json();
}

export async function fetchGaps(ticker: string): Promise<GapsResponse> {
  const res = await fetch(`${API_BASE}/data/gaps?ticker=${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to fetch calendar gaps: ${res.statusText}`);
  return res.json();
}

export async function fetchCollinearity(ticker: string): Promise<FeatureDiagnosticsResponse> {
  const res = await fetch(`${API_BASE}/diagnostics/collinearity?ticker=${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to fetch collinearity diagnostics: ${res.statusText}`);
  return res.json();
}

export async function fetchSignificance(ticker: string): Promise<SignificanceResponse> {
  const res = await fetch(`${API_BASE}/diagnostics/significance?ticker=${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to fetch significance results: ${res.statusText}`);
  return res.json();
}

export async function fetchBacktestTearsheet(
  ticker: string,
  shortWindow = 10,
  longWindow = 30,
  commission = 1.0,
  slippageBps = 5.0
): Promise<BacktestTearsheetResponse> {
  const url = `${API_BASE}/backtest/tearsheet?ticker=${encodeURIComponent(ticker)}&short_window=${shortWindow}&long_window=${longWindow}&commission=${commission}&slippage_bps=${slippageBps}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch backtest tearsheet: ${res.statusText}`);
  return res.json();
}

export async function fetchCapitalGateStatus(): Promise<CapitalGateStatusResponse> {
  const res = await fetch(`${API_BASE}/capital_gate/status`);
  if (!res.ok) throw new Error(`Failed to fetch capital gate status: ${res.statusText}`);
  return res.json();
}
