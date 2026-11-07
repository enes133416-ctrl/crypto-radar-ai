"""Uygulama ayarları (yalnızca standart kütüphane; ek bağımlılık gerektirmez)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Crypto Radar AI"
    app_version: str = "0.1.0"
    # Çalışma modu: "local" (tam scanner) veya "cloud" (sınırlı tarama)
    run_mode: str = "local"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    database_url: str = "sqlite:///./data/crypto_radar.db"
    # Binance herkese açık piyasa verileri API anahtarı GEREKTİRMEZ.
    binance_spot_rest: str = "https://api.binance.com"
    binance_futures_rest: str = "https://fapi.binance.com"
    binance_spot_ws: str = "wss://stream.binance.com:9443"
    binance_futures_ws: str = "wss://fstream.binance.com"
    # Risk / filtre eşikleri (Aşama 3'te kullanılacak)
    min_quote_volume_24h: float = 5_000_000.0
    max_spread_pct: float = 0.30
    demo_mode: bool = False
    log_level: str = "INFO"


def load_settings(env: dict[str, str] | None = None) -> Settings:
    e = os.environ if env is None else env
    d = Settings()
    return Settings(
        run_mode=e.get("RUN_MODE", d.run_mode),
        cors_origins=tuple(_list(e.get("CORS_ORIGINS"), list(d.cors_origins))),
        database_url=e.get("DATABASE_URL", d.database_url),
        binance_spot_rest=e.get("BINANCE_SPOT_REST", d.binance_spot_rest),
        binance_futures_rest=e.get("BINANCE_FUTURES_REST", d.binance_futures_rest),
        binance_spot_ws=e.get("BINANCE_SPOT_WS", d.binance_spot_ws),
        binance_futures_ws=e.get("BINANCE_FUTURES_WS", d.binance_futures_ws),
        min_quote_volume_24h=float(e.get("MIN_QUOTE_VOLUME_24H", d.min_quote_volume_24h)),
        max_spread_pct=float(e.get("MAX_SPREAD_PCT", d.max_spread_pct)),
        demo_mode=_bool(e.get("DEMO_MODE"), d.demo_mode),
        log_level=e.get("LOG_LEVEL", d.log_level).upper(),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
