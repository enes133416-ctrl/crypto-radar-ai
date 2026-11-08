import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { fetchScan } from "../services/api";
import { useApi } from "../hooks/useApi";
import type { MarketFilter } from "../types/api";
import { DEFAULT_FILTERS, filterRows } from "../utils/scanner";
import ScannerFilters from "../components/ScannerFilters";
import ScannerTable from "../components/ScannerTable";
import { Card, DataState, PageHeader } from "../components/ui";

export default function ScannerPage({ market = "all", mode = "all", title = "Live Scanner", description }: {
  market?: MarketFilter; mode?: "all" | "early" | "breakout"; title?: string; description?: string;
}) {
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS, market });
  const [timeframe, setTimeframe] = useState("15m");
  const { data, error, loading, reload, updatedAt } = useApi(
    () => fetchScan({ market, eligible_only: false, early_only: mode === "early", breakout_only: mode === "breakout", limit: 200 }),
    30_000, [market, mode],
  );
  const rows = useMemo(() => filterRows(data?.items ?? [], filters), [data, filters]);
  const descriptions = {
    all: "Spot ve Futures sonuçları ayrı etiketlenir. Skor, sinyal değildir; tetiklenmiş strateji ve zorunlu risk kontrollerini birlikte inceleyin.",
    early: "Fiyatı ilgili hacim penceresinde %10'a ulaşmamış, hacim ve alıcı akışı değişimi gösteren erken adaylar. %5 üzeri hareket strateji içinde ayrıca risklenir.",
    breakout: "Önceki direnç üzerinde kapanış, hacim doğrulaması ve güçlü mum konumu gerektiren kırılım sinyalleri.",
  };
  return <>
    <PageHeader title={title} description={description ?? descriptions[mode]} action={<div className="flex items-center gap-3">
      <span className="text-xs text-slate-500">{updatedAt ? `Güncellendi ${new Date(updatedAt).toLocaleTimeString("tr-TR")}` : "İlk tarama bekleniyor"}</span>
      <button className="btn-secondary" onClick={() => void reload()}><RefreshCw size={14} />Yenile</button></div>} />
    <Card>
      <ScannerFilters filters={filters} onChange={setFilters} timeframe={timeframe} onTimeframe={setTimeframe} showMarket={market === "all"} />
      <div className="flex items-center justify-between px-4 py-3 text-xs text-slate-500"><span>{rows.length} coin gösteriliyor · API eşleşmesi {data?.total_matching ?? 0}</span>
        <span>{filters.eligibleOnly ? "Zorunlu filtreleri geçenler" : "Elenenler dahil"}</span></div>
      <DataState loading={loading} error={error} empty={rows.length === 0} onRetry={() => void reload()}>
        <ScannerTable rows={rows} timeframe={timeframe} />
      </DataState>
    </Card>
  </>;
}
