import { expect, test, type Page } from "@playwright/test";

const now = Date.now();
const coin = {
  market: "spot", symbol: "BTCUSDT", generated_at: new Date().toISOString(), as_of_close_time: now, price: 100000,
  snapshots: { "5m": { interval: "5m", candle_count: 100, close: 100000, change_5m_pct: 0.2 },
    "15m": { interval: "15m", candle_count: 100, close: 100000, change_15m_pct: 0.4, change_1h_pct: 1.2, change_4h_pct: 2.3, change_24h_pct: 4.1, atr_pct: 2, rsi14: 60, adx: 25, support: 99000, resistance: 101000 } },
  volume: { source_interval: "15m", taker_buy_ratio: 0.55, windows: { "1h": { ratio: 3, price_change_pct: 1.2, quote_volume: 1000000 } } },
  order_flow: { available: true, score: 80, spread_pct: 0.01, depth_quote: 200000, imbalance: 0.1, reasons: [], risks: [] },
  strategies: [{ name: "volume_explosion", triggered: true, score: 90, direction: "bullish", reasons: ["Hacim arttı"], risks: [], metrics: { price_change_pct: 1.2 } }],
  regime: { regime: "bullish", score: 75, confidence: 1, reasons: ["BTC trendi"], risks: [] },
  risk: { eligible: true, flags: [], data_quality_score: 100, hard_reasons: [], warnings: [] }, risk_level: "low",
  score: { total: 88, label: "very_strong", eligible: true, components: [{ name: "volume", points: 18, maximum: 20, explanation: "Hacim" }], risk_penalty: 0, historical_similarity_status: "insufficient_training_data" },
  mtf_agreement: 0.9, invalidation: ["Trend bozulursa"], scenario: { reference_price: 100000, note: "Analiz senaryosu" },
  ai_status: "insufficient_training_data", ai_probabilities: null, historical_similarity: { status: "insufficient_training_data", samples: 0 },
  market_comparison: { available: true, other_market: "futures", own_quote_volume_24h: 500000000 },
};
const rate = { successes: 0, samples: 0, rate: null, wilson_95: [null, null] };
const summary = { horizon_hours: 72, signal_count: 0, evaluated_count: 0, hit5: rate, hit10_any: rate, hit15: rate,
  hit10_before_stop3: rate, hit10_before_stop5: rate, stop3_before_hit10: rate, stop5_before_hit10: rate,
  average_max_up_pct: null, average_max_down_pct: null, average_net_return_pct: null, ambiguous_barrier_signals: 0 };

async function mockApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let body: unknown = { status: "ok", app: "Crypto Radar AI", version: "1.0.0", run_mode: "local", demo_mode: false, collector_enabled: true, scanner_enabled: true, server_time: new Date().toISOString() };
    if (path === "/api/dashboard") body = { markets: { spot: { btc: 100000, eth: 3000, regime: coin.regime }, futures: { btc: 100010, eth: 3001, regime: coin.regime } }, scanned_coins: 1, strong_signals: 1, new_signals: 1, top10: [coin], market_distribution: { spot: 1 }, last_scan: { spot: now }, connection: { enabled: true, streams: [] }, signal_counts: { resolved: 0, open: 0, partial: 0 }, ai_status: "insufficient_training_data" };
    else if (path === "/api/scan" || path === "/api/predictions") body = { count: 1, total_matching: 1, items: [coin], data_available: true, last_scan: { spot: now } };
    else if (path.includes("/api/analysis/")) body = coin;
    else if (path.includes("/api/klines/")) body = { closed: Array.from({ length: 60 }, (_, i) => ({ market: "spot", symbol: "BTCUSDT", interval: "15m", open_time: now - (60 - i) * 900000, close_time: now - (59 - i) * 900000, open: 99000 + i * 10, high: 99100 + i * 10, low: 98900 + i * 10, close: 99050 + i * 10, volume: 10, quote_volume: 1000000, is_closed: true })), open_candle: null };
    else if (path === "/api/performance") body = { summary, by_strategy: {}, by_market: {}, by_score_band: {}, daily: {}, weekly: {}, monthly: {}, small_sample_warning: "Örneklem yok", methodology: "Test" };
    else if (path === "/api/signals") body = { count: 0, items: [] };
    else if (path === "/api/settings") body = { settings: { run_mode: "local", tracked_intervals: ["15m"] }, editable_note: "Test" };
    else if (path === "/api/data-status") body = { enabled: true, scanner: null };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

test("ana sayfalar tablet görünümünde açılır", async ({ page }) => {
  await mockApi(page);
  const pages = [["/#/", "Piyasa Komuta Merkezi"], ["/#/scanner", "Live Scanner"], ["/#/early", "Early Signals"], ["/#/breakouts", "Breakout Scanner"], ["/#/spot", "Spot Scanner"], ["/#/futures", "Futures Scanner"], ["/#/predictions", "AI Olasılıkları"], ["/#/performance", "Geçmiş Performans & Backtest"], ["/#/market", "Genel Piyasa Rejimi"], ["/#/settings", "Sistem & Ayarlar"]] as const;
  for (const [path, heading] of pages) { await page.goto(path); await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible(); }
});

test("coin listesi arama ile filtrelenir ve coin detay grafiği çizilir", async ({ page }) => {
  await mockApi(page);
  await page.goto("/#/scanner");
  await expect(page.getByText("BTC", { exact: true })).toBeVisible();
  await page.getByPlaceholder("BTC…").fill("NOPE");
  await expect(page.getByText("Henüz gösterilecek veri yok")).toBeVisible();
  await page.goto("/#/coin/spot/BTCUSDT");
  await expect(page.getByTestId("price-chart").locator("canvas").first()).toBeVisible();
  await expect(page.getByText("YETERSİZ EĞİTİM VERİSİ")).toBeVisible();
});

test("API hatası canlı veri varmış gibi gösterilmez", async ({ page }) => {
  await page.route("**/api/health", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok", version: "1", run_mode: "local", demo_mode: false, collector_enabled: false }) }));
  await page.route("**/api/dashboard", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Collector kapalı" }) }));
  await page.goto("/#/");
  await expect(page.getByText("Collector kapalı")).toBeVisible();
  await expect(page.getByText("Eksik veri yerine tahmini veya örnek değer gösterilmez.")).toBeVisible();
});

test("mobil menü açılıp kapanır", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/#/scanner");
  await page.getByRole("button", { name: "Menüyü aç" }).click();
  await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByRole("heading", { name: "Piyasa Komuta Merkezi" })).toBeVisible();
});
