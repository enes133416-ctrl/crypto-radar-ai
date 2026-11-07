"""Binance REST istemcisi (Spot ve USDⓈ-M Futures). Herkese açık uç noktalar; API key gerekmez."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .models import FundingRate, Market, OpenInterest, OrderBookSummary, SymbolInfo, TakerRatio, Ticker24h, Candle
from .parsers import (
    parse_depth, parse_exchange_info, parse_funding_rates, parse_kline_row, parse_open_interest,
    parse_taker_ratio, parse_tickers,
)
from .rate_limiter import WeightLimiter

try:  # httpx yalnızca gerçek ağ çağrılarında gerekir
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

log = logging.getLogger(__name__)
TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (OSError, asyncio.TimeoutError) + ((httpx.TransportError,) if httpx else ())


class BinanceAPIError(Exception):
    def __init__(self, status: int | None, message: str, code: int | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code

    def __str__(self) -> str:
        return f"[HTTP {self.status}] {self.message}" if self.status else self.message


class BinanceRestClient:
    def __init__(self, market: Market, base_url: str, http: Any = None, limiter: WeightLimiter | None = None,
                 max_retries: int = 3, timeout: float = 10.0, sleep=asyncio.sleep, clock_ms=lambda: int(time.time() * 1000)):
        self.market = market
        self.base_url = base_url.rstrip("/")
        self._http = http
        self._owns_http = http is None
        # Konservatif bütçe: Spot 1200/dk, Futures 2400/dk limitinin yaklaşık yarısı
        self.limiter = limiter or WeightLimiter(600 if market == Market.SPOT else 1200)
        self.max_retries = max_retries
        self.timeout = timeout
        self._sleep = sleep
        self._clock_ms = clock_ms
        self._prefix = "/api/v3" if market == Market.SPOT else "/fapi/v1"

    async def start(self) -> None:
        if self._http is None:
            if httpx is None:
                raise RuntimeError("httpx kurulu değil: pip install -r requirements.txt")
            self._http = httpx.AsyncClient()

    async def close(self) -> None:
        if self._http is not None and self._owns_http and hasattr(self._http, "aclose"):
            await self._http.aclose()
        self._http = None

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(30.0, 1.0 * 2 ** attempt)

    async def _get(self, path: str, params: dict | None = None, weight: int = 1) -> Any:
        if self._http is None:
            await self.start()
        url = self.base_url + path
        for attempt in range(self.max_retries + 1):
            last = attempt == self.max_retries
            await self.limiter.acquire(weight)
            try:
                resp = await self._http.get(url, params=params, timeout=self.timeout)
            except TRANSPORT_ERRORS as e:
                if last:
                    raise BinanceAPIError(None, f"Ağ hatası ({type(e).__name__}); Binance'e ulaşılamadı") from e
                await self._sleep(self._backoff(attempt))
                continue
            status = resp.status_code
            if status == 200:
                try:
                    return resp.json()
                except ValueError:
                    raise BinanceAPIError(status, "Binance geçersiz JSON döndürdü") from None
            if status in (451, 403):
                raise BinanceAPIError(status, "Binance bu sunucu/konumdan erişimi engelliyor (bölge kısıtlaması). Farklı bir bölge veya yerel bilgisayar deneyin.")
            if status == 418:
                raise BinanceAPIError(status, "IP adresi Binance tarafından geçici olarak engellendi (aşırı istek). Bir süre bekleyin.")
            if status == 429 or status >= 500:
                if last:
                    raise BinanceAPIError(status, "Binance istek limiti veya sunucu hatası; yeniden denemeler tükendi")
                try:
                    wait = min(60.0, float(resp.headers.get("Retry-After", ""))) if resp.headers.get("Retry-After") else self._backoff(attempt)
                except ValueError:
                    wait = self._backoff(attempt)
                log.warning("Binance HTTP %s, %.1fs sonra yeniden denenecek", status, wait)
                await self._sleep(wait)
                continue
            msg, code = "Beklenmeyen yanıt", None
            try:
                body = resp.json()
                msg, code = str(body.get("msg", msg)), body.get("code")
            except Exception:
                pass
            raise BinanceAPIError(status, msg, code)
        raise BinanceAPIError(None, "Bilinmeyen hata")  # pragma: no cover

    async def exchange_info(self) -> list[SymbolInfo]:
        return parse_exchange_info(await self._get(f"{self._prefix}/exchangeInfo", weight=20), self.market)

    async def tickers_24h(self) -> list[Ticker24h]:
        return parse_tickers(await self._get(f"{self._prefix}/ticker/24hr", weight=80), self.market)

    async def klines(self, symbol: str, interval: str, limit: int = 500, start_time: int | None = None, end_time: int | None = None) -> list[Candle]:
        limit = max(1, min(limit, 1000))
        params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        weight = 2 if limit <= 100 else 5 if limit < 500 else 10
        rows = await self._get(f"{self._prefix}/klines", params, weight=weight)
        if not isinstance(rows, list):
            from .parsers import DataError
            raise DataError("klines yanıtı liste değil")
        now = self._clock_ms()
        return [parse_kline_row(r, self.market, symbol, interval, now) for r in rows]

    async def depth(self, symbol: str, limit: int = 100) -> OrderBookSummary:
        data = await self._get(f"{self._prefix}/depth", {"symbol": symbol, "limit": limit}, weight=5)
        return parse_depth(data, self.market, symbol)

    # ---- yalnızca Futures ----
    def _require_futures(self) -> None:
        if self.market != Market.FUTURES:
            raise ValueError("Bu uç nokta yalnızca Futures için geçerli")

    async def open_interest(self, symbol: str) -> OpenInterest:
        self._require_futures()
        return parse_open_interest(await self._get("/fapi/v1/openInterest", {"symbol": symbol}, weight=2))

    async def funding_rates(self, symbol: str, limit: int = 10) -> list[FundingRate]:
        self._require_futures()
        return parse_funding_rates(await self._get("/fapi/v1/fundingRate", {"symbol": symbol, "limit": limit}, weight=2))

    async def taker_long_short_ratio(self, symbol: str, period: str = "5m", limit: int = 30) -> list[TakerRatio]:
        self._require_futures()
        data = await self._get("/futures/data/takerlongshortRatio", {"symbol": symbol, "period": period, "limit": limit}, weight=2)
        return parse_taker_ratio(data, symbol)
