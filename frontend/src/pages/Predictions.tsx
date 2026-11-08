import { useState } from "react";
import { BrainCircuit, Info } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchScan } from "../services/api";
import { useApi } from "../hooks/useApi";
import type { MarketFilter, ProbabilitySet } from "../types/api";
import { Badge, Card, DataState, PageHeader, Probability, ScoreBadge } from "../components/ui";

function Horizon({ title, values }: { title: string; values?: ProbabilitySet }) {
  return <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3"><div className="mb-2 text-xs font-semibold text-slate-300">{title}</div>
    <div className="grid grid-cols-3 gap-2 text-center text-xs"><span><small className="block text-slate-500">+5</small><Probability value={values?.up5} /></span>
      <span><small className="block text-slate-500">+10</small><Probability value={values?.up10} /></span><span><small className="block text-slate-500">+15</small><Probability value={values?.up15} /></span></div>
    <div className="mt-3 space-y-1 border-t border-slate-800 pt-2 text-[11px]"><div className="flex justify-between"><span className="text-slate-500">+10, önce -5 yok</span><Probability value={values?.up10_before_stop5} /></div>
      <div className="flex justify-between"><span className="text-slate-500">Önce -3</span><Probability value={values?.stop3_before_up10} /></div>
      <div className="flex justify-between"><span className="text-slate-500">Önce -5</span><Probability value={values?.stop5_before_up10} /></div></div></div>;
}

export default function Predictions() {
  const [market, setMarket] = useState<MarketFilter>("all");
  const [minimum, setMinimum] = useState(0);
  const { data, error, loading, reload } = useApi(() => fetchScan({ market, min_ai_up10: minimum || undefined, eligible_only: true }), 60_000, [market, minimum]);
  const unavailable = data?.items.every((item) => item.ai_status !== "available") ?? true;
  return <>
    <PageHeader title="AI Olasılıkları" description="Her ufuk ve hedef ayrı sınıflandırıcıdır. +%10'a herhangi bir noktada ulaşma ile zarar eşiğinden önce ulaşma olasılıkları karıştırılmaz." action={<div className="flex gap-2">
      <select className="input w-36" value={market} onChange={(e) => setMarket(e.target.value as MarketFilter)}><option value="all">Tüm piyasalar</option><option value="spot">Spot</option><option value="futures">Futures</option></select>
      <select className="input w-40" value={minimum} onChange={(e) => setMinimum(Number(e.target.value))}><option value="0">Tüm olasılıklar</option><option value="50">72h +10 ≥ %50</option><option value="70">72h +10 ≥ %70</option></select></div>} />
    {unavailable && !loading && <div className="mb-4 flex gap-3 rounded-xl border border-amber-900/60 bg-amber-950/20 p-4 text-sm text-amber-200"><Info className="shrink-0" size={19} />
      <div><b>Yetersiz eğitim verisi</b><p className="mt-1 text-xs leading-5 text-amber-200/70">Henüz kalibre edilmiş model yok veya filtreleri geçen coinlerde model sonucu bulunmuyor. Olasılık yerine sıfır/rastgele değer gösterilmez. Model ayrı komutla, yeterli çözülmüş sinyal oluştuğunda eğitilir.</p></div></div>}
    <DataState loading={loading} error={error} empty={!data?.items.length} onRetry={() => void reload()}>
      <div className="grid gap-4 2xl:grid-cols-2">{data?.items.map((item) => <Card key={`${item.market}-${item.symbol}`} className="p-4">
        <div className="mb-4 flex items-center justify-between"><div><Link to={`/coin/${item.market}/${item.symbol}`} className="font-semibold text-slate-100 hover:text-cyan-300">{item.symbol}</Link>
          <div className="mt-1 flex gap-2"><Badge tone={item.market === "spot" ? "cyan" : "violet"}>{item.market.toUpperCase()}</Badge><Badge tone={item.ai_status === "available" ? "green" : "slate"}>{item.ai_status === "available" ? `${item.ai_probabilities?.training_samples} EĞİTİM ÖRNEĞİ` : "MODEL YOK"}</Badge></div></div>
          <div className="text-right"><ScoreBadge score={item.score.total} /><div className="mt-1 text-xs text-slate-500">Skor</div></div></div>
        <div className="grid gap-3 md:grid-cols-3"><Horizon title="24 saat" values={item.ai_probabilities?.horizons["24"]} /><Horizon title="48 saat" values={item.ai_probabilities?.horizons["48"]} /><Horizon title="72 saat" values={item.ai_probabilities?.horizons["72"]} /></div>
        {item.ai_probabilities && <p className="mt-3 text-[11px] leading-5 text-slate-500"><BrainCircuit size={12} className="mr-1 inline" />{item.ai_probabilities.warning}</p>}
      </Card>)}</div>
    </DataState>
  </>;
}
