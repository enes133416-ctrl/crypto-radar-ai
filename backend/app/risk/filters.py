"""Puanlamadan önce çalışan zorunlu filtreler ve ayrı risk uyarıları."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

from app.collectors.models import INTERVAL_MS, FundingRate, Market, OrderBookSummary, SymbolInfo, Ticker24h
from app.indicators.snapshot import IndicatorSnapshot
from app.strategies.volume import VolumeMetrics

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskConfig:
    min_quote_volume_24h: float = 5_000_000.0
    max_spread_pct: float = 0.30
    min_orderbook_depth_quote: float = 50_000.0
    max_atr_pct: float = 12.0
    extreme_funding_rate: float = 0.001
    critical_funding_rate: float = 0.003
    min_listing_age_days: int = 30
    max_spot_futures_price_diff_pct: float = 2.0
    stale_intervals: int = 3
    min_primary_candles: int = 60


@dataclass(frozen=True)
class RiskFlag:
    code: str
    message: str
    severity: str  # "hard" = öne çıkarmayı engeller, "warning" = puan cezası/etiket


@dataclass
class RiskAssessment:
    eligible: bool
    flags: list[RiskFlag] = field(default_factory=list)
    data_quality_score: float = 100.0

    @property
    def hard_reasons(self) -> list[str]:
        return [f.message for f in self.flags if f.severity == "hard"]

    @property
    def warnings(self) -> list[str]:
        return [f.message for f in self.flags if f.severity == "warning"]

    def to_dict(self) -> dict:
        out = asdict(self)
        out["hard_reasons"] = self.hard_reasons
        out["warnings"] = self.warnings
        return out


def assess_risk(market: Market, symbol: str, ticker: Ticker24h | None, snapshots: dict[str, IndicatorSnapshot],
                volume: VolumeMetrics | None, orderbook: OrderBookSummary | None = None,
                funding: FundingRate | None = None, symbol_info: SymbolInfo | None = None,
                now_ms: int | None = None, spot_futures_price_diff_pct: float | None = None,
                has_recent_gaps: bool = False, last_close_time_ms: int | None = None,
                config: RiskConfig = RiskConfig()) -> RiskAssessment:
    flags: list[RiskFlag] = []

    def add(code: str, message: str, hard: bool = False) -> None:
        flags.append(RiskFlag(code, message, "hard" if hard else "warning"))
        log.info("Risk filtresi %s:%s %s (%s): %s", market.value, symbol, code, "hard" if hard else "warning", message)

    if ticker is None:
        add("TICKER_MISSING", "24 saatlik ticker verisi yok", True)
    else:
        if ticker.quote_volume < config.min_quote_volume_24h:
            add("LOW_LIQUIDITY", f"24s hacim {ticker.quote_volume:,.0f} USDT; alt sınır {config.min_quote_volume_24h:,.0f}", True)
        if abs(ticker.price_change_pct) >= 20:
            add("OVEREXTENDED_24H", f"24s değişim %{ticker.price_change_pct:.2f}; aşırı hareket/geri dönüş riski")
    primary = snapshots.get("15m")
    if primary is None or primary.candle_count < config.min_primary_candles:
        count = primary.candle_count if primary else 0
        add("INSUFFICIENT_HISTORY", f"15m kapanmış mum sayısı {count}; en az {config.min_primary_candles} gerekli", True)
    else:
        if primary.atr_pct is not None and primary.atr_pct > config.max_atr_pct:
            add("EXTREME_ATR", f"15m ATR% {primary.atr_pct:.2f}; üst sınır {config.max_atr_pct}", True)
        if now_ms is not None and last_close_time_ms is not None:
            age_ms = now_ms - last_close_time_ms
            if age_ms > config.stale_intervals * INTERVAL_MS["15m"]:
                add("STALE_DATA", f"Son kapanmış 15m mumu {age_ms / 60_000:.1f} dakika eski", True)
    for interval, minimum in (("1h", 60), ("4h", 30), ("1d", 15)):
        snap = snapshots.get(interval)
        if snap is None or snap.candle_count < minimum:
            add("MTF_DATA_MISSING", f"{interval} için en az {minimum} kapanmış mum gerekli", True)
    if has_recent_gaps:
        add("CANDLE_GAPS", "Yakın mum geçmişinde boşluk var; REST onarımı gerekli", True)
    if orderbook is None:
        add("ORDERBOOK_UNAVAILABLE", "Spread ve derinlik zorunlu kontrolleri order book olmadan doğrulanamadı")
    else:
        if orderbook.spread_pct > config.max_spread_pct:
            add("WIDE_SPREAD", f"Spread %{orderbook.spread_pct:.3f}; üst sınır %{config.max_spread_pct}", True)
        shallow = min(orderbook.bid_depth_quote, orderbook.ask_depth_quote)
        if shallow < config.min_orderbook_depth_quote:
            add("SHALLOW_ORDERBOOK", f"Zayıf taraf derinliği {shallow:,.0f} USDT; alt sınır {config.min_orderbook_depth_quote:,.0f}", True)
        if orderbook.imbalance < -0.35:
            add("SELL_SIDE_PRESSURE", f"Order book imbalance {orderbook.imbalance:.2f}; ask likiditesi baskın")
    if market == Market.FUTURES:
        if funding is None:
            add("FUNDING_UNAVAILABLE", "Futures funding verisi alınamadı")
        elif abs(funding.funding_rate) >= config.critical_funding_rate:
            add("CRITICAL_FUNDING", f"Funding oranı {funding.funding_rate:.4%}; kritik kalabalık pozisyon riski", True)
        elif abs(funding.funding_rate) >= config.extreme_funding_rate:
            add("EXTREME_FUNDING", f"Funding oranı {funding.funding_rate:.4%}; aşırı kalabalık pozisyon riski")
    if symbol_info and symbol_info.onboard_date_ms and now_ms:
        age_days = (now_ms - symbol_info.onboard_date_ms) / 86_400_000
        if age_days < config.min_listing_age_days:
            add("NEW_LISTING", f"Listeleme yaşı {age_days:.1f} gün; en az {config.min_listing_age_days} gün gerekli", True)
    if spot_futures_price_diff_pct is not None and abs(spot_futures_price_diff_pct) > config.max_spot_futures_price_diff_pct:
        add("CROSS_MARKET_MISMATCH", f"Spot/Futures fiyat farkı %{spot_futures_price_diff_pct:.2f}; veri tutarsızlığı", True)
    if volume:
        ratio = next((w.ratio for w in volume.windows.values() if w.ratio is not None), 0) or 0
        if ratio > 10 or (volume.latest_zscore or 0) > 8:
            add("UNSUSTAINABLE_VOLUME", "Hacim sıçraması olağan dışı; sürdürülebilirliği doğrulanmalı")
        if volume.taker_buy_ratio is not None and volume.taker_buy_ratio < 0.45:
            add("AGGRESSIVE_SELLING", "Aktif satıcı hacmi belirgin biçimde baskın")
    # Eksik order book/funding gibi kalite sorunları puanı düşürür; hard filtreler coin'i tamamen eler.
    quality = max(0.0, 100 - 45 * sum(f.severity == "hard" for f in flags) - 8 * sum(f.severity == "warning" for f in flags))
    return RiskAssessment(not any(f.severity == "hard" for f in flags), flags, quality)
