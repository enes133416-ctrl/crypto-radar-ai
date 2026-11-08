import { ArrowDownRight, ArrowUpRight, Gauge } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchAnalysis, fetchDashboard } from "../services/api";
import { useApi } from "../hooks/useApi";
import { Badge, Card, Change, DataState, Metric, PageHeader } from "../components/ui";
import { formatNumber, formatPrice, relativeStrength, STRATEGY_LABELS } from "../utils/scanner";

export default function MarketOverview() {
  const dashboard = useApi(fetchDashboard, 30_000);
  const btc = useApi(() => fetchAnalysis("spot", "BTCUSDT"), 60_000);
  const primary = btc.data?.snapshots["4h"] ?? btc.data?.snapshots["15m"];
  const strongest = [...(dashboard.data?.top10 ?? [])].sort((a, b) => (relativeStrength(b) ?? -999) - (relativeStrength(a) ?? -999));
  return <>
    <PageHeader title="Genel Piyasa Rejimi" description="Altcoin skorları BTC 15m/1h/4h/1d trendi, ATR%, hacim ve volatiliteyle birlikte değerlendirilir. Bilinmeyen rejim boğa kabul edilmez." />
    <DataState loading={dashboard.loading} error={dashboard.error} onRetry={() => void dashboard.reload()}>
      {dashboard.data && <><div className="grid grid-cols-2 gap-3 xl:grid-cols-4">{(["spot", "futures"] as const).flatMap((market) => {
        const data = dashboard.data!.markets[market];
        return [<Metric key={`${market}-btc`} label={`BTC · ${market}`} value={`$${formatPrice(data.btc)}`} detail={<Change value={data.btc_change_24h} />} />,
          <Metric key={`${market}-eth`} label={`ETH · ${market}`} value={`$${formatPrice(data.eth)}`} detail={<Change value={data.eth_change_24h} />} />];
      })}</div>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">{(["spot", "futures"] as const).map((market) => { const regime = dashboard.data!.markets[market].regime; return <Card key={market} className="p-5"><div className="flex items-center justify-between"><h2 className="font-medium capitalize">{market} rejimi</h2><Gauge className="text-cyan-400" /></div>
        <div className="mt-3 text-xl font-semibold text-slate-100">{regime.regime.replace(/_/g, " ").toUpperCase()}</div><div className="mt-1 text-sm text-slate-500">Trend puanı {formatNumber(regime.score)} / 100 · Güven %{regime.confidence * 100}</div>
        <div className="mt-4 h-2 rounded-full bg-slate-800"><div className="h-2 rounded-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400" style={{ width: `${regime.score ?? 0}%` }} /></div>
        <ul className="mt-4 space-y-2 text-xs leading-5 text-slate-400">{[...regime.reasons, ...regime.risks].slice(0, 6).map((reason, i) => <li key={i}>• {reason}</li>)}</ul></Card>; })}
        <Card className="p-5"><h2 className="font-medium text-slate-100">BTC Teknik Görünüm</h2><DataState loading={btc.loading} error={btc.error}><div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div><span className="label">Fiyat</span><p className="mt-1 text-lg">${formatPrice(btc.data?.price)}</p></div><div><span className="label">RSI 14</span><p className="mt-1 text-lg">{formatNumber(primary?.rsi14)}</p></div>
          <div><span className="label">ATR%</span><p className="mt-1">{formatNumber(primary?.atr_pct)}%</p></div><div><span className="label">ADX</span><p className="mt-1">{formatNumber(primary?.adx)}</p></div>
          <div><span className="label">Destek</span><p className="mt-1 text-emerald-400">${formatPrice(primary?.support)}</p></div><div><span className="label">Direnç</span><p className="mt-1 text-rose-400">${formatPrice(primary?.resistance)}</p></div>
          <div><span className="label">EMA 21</span><p className="mt-1">${formatPrice(primary?.ema21)}</p></div><div><span className="label">EMA 50</span><p className="mt-1">${formatPrice(primary?.ema50)}</p></div></div></DataState>
          <Link to="/coin/spot/BTCUSDT" className="btn-secondary mt-5 w-full justify-center">BTC detayını aç</Link></Card></div>
      <Card className="mt-4"><div className="border-b border-slate-800 p-4"><h2 className="font-medium">Göreceli Güç Liderleri</h2><p className="mt-1 text-xs text-slate-500">BTC ve ETH'ye göre 1h/4h/24h ortak pencere performansı</p></div>
        <div className="divide-y divide-slate-800">{strongest.map((item) => { const strength = relativeStrength(item); return <Link key={`${item.market}-${item.symbol}`} to={`/coin/${item.market}/${item.symbol}`} className="flex items-center justify-between p-4 hover:bg-slate-800/40"><div><b>{item.symbol}</b><span className="ml-2 text-xs text-slate-500">{item.market}</span></div><div className="flex items-center gap-3">{strength != null && (strength >= 0 ? <ArrowUpRight className="text-emerald-400" size={16} /> : <ArrowDownRight className="text-rose-400" size={16} />)}<Change value={strength} /><Badge tone="slate">{STRATEGY_LABELS.relative_strength}</Badge></div></Link>; })}</div></Card></>}
    </DataState>
  </>;
}
