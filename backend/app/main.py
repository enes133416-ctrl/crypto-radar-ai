"""FastAPI giriş noktası. Çalıştırma: backend/ klasöründe `uvicorn app.main:app --reload`"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "run_mode": settings.run_mode,
        "demo_mode": settings.demo_mode,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
