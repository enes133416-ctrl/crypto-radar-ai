import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import type { CoinAnalysis } from "../types/api";
import { aiProbability, change, formatCompact, formatNumber, formatPrice, formatTime, relativeStrength, sortRows, volumeRatio, type SortKey } from "../utils/scanner";
import { Badge, Change, Probability, ScoreBadge } from "./ui";

type Header = { key?: SortKey; label: string; className?: string };
const headers: Header[] = [
  { key: "symbol", label: "Coin / Piyasa" }, { key: "price", label: "Fiyat" },
  { label: "5m" }, { label: "15m" }, { label: "1h" }, { label: "4h" }, { key: "change24h", label: "24h" },
  { key: "volumeRatio", label: "Vol. Ratio" }, { key: "atr", label: "ATR%" }, { key: "rsi", label: "RSI" },
  { key: "adx", label: "ADX" }, { label: "Rel. Strength" }, { label: "OB Imbalance" },
  { key: "ai", label: "AI +10%" }, { label: "AI 24h" }, { label: "AI 48h" }, { label: "AI 72h" },
  { key: "score", label: "Skor" }, { label: "Risk" }, { key: "signalTime", label: "Sinyal" }, { label: "" },
];

export default function ScannerTable({ rows, timeframe = "15m", compact = false }: { rows: CoinAnalysis[]; timeframe?: string; compact?: boolean }) {
  const [sort, setSort] = useState<{ key: SortKey; direction: "asc" | "desc" }>({ key: "score", direction: "desc" });
  const [expanded, setExpanded] = useState<string | null>(null);
  const sorted = useMemo(() => sortRows(rows, sort.key, sort.direction, timeframe), [rows, sort, timeframe]);
  const visibleHeaders = compact ? headers.filter((h) => ["Coin / Piyasa", "Fiyat", "24h", "Vol. Ratio", "RSI", "AI +10%", "Skor", "Risk", ""].includes(h.label)) : headers;

  const toggleSort = (key?: SortKey) => {
    if (!key) return;
    setSort((current) => ({ key, direction: current.key === key && current.direction === "desc" ? "asc" : "desc" }));
  };
  const header = (item: typeof headers[number]) => <th key={item.label} className="whitespace-nowrap px-3 py-3 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
    {item.key ? <button className="inline-flex items-center gap-1 hover:text-slate-300" onClick={() => toggleSort(item.key)}>{item.label}
      {sort.key === item.key ? sort.direction === "desc" ? <ArrowDown size={11} /> : <ArrowUp size={11} /> : <ArrowUpDown size={11} className="opacity-40" />}</button> : item.label}
  </th>;

  return <div className="overflow-x-auto">
    <table className={`w-full border-collapse text-xs tabular-nums ${compact ? "min-w-[780px]" : "min-w-[1750px]"}`}>
      <thead className="border-y border-slate-800 bg-slate-900/95"><tr>{visibleHeaders.map(header)}</tr></thead>
      <tbody className="divide-y divide-slate-800/70">
        {sorted.map((row) => {
          const id = `${row.market}-${row.symbol}`;
          const primary = row.snapshots[timeframe] ?? row.snapshots["15m"];
          const cells: Record<string, React.ReactNode> = {
            "Coin / Piyasa": <Link to={`/coin/${row.market}/${row.symbol}`} className="group flex items-center gap-2"><span>
              <span className="block font-semibold text-slate-100 group-hover:text-cyan-300">{row.symbol.replace("USDT", "")}<span className="text-slate-500">/USDT</span></span>
              <span className="mt-1 block"><Badge tone={row.market === "spot" ? "cyan" : "violet"}>{row.market.toUpperCase()}</Badge></span></span></Link>,
            "Fiyat": <span className="text-slate-200">${formatPrice(row.price)}</span>,
            "5m": <Change value={change(row, "5m", timeframe)} />, "15m": <Change value={change(row, "15m", timeframe)} />,
            "1h": <Change value={change(row, "1h", timeframe)} />, "4h": <Change value={change(row, "4h", timeframe)} />,
            "24h": <Change value={change(row, "24h", timeframe)} />,
            "Vol. Ratio": <span className={(volumeRatio(row) ?? 0) >= 2.5 ? "text-cyan-300" : "text-slate-300"}>{formatNumber(volumeRatio(row))}x</span>,
            "ATR%": formatNumber(primary?.atr_pct), "RSI": formatNumber(primary?.rsi14, 1), "ADX": formatNumber(primary?.adx, 1),
            "Rel. Strength": <Change value={relativeStrength(row)} />,
            "OB Imbalance": formatNumber(row.order_flow?.imbalance, 3),
            "AI +10%": <Probability value={aiProbability(row)} />,
            "AI 24h": <Probability value={aiProbability(row, "24")} />, "AI 48h": <Probability value={aiProbability(row, "48")} />,
            "AI 72h": <Probability value={aiProbability(row, "72")} />,
            "Skor": <ScoreBadge score={row.score.total} eligible={row.risk.eligible} />,
            "Risk": <Badge tone={!row.risk.eligible ? "red" : row.risk_level === "high" ? "amber" : row.risk_level === "medium" ? "amber" : "green"}>
              {!row.risk.eligible ? "ELENDİ" : row.risk_level === "high" ? "YÜKSEK" : row.risk_level === "medium" ? "ORTA" : "DÜŞÜK"}</Badge>,
            "Sinyal": <span className="whitespace-nowrap text-slate-400">{formatTime(row.as_of_close_time)}</span>,
          };
          return <FragmentRow key={id} row={row} id={id} cells={cells} headers={visibleHeaders} expanded={expanded === id}
            onExpand={() => setExpanded(expanded === id ? null : id)} compact={compact} />;
        })}
      </tbody>
    </table>
  </div>;
}

function FragmentRow({ row, id, cells, headers, expanded, onExpand, compact }: {
  row: CoinAnalysis; id: string; cells: Record<string, React.ReactNode>; headers: Header[];
  expanded: boolean; onExpand: () => void; compact: boolean;
}) {
  return <>
    <tr className="bg-slate-900/30 transition hover:bg-slate-800/40">
      {headers.map((header) => <td key={header.label} className="whitespace-nowrap px-3 py-3">{header.label === "" ?
        <button className="text-slate-500 hover:text-cyan-300" onClick={onExpand} aria-label={`${row.symbol} detayını aç`}>
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</button> : cells[header.label]}</td>)}
    </tr>
    {expanded && <tr className="bg-slate-950/70"><td colSpan={headers.length} className="px-5 py-4">
      <div className="grid gap-5 xl:grid-cols-3">
        <div><h4 className="mb-2 text-xs font-semibold text-slate-300">Sinyal nedenleri</h4>
          <ul className="space-y-1 text-xs leading-5 text-slate-400">{row.strategies.filter((s) => s.triggered).flatMap((s) => s.reasons).slice(0, 5).map((reason, i) => <li key={i}>• {reason}</li>)}
            {!row.strategies.some((s) => s.triggered) && <li>Henüz tetiklenmiş strateji yok; skor tek başına sinyal değildir.</li>}</ul></div>
        <div><h4 className="mb-2 text-xs font-semibold text-slate-300">Skor dağılımı</h4>
          <div className="grid grid-cols-2 gap-2">{row.score.components.map((c) => <span key={c.name} className="text-xs text-slate-500">{c.name}: <b className="text-slate-300">{c.points}/{c.maximum}</b></span>)}</div></div>
        <div className="flex items-start justify-between gap-4"><div><h4 className="mb-2 text-xs font-semibold text-slate-300">Risk / veri kalitesi</h4>
          <p className="text-xs leading-5 text-slate-400">{row.risk.flags[0]?.message ?? "Zorunlu kontroller geçti"}</p>
          <p className="mt-1 text-xs text-slate-500">24s hacim: {formatCompact(row.market_comparison?.own_quote_volume_24h)} USDT</p></div>
          {!compact && <Link to={`/coin/${row.market}/${row.symbol}`} className="btn-secondary shrink-0">Detay<ExternalLink size={13} /></Link>}</div>
      </div>
    </td></tr>}
  </>;
}
