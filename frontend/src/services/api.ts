import type { HealthResponse } from "../types/api";

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function fetchHealth(base: string = API_BASE): Promise<HealthResponse> {
  const res = await fetch(`${base}/api/health`);
  if (!res.ok) throw new Error(`Backend hatası: HTTP ${res.status}`);
  return (await res.json()) as HealthResponse;
}
