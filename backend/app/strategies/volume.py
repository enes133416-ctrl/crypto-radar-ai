"""Kapanmış mumlardan zaman pencereli hacim anomalisi ve Strateji A."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import mean

from app.collectors.models import INTERVAL_MS, Candle
from app.indicators.core import pct_change

from .models import StrategyName, StrategyResult


@dataclass(frozen=True)
class VolumeWindow:
    quote_volume: float | None
    baseline_average: float | None
    ratio: float | None
    price_change_pct: float | None


@dataclass(frozen=True)
class VolumeMetrics:
    source_interval: str
    windows: dict[str, VolumeWindow]
    latest_zscore: float | None
    taker_buy_ratio: float | None
    taker_imbalance: float | None
    obv_volume_alignment: bool | None

    def to_dict(self) -> dict:
        return asdict(self)


def _window(candles: list[Candle], bars: int) -> VolumeWindow:
    if bars < 1 or len(candles) < bars * 6:
        return VolumeWindow(None, None, None, None)
    recent = candles[-bars:]
    historical = candles[:-bars]
    # Önceki eşit uzunluktaki en fazla 20 pencere; son pencere kendisiyle karşılaştırılmaz.
    blocks = [historical[i:i + bars] for i in range(len(historical) - bars, -1, -bars)][:20]
    complete = [b for b in blocks if len(b) == bars]
    if not complete:
        return VolumeWindow(None, None, None, None)
    baseline = mean(sum(c.quote_volume for c in b) for b in complete)
    current = sum(c.quote_volume for c in recent)
    previous_close = candles[-bars - 1].close
    return VolumeWindow(current, baseline, current / baseline if baseline > 0 else None,
                        (recent[-1].close / previous_close - 1) * 100 if previous_close else None)


def analyze_volume(candles: list[Candle]) -> VolumeMetrics:
    if not candles or any(not c.is_closed for c in candles):
        raise ValueError("Hacim analizi yalnızca kapanmış mumlarla yapılır")
    interval = candles[0].interval
    step = INTERVAL_MS[interval]
    windows = {}
    for label, milliseconds in (("5m", 300_000), ("15m", 900_000), ("1h", 3_600_000), ("4h", 14_400_000), ("24h", 86_400_000)):
        windows[label] = _window(candles, round(milliseconds / step))
    history = [c.quote_volume for c in candles[-41:-1]]
    zscore = None
    if len(history) >= 20:
        avg = mean(history)
        std = sqrt(sum((v - avg) ** 2 for v in history) / len(history))
        # Sabit seride std=0 diye sıçramayı gizleme; %1 ortalama tabanı ölçek sağlar.
        denominator = max(std, avg * 0.01, 1e-12)
        zscore = (candles[-1].quote_volume - avg) / denominator
    recent = candles[-min(12, len(candles)):]
    buy = sum(c.taker_buy_quote for c in recent)
    total = sum(c.quote_volume for c in recent)
    buy_ratio = buy / total if total > 0 else None
    up_vol = sum(c.volume for c in recent if c.close > c.open)
    down_vol = sum(c.volume for c in recent if c.close < c.open)
    alignment = up_vol > down_vol if up_vol + down_vol > 0 else None
    return VolumeMetrics(interval, windows, zscore, buy_ratio, 2 * buy_ratio - 1 if buy_ratio is not None else None, alignment)


def volume_explosion(metrics: VolumeMetrics, min_ratio: float = 2.5, max_early_price_change_pct: float = 5.0) -> StrategyResult:
    preferred = next((metrics.windows[w] for w in ("1h", "15m", "4h", "24h") if metrics.windows[w].ratio is not None), None)
    result = StrategyResult(StrategyName.VOLUME_EXPLOSION, False, 0)
    if preferred is None:
        result.risks.append("Hacim oranı için yeterli kapanmış mum geçmişi yok")
        return result
    ratio = preferred.ratio or 0.0
    change = preferred.price_change_pct or 0.0
    z = metrics.latest_zscore or 0.0
    buy = metrics.taker_buy_ratio
    score = min(45.0, ratio / min_ratio * 30.0) + min(20.0, max(0.0, z) * 4.0)
    if buy is not None:
        score += max(0.0, min(20.0, (buy - 0.45) * 200))
    if -2.0 <= change <= max_early_price_change_pct:
        score += 15.0
    elif change > max_early_price_change_pct:
        result.risks.append(f"Fiyat hacim penceresinde %{change:.2f} hareket etti; erken sinyal olmayabilir")
    result.score = score
    result.metrics = {"volume_ratio": ratio, "price_change_pct": change, "zscore": metrics.latest_zscore,
                      "taker_buy_ratio": buy, "source_interval": metrics.source_interval}
    result.triggered = ratio >= min_ratio and -2.0 <= change <= max_early_price_change_pct and (buy is None or buy >= 0.5)
    if ratio >= min_ratio:
        result.reasons.append(f"Son pencere hacmi önceki eşit pencerelerin {ratio:.2f} katı")
    if z >= 2:
        result.reasons.append(f"Son mum hacmi ortalamadan {z:.1f} standart sapma yüksek")
    if buy is not None and buy >= 0.52:
        result.reasons.append(f"Aktif alıcı hacim payı %{buy * 100:.1f}")
    if change < -2:
        result.risks.append("Hacim artışı fiyat düşüşüyle birlikte; satış baskısı olabilir")
    if ratio >= 10 or z >= 8:
        result.risks.append("Olağan dışı hacim sıçraması sürdürülemeyebilir")
    result.direction = "bullish" if result.triggered else "neutral"
    return result
