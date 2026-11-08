"""Kaydedilmiş sinyallerin örneklem ve belirsizlik aralıklı performans raporu."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Callable


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float | None]:
    if total <= 0:
        return [None, None]
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def _rate(rows: list[dict], field: str) -> dict:
    valid = [r for r in rows if r.get(field) is not None]
    successes = sum(bool(r[field]) for r in valid)
    total = len(valid)
    return {"successes": successes, "samples": total,
            "rate": round(successes / total, 4) if total else None,
            "wilson_95": wilson_interval(successes, total)}


def _average(rows: list[dict], field: str) -> float | None:
    values = [float(r[field]) for r in rows if r.get(field) is not None]
    return round(mean(values), 4) if values else None


def summarize(rows: list[dict], horizon: int = 72) -> dict:
    if horizon not in (24, 48, 72):
        raise ValueError("horizon 24, 48 veya 72 olmalı")
    return {
        "horizon_hours": horizon,
        "signal_count": len(rows),
        "evaluated_count": sum(r.get(f"price_{horizon}h") is not None for r in rows),
        "hit5": _rate(rows, f"hit5_{horizon}h"),
        "hit10_any": _rate(rows, f"hit10_{horizon}h"),
        "hit15": _rate(rows, f"hit15_{horizon}h"),
        "hit10_before_stop3": _rate(rows, f"up10_before_stop3_{horizon}h"),
        "hit10_before_stop5": _rate(rows, f"up10_before_stop5_{horizon}h"),
        "stop3_before_hit10": _rate(rows, f"stop3_before_up10_{horizon}h"),
        "stop5_before_hit10": _rate(rows, f"stop5_before_up10_{horizon}h"),
        "average_max_up_pct": _average(rows, f"max_up_{horizon}h"),
        "average_max_down_pct": _average(rows, f"max_down_{horizon}h"),
        "average_net_return_pct": _average(rows, f"net_return_{horizon}h"),
        "ambiguous_barrier_signals": sum(int(r.get("ambiguous_barriers") or 0) > 0 for r in rows),
        "cost_note": "Net getiriye yapılandırılmış gidiş-dönüş komisyon/spread/slippage bedeli düşülmüştür; MFE/MAE brüttür.",
    }


def _band(score: float) -> str:
    if score >= 85:
        return "85-100"
    if score >= 75:
        return "75-84"
    if score >= 65:
        return "65-74"
    if score >= 50:
        return "50-64"
    return "0-49"


def _groups(rows: list[dict], key: Callable[[dict], str], horizon: int) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return {name: summarize(values, horizon) for name, values in sorted(grouped.items())}


def performance_report(rows: list[dict], horizon: int = 72) -> dict:
    usable = [r for r in rows if r.get(f"price_{horizon}h") is not None]

    def day(row: dict) -> str:
        return datetime.fromtimestamp(row["signal_time"] / 1000, timezone.utc).strftime("%Y-%m-%d")

    def week(row: dict) -> str:
        date = datetime.fromtimestamp(row["signal_time"] / 1000, timezone.utc)
        year, week_number, _ = date.isocalendar()
        return f"{year}-W{week_number:02d}"

    def month(row: dict) -> str:
        return day(row)[:7]

    warning = None
    if len(usable) < 30:
        warning = "Örneklem 30 sinyalin altında; oranlar kararsızdır, kesin performans sonucu çıkarılamaz."
    return {
        "summary": summarize(rows, horizon),
        "by_strategy": _groups(usable, lambda r: r["strategy"], horizon),
        "by_market": _groups(usable, lambda r: r["market"], horizon),
        "by_score_band": _groups(usable, lambda r: _band(float(r["score"])), horizon),
        "daily": _groups(usable, day, horizon), "weekly": _groups(usable, week, horizon),
        "monthly": _groups(usable, month, horizon),
        "small_sample_warning": warning,
        "methodology": "Sinyal anındaki kayıtlı özellikler ile sonraki kapalı 15m mumlar karşılaştırılır. Aynı mumda iki bariyer görülmesi zarar-önce sayılır ve ayrıca raporlanır.",
    }
