export interface BarData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketStatsResponse {
  ticker: string;
  bars_count: number;
  start_date: string;
  end_date: string;
  annual_volatility: number;
  skewness: number;
  excess_kurtosis: number;
  max_drawdown: number;
  peak_date: string | null;
  trough_date: string | null;
}

export interface GapsResponse {
  ticker: string;
  total_missing_bars: number;
  sample_dates: string[];
}

export interface CollinearityEntry {
  feature_set: string;
  condition_number: number;
  max_vif: number;
  max_vif_feature: string;
  max_correlation_pair: string[];
  max_correlation_value: number;
}

export interface FeatureDiagnosticsResponse {
  ticker: string;
  features_levels: string[];
  features_scale_free: string[];
  diagnostics: CollinearityEntry[];
  correlation_matrix: Record<string, Record<string, number>>;
}

export interface SignificanceEntry {
  estimator: string;
  task: string;
  test_name: string;
  p_value: number;
  alpha: number;
  passed_screening: boolean;
}

export interface SignificanceResponse {
  ticker: string;
  screening_alpha: number;
  entries: SignificanceEntry[];
}

export interface TradeRecord {
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  pnl: number;
  cumulative_pnl: number;
  holding_bars: number;
}

export interface BaselineComparisonRow {
  strategy_name: string;
  total_trades: number;
  net_pnl: number;
  win_rate: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  std_pnl: number | null;
}

export interface EquityPoint {
  time: string;
  equity: number;
  drawdown: number;
  position: number;
  bar_pnl: number;
}

export interface BacktestTearsheetResponse {
  ticker: string;
  strategy_name: string;
  commission_per_trade: number;
  slippage_bps: number;
  capital_base: number;
  total_return: number;
  total_pnl: number;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  reconciliation_passed: boolean;
  equity_curve: EquityPoint[];
  trade_log: TradeRecord[];
  comparison_table: BaselineComparisonRow[];
}

export interface CapitalGateItem {
  gate_number: number;
  title: string;
  description: string;
  status: 'passed' | 'in_progress' | 'pending';
  details: string;
  evidence: string | null;
}

export interface CapitalGateStatusResponse {
  overall_readiness: string;
  gates: CapitalGateItem[];
}
