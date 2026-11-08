"""Bir zaman diliminin son kapanmış mumundaki gösterge görünümü."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median

from app.collectors.models import Candle

from .core import adx, atr, bollinger, ema, last, macd, obv, pct_change, rolling_vwap, rsi, sma, stochastic_rsi


@dataclass(frozen=True)
class IndicatorSnapshot:
    interval: str
    candle_count: int
    close: float
    ema9: float | None
    ema21: float | None
    ema50: float | None
    ema200: float | None
    sma20: float | None
    rsi7: float | None
    rsi14: float | None
    rsi21: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    macd_histogram_previous: float | None
    bb_middle: float | None
    bb_upper: float | None
    bb_lower: float | None
    bb_width_pct: float | None
    bb_width_median_pct: float | None
    atr: float | None
    atr_pct: float | None
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    stoch_rsi_k: float | None
    stoch_rsi_d: float | None
    obv: float | None
    obv_slope_pct: float | None
    vwap20: float | None
    support: float | None
    resistance: float | None
    pivot: float | None
    pivot_r1: float | None
    pivot_s1: float | None
    higher_highs: bool
    higher_lows: bool
    bullish_engulfing: bool
    hammer: bool
    change_5m_pct: float | None
    change_15m_pct: float | None
    change_1h_pct: float | None
    change_4h_pct: float | None
    change_24h_pct: float | None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def trend(self) -> str:
        if self.ema21 is None or self.ema50 is None:
            return "unknown"
        bullish = self.close > self.ema21 > self.ema50 and (self.macd_histogram or 0) > 0
        bearish = self.close < self.ema21 < self.ema50 and (self.macd_histogram or 0) < 0
        return "bullish" if bullish else "bearish" if bearish else "neutral"


def _change_for_hours(candles: list[Candle], interval_ms: int, hours: float) -> float | None:
    period_ms = hours * 3_600_000
    if period_ms < interval_ms:
        return None  # 1d mumdan 1h değişim gibi uydurma alt-zaman verisi türetme
    return pct_change([c.close for c in candles], max(1, round(period_ms / interval_ms)))


def compute_snapshot(candles: list[Candle], interval_ms: int) -> IndicatorSnapshot:
    if not candles:
        raise ValueError("Gösterge için en az bir kapanmış mum gerekli")
    if any(not c.is_closed for c in candles):
        raise ValueError("Göstergelerde tamamlanmamış mum kullanılamaz")
    close = [c.close for c in candles]
    high, low, volume = [c.high for c in candles], [c.low for c in candles], [c.volume for c in candles]
    e9, e21, e50, e200 = (ema(close, p) for p in (9, 21, 50, 200))
    rsis = {p: rsi(close, p) for p in (7, 14, 21)}
    mac = macd(close)
    bb = bollinger(close)
    atrs = atr(high, low, close)
    dmi = adx(high, low, close)
    stoch = stochastic_rsi(close)
    obvs = obv(close, volume)
    vwap = rolling_vwap(high, low, close, volume)
    widths = [v for v in bb["width"][-60:-1] if v is not None]
    previous = candles[-2] if len(candles) >= 2 else candles[-1]
    structure = candles[-21:-1] if len(candles) > 1 else []
    support = min((c.low for c in structure), default=None)
    resistance = max((c.high for c in structure), default=None)
    pivot = (previous.high + previous.low + previous.close) / 3
    current = candles[-1]
    body, full_range = abs(current.close - current.open), current.high - current.low
    hammer = bool(full_range > 0 and current.close >= current.open and min(current.open, current.close) - current.low >= 2 * body and current.high - max(current.open, current.close) <= body)
    engulfing = bool(len(candles) >= 2 and previous.close < previous.open and current.close > current.open and current.open <= previous.close and current.close >= previous.open)
    obv_base = sum(volume[-6:-1]) / 5 if len(volume) >= 6 and sum(volume[-6:-1]) else None
    return IndicatorSnapshot(
        interval=current.interval, candle_count=len(candles), close=current.close,
        ema9=last(e9), ema21=last(e21), ema50=last(e50), ema200=last(e200), sma20=last(sma(close, 20)),
        rsi7=last(rsis[7]), rsi14=last(rsis[14]), rsi21=last(rsis[21]),
        macd=last(mac["macd"]), macd_signal=last(mac["signal"]), macd_histogram=last(mac["histogram"]),
        macd_histogram_previous=mac["histogram"][-2] if len(mac["histogram"]) > 1 else None,
        bb_middle=last(bb["middle"]), bb_upper=last(bb["upper"]), bb_lower=last(bb["lower"]),
        bb_width_pct=last(bb["width"]), bb_width_median_pct=median(widths) if widths else None,
        atr=last(atrs), atr_pct=(last(atrs) / current.close * 100) if last(atrs) is not None and current.close else None,
        adx=last(dmi["adx"]), plus_di=last(dmi["plus_di"]), minus_di=last(dmi["minus_di"]),
        stoch_rsi_k=last(stoch["k"]), stoch_rsi_d=last(stoch["d"]), obv=obvs[-1],
        obv_slope_pct=((obvs[-1] - obvs[-6]) / obv_base * 100) if obv_base else None,
        vwap20=last(vwap), support=support, resistance=resistance,
        pivot=pivot, pivot_r1=2 * pivot - previous.low, pivot_s1=2 * pivot - previous.high,
        higher_highs=len(candles) >= 6 and max(c.high for c in candles[-3:]) > max(c.high for c in candles[-6:-3]),
        higher_lows=len(candles) >= 6 and min(c.low for c in candles[-3:]) > min(c.low for c in candles[-6:-3]),
        bullish_engulfing=engulfing, hammer=hammer,
        change_5m_pct=_change_for_hours(candles, interval_ms, 1 / 12),
        change_15m_pct=_change_for_hours(candles, interval_ms, 0.25),
        change_1h_pct=_change_for_hours(candles, interval_ms, 1),
        change_4h_pct=_change_for_hours(candles, interval_ms, 4),
        change_24h_pct=_change_for_hours(candles, interval_ms, 24),
    )
