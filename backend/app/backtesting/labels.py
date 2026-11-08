"""Gelecek mumlardan Triple Barrier sonuçları.

Bu modül yalnız sinyal zamanından SONRAKİ kapalı mumları kabul eder. Aynı mumda hedef
ve zarar görülürse intramum sıra bilinemeyeceği için sonuç 'ambiguous' döner; eğitimde
iyimser hedef-önce etiketi üretmek yerine zarar-önce kabul edilir ve belirsizlik sayılır.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.collectors.models import INTERVAL_MS, Candle

BarrierResult = Literal["target", "stop", "none", "ambiguous"]


@dataclass(frozen=True)
class FirstBarrier:
    result: BarrierResult
    time_ms: int | None


def first_barrier(candles: list[Candle], entry_price: float, target_pct: float = 10.0,
                  stop_pct: float = 5.0) -> FirstBarrier:
    if entry_price <= 0:
        raise ValueError("entry_price pozitif olmalı")
    target = entry_price * (1 + target_pct / 100)
    stop = entry_price * (1 - stop_pct / 100)
    for candle in candles:
        target_hit = candle.high >= target
        stop_hit = candle.low <= stop
        if target_hit and stop_hit:
            return FirstBarrier("ambiguous", candle.close_time)
        if stop_hit:
            return FirstBarrier("stop", candle.close_time)
        if target_hit:
            return FirstBarrier("target", candle.close_time)
    return FirstBarrier("none", None)


def _pct(value: float, entry: float) -> float:
    return (value / entry - 1) * 100


def evaluate_horizon(candles: list[Candle], entry_price: float, cost_pct: float = 0.15) -> dict:
    """Bir ufuk içindeki fiyat, MFE/MAE ve ayrı hedef/zarar etiketleri."""
    if not candles:
        raise ValueError("Sonuç için en az bir kapalı mum gerekli")
    if any(not c.is_closed for c in candles):
        raise ValueError("Sonuç hesabında açık mum kullanılamaz")
    highest = max(c.high for c in candles)
    lowest = min(c.low for c in candles)
    close = candles[-1].close
    barriers = {stop: first_barrier(candles, entry_price, 10.0, stop) for stop in (3.0, 5.0)}
    return {
        "price": close,
        "max_up": _pct(highest, entry_price),
        "max_down": _pct(lowest, entry_price),
        "net_return": _pct(close, entry_price) - cost_pct,
        "hit5": highest >= entry_price * 1.05,
        "hit10": highest >= entry_price * 1.10,
        "hit15": highest >= entry_price * 1.15,
        "up10_before_stop3": barriers[3.0].result == "target",
        "up10_before_stop5": barriers[5.0].result == "target",
        "stop3_before_up10": barriers[3.0].result in {"stop", "ambiguous"},
        "stop5_before_up10": barriers[5.0].result in {"stop", "ambiguous"},
        "ambiguous": sum(b.result == "ambiguous" for b in barriers.values()),
    }


def outcome_values(signal: dict, future_candles: list[Candle], now_ms: int,
                   cost_pct: float = 0.15) -> tuple[dict, bool]:
    """24/48/72 saat sonuçlarını yalnız ilgili ufuk kapandıysa üretir."""
    entry = float(signal["entry_price"])
    start = int(signal["signal_time"])
    values: dict = {}
    ambiguous = 0
    for hours in (24, 48, 72):
        end = start + hours * 3_600_000
        if now_ms < end:
            continue
        rows = [c for c in future_candles if start < c.close_time <= end and c.is_closed]
        # Ufku kapatmak için veri yalnızca birkaç mumdan ibaret olamaz. %80 kapsama
        # ve ufkun sonuna yakın mum zorunludur; aksi hâlde sonuç beklemeye devam eder.
        required = max(1, int(hours * 4 * 0.80))
        if len(rows) < required or rows[-1].close_time < end - INTERVAL_MS["15m"]:
            continue
        result = evaluate_horizon(rows, entry, cost_pct)
        values[f"price_{hours}h"] = result["price"]
        values[f"max_up_{hours}h"] = result["max_up"]
        values[f"max_down_{hours}h"] = result["max_down"]
        values[f"net_return_{hours}h"] = result["net_return"]
        for target in (5, 10, 15):
            values[f"hit{target}_{hours}h"] = int(result[f"hit{target}"])
        for stop in (3, 5):
            values[f"up10_before_stop{stop}_{hours}h"] = int(result[f"up10_before_stop{stop}"])
            values[f"stop{stop}_before_up10_{hours}h"] = int(result[f"stop{stop}_before_up10"])
        ambiguous += int(result["ambiguous"])
    values["ambiguous_barriers"] = ambiguous
    return values, "price_72h" in values
