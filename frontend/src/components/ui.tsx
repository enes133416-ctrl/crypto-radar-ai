import type { ReactNode } from "react";
import { AlertTriangle, LoaderCircle, RefreshCw } from "lucide-react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-slate-800 bg-slate-900/70 shadow-panel ${className}`}>{children}</section>;
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div><h1 className="text-xl font-semibold tracking-tight text-slate-50 md:text-2xl">{title}</h1>
      {description && <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">{description}</p>}</div>
    {action}
  </div>;
}

export function Badge({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "green" | "red" | "amber" | "cyan" | "violet" }) {
  const tones = { slate: "border-slate-700 bg-slate-800 text-slate-300", green: "border-emerald-800 bg-emerald-950 text-emerald-300",
    red: "border-rose-800 bg-rose-950 text-rose-300", amber: "border-amber-800 bg-amber-950 text-amber-300",
    cyan: "border-cyan-800 bg-cyan-950 text-cyan-300", violet: "border-violet-800 bg-violet-950 text-violet-300" };
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>{children}</span>;
}

export function ScoreBadge({ score, eligible = true }: { score: number; eligible?: boolean }) {
  const tone = !eligible ? "red" : score >= 85 ? "green" : score >= 75 ? "cyan" : score >= 65 ? "violet" : score >= 50 ? "amber" : "slate";
  return <Badge tone={tone}>{score.toFixed(1)}</Badge>;
}

export function Change({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-slate-600">—</span>;
  return <span className={value >= 0 ? "text-emerald-400" : "text-rose-400"}>{value >= 0 ? "+" : ""}{value.toFixed(2)}%</span>;
}

export function Metric({ label, value, detail, tone = "default" }: { label: string; value: ReactNode; detail?: ReactNode; tone?: "default" | "positive" | "negative" }) {
  return <Card className="p-4"><div className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</div>
    <div className={`mt-2 text-2xl font-semibold tabular-nums ${tone === "positive" ? "text-emerald-400" : tone === "negative" ? "text-rose-400" : "text-slate-100"}`}>{value}</div>
    {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}</Card>;
}

export function DataState({ loading, error, empty, onRetry, children }: { loading: boolean; error: string | null; empty?: boolean; onRetry?: () => void; children: ReactNode }) {
  if (loading) return <Card className="flex min-h-52 items-center justify-center gap-3 text-sm text-slate-400"><LoaderCircle className="animate-spin text-cyan-400" size={20} />Gerçek veriler yükleniyor…</Card>;
  if (error) return <Card className="flex min-h-40 flex-col items-center justify-center gap-3 p-6 text-center"><AlertTriangle className="text-amber-400" />
    <div><p className="font-medium text-slate-200">Veri alınamadı</p><p className="mt-1 text-sm text-slate-400">{error}</p>
      <p className="mt-2 text-xs text-slate-500">Eksik veri yerine tahmini veya örnek değer gösterilmez.</p></div>
    {onRetry && <button className="btn-secondary" onClick={onRetry}><RefreshCw size={14} />Tekrar dene</button>}</Card>;
  if (empty) return <Card className="flex min-h-36 flex-col items-center justify-center p-6 text-center"><p className="text-slate-300">Henüz gösterilecek veri yok</p>
    <p className="mt-1 max-w-lg text-sm text-slate-500">Collector ilk mum geçmişini tamamlamamış veya zorunlu filtreleri geçen sonuç bulunmamış olabilir.</p></Card>;
  return <>{children}</>;
}

export function Probability({ value }: { value: number | null | undefined }) {
  return value == null ? <span title="Eğitim verisi yok" className="text-slate-600">—</span> : <span className="text-cyan-300">%{(value * 100).toFixed(1)}</span>;
}
