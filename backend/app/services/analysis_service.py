"""MarketDataService deposundaki gerçek veriyi analiz motoruna bağlar."""
from __future__ import annotations

import logging
import time

from app.collectors.binance_rest import BinanceAPIError
from app.collectors.models import Market
from app.collectors.parsers import DataError
from app.config.settings import Settings
from app.services.analysis_engine import AnalysisEngine, CoinAnalysis, risk_config_from_settings
from app.services.market_data import MarketDataService

log = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, settings: Settings, market_data: MarketDataService, engine: AnalysisEngine | None = None):
        self.settings = settings
        self.market_data = market_data
        self.engine = engine or AnalysisEngine(risk_config_from_settings(settings))

    def _series(self, market: Market, symbol: str) -> dict[str, list]:
        return {interval: self.market_data.store.closed(market, symbol, interval) for interval in self.settings.tracked_intervals}

    def _benchmarks(self, market: Market) -> tuple[dict, dict]:
        return self._series(market, "BTCUSDT"), self._series(market, "ETHUSDT")

    def market_regime(self, market: Market) -> dict:
        return self.engine.regime(self._series(market, "BTCUSDT"), market).to_dict()

    async def analyze_symbol(self, market: Market, symbol: str, fetch_orderbook: bool = True) -> CoinAnalysis:
        symbol = symbol.upper()
        info = next((s for s in self.market_data.universe.get(market, []) if s.symbol == symbol), None)
        ticker = self.market_data.tickers.get(market, {}).get(symbol)
        client = self.market_data.clients[market]
        book = None
        if fetch_orderbook:
            try:
                book = await client.depth(symbol)
            except (BinanceAPIError, DataError, OSError) as exc:
                log.warning("%s:%s order book alınamadı: %s", market.value, symbol, exc)
        funding = None
        if market == Market.FUTURES:
            try:
                rates = await client.funding_rates(symbol, limit=1)
                funding = rates[-1] if rates else None
            except (BinanceAPIError, DataError, OSError) as exc:
                log.warning("%s funding alınamadı: %s", symbol, exc)
        other = Market.FUTURES if market == Market.SPOT else Market.SPOT
        other_ticker = self.market_data.tickers.get(other, {}).get(symbol)
        difference = None
        if ticker and other_ticker and ticker.last_price:
            difference = (ticker.last_price / other_ticker.last_price - 1) * 100 if other_ticker.last_price else None
        btc, eth = self._benchmarks(market)
        return self.engine.analyze(market, symbol, self._series(market, symbol), ticker, book, funding, info,
                                   btc, eth, difference, now_ms=int(time.time() * 1000))

    def scan(self, market: Market, min_score: float = 0, eligible_only: bool = True, limit: int = 100) -> dict:
        # Tüm evren için REST depth çağrısı yapılmaz; WebSocket/REST mumlarla tarama yapılır.
        # Detay uç noktası order book zorunlu kontrollerini ayrıca uygular.
        symbols = [s.symbol for s in self.market_data.universe.get(market, [])]
        btc, eth = self._benchmarks(market)
        analyses = []
        for symbol in symbols:
            ticker = self.market_data.tickers.get(market, {}).get(symbol)
            info = next(s for s in self.market_data.universe[market] if s.symbol == symbol)
            analyses.append(self.engine.analyze(market, symbol, self._series(market, symbol), ticker, None,
                                                None, info, btc, eth, now_ms=int(time.time() * 1000)))
        eligible_count = sum(a.risk.eligible for a in analyses)
        filtered = [a for a in analyses if a.score.total >= min_score and (a.risk.eligible or not eligible_only)]
        filtered.sort(key=lambda a: a.score.total, reverse=True)
        return {"market": market.value, "count": min(len(filtered), limit), "total_matching": len(filtered),
                "scanned": len(analyses), "eligible_before_score_filter": eligible_count,
                "orderbook_scope": "detail_only",
                "note": "Taramada order book yoksa ilgili kontroller doğrulanamadı olarak işaretlenir; coin detayında REST ile kontrol edilir.",
                "items": [a.to_dict() for a in filtered[:limit]]}
