"""Bağımlılıksız, deterministik teknik gösterge fonksiyonları.

Girdi dizileri yalnızca KAPANMIŞ mumlardan üretilmelidir. Her fonksiyon girdiyle
aynı uzunlukta sonuç döndürür; ısınma döneminde None kullanır, gelecekten veri almaz.
"""
from __future__ import annotations

import math
from typing import Sequence

Number = float | int
MaybeSeries = list[float | None]


def _values(values: Sequence[Number]) -> list[float]:
    out = [float(v) for v in values]
    if any(not math.isfinite(v) for v in out):
        raise ValueError("Gösterge girdisi NaN veya sonsuz değer içeriyor")
    return out


def _period(period: int, minimum: int = 1) -> int:
    if period < minimum:
        raise ValueError(f"period en az {minimum} olmalı")
    return period


def sma(values: Sequence[Number], period: int) -> MaybeSeries:
    _period(period)
    vals, out, total = _values(values), [], 0.0
    for i, value in enumerate(vals):
        total += value
        if i >= period:
            total -= vals[i - period]
        out.append(total / period if i >= period - 1 else None)
    return out


def ema(values: Sequence[Number], period: int) -> MaybeSeries:
    _period(period)
    vals = _values(values)
    out: MaybeSeries = [None] * len(vals)
    if len(vals) < period:
        return out
    current = sum(vals[:period]) / period
    out[period - 1] = current
    alpha = 2.0 / (period + 1)
    for i in range(period, len(vals)):
        current = alpha * vals[i] + (1 - alpha) * current
        out[i] = current
    return out


def rsi(values: Sequence[Number], period: int = 14) -> MaybeSeries:
    """Wilder RSI. İlk değer period fiyat değişiminden sonra oluşur."""
    _period(period)
    vals = _values(values)
    out: MaybeSeries = [None] * len(vals)
    if len(vals) <= period:
        return out
    gains = [max(vals[i] - vals[i - 1], 0.0) for i in range(1, period + 1)]
    losses = [max(vals[i - 1] - vals[i], 0.0) for i in range(1, period + 1)]
    avg_gain, avg_loss = sum(gains) / period, sum(losses) / period

    def value(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    out[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, len(vals)):
        change = vals[i] - vals[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = value(avg_gain, avg_loss)
    return out


def macd(values: Sequence[Number], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, MaybeSeries]:
    _period(fast)
    _period(slow, fast + 1)
    _period(signal)
    fast_line, slow_line = ema(values, fast), ema(values, slow)
    line = [None if f is None or s is None else f - s for f, s in zip(fast_line, slow_line)]
    valid = [(i, v) for i, v in enumerate(line) if v is not None]
    sig: MaybeSeries = [None] * len(line)
    if len(valid) >= signal:
        smooth = ema([v for _, v in valid], signal)
        for (i, _), value in zip(valid, smooth):
            sig[i] = value
    hist = [None if m is None or s is None else m - s for m, s in zip(line, sig)]
    return {"macd": line, "signal": sig, "histogram": hist}


def true_range(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number]) -> MaybeSeries:
    h, l, c = _values(high), _values(low), _values(close)
    if not (len(h) == len(l) == len(c)):
        raise ValueError("high, low ve close uzunlukları eşit olmalı")
    return [h[0] - l[0] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(len(h))]


def _wilder(values: Sequence[Number], period: int) -> MaybeSeries:
    vals, out = _values(values), [None] * len(values)
    if len(vals) < period:
        return out
    current = sum(vals[:period]) / period
    out[period - 1] = current
    for i in range(period, len(vals)):
        current = (current * (period - 1) + vals[i]) / period
        out[i] = current
    return out


def atr(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number], period: int = 14) -> MaybeSeries:
    _period(period)
    return _wilder([v if v is not None else 0.0 for v in true_range(high, low, close)], period)


def bollinger(values: Sequence[Number], period: int = 20, deviations: float = 2.0) -> dict[str, MaybeSeries]:
    _period(period, 2)
    vals, middle = _values(values), sma(values, period)
    upper: MaybeSeries = [None] * len(vals)
    lower: MaybeSeries = [None] * len(vals)
    width: MaybeSeries = [None] * len(vals)
    for i in range(period - 1, len(vals)):
        mean = middle[i]
        assert mean is not None
        variance = sum((v - mean) ** 2 for v in vals[i - period + 1:i + 1]) / period
        band = deviations * math.sqrt(variance)
        upper[i], lower[i] = mean + band, mean - band
        width[i] = (upper[i] - lower[i]) / mean * 100 if mean else None
    return {"middle": middle, "upper": upper, "lower": lower, "width": width}


def adx(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number], period: int = 14) -> dict[str, MaybeSeries]:
    """Wilder ADX, +DI ve -DI (0-100)."""
    _period(period, 2)
    h, l, c = _values(high), _values(low), _values(close)
    if not (len(h) == len(l) == len(c)):
        raise ValueError("high, low ve close uzunlukları eşit olmalı")
    n = len(h)
    result = {k: [None] * n for k in ("adx", "plus_di", "minus_di")}
    if n <= period:
        return result
    tr = [0.0] * n
    plus, minus = [0.0] * n, [0.0] * n
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        up, down = h[i] - h[i - 1], l[i - 1] - l[i]
        plus[i] = up if up > down and up > 0 else 0.0
        minus[i] = down if down > up and down > 0 else 0.0
    tr_s, p_s, m_s = sum(tr[1:period + 1]), sum(plus[1:period + 1]), sum(minus[1:period + 1])
    dx: MaybeSeries = [None] * n
    for i in range(period, n):
        if i > period:
            tr_s = tr_s - tr_s / period + tr[i]
            p_s = p_s - p_s / period + plus[i]
            m_s = m_s - m_s / period + minus[i]
        pdi = 100 * p_s / tr_s if tr_s else 0.0
        mdi = 100 * m_s / tr_s if tr_s else 0.0
        result["plus_di"][i], result["minus_di"][i] = pdi, mdi
        dx[i] = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0
    first_adx = 2 * period - 1
    if n > first_adx:
        initial = [v for v in dx[period:first_adx + 1] if v is not None]
        current = sum(initial) / period
        result["adx"][first_adx] = current
        for i in range(first_adx + 1, n):
            current = (current * (period - 1) + (dx[i] or 0.0)) / period
            result["adx"][i] = current
    return result


def stochastic_rsi(values: Sequence[Number], period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> dict[str, MaybeSeries]:
    source = rsi(values, period)
    raw: MaybeSeries = [None] * len(source)
    for i in range(len(source)):
        window = [v for v in source[max(0, i - period + 1):i + 1] if v is not None]
        if len(window) == period and source[i] is not None:
            lo, hi = min(window), max(window)
            raw[i] = 50.0 if hi == lo else (source[i] - lo) / (hi - lo) * 100
    compact = [(i, v) for i, v in enumerate(raw) if v is not None]
    k: MaybeSeries = [None] * len(source)
    smoothed = sma([v for _, v in compact], smooth_k)
    for (i, _), value in zip(compact, smoothed):
        k[i] = value
    compact_k = [(i, v) for i, v in enumerate(k) if v is not None]
    d: MaybeSeries = [None] * len(source)
    for (i, _), value in zip(compact_k, sma([v for _, v in compact_k], smooth_d)):
        d[i] = value
    return {"k": k, "d": d}


def obv(close: Sequence[Number], volume: Sequence[Number]) -> list[float]:
    c, v = _values(close), _values(volume)
    if len(c) != len(v):
        raise ValueError("close ve volume uzunlukları eşit olmalı")
    out = [0.0]
    for i in range(1, len(c)):
        out.append(out[-1] + (v[i] if c[i] > c[i - 1] else -v[i] if c[i] < c[i - 1] else 0.0))
    return out[:len(c)]


def rolling_vwap(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number], volume: Sequence[Number], period: int = 20) -> MaybeSeries:
    """Son period mumun tipik-fiyat/hacim VWAP'i; seans VWAP'i olduğu iddia edilmez."""
    _period(period)
    h, l, c, v = _values(high), _values(low), _values(close), _values(volume)
    if not (len(h) == len(l) == len(c) == len(v)):
        raise ValueError("VWAP girdi uzunlukları eşit olmalı")
    typical = [(h[i] + l[i] + c[i]) / 3 for i in range(len(c))]
    out: MaybeSeries = [None] * len(c)
    for i in range(period - 1, len(c)):
        vols = v[i - period + 1:i + 1]
        total = sum(vols)
        out[i] = sum(p * vol for p, vol in zip(typical[i - period + 1:i + 1], vols)) / total if total else None
    return out


def pct_change(values: Sequence[Number], lookback: int) -> float | None:
    _period(lookback)
    vals = _values(values)
    if len(vals) <= lookback or vals[-lookback - 1] == 0:
        return None
    return (vals[-1] / vals[-lookback - 1] - 1) * 100


def last(series: Sequence[float | None]) -> float | None:
    return series[-1] if series else None
