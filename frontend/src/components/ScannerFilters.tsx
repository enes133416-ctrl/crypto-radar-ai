import { RotateCcw, Search, SlidersHorizontal } from "lucide-react";
import { STRATEGY_LABELS, type TableFilters } from "../utils/scanner";
import type { MarketFilter } from "../types/api";

export default function ScannerFilters({ filters, onChange, timeframe, onTimeframe, showMarket = true }: {
  filters: TableFilters; onChange: (value: TableFilters) => void;
  timeframe: string; onTimeframe: (value: string) => void; showMarket?: boolean;
}) {
  const update = <K extends keyof TableFilters>(key: K, value: TableFilters[K]) => onChange({ ...filters, [key]: value });
  return <div className="border-b border-slate-800 p-4">
    <div className="mb-3 flex items-center gap-2 text-xs font-medium text-slate-400"><SlidersHorizontal size={14} className="text-cyan-400" />Filtreler</div>
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6 2xl:grid-cols-10">
      <label className="col-span-2 sm:col-span-1"><span className="label">Coin ara</span><div className="relative"><Search size={14} className="absolute left-3 top-3 text-slate-500" />
        <input className="input pl-9" placeholder="BTC…" value={filters.search} onChange={(e) => update("search", e.target.value)} /></div></label>
      {showMarket && <label><span className="label">Piyasa</span><select className="input" value={filters.market} onChange={(e) => update("market", e.target.value as MarketFilter)}>
        <option value="all">Spot + Futures</option><option value="spot">Spot</option><option value="futures">Futures</option></select></label>}
      <label><span className="label">Zaman dilimi</span><select className="input" value={timeframe} onChange={(e) => onTimeframe(e.target.value)}>
        {["5m", "15m", "1h", "4h", "1d"].map((value) => <option key={value}>{value}</option>)}</select></label>
      <label><span className="label">Minimum skor</span><input className="input" type="number" min="0" max="100" value={filters.minScore} onChange={(e) => update("minScore", Number(e.target.value))} /></label>
      <label><span className="label">Min. hacim (USDT)</span><input className="input" type="number" min="0" step="1000000" value={filters.minVolume} onChange={(e) => update("minVolume", Number(e.target.value))} /></label>
      <label><span className="label">Min. Volume Ratio</span><input className="input" type="number" min="0" step="0.5" value={filters.minVolumeRatio} onChange={(e) => update("minVolumeRatio", Number(e.target.value))} /></label>
      <label><span className="label">Risk</span><select className="input" value={filters.risk} onChange={(e) => update("risk", e.target.value)}>
        <option value="all">Tümü</option><option value="low">Düşük</option><option value="medium">Orta</option><option value="high">Yüksek</option></select></label>
      <label><span className="label">Strateji</span><select className="input" value={filters.strategy} onChange={(e) => update("strategy", e.target.value)}>
        <option value="all">Tüm stratejiler</option>{Object.entries(STRATEGY_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label><span className="label">Min. AI olasılığı %</span><input className="input" type="number" min="0" max="100" value={filters.minAi} onChange={(e) => update("minAi", Number(e.target.value))} /></label>
      <div className="col-span-2 flex flex-wrap items-end gap-3 pb-2 sm:col-span-1 xl:col-span-2">
        <label className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" className="checkbox" checked={filters.newOnly} onChange={(e) => update("newOnly", e.target.checked)} />Yeni sinyaller</label>
        <label className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" className="checkbox" checked={filters.eligibleOnly} onChange={(e) => update("eligibleOnly", e.target.checked)} />Yalnız uygun</label>
        <button className="ml-auto text-slate-500 hover:text-slate-200" title="Filtreleri sıfırla" onClick={() => onChange({ ...filters, search: "", minScore: 0, minVolume: 0, minVolumeRatio: 0, risk: "all", strategy: "all", minAi: 0, newOnly: false, eligibleOnly: true })}><RotateCcw size={16} /></button>
      </div>
    </div>
  </div>;
}
