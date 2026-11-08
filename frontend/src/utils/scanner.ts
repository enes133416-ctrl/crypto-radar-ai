import type { CoinAnalysis, MarketFilter } from "../types/api";

export const STRATEGY_LABELS: Record<string, string> = {
  volume_explosion: "Volume Explosion",
  consolidation_breakout: "Consolidation Breakout",
  relative_strength: "Relative Strength",
  oversold_reversal: "Oversold Reversal",
  momentum_continuation: "Momentum Continuation",
};

export function volumeRatio(row: CoinAnalysis): number | null {
  const windows = row.volume?.windows;
  if (!windows) return null;
  for (const period of ["1h", "15m", "4h", "24h"]) {
    const value = windows[period]?.ratio;
    if (typeof value === "number") return value;
  }
  return null;
}

export function aiProbability(row: CoinAnalysis, horizon: "24" | "48" | "72" = "72", field = "up10"): number | null {
  const value = row.ai_probabilities?.horizons?.[horizon]?.[field as keyof NonNullable<CoinAnalysis["ai_probabilities"]>["horizons"]["24"]];
  return typeof value === "number" ? value : null;
}

export function change(row: CoinAnalysis, period: "5m" | "15m" | "1h" | "4h" | "24h", timeframe = "15m"): number | null {
  if (period === "5m" && row.snapshots["5m"]?.change_5m_pct != null) return row.snapshots["5m"].change_5m_pct;
  const snapshot = row.snapshots[timeframe] ?? row.snapshots["15m"];
  const value = snapshot?.[`change_${period}_pct`];
  return typeof value === "number" ? value : null;
}

export function relativeStrength(row: CoinAnalysis): number | null {
  const strategy = row.strategies.find((item) => item.name === "relative_strength");
  const value = strategy?.metrics.average_relative_pct;
  return typeof value === "number" ? value : null;
}

export interface TableFilters {
  search: string;
  market: MarketFilter;
  minScore: number;
  minVolume: number;
  minVolumeRatio: number;
  risk: string;
  strategy: string;
  minAi: number;
  newOnly: boolean;
  eligibleOnly: boolean;
}

export const DEFAULT_FILTERS: TableFilters = {
  search: "", market: "all", minScore: 0, minVolume: 0, minVolumeRatio: 0,
  risk: "all", strategy: "all", minAi: 0, newOnly: false, eligibleOnly: true,
};

export function filterRows(rows: CoinAnalysis[], filters: TableFilters): CoinAnalysis[] {
  const now = Date.now();
  return rows.filter((row) => {
    if (!row.symbol.toLowerCase().includes(filters.search.trim().toLowerCase())) return false;
    if (filters.market !== "all" && row.market !== filters.market) return false;
    if (row.score.total < filters.minScore) return false;
    if (filters.eligibleOnly && !row.risk.eligible) return false;
    if ((row.market_comparison?.own_quote_volume_24h ?? 0) < filters.minVolume) return false;
    if ((volumeRatio(row) ?? 0) < filters.minVolumeRatio) return false;
    if (filters.risk !== "all" && row.risk_level !== filters.risk) return false;
    if (filters.strategy !== "all" && !row.strategies.some((s) => s.name === filters.strategy && s.triggered)) return false;
    if ((aiProbability(row) ?? 0) * 100 < filters.minAi) return false;
    if (filters.newOnly && (!row.as_of_close_time || now - row.as_of_close_time > 2 * 3_600_000)) return false;
    return true;
  });
}

export type SortKey = "symbol" | "price" | "score" | "volumeRatio" | "atr" | "rsi" | "adx" | "ai" | "signalTime" | "change24h";
export function sortRows(rows: CoinAnalysis[], key: SortKey, direction: "asc" | "desc", timeframe = "15m"): CoinAnalysis[] {
  const value = (row: CoinAnalysis): string | number | null => {
    switch (key) {
      case "symbol": return row.symbol;
      case "price": return row.price ?? null;
      case "score": return row.score.total;
      case "volumeRatio": return volumeRatio(row);
      case "atr": return row.snapshots[timeframe]?.atr_pct ?? null;
      case "rsi": return row.snapshots[timeframe]?.rsi14 ?? null;
      case "adx": return row.snapshots[timeframe]?.adx ?? null;
      case "ai": return aiProbability(row);
      case "signalTime": return row.as_of_close_time ?? null;
      case "change24h": return change(row, "24h", timeframe);
    }
  };
  return [...rows].sort((a, b) => {
    const av = value(a); const bv = value(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    const comparison = typeof av === "string" ? av.localeCompare(String(bv)) : av - Number(bv);
    return direction === "asc" ? comparison : -comparison;
  });
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: digits }).format(value);
}
export function formatPrice(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const digits = value < 0.01 ? 8 : value < 1 ? 5 : value < 100 ? 3 : 2;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}
export function formatPercent(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : `${value >= 0 ? "+" : ""}${formatNumber(value, digits)}%`;
}
export function formatProbability(value: number | null | undefined): string {
  return value == null ? "—" : `%${formatNumber(value * 100, 1)}`;
}
export function formatTime(value: number | null | undefined): string {
  return value == null ? "—" : new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" }).format(value);
}
export function formatCompact(value: number | null | undefined): string {
  return value == null ? "—" : new Intl.NumberFormat("tr-TR", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}
