"""Gerçek collector verisini analiz, AI, benzerlik ve piyasa karşılaştırmasıyla birleştirir."""
from __future__ import annotations

import asyncio
import logging
import math
import time
from statistics import mean

from app.collectors.binance_rest import BinanceAPIError
from app.collectors.models import Market
from app.collectors.parsers import DataError
from app.config.settings import Settings
from app.database.sqlite import Database
from app.ml.features import extract_features
from app.ml.model import Predictor
from app.ml.similarity import SimilarityAnalyzer
from app.scoring.opportunity import calculate_score
from app.services.analysis_engine import AnalysisEngine, CoinAnalysis, risk_config_from_settings
from app.services.market_data import MarketDataService

log = logging.getLogger(__name__)


def _correlation(own: list, benchmark: list) -> float | None:
    own_by_time = {c.open_time: c.close for c in own}
    btc_by_time = {c.open_time: c.close for c in benchmark}
    times = sorted(set(own_by_time) & set(btc_by_time))[-51:]
    if len(times) < 20:
        return None
    a, b = [], []
    for previous, current in zip(times, times[1:]):
        if own_by_time[previous] > 0 and btc_by_time[previous] > 0:
            a.append(math.log(own_by_time[current] / own_by_time[previous]))
            b.append(math.log(btc_by_time[current] / btc_by_time[previous]))
    if len(a) < 15:
        return None
    ma, mb = mean(a), mean(b)
    covariance = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return round(covariance / math.sqrt(va * vb), 4) if va > 0 and vb > 0 else None


class AnalysisService:
    def __init__(self, settings: Settings, market_data: MarketDataService,
                 engine: AnalysisEngine | None = None, db: Database | None = None,
                 predictor: Predictor | None = None):
        self.settings = settings
        self.market_data = market_data
        self.engine = engine or AnalysisEngine(risk_config_from_settings(settings, live=True))
        self.db = db
        self.predictor = predictor or Predictor(settings.model_path)
        self.similarity = SimilarityAnalyzer()

    def _series(self, market: Market, symbol: str) -> dict[str, list]:
        return {interval: self.market_data.store.closed(market, symbol, interval)
                for interval in self.settings.tracked_intervals}

    def _benchmarks(self, market: Market) -> tuple[dict, dict]:
        return self._series(market, "BTCUSDT"), self._series(market, "ETHUSDT")

    def market_regime(self, market: Market) -> dict:
        return self.engine.regime(self._series(market, "BTCUSDT"), market).to_dict()

    def _enrich(self, analysis: CoinAnalysis, btc: dict) -> CoinAnalysis:
        as_of = analysis.as_of_close_time or int(time.time() * 1000)
        initial = analysis.to_dict()
        similarity = self.similarity.analyze(extract_features(initial),
                                             self.db.resolved_training_rows(as_of) if self.db else [], as_of)
        analysis.historical_similarity = similarity
        if similarity.get("similarity_score") is not None and analysis.volume and analysis.order_flow:
            analysis.score = calculate_score(analysis.strategies, analysis.volume, analysis.order_flow,
                                             analysis.regime, analysis.risk, analysis.mtf_agreement,
                                             similarity["similarity_score"])
        analysis.btc_correlation_15m = _correlation((analysis.to_dict().get("snapshots") and
                                                     self._series(Market(analysis.market), analysis.symbol).get("15m", [])),
                                                    btc.get("15m", []))
        status, probabilities, trained_before = self.predictor.predict(analysis.to_dict())
        analysis.ai_status = status
        analysis.ai_probabilities = probabilities
        if analysis.market == Market.FUTURES.value:
            funding = self.market_data.fundings.get(analysis.symbol)
            oi = self.market_data.open_interests.get(analysis.symbol)
            analysis.futures_context = {
                "funding_rate": funding.funding_rate if funding else None,
                "funding_time": funding.funding_time if funding else None,
                "open_interest": oi.open_interest if oi else None,
                "open_interest_time": oi.time if oi else None,
                "long_short_ratio": None,
                "liquidation_note": "Halka açık likidasyon akışı bu sürümde kalıcı sinyal özelliği olarak kullanılmaz.",
            }
        other = Market.FUTURES if analysis.market == Market.SPOT.value else Market.SPOT
        own_ticker = self.market_data.tickers.get(Market(analysis.market), {}).get(analysis.symbol)
        other_ticker = self.market_data.tickers.get(other, {}).get(analysis.symbol)
        analysis.market_comparison = {
            "other_market": other.value, "available": other_ticker is not None,
            "own_last_price": own_ticker.last_price if own_ticker else None,
            "other_last_price": other_ticker.last_price if other_ticker else None,
            "own_quote_volume_24h": own_ticker.quote_volume if own_ticker else None,
            "other_quote_volume_24h": other_ticker.quote_volume if other_ticker else None,
            "price_difference_pct": ((own_ticker.last_price / other_ticker.last_price - 1) * 100
                                     if own_ticker and other_ticker and other_ticker.last_price else None),
        }
        return analysis

    async def analyze_symbol(self, market: Market, symbol: str, fetch_orderbook: bool = True) -> CoinAnalysis:
        symbol = symbol.upper()
        info = next((s for s in self.market_data.universe.get(market, []) if s.symbol == symbol), None)
        ticker = self.market_data.tickers.get(market, {}).get(symbol)
        client = self.market_data.clients[market]
        book = self.market_data.orderbooks[market].get(symbol)
        if fetch_orderbook:
            try:
                book = await client.depth(symbol)
                self.market_data.orderbooks[market][symbol] = book
            except (BinanceAPIError, DataError, OSError) as exc:
                book = None
                log.warning("%s:%s order book alınamadı: %s", market.value, symbol, exc)
        funding = None
        ratio = None
        if market == Market.FUTURES:
            try:
                rates = await client.funding_rates(symbol, limit=1)
                funding = rates[-1] if rates else None
                if funding:
                    self.market_data.fundings[symbol] = funding
            except (BinanceAPIError, DataError, OSError) as exc:
                log.warning("%s funding alınamadı: %s", symbol, exc)
            try:
                self.market_data.open_interests[symbol] = await client.open_interest(symbol)
            except (BinanceAPIError, DataError, OSError) as exc:
                log.warning("%s open interest alınamadı: %s", symbol, exc)
            try:
                ratios = await client.global_long_short_ratio(symbol, period="5m", limit=1)
                ratio = ratios[-1] if ratios else None
            except (BinanceAPIError, DataError, OSError) as exc:
                log.warning("%s long/short oranı alınamadı: %s", symbol, exc)
        other = Market.FUTURES if market == Market.SPOT else Market.SPOT
        other_ticker = self.market_data.tickers.get(other, {}).get(symbol)
        difference = None
        if ticker and other_ticker and ticker.last_price and other_ticker.last_price:
            difference = (ticker.last_price / other_ticker.last_price - 1) * 100
        btc, eth = self._benchmarks(market)
        result = self.engine.analyze(market, symbol, self._series(market, symbol), ticker, book, funding, info,
                                     btc, eth, difference, now_ms=int(time.time() * 1000))
        if result.futures_context is not None:
            result.futures_context.update({
                "long_short_ratio": ratio.long_short_ratio if ratio else None,
                "long_account": ratio.long_account if ratio else None,
                "short_account": ratio.short_account if ratio else None,
                "long_short_status": "ok" if ratio else "unavailable",
                "open_interest_status": "ok" if symbol in self.market_data.open_interests else "unavailable",
            })
        return self._enrich(result, btc)

    def scan(self, market: Market, min_score: float = 0, eligible_only: bool = True, limit: int = 100) -> dict:
        """Senkron, REST'siz önizleme. Derinlik yoksa canlı risk config'i coin'i elememeli değil, eler."""
        symbols = [s.symbol for s in self.market_data.universe.get(market, [])]
        btc, eth = self._benchmarks(market)
        analyses = []
        for symbol in symbols:
            ticker = self.market_data.tickers.get(market, {}).get(symbol)
            info = next(s for s in self.market_data.universe[market] if s.symbol == symbol)
            result = self.engine.analyze(market, symbol, self._series(market, symbol), ticker, None,
                                         None, info, btc, eth, now_ms=int(time.time() * 1000))
            analyses.append(self._enrich(result, btc))
        return self._scan_response(market, analyses, min_score, eligible_only, limit, "unverified_preview")

    async def scan_live(self, market: Market, min_score: float = 0, eligible_only: bool = True,
                        limit: int = 100) -> tuple[dict, list[CoinAnalysis]]:
        """Derinlik/funding kontrollü tam tarama; background scanner bunu kullanır."""
        symbols = [s.symbol for s in self.market_data.universe.get(market, [])]
        semaphore = asyncio.Semaphore(self.settings.scan_orderbook_concurrency)

        async def one(symbol: str) -> CoinAnalysis:
            async with semaphore:
                return await self.analyze_symbol(market, symbol, fetch_orderbook=True)

        analyses = list(await asyncio.gather(*(one(s) for s in symbols), return_exceptions=True))
        successful = []
        for symbol, result in zip(symbols, analyses):
            if isinstance(result, Exception):
                log.error("Tarama analizi başarısız %s:%s: %s", market.value, symbol, result)
            else:
                successful.append(result)
        return self._scan_response(market, successful, min_score, eligible_only, limit, "live_orderbook_checked"), successful

    @staticmethod
    def _scan_response(market: Market, analyses: list[CoinAnalysis], min_score: float,
                       eligible_only: bool, limit: int, scope: str) -> dict:
        eligible_count = sum(a.risk.eligible for a in analyses)
        filtered = [a for a in analyses if a.score.total >= min_score and (a.risk.eligible or not eligible_only)]
        filtered.sort(key=lambda a: a.score.total, reverse=True)
        return {"market": market.value, "count": min(len(filtered), limit), "total_matching": len(filtered),
                "scanned": len(analyses), "eligible_before_score_filter": eligible_count,
                "orderbook_scope": scope, "generated_at": int(time.time() * 1000),
                "note": "Yalnız eligible=true sonuçlar zorunlu veri/likidite kontrollerinden geçmiştir.",
                "items": [a.to_dict() for a in filtered[:limit]]}
