"""Merkezi uygulama ayarları.

Yerel çalışmada kök ``.env`` otomatik okunur. Testlerde ``load_settings({})`` çağrısı
ortamdan tamamen izole, varsayılan ayarları üretir.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from app.collectors.models import SUPPORTED_INTERVALS


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Geçersiz boolean ayar: {value!r}")


def _list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Crypto Radar AI"
    app_version: str = "1.0.0"
    run_mode: str = "local"  # local: tam tarama, cloud: sınırlı evren/arama
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    database_url: str = "sqlite:///./data/crypto_radar.db"
    binance_spot_rest: str = "https://api.binance.com"
    binance_futures_rest: str = "https://fapi.binance.com"
    binance_spot_ws: str = "wss://stream.binance.com:9443"
    binance_futures_ws: str = "wss://fstream.binance.com"

    min_quote_volume_24h: float = 5_000_000.0
    max_spread_pct: float = 0.30
    min_orderbook_depth_quote: float = 50_000.0
    max_atr_pct: float = 12.0
    extreme_funding_rate: float = 0.001
    critical_funding_rate: float = 0.003
    min_listing_age_days: int = 30
    max_spot_futures_price_diff_pct: float = 2.0
    volume_explosion_ratio: float = 2.5
    signal_min_score: float = 50.0
    signal_cooldown_hours: int = 4

    demo_mode: bool = False
    log_level: str = "INFO"
    collector_enabled: bool = True
    scanner_enabled: bool = True
    max_symbols_per_market: int = 60
    tracked_intervals: tuple[str, ...] = ("5m", "15m", "1h", "4h", "1d")
    backfill_limit: int = 300
    scan_interval_seconds: int = 300
    discovery_interval_seconds: int = 900
    outcome_interval_seconds: int = 900
    scan_orderbook_concurrency: int = 6

    model_path: str = "./data/models/opportunity_models.joblib"
    ml_min_samples: int = 200
    round_trip_cost_pct: float = 0.15
    api_rate_limit_per_minute: int = 240

    def public_dict(self) -> dict:
        """Gizli bilgi içermeyen, frontendde gösterilebilir çalışma ayarları."""
        result = asdict(self)
        result["cors_origins"] = list(self.cors_origins)
        result["tracked_intervals"] = list(self.tracked_intervals)
        # URL'ler sır değildir; veritabanı/model dosya yollarını dışarı açmıyoruz.
        result.pop("database_url", None)
        result.pop("model_path", None)
        return result


def _load_dotenv_files() -> None:
    root = Path(__file__).resolve().parents[3] / ".env"
    local = Path.cwd() / ".env"
    # override=False: servis sağlayıcısının gerçek ortam değişkenleri her zaman önceliklidir.
    load_dotenv(root, override=False)
    if local != root:
        load_dotenv(local, override=False)


def load_settings(env: dict[str, str] | None = None) -> Settings:
    if env is None:
        _load_dotenv_files()
        e = os.environ
    else:
        e = env
    d = Settings()
    settings = Settings(
        run_mode=e.get("RUN_MODE", d.run_mode).lower(),
        cors_origins=tuple(_list(e.get("CORS_ORIGINS"), list(d.cors_origins))),
        database_url=e.get("DATABASE_URL", d.database_url),
        binance_spot_rest=e.get("BINANCE_SPOT_REST", d.binance_spot_rest),
        binance_futures_rest=e.get("BINANCE_FUTURES_REST", d.binance_futures_rest),
        binance_spot_ws=e.get("BINANCE_SPOT_WS", d.binance_spot_ws),
        binance_futures_ws=e.get("BINANCE_FUTURES_WS", d.binance_futures_ws),
        min_quote_volume_24h=float(e.get("MIN_QUOTE_VOLUME_24H", d.min_quote_volume_24h)),
        max_spread_pct=float(e.get("MAX_SPREAD_PCT", d.max_spread_pct)),
        min_orderbook_depth_quote=float(e.get("MIN_ORDERBOOK_DEPTH_QUOTE", d.min_orderbook_depth_quote)),
        max_atr_pct=float(e.get("MAX_ATR_PCT", d.max_atr_pct)),
        extreme_funding_rate=float(e.get("EXTREME_FUNDING_RATE", d.extreme_funding_rate)),
        critical_funding_rate=float(e.get("CRITICAL_FUNDING_RATE", d.critical_funding_rate)),
        min_listing_age_days=int(e.get("MIN_LISTING_AGE_DAYS", d.min_listing_age_days)),
        max_spot_futures_price_diff_pct=float(e.get("MAX_SPOT_FUTURES_PRICE_DIFF_PCT", d.max_spot_futures_price_diff_pct)),
        volume_explosion_ratio=float(e.get("VOLUME_EXPLOSION_RATIO", d.volume_explosion_ratio)),
        signal_min_score=float(e.get("SIGNAL_MIN_SCORE", d.signal_min_score)),
        signal_cooldown_hours=int(e.get("SIGNAL_COOLDOWN_HOURS", d.signal_cooldown_hours)),
        demo_mode=_bool(e.get("DEMO_MODE"), d.demo_mode),
        log_level=e.get("LOG_LEVEL", d.log_level).upper(),
        collector_enabled=_bool(e.get("COLLECTOR_ENABLED"), d.collector_enabled),
        scanner_enabled=_bool(e.get("SCANNER_ENABLED"), d.scanner_enabled),
        max_symbols_per_market=int(e.get("MAX_SYMBOLS_PER_MARKET", d.max_symbols_per_market)),
        tracked_intervals=tuple(_list(e.get("TRACKED_INTERVALS"), list(d.tracked_intervals))),
        backfill_limit=int(e.get("BACKFILL_LIMIT", d.backfill_limit)),
        scan_interval_seconds=int(e.get("SCAN_INTERVAL_SECONDS", d.scan_interval_seconds)),
        discovery_interval_seconds=int(e.get("DISCOVERY_INTERVAL_SECONDS", d.discovery_interval_seconds)),
        outcome_interval_seconds=int(e.get("OUTCOME_INTERVAL_SECONDS", d.outcome_interval_seconds)),
        scan_orderbook_concurrency=int(e.get("SCAN_ORDERBOOK_CONCURRENCY", d.scan_orderbook_concurrency)),
        model_path=e.get("MODEL_PATH", d.model_path),
        ml_min_samples=int(e.get("ML_MIN_SAMPLES", d.ml_min_samples)),
        round_trip_cost_pct=float(e.get("ROUND_TRIP_COST_PCT", d.round_trip_cost_pct)),
        api_rate_limit_per_minute=int(e.get("API_RATE_LIMIT_PER_MINUTE", d.api_rate_limit_per_minute)),
    )
    validate_settings(settings)
    return settings


def validate_settings(s: Settings) -> None:
    if s.run_mode not in {"local", "cloud"}:
        raise ValueError("RUN_MODE 'local' veya 'cloud' olmalı")
    unknown = set(s.tracked_intervals) - set(SUPPORTED_INTERVALS)
    if unknown or not s.tracked_intervals:
        raise ValueError(f"Desteklenmeyen/boş TRACKED_INTERVALS: {sorted(unknown)}")
    if "15m" not in s.tracked_intervals:
        raise ValueError("Analiz motoru için TRACKED_INTERVALS içinde 15m zorunludur")
    for name in ("max_symbols_per_market", "backfill_limit", "scan_interval_seconds",
                 "discovery_interval_seconds", "outcome_interval_seconds", "scan_orderbook_concurrency",
                 "ml_min_samples", "api_rate_limit_per_minute"):
        if getattr(s, name) <= 0:
            raise ValueError(f"{name} sıfırdan büyük olmalı")
    if not 1 <= s.backfill_limit <= 1000:
        raise ValueError("BACKFILL_LIMIT 1..1000 olmalı")
    if not 0 <= s.signal_min_score <= 100:
        raise ValueError("SIGNAL_MIN_SCORE 0..100 olmalı")
    if s.max_spread_pct <= 0 or s.min_quote_volume_24h < 0 or s.min_orderbook_depth_quote < 0:
        raise ValueError("Likidite/spread ayarları geçersiz")
    if s.round_trip_cost_pct < 0:
        raise ValueError("ROUND_TRIP_COST_PCT negatif olamaz")


@lru_cache
def get_settings() -> Settings:
    return load_settings()
