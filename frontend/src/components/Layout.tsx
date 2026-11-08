import { useState } from "react";
import { Activity, BrainCircuit, ChartCandlestick, ChevronRight, Gauge, History, LayoutDashboard, Menu, Radar, ScanLine, Settings, ShieldAlert, Sparkles, X, Zap } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { fetchHealth } from "../services/api";
import { useApi } from "../hooks/useApi";
import { Badge } from "./ui";

const navigation = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/scanner", label: "Live Scanner", icon: Radar },
  { to: "/early", label: "Early Signals", icon: Sparkles },
  { to: "/breakouts", label: "Breakout Scanner", icon: Zap },
  { to: "/spot", label: "Spot Scanner", icon: ScanLine },
  { to: "/futures", label: "Futures Scanner", icon: ChartCandlestick },
  { to: "/predictions", label: "AI Predictions", icon: BrainCircuit },
  { to: "/performance", label: "Historical Performance", icon: History },
  { to: "/market", label: "Market Overview", icon: Gauge },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { data: health } = useApi(fetchHealth, 30_000);
  return <div className="min-h-screen bg-slate-950 text-slate-200">
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-800 bg-slate-925 transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex h-16 items-center justify-between border-b border-slate-800 px-5">
        <NavLink to="/" className="flex items-center gap-3" onClick={() => setOpen(false)}>
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-cyan-500/15 text-cyan-400"><Activity size={21} /></span>
          <span><span className="block text-sm font-semibold text-white">CRYPTO RADAR</span><span className="block text-[10px] tracking-[0.25em] text-cyan-500">AI TERMINAL</span></span>
        </NavLink>
        <button className="text-slate-400 lg:hidden" onClick={() => setOpen(false)} aria-label="Menüyü kapat"><X size={20} /></button>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Ana menü">
        {navigation.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
          className={({ isActive }) => `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${isActive ? "bg-cyan-500/10 font-medium text-cyan-300" : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-200"}`}>
          <Icon size={17} /><span className="flex-1">{label}</span><ChevronRight size={13} className="opacity-0 group-hover:opacity-50" />
        </NavLink>)}
      </nav>
      <div className="border-t border-slate-800 p-4 text-[11px] leading-5 text-slate-500">
        <ShieldAlert size={15} className="mb-2 text-amber-500" />Analiz amaçlıdır. Otomatik emir göndermez.<br />Kâr garantisi ve yatırım tavsiyesi değildir.
      </div>
    </aside>
    {open && <button className="fixed inset-0 z-30 bg-black/60 lg:hidden" aria-label="Menüyü kapat" onClick={() => setOpen(false)} />}
    <div className="lg:pl-64">
      <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-800 bg-slate-950/90 px-4 backdrop-blur md:px-6">
        <div className="flex items-center gap-3"><button className="btn-icon lg:hidden" onClick={() => setOpen(true)} aria-label="Menüyü aç"><Menu size={20} /></button>
          <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex"><span className={`h-2 w-2 rounded-full ${health?.status === "ok" ? "bg-emerald-400 shadow-live" : "bg-rose-500"}`} />
            {health?.status === "ok" ? "Backend bağlı" : "Backend bekleniyor"}</div></div>
        <div className="flex items-center gap-2 md:gap-3">
          {health?.demo_mode && <Badge tone="amber">DEMO</Badge>}
          <Badge tone={health?.collector_enabled ? "green" : "red"}>{health?.collector_enabled ? "BINANCE LIVE" : "COLLECTOR OFF"}</Badge>
          <span className="hidden text-xs text-slate-500 md:inline">v{health?.version ?? "—"} · {health?.run_mode ?? "—"}</span>
        </div>
      </header>
      <main className="mx-auto max-w-[1800px] p-4 md:p-6"><Outlet /></main>
    </div>
  </div>;
}
