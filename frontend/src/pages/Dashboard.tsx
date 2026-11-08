import { Activity, ArrowUpRight, Bitcoin, Database, Radio, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchDashboard } from "../services/api";
import { useApi } from "../hooks/useApi";
import ScannerTable from "../components/ScannerTable";
import { Badge, Card, Change, DataState, Metric, PageHeader } from "../components/ui";
import { formatPrice, formatTime } from "../utils/scanner";

const regimeLabels: Record<string, string> = { strong_bullish: "Strong Bullish", bullish: "Bullish", neutral: "Neutral", bearish: "Bearish", high_volatility_risk_off: "High Volatility / Risk-Off", unknown: "Bilinmiyor" };
const regimeTone = (regime: string) => regime.includes("bullish") ? "green" : regime === "bearish" || regime.includes("risk") ? "red" : "amber";

export default function Dashboard() {
  const { data, error, loading, reload } = useApi(fetchDashboard, 30_000);
  return <>
    <PageHeader title="Piyasa Komuta Merkezi" description="Gerçek Binance Spot ve USDⓈ-M Futures verisiyle üretilen son taramanın özeti. Fiyat ve sinyal zamanları birbirinden ayrıdır." />
    <DataState loading={loading} error={error} onRetry={() => void reload()}>
      {data && <>
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <Metric label="Taranan coin" value={data.scanned_coins} detail="Her iki piyasanın toplamı" />
          <Metric label="Güçlü sinyal" value={data.strong_signals} detail="Skor ≥ 75 ve zorunlu filtreler geçti" tone="positive" />
          <Metric label="Yeni sinyal" value={data.new_signals} detail="Son iki saat içinde" />
          <Metric label="Kayıtlı sonuç" value={data.signal_counts.resolved ?? 0} detail={`${data.signal_counts.open ?? 0} açık · ${data.signal_counts.partial ?? 0} kısmi`} />
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          {(["spot", "futures"] as const).map((market) => { const item = data.markets[market]; return <Card key={market} className="p-5">
            <div className="flex items-center justify-between"><div className="flex items-center gap-2"><Bitcoin size={18} className="text-amber-400" /><h2 className="font-medium text-slate-200">{market === "spot" ? "Spot Piyasası" : "USDⓈ-M Futures"}</h2></div>
              <Badge tone={regimeTone(item.regime.regime)}>{regimeLabels[item.regime.regime] ?? item.regime.regime}</Badge></div>
            <div className="mt-5 grid grid-cols-2 gap-4"><div><span className="label">BTC / USDT</span><div className="mt-1 text-xl font-semibold text-slate-100">${formatPrice(item.btc)}</div><Change value={item.btc_change_24h} /></div>
              <div><span className="label">ETH / USDT</span><div className="mt-1 text-xl font-semibold text-slate-100">${formatPrice(item.eth)}</div><Change value={item.eth_change_24h} /></div></div>
            <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-3 text-xs text-slate-500"><span>Rejim güveni: %{Math.round(item.regime.confidence * 100)}</span><span>Sinyal dağılımı: {data.market_distribution[market] ?? 0}</span></div>
          </Card>; })}
          <Card className="p-5"><div className="flex items-center gap-2"><Radio size={18} className="text-cyan-400" /><h2 className="font-medium text-slate-200">Veri Bağlantısı</h2></div>
            <div className="mt-4 space-y-3 text-sm"><div className="flex justify-between"><span className="text-slate-500">Collector</span><Badge tone={data.connection.enabled ? "green" : "red"}>{data.connection.enabled ? "AÇIK" : "KAPALI"}</Badge></div>
              <div className="flex justify-between"><span className="text-slate-500">WebSocket bağlantıları</span><span>{data.connection.streams?.filter((s) => s.connected).length ?? 0} / {data.connection.streams?.length ?? 0}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Collector hatası</span><span className={data.connection.error_count ? "text-amber-400" : "text-emerald-400"}>{data.connection.error_count ?? 0}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">AI modeli</span><Badge tone={data.ai_status === "available" ? "cyan" : "slate"}>{data.ai_status === "available" ? "HAZIR" : "VERİ YOK"}</Badge></div></div>
            <p className="mt-4 border-t border-slate-800 pt-3 text-xs leading-5 text-slate-500">Son tarama: {formatTime(Math.max(0, ...Object.values(data.last_scan)))}<br />AI veri yokken olasılık üretilmez.</p>
          </Card>
        </div>
        <Card className="mt-4"><div className="flex items-center justify-between border-b border-slate-800 p-4"><div><h2 className="flex items-center gap-2 font-medium text-slate-100"><ArrowUpRight size={18} className="text-emerald-400" />En Yüksek Puanlı 10 Coin</h2>
          <p className="mt-1 text-xs text-slate-500">Yalnız zorunlu filtreleri geçen adaylar</p></div><Link className="btn-secondary" to="/scanner">Tümünü aç</Link></div>
          {data.top10.length ? <ScannerTable rows={data.top10} compact /> : <div className="p-8 text-center text-sm text-slate-500">Henüz uygun aday yok. İlk veri geçmişi ve order book kontrolleri bekleniyor.</div>}
        </Card>
        <div className="mt-4 grid gap-3 text-xs text-slate-500 md:grid-cols-3"><div className="flex gap-2"><ShieldCheck size={16} className="shrink-0 text-cyan-500" />Zorunlu risk filtreleri skorlamadan önce uygulanır.</div>
          <div className="flex gap-2"><Database size={16} className="shrink-0 text-cyan-500" />Başarılı ve başarısız bütün kayıtlı sinyaller saklanır.</div>
          <div className="flex gap-2"><Activity size={16} className="shrink-0 text-cyan-500" />Skor geçmiş performans veya kazanç garantisi değildir.</div></div>
      </>}
    </DataState>
  </>;
}
