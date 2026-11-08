"""Aşama 3 analiz orkestratörü: kapalı mumlar -> göstergeler -> stratejiler -> risk -> skor."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.collectors.models import INTERVAL_MS, Candle, FundingRate, Market, OrderBookSummary, SymbolInfo, Ticker24h
from app.indicators.snapshot import IndicatorSnapshot, compute_snapshot
from app.risk.filters import RiskAssessment, RiskConfig, assess_risk
from app.scoring.opportunity import OpportunityScore, calculate_score
from app.services.market_regime import MarketRegime, classify_market_regime
from app.strategies.breakout import consolidation_breakout
from app.strategies.models import StrategyResult
from app.strategies.momentum import momentum_continuation
from app.strategies.order_flow import OrderFlowAnalysis, analyze_order_flow
from app.strategies.relative_strength import relative_strength
from app.strategies.reversal import oversold_reversal
from app.strategies.volume import VolumeMetrics, analyze_volume, volume_explosion


@dataclass
class CoinAnalysis:
    market: str
    symbol: str
    generated_at: str
    as_of_close_time: int | None
    price: float | None
    snapshots: dict[str, IndicatorSnapshot]
    volume: VolumeMetrics | None
    order_flow: OrderFlowAnalysis | None
    strategies: list[StrategyResult]
    regime: MarketRegime
    risk: RiskAssessment
    score: OpportunityScore
    mtf_agreement: float
    signal_valid_until_ms: int | None
    invalidation: list[str] = field(default_factory=list)
    scenario: dict[str, float | str | None] = field(default_factory=dict)
    ai_status: str = "insufficient_training_data"
    ai_probabilities: dict | None = None
    historical_similarity: dict | None = None
    futures_context: dict | None = None
    market_comparison: dict | None = None
    btc_correlation_15m: float | None = None

    def to_dict(self) -> dict:
        return {
            "market": self.market, "symbol": self.symbol, "generated_at": self.generated_at,
            "as_of_close_time": self.as_of_close_time, "price": self.price,
            "snapshots": {k: v.to_dict() for k, v in self.snapshots.items()},
            "volume": self.volume.to_dict() if self.volume else None,
            "order_flow": self.order_flow.to_dict() if self.order_flow else None,
            "strategies": [s.to_dict() for s in self.strategies], "regime": self.regime.to_dict(),
            "risk": self.risk.to_dict(), "score": self.score.to_dict(), "mtf_agreement": self.mtf_agreement,
            "signal_valid_until_ms": self.signal_valid_until_ms, "invalidation": self.invalidation,
            "scenario": self.scenario, "ai_status": self.ai_status, "ai_probabilities": self.ai_probabilities,
            "historical_similarity": self.historical_similarity, "futures_context": self.futures_context,
            "market_comparison": self.market_comparison, "btc_correlation_15m": self.btc_correlation_15m,
        }


def _closed(candles: list[Candle] | None, market: Market, symbol: str, interval: str) -> list[Candle]:
    return sorted((c for c in candles or [] if c.is_closed and c.market == market and c.symbol == symbol and c.interval == interval),
                  key=lambda c: c.open_time)


class AnalysisEngine:
    def __init__(self, risk_config: RiskConfig = RiskConfig()):
        self.risk_config = risk_config

    def regime(self, btc_candles: dict[str, list[Candle]], market: Market = Market.SPOT) -> MarketRegime:
        snapshots = {}
        for interval in ("15m", "1h", "4h", "1d"):
            rows = _closed(btc_candles.get(interval), market, "BTCUSDT", interval)
            if len(rows) >= 30:
                snapshots[interval] = compute_snapshot(rows, INTERVAL_MS[interval])
        return classify_market_regime(snapshots)

    def analyze(self, market: Market, symbol: str, candles: dict[str, list[Candle]], ticker: Ticker24h | None,
                orderbook: OrderBookSummary | None = None, funding: FundingRate | None = None,
                symbol_info: SymbolInfo | None = None, btc_candles: dict[str, list[Candle]] | None = None,
                eth_candles: dict[str, list[Candle]] | None = None,
                spot_futures_price_diff_pct: float | None = None, now_ms: int | None = None,
                historical_similarity_score: float | None = None) -> CoinAnalysis:
        rows = {interval: _closed(candles.get(interval), market, symbol, interval) for interval in INTERVAL_MS}
        snapshots = {i: compute_snapshot(v, INTERVAL_MS[i]) for i, v in rows.items() if len(v) >= 30}
        regime = self.regime(btc_candles or rows if symbol == "BTCUSDT" else btc_candles or {}, market)
        primary = rows["15m"]
        volume = analyze_volume(primary) if primary else None
        risk = assess_risk(market, symbol, ticker, snapshots, volume, orderbook, funding, symbol_info,
                           now_ms, spot_futures_price_diff_pct,
                           has_recent_gaps=self._has_gaps(primary), last_close_time_ms=primary[-1].close_time if primary else None,
                           config=self.risk_config)
        generated = datetime.now(timezone.utc).isoformat()
        if not primary or "15m" not in snapshots or volume is None:
            empty_regime = regime
            score = OpportunityScore(0, "unsuitable", False, [], 0, "insufficient_training_data")
            return CoinAnalysis(market.value, symbol, generated, primary[-1].close_time if primary else None,
                                primary[-1].close if primary else ticker.last_price if ticker else None,
                                snapshots, volume, None, [], empty_regime, risk, score, 0, None,
                                invalidation=["Yeterli kapanmış mum verisi olmadan senaryo üretilmez"])
        order_flow = analyze_order_flow(orderbook, volume)
        higher_trends = {i: snapshots[i].trend for i in ("1h", "4h", "1d") if i in snapshots}
        strategies = [
            volume_explosion(volume, self.risk_config.__dict__.get("volume_explosion_ratio", 2.5)),
            consolidation_breakout(primary, snapshots["15m"], volume),
            relative_strength(symbol, primary, _closed((btc_candles or {}).get("15m"), market, "BTCUSDT", "15m"),
                              _closed((eth_candles or {}).get("15m"), market, "ETHUSDT", "15m")),
            oversold_reversal(primary, snapshots["15m"], volume),
            momentum_continuation(snapshots["15m"], volume, higher_trends),
        ]
        mtf = self._mtf_agreement(snapshots)
        score = calculate_score(strategies, volume, order_flow, regime, risk, mtf, historical_similarity_score)
        snap = snapshots["15m"]
        atr = snap.atr or snap.close * 0.01
        stop = max(snap.support or snap.close - 2 * atr, snap.close - 2 * atr)
        target = snap.close + 3 * (snap.close - stop)
        valid_until = primary[-1].close_time + 4 * INTERVAL_MS["15m"] + 1
        invalidation = [f"15m kapanışın {stop:.8g} altına inmesi",
                        "Hacim oranının 1'in altına düşmesi veya aktif satıcı baskısının artması"]
        if snapshots.get("4h") and snapshots["4h"].trend == "bearish":
            invalidation.append("4h trendi aşağı; sinyal yalnızca zayıf/izleme adayı olarak değerlendirilmeli")
        triggered = [s for s in strategies if s.triggered]
        if not triggered:
            invalidation.append("Henüz tetiklenmiş strateji yok; giriş senaryosu sinyal değildir")
        return CoinAnalysis(market.value, symbol, generated, primary[-1].close_time, snap.close, snapshots, volume,
                            order_flow, strategies, regime, risk, score, mtf, valid_until, invalidation,
                            {"type": "analysis_only", "reference_price": snap.close,
                             "invalidation_stop": round(stop, 10), "target_3r": round(target, 10),
                             "note": "Yalnız analiz senaryosudur; otomatik emir/yatırım tavsiyesi değildir. Komisyon/slippage bu seviyelere dahil değildir."})

    @staticmethod
    def _has_gaps(primary: list[Candle]) -> bool:
        if len(primary) < 2:
            return False
        step = INTERVAL_MS["15m"]
        return any(b.open_time - a.open_time != step for a, b in zip(primary, primary[1:]))

    @staticmethod
    def _mtf_agreement(snapshots: dict[str, IndicatorSnapshot]) -> float:
        weights = {"15m": 0.20, "1h": 0.25, "4h": 0.35, "1d": 0.20}
        available = [(weights[i], s.trend) for i, s in snapshots.items() if i in weights and s.trend != "unknown"]
        if not available:
            return 0.0
        total = sum(w for w, _ in available)
        primary_trend = snapshots["15m"].trend if "15m" in snapshots else "neutral"
        aligned = sum(w for w, trend in available if trend == primary_trend and trend == "bullish")
        partial = sum(w * 0.35 for w, trend in available if trend == "neutral")
        return (aligned + partial) / total


def risk_config_from_settings(settings, live: bool = True) -> RiskConfig:
    return RiskConfig(min_quote_volume_24h=settings.min_quote_volume_24h, max_spread_pct=settings.max_spread_pct,
                      min_orderbook_depth_quote=settings.min_orderbook_depth_quote,
                      max_atr_pct=settings.max_atr_pct, extreme_funding_rate=settings.extreme_funding_rate,
                      critical_funding_rate=settings.critical_funding_rate,
                      min_listing_age_days=settings.min_listing_age_days,
                      max_spot_futures_price_diff_pct=settings.max_spot_futures_price_diff_pct,
                      volume_explosion_ratio=settings.volume_explosion_ratio,
                      require_orderbook=live, require_funding=live)
