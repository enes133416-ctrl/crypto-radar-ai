import type { CoinAnalysis } from "../src/types/api";

export const coin: CoinAnalysis = {
  market: "spot", symbol: "BTCUSDT", generated_at: new Date().toISOString(), as_of_close_time: Date.now(), price: 100_000,
  snapshots: {
    "5m": { interval: "5m", candle_count: 100, close: 100_000, change_5m_pct: 0.2 },
    "15m": { interval: "15m", candle_count: 100, close: 100_000, change_5m_pct: 0.2, change_15m_pct: 0.4, change_1h_pct: 1.2, change_4h_pct: 2.4, change_24h_pct: 4.2, atr_pct: 2.1, rsi14: 62, adx: 27, ema21: 99_000, ema50: 98_000 },
  },
  volume: { source_interval: "15m", latest_zscore: 2.3, taker_buy_ratio: 0.58, windows: { "1h": { ratio: 3.1, price_change_pct: 1.2, quote_volume: 10_000_000 } } },
  order_flow: { available: true, score: 80, spread_pct: 0.01, depth_quote: 200_000, imbalance: 0.12, reasons: ["Alıcı akışı güçlü"], risks: [] },
  strategies: [{ name: "volume_explosion", triggered: true, score: 90, direction: "bullish", reasons: ["Hacim ortalamanın 3 katı"], risks: [], metrics: { price_change_pct: 1.2 } }],
  regime: { regime: "bullish", score: 75, confidence: 1, reasons: [], risks: [] },
  risk: { eligible: true, flags: [], data_quality_score: 100, hard_reasons: [], warnings: [] }, risk_level: "low",
  score: { total: 88, label: "very_strong", eligible: true, components: [{ name: "volume", points: 18, maximum: 20, explanation: "Hacim" }], risk_penalty: 0, historical_similarity_status: "insufficient_training_data" },
  mtf_agreement: 0.9, signal_valid_until_ms: Date.now() + 3_600_000, invalidation: ["4h trend aşağı dönerse"], scenario: { reference_price: 100_000 },
  ai_status: "available", ai_probabilities: { horizons: { "24": { up10: 0.4 }, "48": { up10: 0.55 }, "72": { up10: 0.7, up10_before_stop5: 0.45 } }, trained_before: 1, training_samples: 300, out_of_sample: {}, warning: "Garanti değildir" },
  market_comparison: { available: true, other_market: "futures", own_quote_volume_24h: 500_000_000, other_quote_volume_24h: 900_000_000 },
};
