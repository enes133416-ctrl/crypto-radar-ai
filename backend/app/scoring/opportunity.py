"""Açıklanabilir 100 puanlık fırsat skoru.

Zorunlu risk filtreleri bu modülden ÖNCE çalışır. Benzerlik/AI bileşeni Aşama 5'e
kadar nötr 5/10'dur ve geçmiş başarı ölçülmüş gibi yorumlanmamalıdır.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from app.risk.filters import RiskAssessment
from app.services.market_regime import MarketRegime, regime_score
from app.strategies.models import StrategyName, StrategyResult
from app.strategies.order_flow import OrderFlowAnalysis
from app.strategies.volume import VolumeMetrics


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    points: float
    maximum: float
    explanation: str


@dataclass
class OpportunityScore:
    total: float
    label: str
    eligible: bool
    components: list[ScoreComponent]
    risk_penalty: float
    historical_similarity_status: str

    def to_dict(self) -> dict:
        return asdict(self)


def score_label(score: float) -> str:
    if score >= 85:
        return "very_strong"
    if score >= 75:
        return "strong"
    if score >= 65:
        return "watch"
    if score >= 50:
        return "weak"
    return "unsuitable"


def calculate_score(strategies: list[StrategyResult], volume: VolumeMetrics, order_flow: OrderFlowAnalysis,
                    regime: MarketRegime, risk: RiskAssessment, mtf_agreement: float,
                    historical_similarity_score: float | None = None) -> OpportunityScore:
    by_name = {s.name: s for s in strategies}
    a = by_name[StrategyName.VOLUME_EXPLOSION].score
    d = by_name[StrategyName.OVERSOLD_REVERSAL].score
    e = by_name[StrategyName.MOMENTUM_CONTINUATION].score
    b = by_name[StrategyName.CONSOLIDATION_BREAKOUT].score
    volatility_base = b
    similarity_available = historical_similarity_score is not None
    similarity = max(0.0, min(100.0, historical_similarity_score)) if similarity_available else 50.0
    penalty = min(10.0, len(risk.warnings) * 1.5) if risk.eligible else 0.0
    components = [
        ScoreComponent("volume_capital_flow", round(a * 0.20, 2), 20, "Strateji A hacim oranı, z-score ve aktif alıcı akışı"),
        ScoreComponent("momentum_technical", round((0.4 * d + 0.6 * e) * 0.20, 2), 20, "RSI/MACD/EMA/ADX ve dönüş-devam stratejileri"),
        ScoreComponent("multi_timeframe", round(max(0, min(1, mtf_agreement)) * 15, 2), 15, "15m, 1h, 4h ve 1d trend uyumu"),
        ScoreComponent("volatility_structure", round(max(0, min(100, volatility_base)) * 0.10, 2), 10, "Bollinger/ATR, kırılım kalitesi ve hacim yapısı"),
        ScoreComponent("orderbook_trade_flow", round(order_flow.score * 0.15, 2), 15, "Spread, derinlik, imbalance ve taker akışı"),
        ScoreComponent("btc_market_regime", round(regime_score(regime) * 0.10, 2), 10, f"BTC rejimi: {regime.regime.value}"),
        ScoreComponent("historical_similarity", round(similarity * 0.10, 2), 10,
                       "Ölçülmüş walk-forward benzerlik skoru" if similarity_available else "Aşama 5 verisi yok; nötr 5/10, performans iddiası değil"),
    ]
    raw = sum(c.points for c in components)
    total = max(0.0, min(100.0, raw - penalty))
    return OpportunityScore(round(total, 2), score_label(total), risk.eligible, components, round(penalty, 2),
                            "available" if similarity_available else "insufficient_training_data")
