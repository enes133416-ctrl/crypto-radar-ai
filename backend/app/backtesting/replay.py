"""Mum dilimleriyle look-ahead içermeyen tarihsel strateji replay/backtest."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.backtesting.labels import evaluate_horizon
from app.backtesting.performance import performance_report
from app.collectors.models import Candle, Market, SymbolInfo, Ticker24h
from app.ml.features import extract_features
from app.services.analysis_engine import AnalysisEngine


def _ticker_at(rows: list[Candle], market: Market, symbol: str) -> Ticker24h:
    last = rows[-1]
    start = last.close_time - 86_400_000
    window = [c for c in rows if c.close_time > start]
    previous = next((c.close for c in reversed(rows) if c.open_time <= start), window[0].open)
    return Ticker24h(market, symbol, last.close, (last.close / previous - 1) * 100 if previous else 0,
                     max(c.high for c in window), min(c.low for c in window),
                     sum(c.volume for c in window), sum(c.quote_volume for c in window),
                     sum(c.trades for c in window), last.close_time)


class HistoricalBacktester:
    def __init__(self, engine: AnalysisEngine, cooldown_bars: int = 16, cost_pct: float = 0.15):
        self.engine = engine
        self.cooldown_bars = cooldown_bars
        self.cost_pct = cost_pct

    def run(self, market: Market, symbol: str, candles: dict[str, list[Candle]],
            symbol_info: SymbolInfo | None = None, btc: dict[str, list[Candle]] | None = None,
            eth: dict[str, list[Candle]] | None = None, step_bars: int = 4) -> dict:
        primary = sorted((c for c in candles.get("15m", []) if c.is_closed), key=lambda c: c.open_time)
        if len(primary) < 180:
            raise ValueError("Backtest için en az 180 kapalı 15m mumu gerekli")
        results = []
        last_signal_index = -self.cooldown_bars
        # İlk 72 saatlik bölüm gösterge ısınması, son 72 saat sonuç ölçümü için ayrılır.
        for index in range(120, len(primary) - 1, max(1, step_bars)):
            if index - last_signal_index < self.cooldown_bars:
                continue
            current = primary[index]
            cutoff = current.close_time
            sliced = {interval: [c for c in rows if c.is_closed and c.close_time <= cutoff]
                      for interval, rows in candles.items()}
            btc_slice = {interval: [c for c in rows if c.is_closed and c.close_time <= cutoff]
                         for interval, rows in (btc or {}).items()}
            eth_slice = {interval: [c for c in rows if c.is_closed and c.close_time <= cutoff]
                         for interval, rows in (eth or {}).items()}
            analysis = self.engine.analyze(market, symbol, sliced, _ticker_at(primary[:index + 1], market, symbol),
                                           None, None, symbol_info, btc_slice, eth_slice,
                                           now_ms=cutoff).to_dict()
            triggered = [s for s in analysis["strategies"] if s["triggered"]]
            if not triggered or not analysis["risk"]["eligible"]:
                continue
            next_candle = primary[index + 1]
            entry = next_candle.open  # sinyal kapanışında bilinmeyen aynı mum close kullanılmaz
            last_signal_index = index
            for strategy in triggered:
                row: dict[str, Any] = {"id": len(results) + 1, "market": market.value, "symbol": symbol,
                                       "strategy": strategy["name"], "signal_time": cutoff,
                                       "score": analysis["score"]["total"], "entry_price": entry,
                                       "features": extract_features(analysis), "analysis": analysis,
                                       "status": "resolved", "resolved_at": None,
                                       "ambiguous_barriers": 0}
                for hours in (24, 48, 72):
                    future = [c for c in primary[index + 1:] if c.close_time <= cutoff + hours * 3_600_000]
                    if not future or future[-1].close_time < cutoff + hours * 3_600_000 - 900_000:
                        continue
                    outcome = evaluate_horizon(future, entry, self.cost_pct)
                    row[f"price_{hours}h"] = outcome["price"]
                    row[f"max_up_{hours}h"] = outcome["max_up"]
                    row[f"max_down_{hours}h"] = outcome["max_down"]
                    row[f"net_return_{hours}h"] = outcome["net_return"]
                    for target in (5, 10, 15):
                        row[f"hit{target}_{hours}h"] = int(outcome[f"hit{target}"])
                    for stop in (3, 5):
                        row[f"up10_before_stop{stop}_{hours}h"] = int(outcome[f"up10_before_stop{stop}"])
                        row[f"stop{stop}_before_up10_{hours}h"] = int(outcome[f"stop{stop}_before_up10"])
                    row["ambiguous_barriers"] += outcome["ambiguous"]
                results.append(row)
        return {"market": market.value, "symbol": symbol, "signals": results,
                "performance": performance_report(results, 72),
                "assumptions": ["Giriş sinyalden sonraki 15m mumun açılışındadır.",
                                "Komisyon/spread/slippage için sabit gidiş-dönüş bedeli uygulanır.",
                                "Tarihsel order book/funding tick verisi yoktur; bu bileşenler doğrulanmamıştır.",
                                "Delist evreni ancak veri setine delist semboller de dahil edilirse temsil edilir."],
                "data_note": "Bu bir tarihsel simülasyondur; gelecek performans garantisi değildir."}
