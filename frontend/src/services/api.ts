import type { Candle, CoinAnalysis, DashboardResponse, HealthResponse, MarketFilter, PerformanceResponse, ScanResponse, SignalRecord } from "../types/api";

// Tarayıcı asla başka bir cihazdaki backend için localhost'a yönlendirilmez.
// Vite geliştirme proxy'si /api'yi backend'e taşır; production VITE_API_BASE ile ayrılabilir.
export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = "ApiError"; }
}

export async function request<T>(path: string, base: string = API_BASE, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${base}${path}`, { signal: controller.signal, headers: { Accept: "application/json" } });
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    if (!response.ok) throw new ApiError(body?.detail ?? `Backend hatası: HTTP ${response.status}`, response.status);
    return body as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw new ApiError("Backend zaman aşımına uğradı", 408);
    if (error instanceof TypeError) throw new ApiError("Backend'e ulaşılamıyor; servis ve CORS ayarını kontrol edin", 0);
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

function query(values: Record<string, string | number | boolean | undefined | null>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function fetchHealth(base: string = API_BASE) { return request<HealthResponse>("/api/health", base); }
export function fetchDashboard() { return request<DashboardResponse>("/api/dashboard"); }
export function fetchDataStatus() { return request<Record<string, unknown>>("/api/data-status"); }

export interface ScanFilters {
  market?: MarketFilter;
  min_score?: number;
  eligible_only?: boolean;
  strategy?: string;
  new_only?: boolean;
  risk?: string;
  min_ai_up10?: number;
  early_only?: boolean;
  breakout_only?: boolean;
  limit?: number;
}
export function fetchScan(filters: ScanFilters = {}) {
  return request<ScanResponse>(`/api/scan${query({ market: "all", limit: 200, ...filters })}`);
}
export function fetchAnalysis(market: string, symbol: string) {
  return request<CoinAnalysis>(`/api/analysis/${encodeURIComponent(market)}/${encodeURIComponent(symbol)}`);
}
export function fetchKlines(market: string, symbol: string, interval: string, limit = 300) {
  return request<{ closed: Candle[]; open_candle?: Candle | null }>(`/api/klines/${market}/${symbol}${query({ interval, limit })}`);
}
export function fetchPerformance(market: MarketFilter = "all", horizon = 72) {
  return request<PerformanceResponse>(`/api/performance${query({ market, horizon })}`);
}
export function fetchSignals(market: MarketFilter = "all") {
  return request<{ count: number; items: SignalRecord[] }>(`/api/signals${query({ market, limit: 200 })}`);
}
export function fetchSettings() {
  return request<{ settings: Record<string, string | number | boolean | string[]>; editable_note: string }>("/api/settings");
}
