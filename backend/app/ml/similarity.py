"""Geçmiş çözülmüş sinyallerle zaman-güvenli, ölçeklenmiş benzerlik analizi."""
from __future__ import annotations

import math
from statistics import median
from typing import Any

from app.backtesting.performance import wilson_interval
from app.ml.features import FEATURE_NAMES


def _distance(a: dict, b: dict, scales: dict[str, float]) -> tuple[float, int]:
    total, count = 0.0, 0
    for name in FEATURE_NAMES:
        x, y = a.get(name), b.get(name)
        if x is None or y is None:
            continue
        scale = scales[name]
        total += ((float(x) - float(y)) / scale) ** 2
        count += 1
    return (math.sqrt(total / count), count) if count >= 8 else (float("inf"), count)


class SimilarityAnalyzer:
    def __init__(self, min_neighbors: int = 10, neighbors: int = 30):
        self.min_neighbors = min_neighbors
        self.neighbors = neighbors

    def analyze(self, features: dict, historical_rows: list[dict], as_of_ms: int) -> dict:
        # resolved_at < as_of: o anda henüz sonucu bilinmeyen örnekler özelliklere sızmaz.
        eligible = [r for r in historical_rows if r.get("resolved_at") is not None
                    and r["resolved_at"] < as_of_ms and r["signal_time"] < as_of_ms]
        if not eligible:
            return {"status": "insufficient_training_data", "samples": 0, "neighbors": []}
        scales = {}
        for name in FEATURE_NAMES:
            values = [abs(float(r["features"][name])) for r in eligible if r["features"].get(name) is not None]
            scales[name] = max(median(values) if values else 1.0, 1e-6)
        ranked = []
        for row in eligible:
            distance, common = _distance(features, row["features"], scales)
            if math.isfinite(distance):
                ranked.append((distance, common, row))
        ranked.sort(key=lambda item: item[0])
        selected = ranked[:self.neighbors]
        if len(selected) < self.min_neighbors:
            return {"status": "insufficient_training_data", "samples": len(selected), "neighbors": []}
        result: dict[str, Any] = {"status": "available", "samples": len(selected),
                                  "mean_distance": round(sum(x[0] for x in selected) / len(selected), 4),
                                  "horizons": {}}
        similarity_values = []
        for hours in (24, 48, 72):
            field = f"up10_before_stop5_{hours}h"
            valid = [r for _, _, r in selected if r.get(field) is not None]
            hits = sum(bool(r[field]) for r in valid)
            rate = hits / len(valid) if valid else None
            result["horizons"][str(hours)] = {
                "samples": len(valid), "hits": hits, "hit10_before_stop5_rate": rate,
                "wilson_95": wilson_interval(hits, len(valid)),
            }
            if rate is not None:
                # Küçük komşu grubunun skora etkisini sınırla; bu geçmiş başarı garantisi değildir.
                similarity_values.append(rate * 100 * min(1.0, len(valid) / 30))
        result["similarity_score"] = round(sum(similarity_values) / len(similarity_values), 2) if similarity_values else None
        result["neighbors"] = [{
            "signal_id": r["id"], "symbol": r["symbol"], "market": r["market"],
            "strategy": r["strategy"], "signal_time": r["signal_time"], "score": r["score"],
            "distance": round(distance, 4), "common_features": common,
            "outcomes": {str(h): {"hit10": r.get(f"hit10_{h}h"),
                                  "up10_before_stop5": r.get(f"up10_before_stop5_{h}h"),
                                  "net_return_pct": r.get(f"net_return_{h}h")}
                         for h in (24, 48, 72)},
        } for distance, common, r in selected[:10]]
        return result
