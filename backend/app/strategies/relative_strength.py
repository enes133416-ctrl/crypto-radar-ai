"""Strateji C — BTC, ETH ve isteğe bağlı piyasa medyanına göre güç."""
from __future__ import annotations

from app.collectors.models import Candle
from app.indicators.core import pct_change

from .models import StrategyName, StrategyResult


def _returns(candles: list[Candle], bars_1h: int) -> dict[str, float | None]:
    closes = [c.close for c in candles]
    return {"1h": pct_change(closes, bars_1h), "4h": pct_change(closes, bars_1h * 4), "24h": pct_change(closes, bars_1h * 24)}


def relative_strength(symbol: str, candles: list[Candle], btc: list[Candle] | None = None,
                      eth: list[Candle] | None = None, bars_1h: int = 4,
                      market_returns: dict[str, float] | None = None) -> StrategyResult:
    r = StrategyResult(StrategyName.RELATIVE_STRENGTH, False, 0)
    own = _returns(candles, bars_1h)
    benchmarks: dict[str, dict[str, float | None]] = {}
    if symbol != "BTCUSDT" and btc:
        benchmarks["BTC"] = _returns(btc, bars_1h)
    if symbol not in ("BTCUSDT", "ETHUSDT") and eth:
        benchmarks["ETH"] = _returns(eth, bars_1h)
    spreads: dict[str, float | None] = {}
    all_spreads: list[float] = []
    for horizon in ("1h", "4h", "24h"):
        values = [b[horizon] for b in benchmarks.values() if b[horizon] is not None]
        if market_returns and horizon in market_returns:
            values.append(market_returns[horizon])
        spreads[horizon] = own[horizon] - sum(values) / len(values) if own[horizon] is not None and values else None
        if spreads[horizon] is not None:
            all_spreads.append(spreads[horizon])
    if not all_spreads:
        r.risks.append("Göreceli güç için ortak BTC/ETH/piyasa geçmişi yok")
        r.metrics = {"returns": own, "relative_pct": spreads}
        return r
    positive = sum(v > 0 for v in all_spreads)
    avg = sum(all_spreads) / len(all_spreads)
    resilient = own["4h"] is not None and own["4h"] > 0 and any(
        b["4h"] is not None and b["4h"] < 0 for b in benchmarks.values())
    r.score = min(100, 35 + positive / len(all_spreads) * 35 + max(-20, min(30, avg * 3)))
    r.triggered = positive == len(all_spreads) and avg > 0.5 and (own["1h"] or 0) > -1
    r.direction = "bullish" if r.triggered else "neutral"
    if positive:
        r.reasons.append(f"{len(all_spreads)} ortak zaman penceresinin {positive} tanesinde benchmark üzeri performans")
    if resilient:
        r.reasons.append("Benchmark 4 saatte düşerken coin pozitif kaldı")
    if avg < 0:
        r.risks.append(f"Ortalama göreceli performans {avg:.2f} puan; piyasanın gerisinde")
    r.metrics = {"returns": own, "benchmarks": benchmarks, "relative_pct": spreads,
                 "average_relative_pct": avg, "resilient": resilient}
    return r
