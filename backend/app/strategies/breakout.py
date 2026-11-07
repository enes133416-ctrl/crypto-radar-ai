"""Strateji B — daralma sonrası doğrulanmış direnç kırılımı."""
from __future__ import annotations

from app.collectors.models import Candle
from app.indicators.snapshot import IndicatorSnapshot

from .models import StrategyName, StrategyResult
from .volume import VolumeMetrics


def consolidation_breakout(candles: list[Candle], snap: IndicatorSnapshot, volume: VolumeMetrics,
                           min_volume_ratio: float = 1.3) -> StrategyResult:
    r = StrategyResult(StrategyName.CONSOLIDATION_BREAKOUT, False, 0)
    if len(candles) < 25 or snap.resistance is None or snap.bb_width_pct is None:
        r.risks.append("Kırılım analizi için en az 25 mum ve Bollinger verisi gerekli")
        return r
    current = candles[-1]
    # Direnç yalnızca önceki mumlardan hesaplandı; kırılım kontrolüne gelecek sızmaz.
    breakout = current.close > snap.resistance
    penetration = (current.close / snap.resistance - 1) * 100
    contracted = snap.bb_width_median_pct is not None and snap.bb_width_pct < snap.bb_width_median_pct
    ratio = next((w.ratio for w in (volume.windows["15m"], volume.windows["1h"], volume.windows["4h"]) if w.ratio is not None), None)
    atr = snap.atr or 0.0
    close_near_high = current.high == current.low or (current.high - current.close) / (current.high - current.low) <= 0.3
    score = 20.0
    if contracted:
        score += 20
        r.reasons.append("Bollinger bant genişliği son dönem medyanının altında; volatilite sıkışması var")
    if breakout:
        score += 35
        r.reasons.append(f"Kapanış önceki 20 mum direncinin %{penetration:.2f} üzerinde")
    if ratio is not None and ratio >= min_volume_ratio:
        score += 15
        r.reasons.append(f"Kırılım hacmi referansın {ratio:.2f} katı")
    if close_near_high and breakout:
        score += 10
        r.reasons.append("Kapanış mumun üst bölgesinde; kırılım kapanışı güçlü")
    r.score = min(100, score)
    r.triggered = breakout and ratio is not None and ratio >= min_volume_ratio and close_near_high
    r.direction = "bullish" if r.triggered else "neutral"
    r.metrics = {"breakout": breakout, "resistance": snap.resistance, "penetration_pct": penetration,
                 "bb_width_pct": snap.bb_width_pct, "bb_width_median_pct": snap.bb_width_median_pct,
                 "volume_ratio": ratio, "contracted": contracted}
    if breakout and (ratio is None or ratio < min_volume_ratio):
        r.risks.append("Direnç aşıldı ancak hacim doğrulaması yetersiz; sahte kırılım riski")
    if snap.atr_pct is not None and atr and penetration > snap.atr_pct:
        r.risks.append("Kırılım mesafesi ATR'ye göre uzamış; geri dönüş riski")
    if not contracted:
        r.risks.append("Belirgin bant sıkışması yok")
    return r
