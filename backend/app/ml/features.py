"""Sinyal anında bilinen özelliklerin sabit, sürümlenebilir vektörü."""
from __future__ import annotations

import math
from typing import Any

FEATURE_NAMES = [
    "score", "mtf_agreement", "volume_ratio_15m", "volume_ratio_1h", "volume_ratio_4h",
    "volume_ratio_24h", "volume_zscore", "taker_buy_ratio", "rsi14", "adx", "atr_pct",
    "bb_width_pct", "macd_histogram_pct", "close_ema21_pct", "close_ema50_pct",
    "change_1h_pct", "change_4h_pct", "change_24h_pct", "orderbook_imbalance",
    "spread_pct", "depth_log10", "regime_score", "volume_strategy_score",
    "breakout_strategy_score", "relative_strength_score", "reversal_strategy_score",
    "momentum_strategy_score", "triggered_strategy_count",
]


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def extract_features(analysis: dict) -> dict[str, float | None]:
    primary = (analysis.get("snapshots") or {}).get("15m") or {}
    volume = analysis.get("volume") or {}
    windows = volume.get("windows") or {}
    flow = analysis.get("order_flow") or {}
    strategies = {s.get("name"): s for s in analysis.get("strategies") or []}
    close = _finite(primary.get("close"))

    def ratio(period: str) -> float | None:
        return _finite((windows.get(period) or {}).get("ratio"))

    def distance(key: str) -> float | None:
        ema = _finite(primary.get(key))
        return (close / ema - 1) * 100 if close is not None and ema else None

    macd = _finite(primary.get("macd_histogram"))
    depth = _finite(flow.get("depth_quote"))
    regime = analysis.get("regime") or {}
    regime_map = {"strong_bullish": 100, "bullish": 80, "neutral": 55,
                  "bearish": 25, "high_volatility_risk_off": 0, "unknown": 40}
    values = {
        "score": (analysis.get("score") or {}).get("total"),
        "mtf_agreement": analysis.get("mtf_agreement"),
        "volume_ratio_15m": ratio("15m"), "volume_ratio_1h": ratio("1h"),
        "volume_ratio_4h": ratio("4h"), "volume_ratio_24h": ratio("24h"),
        "volume_zscore": volume.get("latest_zscore"), "taker_buy_ratio": volume.get("taker_buy_ratio"),
        "rsi14": primary.get("rsi14"), "adx": primary.get("adx"), "atr_pct": primary.get("atr_pct"),
        "bb_width_pct": primary.get("bb_width_pct"),
        "macd_histogram_pct": macd / close * 100 if macd is not None and close else None,
        "close_ema21_pct": distance("ema21"), "close_ema50_pct": distance("ema50"),
        "change_1h_pct": primary.get("change_1h_pct"), "change_4h_pct": primary.get("change_4h_pct"),
        "change_24h_pct": primary.get("change_24h_pct"),
        "orderbook_imbalance": flow.get("imbalance"), "spread_pct": flow.get("spread_pct"),
        "depth_log10": math.log10(max(depth, 1)) if depth is not None else None,
        "regime_score": regime_map.get(regime.get("regime"), 40),
        "volume_strategy_score": (strategies.get("volume_explosion") or {}).get("score"),
        "breakout_strategy_score": (strategies.get("consolidation_breakout") or {}).get("score"),
        "relative_strength_score": (strategies.get("relative_strength") or {}).get("score"),
        "reversal_strategy_score": (strategies.get("oversold_reversal") or {}).get("score"),
        "momentum_strategy_score": (strategies.get("momentum_continuation") or {}).get("score"),
        "triggered_strategy_count": sum(bool(s.get("triggered")) for s in strategies.values()),
    }
    return {name: _finite(values.get(name)) for name in FEATURE_NAMES}
