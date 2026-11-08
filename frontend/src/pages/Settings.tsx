import { CheckCircle2, KeyRound, ServerCog, ShieldCheck } from "lucide-react";
import { fetchDataStatus, fetchHealth, fetchSettings } from "../services/api";
import { useApi } from "../hooks/useApi";
import { Badge, Card, DataState, PageHeader } from "../components/ui";

const labels: Record<string, string> = {
  run_mode: "Çalışma modu", min_quote_volume_24h: "Minimum 24s hacim (USDT)", max_spread_pct: "Maksimum spread (%)",
  min_orderbook_depth_quote: "Minimum zayıf taraf derinliği", max_atr_pct: "Maksimum ATR%", volume_explosion_ratio: "Hacim patlaması eşiği",
  signal_min_score: "Sinyal kayıt skoru", signal_cooldown_hours: "Sinyal cooldown (saat)", max_symbols_per_market: "Piyasa başına sembol",
  tracked_intervals: "İzlenen zaman dilimleri", scan_interval_seconds: "Tarama aralığı (saniye)", round_trip_cost_pct: "Gidiş-dönüş maliyet (%)",
  ml_min_samples: "AI minimum örneklem", api_rate_limit_per_minute: "API limiti / dakika",
};

export default function Settings() {
  const settings = useApi(fetchSettings);
  const health = useApi(fetchHealth, 30_000);
  const status = useApi(fetchDataStatus, 30_000);
  return <>
    <PageHeader title="Sistem & Ayarlar" description="Eşikler merkezi .env üzerinden yönetilir. Arayüz API anahtarı, secret veya Binance hesap bilgisi istemez; otomatik emir özelliği yoktur." />
    <div className="grid gap-4 xl:grid-cols-3"><Card className="p-5 xl:col-span-2"><div className="flex items-center gap-2"><ServerCog className="text-cyan-400" size={19} /><h2 className="font-medium">Aktif tarama yapılandırması</h2></div>
      <DataState loading={settings.loading} error={settings.error} onRetry={() => void settings.reload()}><dl className="mt-4 grid gap-x-6 sm:grid-cols-2">{Object.entries(settings.data?.settings ?? {}).filter(([key]) => labels[key]).map(([key, value]) => <div key={key} className="flex items-center justify-between border-b border-slate-800 py-3 text-sm"><dt className="text-slate-500">{labels[key]}</dt><dd className="ml-3 text-right font-medium text-slate-200">{Array.isArray(value) ? value.join(", ") : String(value)}</dd></div>)}</dl>
        <p className="mt-4 text-xs leading-5 text-slate-500">{settings.data?.editable_note}</p></DataState></Card>
      <Card className="p-5"><div className="flex items-center gap-2"><ShieldCheck className="text-emerald-400" size={19} /><h2 className="font-medium">Güvenlik durumu</h2></div><div className="mt-4 space-y-3 text-sm">
        <div className="flex justify-between"><span className="text-slate-500">Çalışma modu</span><Badge tone="cyan">{health.data?.run_mode ?? "—"}</Badge></div><div className="flex justify-between"><span className="text-slate-500">Demo veri</span><Badge tone={health.data?.demo_mode ? "amber" : "green"}>{health.data?.demo_mode ? "DEMO" : "KAPALI"}</Badge></div>
        <div className="flex justify-between"><span className="text-slate-500">Collector</span><Badge tone={health.data?.collector_enabled ? "green" : "red"}>{health.data?.collector_enabled ? "AÇIK" : "KAPALI"}</Badge></div>
        <div className="flex justify-between"><span className="text-slate-500">Otomatik alım/satım</span><Badge tone="green">YOK</Badge></div></div>
        <div className="mt-5 rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs leading-5 text-slate-400"><KeyRound size={15} className="mb-2 text-amber-400" />Herkese açık piyasa verisi için API key gerekmez. Özel key kullanılmaz; para çekme/işlem yetkisi geliştirilmez.</div></Card></div>
    <Card className="mt-4 p-5"><h2 className="font-medium">Bağlantı ve veri güncelliği</h2><DataState loading={status.loading} error={status.error}><pre className="mt-4 max-h-96 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs leading-5 text-slate-400">{JSON.stringify(status.data, null, 2)}</pre></DataState></Card>
    <div className="mt-4 grid gap-3 text-xs text-slate-500 md:grid-cols-3">{["Tamamlanmamış mumlar analiz edilmez", "Eski/eksik veri risk etiketi üretir", "AI için yetersiz veri açıkça gösterilir"].map((text) => <div key={text} className="flex items-center gap-2"><CheckCircle2 size={15} className="text-emerald-500" />{text}</div>)}</div>
  </>;
}
