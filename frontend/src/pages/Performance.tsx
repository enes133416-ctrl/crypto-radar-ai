import { useState } from "react";
import { AlertTriangle, BarChart3 } from "lucide-react";
import { fetchPerformance, fetchSignals } from "../services/api";
import { useApi } from "../hooks/useApi";
import type { MarketFilter, PerformanceSummary } from "../types/api";
import { Badge, Card, DataState, Metric, PageHeader } from "../components/ui";
import { formatNumber, formatPercent, formatPrice, formatTime, STRATEGY_LABELS } from "../utils/scanner";

function Rate({ summary }: { summary: PerformanceSummary["hit10_any"] }) {
  return <span>{summary.rate == null ? "—" : `%${formatNumber(summary.rate * 100, 1)}`} <small className="text-slate-600">({summary.successes}/{summary.samples})</small></span>;
}
function GroupTable({ title, groups }: { title: string; groups: Record<string, PerformanceSummary> }) {
  return <Card className="overflow-hidden"><h3 className="border-b border-slate-800 p-4 text-sm font-medium text-slate-200">{title}</h3><div className="overflow-x-auto"><table className="w-full min-w-[620px] text-xs">
    <thead className="bg-slate-950/50 text-left text-slate-500"><tr><th className="p-3">Grup</th><th className="p-3">Sinyal</th><th className="p-3">+%10 herhangi</th><th className="p-3">+%10 / önce -5 yok</th><th className="p-3">Ort. MFE</th><th className="p-3">Ort. net</th></tr></thead>
    <tbody className="divide-y divide-slate-800">{Object.entries(groups).map(([name, value]) => <tr key={name}><td className="p-3 text-slate-300">{STRATEGY_LABELS[name] ?? name}</td><td className="p-3">{value.signal_count}</td><td className="p-3"><Rate summary={value.hit10_any} /></td><td className="p-3"><Rate summary={value.hit10_before_stop5} /></td><td className="p-3 text-emerald-400">{formatPercent(value.average_max_up_pct)}</td><td className="p-3">{formatPercent(value.average_net_return_pct)}</td></tr>)}</tbody></table></div></Card>;
}

export default function Performance() {
  const [horizon, setHorizon] = useState(72);
  const [market, setMarket] = useState<MarketFilter>("all");
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("daily");
  const report = useApi(() => fetchPerformance(market, horizon), 60_000, [market, horizon]);
  const signals = useApi(() => fetchSignals(market), 60_000, [market]);
  const summary = report.data?.summary;
  return <>
    <PageHeader title="Geçmiş Performans & Backtest" description="Başarılı ve başarısız bütün kaydedilmiş sinyaller, gelecek mumlar geldikçe aynı yöntemle çözülür. Wilson %95 aralığı küçük örneklemin belirsizliğini gösterir." action={<div className="flex gap-2">
      <select className="input w-36" value={market} onChange={(e) => setMarket(e.target.value as MarketFilter)}><option value="all">Spot + Futures</option><option value="spot">Spot</option><option value="futures">Futures</option></select>
      <select className="input w-32" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}><option value="24">24 saat</option><option value="48">48 saat</option><option value="72">72 saat</option></select></div>} />
    <DataState loading={report.loading} error={report.error} onRetry={() => void report.reload()}>
      {summary && <>
        {report.data?.small_sample_warning && <div className="mb-4 flex gap-2 rounded-lg border border-amber-900/60 bg-amber-950/20 p-3 text-xs text-amber-200"><AlertTriangle size={16} />{report.data.small_sample_warning}</div>}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6"><Metric label="Toplam sinyal" value={summary.signal_count} detail={`${summary.evaluated_count} sonucu kapandı`} />
          <Metric label="+%10 herhangi" value={<Rate summary={summary.hit10_any} />} detail={`Wilson %95: ${summary.hit10_any.wilson_95[0] == null ? "—" : `%${formatNumber((summary.hit10_any.wilson_95[0] ?? 0) * 100, 1)}–${formatNumber((summary.hit10_any.wilson_95[1] ?? 0) * 100, 1)}`}`} />
          <Metric label="+%10 / önce -5 yok" value={<Rate summary={summary.hit10_before_stop5} />} detail="Sıralı Triple Barrier" />
          <Metric label="Ortalama MFE" value={formatPercent(summary.average_max_up_pct)} tone="positive" /><Metric label="Ortalama MAE" value={formatPercent(summary.average_max_down_pct)} tone="negative" />
          <Metric label="Ortalama net getiri" value={formatPercent(summary.average_net_return_pct)} detail="Maliyet modeli sonrası" /></div>
        <div className="mt-4 grid gap-4 2xl:grid-cols-2"><GroupTable title="Strateji bazında başarı" groups={report.data?.by_strategy ?? {}} /><GroupTable title="Skor aralıklarına göre başarı" groups={report.data?.by_score_band ?? {}} />
          <GroupTable title="Spot / Futures karşılaştırması" groups={report.data?.by_market ?? {}} />
          <Card><div className="flex items-center justify-between border-b border-slate-800 p-4"><h3 className="text-sm font-medium text-slate-200">Dönemsel başarı</h3><select className="input w-28" value={period} onChange={(e) => setPeriod(e.target.value as typeof period)}><option value="daily">Günlük</option><option value="weekly">Haftalık</option><option value="monthly">Aylık</option></select></div>
            <div className="max-h-80 overflow-y-auto p-4">{Object.entries(report.data?.[period] ?? {}).map(([name, value]) => <div key={name} className="mb-3 grid grid-cols-[80px_1fr_auto] items-center gap-3 text-xs"><span className="text-slate-400">{name}</span><div className="h-2 rounded bg-slate-800"><div className="h-2 rounded bg-cyan-500" style={{ width: `${(value.hit10_any.rate ?? 0) * 100}%` }} /></div><Rate summary={value.hit10_any} /></div>)}</div></Card></div>
        <p className="mt-4 text-xs leading-5 text-slate-500">{report.data?.methodology}</p>
      </>}
    </DataState>
    <Card className="mt-5"><div className="flex items-center gap-2 border-b border-slate-800 p-4"><BarChart3 size={17} className="text-cyan-400" /><h2 className="text-sm font-medium">Sinyal Kayıtları</h2></div>
      <DataState loading={signals.loading} error={signals.error} empty={!signals.data?.items.length}><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-xs"><thead className="bg-slate-950/50 text-left text-slate-500"><tr><th className="p-3">Zaman</th><th className="p-3">Coin</th><th className="p-3">Strateji</th><th className="p-3">Skor</th><th className="p-3">Giriş</th><th className="p-3">24h</th><th className="p-3">48h</th><th className="p-3">72h</th><th className="p-3">MFE / MAE</th><th className="p-3">Durum</th></tr></thead>
        <tbody className="divide-y divide-slate-800">{signals.data?.items.map((signal) => <tr key={signal.id}><td className="p-3 text-slate-400">{formatTime(signal.signal_time)}</td><td className="p-3"><b>{signal.symbol}</b><Badge tone={signal.market === "spot" ? "cyan" : "violet"}>{signal.market}</Badge></td><td className="p-3">{STRATEGY_LABELS[signal.strategy]}</td><td className="p-3">{signal.score}</td><td className="p-3">${formatPrice(signal.entry_price)}</td><td className="p-3">${formatPrice(signal.price_24h)}</td><td className="p-3">${formatPrice(signal.price_48h)}</td><td className="p-3">${formatPrice(signal.price_72h)}</td><td className="p-3"><span className="text-emerald-400">{formatPercent(signal.max_up_72h)}</span> / <span className="text-rose-400">{formatPercent(signal.max_down_72h)}</span></td><td className="p-3"><Badge tone={signal.status === "resolved" ? "green" : "amber"}>{signal.status}</Badge></td></tr>)}</tbody></table></div></DataState></Card>
  </>;
}
