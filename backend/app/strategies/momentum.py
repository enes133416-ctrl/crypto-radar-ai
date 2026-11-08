"""Strateji E — trend, momentum, hacim ve çoklu zaman uyumu."""
from __future__ import annotations

from app.indicators.snapshot import IndicatorSnapshot

from .models import StrategyName, StrategyResult
from .volume import VolumeMetrics


def momentum_continuation(snap: IndicatorSnapshot, volume: VolumeMetrics, higher_trends: dict[str, str],
                          max_extension_atr: float = 4.0) -> StrategyResult:
    r = StrategyResult(StrategyName.MOMENTUM_CONTINUATION, False, 0)
    required = (snap.ema9, snap.ema21, snap.ema50, snap.rsi14, snap.adx, snap.plus_di, snap.minus_di)
    if any(v is None for v in required):
        r.risks.append("Momentum için EMA9/21/50, RSI ve ADX ısınma geçmişi yetersiz")
        return r
    assert snap.ema9 is not None and snap.ema21 is not None and snap.ema50 is not None
    assert snap.rsi14 is not None and snap.adx is not None and snap.plus_di is not None and snap.minus_di is not None
    ema_aligned = snap.close > snap.ema9 > snap.ema21 > snap.ema50
    long_term_ok = snap.ema200 is None or snap.close > snap.ema200
    macd_ok = snap.macd_histogram is not None and snap.macd_histogram > 0
    dmi_ok = snap.adx >= 20 and snap.plus_di > snap.minus_di
    rsi_ok = 50 <= snap.rsi14 <= 75
    structure = snap.higher_highs and snap.higher_lows
    volume_ok = bool(volume.obv_volume_alignment) and (volume.taker_buy_ratio is None or volume.taker_buy_ratio >= 0.5)
    agreement = sum(t == "bullish" for t in higher_trends.values())
    total_higher = len(higher_trends)
    mtf_ok = total_higher > 0 and agreement == total_higher
    extension = ((snap.close - snap.ema21) / snap.atr) if snap.atr else None
    overextended = bool((extension is not None and extension > max_extension_atr) or snap.rsi14 > 80)
    checks = [ema_aligned, long_term_ok, macd_ok, dmi_ok, rsi_ok, structure, volume_ok, mtf_ok]
    weights = [18, 8, 12, 18, 10, 12, 10, 12]
    r.score = sum(weight for check, weight in zip(checks, weights) if check)
    r.triggered = ema_aligned and dmi_ok and macd_ok and structure and mtf_ok and not overextended
    r.direction = "bullish" if r.triggered else "neutral"
    if ema_aligned:
        r.reasons.append("Fiyat > EMA9 > EMA21 > EMA50; kısa/orta trend hizalı")
    if dmi_ok:
        r.reasons.append(f"ADX {snap.adx:.1f} ve +DI > -DI; yönlü trend güçlü")
    if macd_ok:
        r.reasons.append("MACD histogramı pozitif")
    if structure:
        r.reasons.append("Higher high / higher low fiyat yapısı korunuyor")
    if mtf_ok:
        r.reasons.append(f"{total_higher} üst zaman diliminin tamamı yükseliş yönünde")
    if overextended:
        r.risks.append("Fiyat EMA21'den ATR ile aşırı uzaklaştı veya RSI > 80; geç kalma riski")
    if snap.rsi14 > 75:
        r.risks.append(f"RSI {snap.rsi14:.1f}; momentum güçlü ama aşırı alım bölgesinde")
    if not volume_ok:
        r.risks.append("Hacim/OBV ve aktif alıcı akışı trendi doğrulamıyor")
    if total_higher and agreement < total_higher:
        r.risks.append("Üst zaman dilimleriyle uyum eksik")
    r.metrics = {"ema_aligned": ema_aligned, "long_term_ok": long_term_ok, "macd_positive": macd_ok,
                 "adx_dmi_ok": dmi_ok, "rsi_ok": rsi_ok, "structure_ok": structure, "volume_ok": volume_ok,
                 "mtf_ok": mtf_ok, "ema21_extension_atr": extension, "overextended": overextended,
                 "higher_trends": higher_trends}
    return r
