"""Sürekli arka plan tarayıcı, sonuç önbelleği, dashboard ve sinyal kaydı."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from typing import Any

from app.collectors.models import Market
from app.config.settings import Settings
from app.database.sqlite import Database
from app.services.analysis_engine import CoinAnalysis
from app.services.analysis_service import AnalysisService
from app.services.market_data import MarketDataService
from app.services.signal_tracker import SignalTracker

log = logging.getLogger(__name__)


class ScannerService:
    def __init__(self, settings: Settings, market_data: MarketDataService,
                 analysis: AnalysisService, tracker: SignalTracker):
        self.settings = settings
        self.market_data = market_data
        self.analysis = analysis
        self.tracker = tracker
        self._results: dict[Market, list[CoinAnalysis]] = {m: [] for m in Market}
        self.last_scan: dict[str, int] = {}
        self.errors: dict[str, str] = {}
        self.new_signal_ids: list[int] = []
        self._stop = False
        self._refresh_lock = asyncio.Lock()

    async def refresh_market(self, market: Market) -> None:
        async with self._refresh_lock:
            _, analyses = await self.analysis.scan_live(market, min_score=0, eligible_only=False, limit=200)
            self._results[market] = analyses
            self.last_scan[market.value] = int(time.time() * 1000)
            for analysis in analyses:
                data = analysis.to_dict()
                probabilities = data.get("ai_probabilities")
                trained_before = probabilities.get("trained_before") if probabilities else None
                ids = self.tracker.record(data, probabilities, trained_before)
                self.new_signal_ids.extend(ids)
            self.new_signal_ids = self.new_signal_ids[-1000:]
            self.errors.pop(market.value, None)

    async def run(self) -> None:
        last_outcome_update = 0.0
        while not self._stop:
            started = time.monotonic()
            for market in self.market_data.clients:
                if self._stop:
                    break
                try:
                    await self.refresh_market(market)
                except Exception as exc:
                    self.errors[market.value] = str(exc)
                    log.error("%s taraması başarısız: %s", market.value, exc)
            if time.monotonic() - last_outcome_update >= self.settings.outcome_interval_seconds:
                try:
                    await self.tracker.update_outcomes(self.market_data)
                    last_outcome_update = time.monotonic()
                except Exception as exc:
                    log.warning("Sinyal sonuç güncellemesi ertelendi: %s", exc)
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(1.0, self.settings.scan_interval_seconds - elapsed))

    def stop(self) -> None:
        self._stop = True

    def query(self, market: Market | None = None, min_score: float = 0,
              eligible_only: bool = True, strategy: str | None = None,
              new_only: bool = False, risk: str | None = None,
              min_ai_up10: float | None = None, early_only: bool = False,
              breakout_only: bool = False, limit: int = 200) -> dict:
        markets = [market] if market else list(self._results)
        now = int(time.time() * 1000)
        items = []
        for current in markets:
            for analysis in self._results.get(current, []):
                data = analysis.to_dict()
                if data["score"]["total"] < min_score or (eligible_only and not data["risk"]["eligible"]):
                    continue
                strategies = data.get("strategies") or []
                if strategy and not any(s["name"] == strategy and s["triggered"] for s in strategies):
                    continue
                if breakout_only and not any(s["name"] == "consolidation_breakout" and s["triggered"] for s in strategies):
                    continue
                if early_only:
                    volume_strategy = next((s for s in strategies if s["name"] == "volume_explosion"), None)
                    change = ((volume_strategy or {}).get("metrics") or {}).get("price_change_pct")
                    if not volume_strategy or not volume_strategy["triggered"] or change is None or change >= 10:
                        continue
                if new_only and (not data.get("as_of_close_time") or now - data["as_of_close_time"] > 2 * 3_600_000):
                    continue
                warnings = len(data["risk"].get("warnings") or [])
                level = "low" if not warnings else "medium" if warnings <= 2 else "high"
                data["risk_level"] = level
                if risk and risk != level:
                    continue
                if min_ai_up10 is not None:
                    probability = (((data.get("ai_probabilities") or {}).get("horizons") or {})
                                   .get("72", {}).get("up10"))
                    if probability is None or probability * 100 < min_ai_up10:
                        continue
                items.append(data)
        items.sort(key=lambda x: x["score"]["total"], reverse=True)
        return {"count": min(len(items), limit), "total_matching": len(items), "items": items[:limit],
                "last_scan": self.last_scan, "errors": self.errors,
                "data_available": any(self.last_scan.values())}

    def dashboard(self) -> dict:
        all_items = [a for values in self._results.values() for a in values if a.risk.eligible]
        all_items.sort(key=lambda a: a.score.total, reverse=True)
        now = int(time.time() * 1000)
        distribution = Counter(a.market for a in all_items)
        market_cards = {}
        for market in self.market_data.clients:
            tickers = self.market_data.tickers.get(market, {})
            market_cards[market.value] = {
                "btc": tickers.get("BTCUSDT").last_price if tickers.get("BTCUSDT") else None,
                "btc_change_24h": tickers.get("BTCUSDT").price_change_pct if tickers.get("BTCUSDT") else None,
                "eth": tickers.get("ETHUSDT").last_price if tickers.get("ETHUSDT") else None,
                "eth_change_24h": tickers.get("ETHUSDT").price_change_pct if tickers.get("ETHUSDT") else None,
                "regime": self.analysis.market_regime(market),
            }
        return {
            "markets": market_cards,
            "scanned_coins": sum(len(v) for v in self._results.values()),
            "strong_signals": sum(a.score.total >= 75 for a in all_items),
            "new_signals": sum(a.as_of_close_time is not None and now - a.as_of_close_time <= 2 * 3_600_000
                               and any(s.triggered for s in a.strategies) for a in all_items),
            "top10": [a.to_dict() for a in all_items[:10]],
            "market_distribution": dict(distribution), "last_scan": self.last_scan,
            "connection": self.market_data.status(), "signal_counts": self.tracker.db.counts(),
            "ai_status": "available" if any(a.ai_status == "available" for a in all_items) else "insufficient_training_data",
        }
