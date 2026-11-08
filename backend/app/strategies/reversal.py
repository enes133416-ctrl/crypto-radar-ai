"""Strateji D — yalnız düşük RSI değil, çok kanıtlı aşırı satış dönüşü."""
from __future__ import annotations

from app.collectors.models import Candle
from app.indicators.core import rsi
from app.indicators.snapshot import IndicatorSnapshot

from .models import StrategyName, StrategyResult
from .volume import VolumeMetrics


def oversold_reversal(candles: list[Candle], snap: IndicatorSnapshot, volume: VolumeMetrics) -> StrategyResult:
    r = StrategyResult(StrategyName.OVERSOLD_REVERSAL, False, 0)
    if len(candles) < 30 or snap.rsi14 is None:
        r.risks.append("Dönüş analizi için yeterli RSI geçmişi yok")
        return r
    series = rsi([c.close for c in candles], 14)
    previous_rsi = next((v for v in reversed(series[-8:-1]) if v is not None), None)
    was_oversold = previous_rsi is not None and previous_rsi <= 35
    recovering = previous_rsi is not None and snap.rsi14 > previous_rsi and snap.rsi14 > 30
    hist_turn = snap.macd_histogram is not None and snap.macd_histogram_previous is not None and snap.macd_histogram > snap.macd_histogram_previous
    recent_low = min(c.low for c in candles[-5:])
    old_low = min(c.low for c in candles[-25:-5])
    old_rsi_values = [v for v in series[-25:-5] if v is not None]
    divergence = recent_low < old_low and bool(old_rsi_values) and snap.rsi14 > min(old_rsi_values) + 3
    support_reaction = snap.support is not None and candles[-1].low <= snap.support * 1.01 and candles[-1].close > snap.support
    buyer_turn = volume.taker_buy_ratio is not None and volume.taker_buy_ratio >= 0.52
    pattern = snap.bullish_engulfing or snap.hammer
    evidence = [recovering, hist_turn, divergence, support_reaction, buyer_turn, pattern]
    confirmations = sum(evidence)
    r.score = min(100, (20 if was_oversold else 0) + confirmations * 13 + (5 if snap.close > (snap.ema9 or float("inf")) else 0))
    r.triggered = was_oversold and recovering and confirmations >= 3
    r.direction = "bullish" if r.triggered else "neutral"
    if was_oversold:
        r.reasons.append(f"RSI önceki mumlarda {previous_rsi:.1f} ile aşırı satım bölgesindeydi")
    if recovering:
        r.reasons.append(f"RSI {snap.rsi14:.1f} seviyesine toparlandı")
    if hist_turn:
        r.reasons.append("MACD histogramı yükseliyor; negatif momentum zayıflıyor")
    if divergence:
        r.reasons.append("Fiyat daha düşük dip yaparken RSI daha güçlü; pozitif uyumsuzluk adayı")
    if support_reaction:
        r.reasons.append("Önceki destek bölgesinden kapanış tepkisi var")
    if buyer_turn:
        r.reasons.append("Aktif alıcı hacmi satıcı hacmini aşıyor")
    if pattern:
        r.reasons.append("Yutan boğa veya çekiç mum formasyonu destekliyor")
    if confirmations < 3:
        r.risks.append("Dönüş için en az üç bağımsız doğrulama yok; düşük RSI tek başına sinyal değildir")
    if snap.ema50 is not None and snap.close < snap.ema50:
        r.risks.append("Fiyat EMA50 altında; ana trend hâlâ zayıf")
    r.metrics = {"was_oversold": was_oversold, "recovering": recovering, "confirmations": confirmations,
                 "macd_turn": hist_turn, "positive_divergence": divergence, "support_reaction": support_reaction,
                 "buyer_turn": buyer_turn, "reversal_pattern": pattern}
    return r
