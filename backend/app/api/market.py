"""Piyasa verisi uç noktaları. Veri yoksa uydurma değer döndürmez; açık hata mesajı verir."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request

from app.collectors.models import SUPPORTED_INTERVALS, Candle, Market
from app.services.analysis_service import AnalysisService

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


@router.get("/market-regime")
async def market_regime(request: Request, market: str = Query("spot")) -> dict:
    svc, m = _service(request), _market(market)
    return AnalysisService(svc.settings, svc).market_regime(m)


@router.get("/analysis/{market}/{symbol}")
async def analyze_symbol(request: Request, market: str, symbol: str, fetch_orderbook: bool = True) -> dict:
    svc, m = _service(request), _market(market)
    sym = symbol.upper()
    if sym not in {s.symbol for s in svc.universe.get(m, [])}:
        raise HTTPException(404, f"{m.value}:{sym} taranan evrende yok")
    result = await AnalysisService(svc.settings, svc).analyze_symbol(m, sym, fetch_orderbook)
    return result.to_dict()


@router.get("/scan")
async def scan(request: Request, market: str = Query("spot"), min_score: float = Query(0, ge=0, le=100),
               eligible_only: bool = True, limit: int = Query(100, ge=1, le=200)) -> dict:
    svc, m = _service(request), _market(market)
    return AnalysisService(svc.settings, svc).scan(m, min_score, eligible_only, limit)
