"""FastAPI giriş noktası. Çalıştırma: backend/ klasöründe `uvicorn app.main:app --reload`"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.market import router as market_router
from app.config import get_settings
from app.services.market_data import build_market_data_service

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    svc, task = None, None
    if settings.collector_enabled:
        svc = build_market_data_service(settings)
        task = asyncio.create_task(svc.run())
    app.state.market_data = svc
    yield
    if svc is not None:
        await svc.stop()
        task.cancel()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET"], allow_headers=["*"])
app.include_router(market_router)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "run_mode": settings.run_mode,
        "demo_mode": settings.demo_mode,
        "collector_enabled": settings.collector_enabled,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
