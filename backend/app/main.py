"""Crypto Radar AI FastAPI giriş noktası.

Çalıştırma: backend/ klasöründe ``uvicorn app.main:app --host 0.0.0.0 --port 8000``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.market import router as market_router
from app.config import get_settings
from app.database.sqlite import Database
from app.services.analysis_service import AnalysisService
from app.services.market_data import build_market_data_service
from app.services.scanner import ScannerService
from app.services.signal_tracker import SignalTracker

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database(settings.database_url)
    app.state.database = db
    app.state.market_data = None
    app.state.analysis_service = None
    app.state.scanner = None
    tasks: list[asyncio.Task] = []
    svc = None
    scanner = None
    if settings.collector_enabled:
        svc = build_market_data_service(settings, db)
        analysis = AnalysisService(settings, svc, db=db)
        tracker = SignalTracker(db, settings)
        scanner = ScannerService(settings, svc, analysis, tracker)
        app.state.market_data = svc
        app.state.analysis_service = analysis
        app.state.scanner = scanner
        tasks.append(asyncio.create_task(svc.run()))
        if settings.scanner_enabled:
            tasks.append(asyncio.create_task(scanner.run()))
    try:
        yield
    finally:
        if scanner:
            scanner.stop()
        for task in tasks:
            task.cancel()
        if svc:
            await svc.stop()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        db.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"],
                   allow_credentials=False)

# Basit process-içi API rate limit. Çok instance'lı production dağıtımında Redis/gateway
# limitiyle değiştirilmelidir; Binance outbound limiti ayrıca WeightLimiter'dadır.
_requests: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and settings.api_rate_limit_per_minute > 0:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = _requests[key]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= settings.api_rate_limit_per_minute:
            return JSONResponse({"detail": "API istek sınırı aşıldı; bir dakika sonra tekrar deneyin"}, 429)
        bucket.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(market_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version,
            "run_mode": settings.run_mode, "demo_mode": settings.demo_mode,
            "collector_enabled": settings.collector_enabled, "scanner_enabled": settings.scanner_enabled,
            "server_time": datetime.now(timezone.utc).isoformat()}


@app.get("/api")
async def api_info() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs",
            "live_data": settings.collector_enabled, "demo_mode": settings.demo_mode}


# Production'da tek servis istenirse frontend/dist (veya image içindeki static) SPA olarak sunulur.
_static_candidates = [Path(__file__).resolve().parents[1] / "static",
                      Path(__file__).resolve().parents[2] / "frontend" / "dist"]
_static = next((p for p in _static_candidates if (p / "index.html").exists()), None)
if _static:
    assets = _static / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = (_static / path).resolve()
        if path and candidate.is_file() and _static.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
