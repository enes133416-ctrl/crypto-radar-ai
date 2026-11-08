export type Market = "spot" | "futures";
export type MarketFilter = Market | "all";

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  run_mode: string;
  demo_mode: boolean;
  collector_enabled: boolean;
  scanner_enabled: boolean;
  server_time: string;
}

export interface IndicatorSnapshot {
  interval: string;
  candle_count: number;
  close: number;
  ema9?: number | null;
  ema21?: number | null;
  ema50?: number | null;
  ema200?: number | null;
  rsi7?: number | null;
  rsi14?: number | null;
  rsi21?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  macd_histogram?: number | null;
  bb_upper?: number | null;
  bb_lower?: number | null;
  bb_width_pct?: number | null;
  atr?: number | null;
  atr_pct?: number | null;
  adx?: number | null;
  plus_di?: number | null;
  minus_di?: number | null;
  stoch_rsi_k?: number | null;
  stoch_rsi_d?: number | null;
  obv?: number | null;
  vwap20?: number | null;
  support?: number | null;
  resistance?: number | null;
  pivot?: number | null;
  change_5m_pct?: number | null;
  change_15m_pct?: number | null;
  change_1h_pct?: number | null;
  change_4h_pct?: number | null;
  change_24h_pct?: number | null;
  [key: string]: unknown;
}

export interface StrategyResult {
  name: "volume_explosion" | "consolidation_breakout" | "relative_strength" | "oversold_reversal" | "momentum_continuation";
  triggered: boolean;
  score: number;
  direction: string;
  reasons: string[];
  risks: string[];
  metrics: Record<string, unknown>;
}

export interface RiskFlag { code: string; message: string; severity: "hard" | "warning" }
export interface ScoreComponent { name: string; points: number; maximum: number; explanation: string }
export interface ProbabilitySet {
  up5?: number;
  up10?: number;
  up15?: number;
  up10_before_stop3?: number;
  up10_before_stop5?: number;
  stop3_before_up10?: number;
  stop5_before_up10?: number;
}

export interface CoinAnalysis {
  market: Market;
  symbol: string;
  generated_at: string;
  as_of_close_time?: number | null;
  price?: number | null;
  snapshots: Record<string, IndicatorSnapshot>;
  volume?: {
    source_interval: string;
    latest_zscore?: number | null;
    taker_buy_ratio?: number | null;
    windows: Record<string, { quote_volume?: number | null; ratio?: number | null; price_change_pct?: number | null }>;
  } | null;
  order_flow?: {
    available: boolean;
    score: number;
    spread_pct?: number | null;
    depth_quote?: number | null;
    imbalance?: number | null;
    taker_buy_ratio?: number | null;
    reasons: string[];
    risks: string[];
  } | null;
  strategies: StrategyResult[];
  regime: { regime: string; score?: number | null; confidence: number; reasons: string[]; risks: string[] };
  risk: { eligible: boolean; flags: RiskFlag[]; data_quality_score: number; hard_reasons: string[]; warnings: string[] };
  score: { total: number; label: string; eligible: boolean; components: ScoreComponent[]; risk_penalty: number; historical_similarity_status: string };
  mtf_agreement: number;
  signal_valid_until_ms?: number | null;
  invalidation: string[];
  scenario: Record<string, string | number | null>;
  ai_status: "available" | "insufficient_training_data" | string;
  ai_probabilities?: {
    horizons: Record<"24" | "48" | "72", ProbabilitySet>;
    trained_before: number;
    training_samples: number;
    out_of_sample: Record<string, { samples: number; brier: number; roc_auc?: number | null }>;
    warning: string;
  } | null;
  historical_similarity?: {
    status: string;
    samples: number;
    similarity_score?: number | null;
    horizons?: Record<string, { samples: number; hit10_before_stop5_rate?: number | null; wilson_95: (number | null)[] }>;
    neighbors?: Array<{ signal_id: number; symbol: string; signal_time: number; distance: number; outcomes: Record<string, { net_return_pct?: number }> }>;
  } | null;
  futures_context?: { funding_rate?: number | null; open_interest?: number | null; long_short_ratio?: number | null; long_account?: number | null; short_account?: number | null; long_short_status?: string; open_interest_status?: string; liquidation_note?: string } | null;
  market_comparison?: { available: boolean; other_market: Market; other_last_price?: number | null; own_quote_volume_24h?: number | null; other_quote_volume_24h?: number | null; price_difference_pct?: number | null } | null;
  btc_correlation_15m?: number | null;
  risk_level?: "low" | "medium" | "high";
}

export interface ScanResponse {
  count: number;
  total_matching: number;
  items: CoinAnalysis[];
  scanned?: number;
  last_scan?: Record<string, number>;
  data_available?: boolean;
  errors?: Record<string, string>;
}

export interface DashboardResponse {
  markets: Record<Market, { btc?: number | null; btc_change_24h?: number | null; eth?: number | null; eth_change_24h?: number | null; regime: CoinAnalysis["regime"] }>;
  scanned_coins: number;
  strong_signals: number;
  new_signals: number;
  top10: CoinAnalysis[];
  market_distribution: Record<string, number>;
  last_scan: Record<string, number>;
  connection: { enabled: boolean; error_count?: number; streams?: Array<{ name: string; connected: boolean; last_message_age_s?: number | null }> };
  signal_counts: Record<string, number>;
  ai_status: string;
}

export interface Candle {
  market: Market;
  symbol: string;
  interval: string;
  open_time: number;
  close_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quote_volume: number;
  is_closed: boolean;
}

export interface RateSummary { successes: number; samples: number; rate?: number | null; wilson_95: (number | null)[] }
export interface PerformanceSummary {
  horizon_hours: number;
  signal_count: number;
  evaluated_count: number;
  hit5: RateSummary;
  hit10_any: RateSummary;
  hit15: RateSummary;
  hit10_before_stop3: RateSummary;
  hit10_before_stop5: RateSummary;
  stop3_before_hit10: RateSummary;
  stop5_before_hit10: RateSummary;
  average_max_up_pct?: number | null;
  average_max_down_pct?: number | null;
  average_net_return_pct?: number | null;
  ambiguous_barrier_signals: number;
}
export interface PerformanceResponse {
  summary: PerformanceSummary;
  by_strategy: Record<string, PerformanceSummary>;
  by_market: Record<string, PerformanceSummary>;
  by_score_band: Record<string, PerformanceSummary>;
  daily: Record<string, PerformanceSummary>;
  weekly: Record<string, PerformanceSummary>;
  monthly: Record<string, PerformanceSummary>;
  small_sample_warning?: string | null;
  methodology: string;
}

export interface SignalRecord {
  id: number;
  market: Market;
  symbol: string;
  strategy: string;
  signal_time: number;
  score: number;
  entry_price: number;
  status: string;
  price_24h?: number | null;
  price_48h?: number | null;
  price_72h?: number | null;
  max_up_72h?: number | null;
  max_down_72h?: number | null;
  net_return_72h?: number | null;
  hit10_72h?: number | null;
  up10_before_stop5_72h?: number | null;
}
