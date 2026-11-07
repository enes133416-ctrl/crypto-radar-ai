"""Piyasa verisi uç noktaları. Veri yoksa uydurma değer döndürmez; açık hata mesajı verir."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request

from app.collectors.models import SUPPORTED_INTERVALS, Candle, Market

router = APIRouter(prefix="/api")


def _service(request: Request):
    svc = getattr(request.app.state, "market_data", None)
    if svc is None:
        raise HTTPException(503, "Veri toplayıcı kapalı (COLLECTOR_ENABLED=false).")
    return svc


def _market(value: str) -> Market:
    try:
        return Market(value.lower())
    except ValueError:
        raise HTTPException(400, "market 'spot' veya 'futures' olmalı") from None


def _candle(c: Candle) -> dict:
    d = asdict(c)
    d["market"] = c.market.value
    return d


@router.get("/data-status")
async def data_status(request: Request) -> dict:
    svc = getattr(request.app.state, "market_data", None)
    return {"enabled": False} if svc is None else svc.status()


@router.get("/symbols")
async def symbols(request: Request, market: str = Query("spot")) -> dict:
    svc, m = _service(request), _market(market)
    tickers = svc.tickers.get(m, {})
    items = [{"symbol": s.symbol, "base": s.base_asset, "quote_volume_24h": tickers[s.symbol].quote_volume if s.symbol in tickers else None}
             for s in svc.universe.get(m, [])]
    return {"market": m.value, "count": len(items), "symbols": items}


@router.get("/klines/{market}/{symbol}")
async def klines(request: Request, market: str, symbol: str, interval: str = "15m", limit: int = Query(200, ge=1, le=1000)) -> dict:
    svc, m = _service(request), _market(market)
    if interval not in SUPPORTED_INTERVALS:
        raise HTTPException(400, f"Desteklenen zaman dilimleri: {', '.join(SUPPORTED_INTERVALS)}")
    sym = symbol.upper()
    closed = svc.store.closed(m, sym, interval, limit)
    if not closed:
        raise HTTPException(404, f"{m.value}:{sym}:{interval} için henüz veri yok")
    open_c = svc.store.open_candle(m, sym, interval)
    return {"market": m.value, "symbol": sym, "interval": interval,
            "closed": [_candle(c) for c in closed], "open_candle": _candle(open_c) if open_c else None}
