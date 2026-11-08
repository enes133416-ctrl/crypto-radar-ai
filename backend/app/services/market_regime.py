"""BTC çoklu zaman dilimi ve volatiliteye dayalı genel piyasa rejimi."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from app.indicators.snapshot import IndicatorSnapshot


class Regime(str, Enum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    RISK_OFF = "high_volatility_risk_off"
    UNKNOWN = "unknown"


@dataclass
class MarketRegime:
    regime: Regime
    score: float | None
    confidence: float
    interval_scores: dict[str, float | None]
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["regime"] = self.regime.value
        return out


def _trend_score(snap: IndicatorSnapshot) -> float | None:
    if snap.ema21 is None or snap.ema50 is None or snap.rsi14 is None:
        return None
    score = 50.0
    score += 15 if snap.close > snap.ema21 else -15
    score += 15 if snap.ema21 > snap.ema50 else -15
    if snap.macd_histogram is not None:
        score += 10 if snap.macd_histogram > 0 else -10
    score += max(-10.0, min(10.0, (snap.rsi14 - 50) / 2))
    return max(0.0, min(100.0, score))


def classify_market_regime(snapshots: dict[str, IndicatorSnapshot], high_atr_pct: float = 6.0) -> MarketRegime:
    weights = {"15m": 0.15, "1h": 0.25, "4h": 0.35, "1d": 0.25}
    scores = {interval: _trend_score(snapshots[interval]) if interval in snapshots else None for interval in weights}
    available = [(weights[i], value) for i, value in scores.items() if value is not None]
    if not available:
        return MarketRegime(Regime.UNKNOWN, None, 0.0, scores, risks=["BTC kapanmış mum geçmişi yetersiz"])
    total_weight = sum(weight for weight, _ in available)
    score = sum(weight * value for weight, value in available if value is not None) / total_weight
    confidence = total_weight
    result = MarketRegime(Regime.NEUTRAL, round(score, 2), round(confidence, 2), scores)
    for interval, value in scores.items():
        if value is not None:
            result.reasons.append(f"BTC {interval} trend puanı {value:.1f}/100")
    atr_4h = snapshots.get("4h").atr_pct if snapshots.get("4h") else None
    atr_1d = snapshots.get("1d").atr_pct if snapshots.get("1d") else None
    high_volatility = (atr_4h is not None and atr_4h >= high_atr_pct) or (atr_1d is not None and atr_1d >= high_atr_pct)
    if high_volatility or score < 20:
        result.regime = Regime.RISK_OFF
        result.risks.append("BTC volatilitesi yüksek veya trend puanı kritik; altcoin riski artırıldı")
    elif score >= 80:
        result.regime = Regime.STRONG_BULLISH
    elif score >= 60:
        result.regime = Regime.BULLISH
    elif score >= 40:
        result.regime = Regime.NEUTRAL
    else:
        result.regime = Regime.BEARISH
        result.risks.append("BTC üst zaman dilimlerinde zayıf; altcoin long sinyalleri daha riskli")
    missing = [i for i, value in scores.items() if value is None]
    if missing:
        result.risks.append(f"BTC zaman dilimi verisi eksik: {', '.join(missing)}")
    return result


def regime_score(regime: MarketRegime) -> float:
    """Skor motoru için 0-100 karşılığı. UNKNOWN nötr değil düşük güvenle 40'tır."""
    return {Regime.STRONG_BULLISH: 100, Regime.BULLISH: 80, Regime.NEUTRAL: 55,
            Regime.BEARISH: 25, Regime.RISK_OFF: 0, Regime.UNKNOWN: 40}[regime.regime]
