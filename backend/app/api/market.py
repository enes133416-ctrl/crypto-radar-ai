"""Canlı piyasa, analiz, tarayıcı ve performans API'leri."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request

from app.backtesting.performance import performance_report
from app.collectors.models import SUPPORTED_INTERVALS, Candle, Market
from app.config import get_settings
from app.services.analysis_service import AnalysisService
from app.strategies.models import StrategyName

router = APIRouter(prefix="/api")


def _service(request: Request):
    svc = getattr(request.app.state, "market_data", None)
    if svc is None:
        raise HTTPException(503, "Veri toplayıcı kapalı veya henüz başlatılmadı.")
    return svc


def _analysis(request: Request) -> AnalysisService:
    svc = _service(request)
    existing = getattr(request.app.state, "analysis_service", None)
    if existing and existing.market_data is svc:
        return existing
    return AnalysisService(svc.settings, svc, db=getattr(request.app.state, "database", None))


def _market(value: str) -> Market:
    try:
        return Market(value.lower())
    except ValueError:
        raise HTTPException(400, "market 'spot' veya 'futures' olmalı") from None


def _optional_market(value: str) -> Market | None:
    return None if value.lower() == "all" else _market(value)


def _candle(c: Candle) -> dict:
    data = asdict(c)
    data["market"] = c.market.value
    return data


@router.get("/data-status")
async def data_status(request: Request) -> dict:
    svc = getattr(request.app.state, "market_data", None)
    scanner = getattr(request.app.state, "scanner", None)
    result = {"enabled": False} if svc is None else svc.status()
    result["scanner"] = None if scanner is None else {"last_scan": scanner.last_scan, "errors": scanner.errors}
    return result


@router.get("/symbols")
async def symbols(request: Request, market: str = Query("spot")) -> dict:
    svc, selected = _service(request), _market(market)
    tickers = svc.tickers.get(selected, {})
    items = [{"symbol": s.symbol, "base": s.base_asset,
              "last_price": tickers[s.symbol].last_price if s.symbol in tickers else None,
              "price_change_24h_pct": tickers[s.symbol].price_change_pct if s.symbol in tickers else None,
              "quote_volume_24h": tickers[s.symbol].quote_volume if s.symbol in tickers else None}
             for s in svc.universe.get(selected, [])]
    return {"market": selected.value, "count": len(items), "symbols": items}


@router.get("/klines/{market}/{symbol}")
async def klines(request: Request, market: str, symbol: str, interval: str = "15m",
                 limit: int = Query(200, ge=1, le=1000)) -> dict:
    svc, selected = _service(request), _market(market)
    if interval not in SUPPORTED_INTERVALS:
        raise HTTPException(400, f"Desteklenen zaman dilimleri: {', '.join(SUPPORTED_INTERVALS)}")
    sym = symbol.upper()
    closed = svc.store.closed(selected, sym, interval, limit)
    if not closed:
        raise HTTPException(404, f"{selected.value}:{sym}:{interval} için henüz veri yok")
    open_c = svc.store.open_candle(selected, sym, interval)
    return {"market": selected.value, "symbol": sym, "interval": interval,
            "closed": [_candle(c) for c in closed], "open_candle": _candle(open_c) if open_c else None}


@router.get("/market-regime")
async def market_regime(request: Request, market: str = Query("spot")) -> dict:
    return _analysis(request).market_regime(_market(market))


@router.get("/analysis/{market}/{symbol}")
async def analyze_symbol(request: Request, market: str, symbol: str, fetch_orderbook: bool = True) -> dict:
    svc, selected = _service(request), _market(market)
    sym = symbol.upper()
    if sym not in {s.symbol for s in svc.universe.get(selected, [])}:
        raise HTTPException(404, f"{selected.value}:{sym} taranan evrende yok")
    result = await _analysis(request).analyze_symbol(selected, sym, fetch_orderbook)
    return result.to_dict()


@router.get("/scan")
async def scan(request: Request, market: str = Query("spot"), min_score: float = Query(0, ge=0, le=100),
               eligible_only: bool = True, limit: int = Query(100, ge=1, le=200),
               strategy: str | None = None, new_only: bool = False,
               risk: str | None = Query(None, pattern="^(low|medium|high)$"),
               min_ai_up10: float | None = Query(None, ge=0, le=100),
               early_only: bool = False, breakout_only: bool = False) -> dict:
    selected = _optional_market(market)
    if strategy:
        try:
            StrategyName(strategy)
        except ValueError:
            raise HTTPException(400, "Geçersiz strateji") from None
    scanner = getattr(request.app.state, "scanner", None)
    if scanner:
        return scanner.query(selected, min_score, eligible_only, strategy, new_only,
                             risk, min_ai_up10, early_only, breakout_only, limit)
    # Birim testleri ve collector-only çalışma için gerçek, fakat derinliği doğrulanmamış önizleme.
    if selected is None:
        raise HTTPException(400, "Scanner kapalıyken market=all desteklenmez")
    if any((strategy, new_only, risk, min_ai_up10, early_only, breakout_only)):
        raise HTTPException(503, "Gelişmiş tarama filtreleri için arka plan scanner gerekli")
    return _analysis(request).scan(selected, min_score, eligible_only, limit)


@router.post("/scan/refresh/{market}")
async def refresh_scan(request: Request, market: str) -> dict:
    scanner = getattr(request.app.state, "scanner", None)
    if scanner is None:
        raise HTTPException(503, "Arka plan scanner kapalı")
    selected = _market(market)
    await scanner.refresh_market(selected)
    return scanner.query(selected, eligible_only=False)


@router.get("/dashboard")
async def dashboard(request: Request) -> dict:
    scanner = getattr(request.app.state, "scanner", None)
    if scanner is None:
        raise HTTPException(503, "Dashboard için arka plan scanner gerekli")
    return scanner.dashboard()


@router.get("/early-signals")
async def early_signals(request: Request, market: str = "all", min_score: float = Query(50, ge=0, le=100)) -> dict:
    return await scan(request, market, min_score, True, 200, early_only=True)


@router.get("/breakouts")
async def breakouts(request: Request, market: str = "all", min_score: float = Query(0, ge=0, le=100)) -> dict:
    return await scan(request, market, min_score, True, 200, breakout_only=True)


@router.get("/predictions")
async def predictions(request: Request, market: str = "all", min_probability: float = Query(0, ge=0, le=100)) -> dict:
    result = await scan(request, market, 0, True, 200)
    if min_probability:
        result["items"] = [item for item in result["items"]
                           if (((item.get("ai_probabilities") or {}).get("horizons") or {})
                               .get("72", {}).get("up10", 0) * 100 >= min_probability)]
        result["count"] = len(result["items"])
        result["total_matching"] = len(result["items"])
    return result


@router.get("/signals")
async def signals(request: Request, market: str = "all", status: str | None = None,
                  limit: int = Query(100, ge=1, le=1000)) -> dict:
    db = getattr(request.app.state, "database", None)
    if db is None:
        return {"count": 0, "items": []}
    selected = _optional_market(market)
    rows = db.signals(status=status, market=selected.value if selected else None, limit=limit)
    # Liste yanıtında büyük analiz JSON'unu taşıma; coin detayı ayrı canlı uçtan alınır.
    for row in rows:
        row.pop("analysis", None)
    return {"count": len(rows), "items": rows}


@router.get("/performance")
async def performance(request: Request, market: str = "all", horizon: int = Query(72, ge=24, le=72)) -> dict:
    if horizon not in (24, 48, 72):
        raise HTTPException(400, "horizon 24, 48 veya 72 olmalı")
    db = getattr(request.app.state, "database", None)
    selected = _optional_market(market)
    rows = db.signals(market=selected.value if selected else None, limit=100_000) if db else []
    return performance_report(rows, horizon)


@router.get("/backtest")
async def backtest(request: Request, market: str = "all", horizon: int = Query(72, ge=24, le=72)) -> dict:
    """Arşivlenmiş gerçek sinyallerin ileriye dönük testi; tarihsel replay scripti ayrıdır."""
    result = await performance(request, market, horizon)
    result["test_type"] = "archived_signal_forward_evaluation"
    result["historical_replay_command"] = "PYTHONPATH=. python ../scripts/backtest.py --symbol BTCUSDT --market spot"
    return result


@router.get("/settings")
async def public_settings() -> dict:
    return {"settings": get_settings().public_dict(),
            "editable_note": "Eşikler sunucuda .env ile yapılandırılır ve restart ile uygulanır; frontend API anahtarı veya sır saklamaz."}
