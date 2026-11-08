"""Sinyalleri kaydetme ve gelecek mumlar geldikçe sonuçlarını kapatma."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.backtesting.labels import outcome_values
from app.collectors.models import INTERVAL_MS, Market
from app.config.settings import Settings
from app.database.sqlite import Database
from app.ml.features import extract_features
from app.services.market_data import MarketDataService

log = logging.getLogger(__name__)


class SignalTracker:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    def record(self, analysis_dict: dict, probabilities: dict | None = None,
               model_trained_before: int | None = None) -> list[int]:
        if not analysis_dict.get("price") or not (analysis_dict.get("score") or {}).get("eligible"):
            return []
        if analysis_dict["score"]["total"] < self.settings.signal_min_score:
            return []
        signal_time = analysis_dict.get("as_of_close_time")
        if signal_time is None:
            return []
        ids = []
        for strategy in analysis_dict.get("strategies") or []:
            if not strategy.get("triggered"):
                continue
            signal_id = self.db.insert_signal(
                market=analysis_dict["market"], symbol=analysis_dict["symbol"],
                strategy=strategy["name"], signal_time=signal_time,
                valid_until=analysis_dict.get("signal_valid_until_ms"),
                score=analysis_dict["score"]["total"], entry_price=analysis_dict["price"],
                features=extract_features(analysis_dict), analysis=analysis_dict,
                probabilities=probabilities, model_trained_before=model_trained_before,
                cooldown_ms=self.settings.signal_cooldown_hours * 3_600_000,
            )
            if signal_id is not None:
                ids.append(signal_id)
        return ids

    async def update_outcomes(self, market_data: MarketDataService, now_ms: int | None = None) -> int:
        now = now_ms or int(time.time() * 1000)
        updated = 0
        # Her çağrıda sınırlı sayıda açık kayıt işlenir; REST çağrıları sırayla ve limitlidir.
        # Resolved kayıtlar kuyruğu doldurup eski açık sinyalleri aç bırakmasın.
        pending = [*self.db.signals(status="partial", limit=500), *self.db.signals(status="open", limit=500)]
        for signal in pending:
            market = Market(signal["market"])
            symbol = signal["symbol"]
            end = min(now, signal["signal_time"] + 72 * 3_600_000)
            rows = self.db.candles_after(market, symbol, "15m", signal["signal_time"], end)
            # Bellekte olup henüz diske yazılmamış mumları da dahil et.
            memory = market_data.store.closed(market, symbol, "15m")
            merged = {c.open_time: c for c in [*rows, *memory] if c.close_time > signal["signal_time"] and c.open_time <= end}
            rows = [merged[k] for k in sorted(merged)]
            expected_end = min(now, signal["signal_time"] + 72 * 3_600_000)
            # Son 15 dakikalık kapanmış mum yoksa REST ile onarmayı dene.
            if not rows or rows[-1].close_time < expected_end - 2 * INTERVAL_MS["15m"]:
                try:
                    candles = await market_data.clients[market].klines(
                        symbol, "15m", limit=500, start_time=signal["signal_time"] + 1, end_time=end,
                    )
                    closed = [c for c in candles if c.is_closed]
                    self.db.save_candles(closed)
                    market_data.store.apply_many(closed)
                    merged.update({c.open_time: c for c in closed})
                    rows = [merged[k] for k in sorted(merged)]
                except Exception as exc:  # ağ hatası sonucu uydurma; bir sonraki turda tekrar dene
                    log.info("Sonuç mumları henüz alınamadı %s:%s: %s", market.value, symbol, exc)
            values, resolved = outcome_values(signal, rows, now, self.settings.round_trip_cost_pct)
            if any(key.startswith("price_") for key in values):
                self.db.update_outcome(signal["id"], values, resolved)
                updated += 1
            await asyncio.sleep(0)  # event loop'u bloke etmemek için işbirlikçi geçiş
        return updated
