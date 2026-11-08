import { describe, expect, it } from "vitest";
import { aiProbability, DEFAULT_FILTERS, filterRows, sortRows, volumeRatio } from "../src/utils/scanner";
import { coin } from "./fixtures";

describe("scanner filtre ve sıralama", () => {
  it("gerçek alanlardan hacim ve AI değerlerini okur", () => {
    expect(volumeRatio(coin)).toBe(3.1);
    expect(aiProbability(coin)).toBe(0.7);
  });
  it("skor, piyasa, hacim, strateji ve AI filtrelerini uygular", () => {
    expect(filterRows([coin], { ...DEFAULT_FILTERS, minScore: 85, minVolumeRatio: 3, strategy: "volume_explosion", minAi: 60 })).toHaveLength(1);
    expect(filterRows([coin], { ...DEFAULT_FILTERS, market: "futures" })).toHaveLength(0);
    expect(filterRows([coin], { ...DEFAULT_FILTERS, minScore: 90 })).toHaveLength(0);
    expect(filterRows([coin], { ...DEFAULT_FILTERS, minAi: 80 })).toHaveLength(0);
  });
  it("null değerleri sıralamada sona bırakır", () => {
    const missing = { ...coin, symbol: "NULUSDT", ai_probabilities: null, score: { ...coin.score, total: 20 } };
    expect(sortRows([missing, coin], "ai", "desc")[0].symbol).toBe("BTCUSDT");
    expect(sortRows([missing, coin], "score", "asc")[0].symbol).toBe("NULUSDT");
  });
});
