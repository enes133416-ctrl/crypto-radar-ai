import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import ScannerPage from "./pages/ScannerPage";
import Predictions from "./pages/Predictions";
import Performance from "./pages/Performance";
import MarketOverview from "./pages/MarketOverview";
import Settings from "./pages/Settings";
import CoinDetail from "./pages/CoinDetail";

export default function App() {
  return <Routes>
    <Route element={<Layout />}>
      <Route index element={<Dashboard />} />
      <Route path="/scanner" element={<ScannerPage />} />
      <Route path="/early" element={<ScannerPage mode="early" title="Early Signals" />} />
      <Route path="/breakouts" element={<ScannerPage mode="breakout" title="Breakout Scanner" />} />
      <Route path="/spot" element={<ScannerPage market="spot" title="Spot Scanner" description="Binance Spot USDT pariteleri. Futures sinyalleri bu listeye karıştırılmaz." />} />
      <Route path="/futures" element={<ScannerPage market="futures" title="Futures Scanner" description="Binance USDⓈ-M perpetual USDT pariteleri; funding, open interest ve Futures order book bağlamıyla." />} />
      <Route path="/predictions" element={<Predictions />} />
      <Route path="/performance" element={<Performance />} />
      <Route path="/market" element={<MarketOverview />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/coin/:market/:symbol" element={<CoinDetail />} />
      <Route path="/404" element={<div className="py-20 text-center"><h1 className="text-2xl">Sayfa bulunamadı</h1><p className="mt-2 text-slate-500">İstenen terminal sayfası mevcut değil.</p></div>} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Route>
  </Routes>;
}
