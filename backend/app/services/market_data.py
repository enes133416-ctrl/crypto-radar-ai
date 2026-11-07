"""Veri toplama orkestrasyonu: coin keşfi, mum geçmişi (REST), canlı mumlar (WebSocket), kopma sonrası onarım."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.collectors.binance_rest import BinanceAPIError, BinanceRestClient
from app.collectors.candle_store import CandleStore
from app.collectors.models import INTERVAL_MS, Market, SymbolInfo, Ticker24h
from app.collectors.parsers import DataError, parse_ws_kline
from app.config.settings import Settings
from app.websocket.manager import ReconnectingStream, build_stream_url, chunked, default_connect

log = logging.getLogger(__name__)
MAX_STREAMS_PER_CONNECTION = 200


class MarketDataService:
    def __init__(self, settings: Settings, clients: dict[Market, BinanceRestClient], store: CandleStore | None = None, connect=default_connect):
        self.settings = settings
        self.clients = clients
        self.store = store or CandleStore()
        self._connect = connect
        self.universe: dict[Market, list[SymbolInfo]] = {}
        self.tickers: dict[Market, dict[str, Ticker24h]] = {}
        self.errors: dict[str, str] = {}
        self.streams: list[ReconnectingStream] = []
        self._tasks: list[asyncio.Task] = []
        self.started_at = time.time()

    # ---- keşif ----
    async def discover(self, market: Market) -> list[SymbolInfo]:
        client = self.clients[market]
        info = await client.exchange_info()
        tickers = {t.symbol: t for t in await client.tickers_24h()}
        self.tickers[market] = tickers
        eligible = [s for s in info if s.symbol in tickers and tickers[s.symbol].quote_volume >= self.settings.min_quote_volume_24h]
        eligible.sort(key=lambda s: tickers[s.symbol].quote_volume, reverse=True)
        self.universe[market] = eligible[: self.settings.max_symbols_per_market]
        log.info("%s: %d uygun sembol (hacim >= %.0f), %d seçildi", market.value, len(eligible), self.settings.min_quote_volume_24h, len(self.universe[market]))
        return self.universe[market]

    # ---- geçmiş ----
    async def backfill(self, market: Market, symbol: str, interval: str, limit: int | None = None) -> int:
        candles = await self.clients[market].klines(symbol, interval, limit=limit or self.settings.backfill_limit)
        self.store.apply_many(candles)
        return len(candles)

    async def backfill_symbols(self, market: Market, symbols: list[str], repair: bool = False) -> None:
        for sym in symbols:
            for itv in self.settings.tracked_intervals:
                limit = None
                if repair:
                    last = self.store.last_closed_open_time(market, sym, itv)
                    if last is not None:
                        missing = int((time.time() * 1000 - last) / INTERVAL_MS[itv]) + 2
                        limit = min(1000, max(2, missing))
                try:
                    await self.backfill(market, sym, itv, limit)
                except (BinanceAPIError, DataError) as e:
                    self.errors[f"{market.value}:{sym}:{itv}"] = str(e)
                    if isinstance(e, BinanceAPIError) and e.status in (418, 451, 403):
                        raise  # bölge/ban hatasında boşuna devam etme

    # ---- canlı akış ----
    async def handle_ws_message(self, market: Market, raw: Any) -> None:
        try:
            self.store.apply(parse_ws_kline(raw, market))
        except DataError as e:
            if "Kline olmayan" not in str(e):
                log.warning("WS mesajı reddedildi: %s", e)

    def _build_streams(self, market: Market) -> list[ReconnectingStream]:
        base = self.settings.binance_spot_ws if market == Market.SPOT else self.settings.binance_futures_ws
        symbols = [s.symbol for s in self.universe.get(market, [])]
        per_conn = max(1, MAX_STREAMS_PER_CONNECTION // max(1, len(self.settings.tracked_intervals)))
        out = []
        for i, group in enumerate(chunked(symbols, per_conn)):
            names = [f"{s.lower()}@kline_{itv}" for s in group for itv in self.settings.tracked_intervals]

            async def on_msg(raw, m=market):
                await self.handle_ws_message(m, raw)

            async def on_reco(m=market, g=list(group)):
                await self.backfill_symbols(m, g, repair=True)

            out.append(ReconnectingStream(f"{market.value}-ws-{i}", build_stream_url(base, names), on_msg, on_reco, connect=self._connect))
        return out

    async def _run_market(self, market: Market) -> None:
        try:
            await self.discover(market)
            self.errors.pop(f"{market.value}:discover", None)
            await self.backfill_symbols(market, [s.symbol for s in self.universe[market]])
        except (BinanceAPIError, DataError) as e:
            self.errors[f"{market.value}:discover"] = str(e)
            log.error("%s veri toplama başlatılamadı: %s", market.value, e)
            return
        streams = self._build_streams(market)
        self.streams.extend(streams)
        await asyncio.gather(*(s.run() for s in streams))

    async def run(self) -> None:
        self._tasks = [asyncio.create_task(self._run_market(m)) for m in self.clients]
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def stop(self) -> None:
        for s in self.streams:
            s.stop()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        for c in self.clients.values():
            await c.close()

    def status(self) -> dict:
        return {
            "enabled": True,
            "uptime_s": round(time.time() - self.started_at),
            "markets": {m.value: {"symbols": len(self.universe.get(m, []))} for m in self.clients},
            "series_with_data": self.store.series_count(),
            "tracked_intervals": list(self.settings.tracked_intervals),
            "streams": [s.status() for s in self.streams],
            "errors": dict(list(self.errors.items())[:20]),
            "error_count": len(self.errors),
        }


def build_market_data_service(settings: Settings) -> MarketDataService:
    clients = {
        Market.SPOT: BinanceRestClient(Market.SPOT, settings.binance_spot_rest),
        Market.FUTURES: BinanceRestClient(Market.FUTURES, settings.binance_futures_rest),
    }
    return MarketDataService(settings, clients)
