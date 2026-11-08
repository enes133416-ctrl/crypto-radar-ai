"""Ayrı komutla eğitilen hafif, kalibre edilmiş olasılık modelleri.

Sunucu açılışında veya tarama döngüsünde eğitim YAPILMAZ. Eğitim yalnız çözülmüş,
geçmiş sinyalleri kullanır; son zaman dilimi out-of-sample olarak ayrılır.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline

from app.ml.features import FEATURE_NAMES, extract_features

TARGETS = {hours: {
    "up5": f"hit5_{hours}h", "up10": f"hit10_{hours}h", "up15": f"hit15_{hours}h",
    "up10_before_stop3": f"up10_before_stop3_{hours}h",
    "up10_before_stop5": f"up10_before_stop5_{hours}h",
    "stop3_before_up10": f"stop3_before_up10_{hours}h",
    "stop5_before_up10": f"stop5_before_up10_{hours}h",
} for hours in (24, 48, 72)}


def _estimator() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", __import__("sklearn.preprocessing", fromlist=["StandardScaler"]).StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])


def _metrics(y: np.ndarray, probabilities: np.ndarray) -> dict:
    result = {"samples": int(len(y)), "brier": round(float(brier_score_loss(y, probabilities)), 5),
              "accuracy_at_0_5": round(float(accuracy_score(y, probabilities >= 0.5)), 5)}
    result["roc_auc"] = round(float(roc_auc_score(y, probabilities)), 5) if len(np.unique(y)) == 2 else None
    return result


def train_models(rows: list[dict], model_path: str, min_samples: int = 200) -> dict:
    rows = sorted((r for r in rows if r.get("status") == "resolved"), key=lambda r: r["signal_time"])
    report: dict[str, Any] = {"status": "insufficient_training_data", "total_resolved": len(rows),
                              "minimum_samples": min_samples, "targets": {}, "feature_names": FEATURE_NAMES}
    if len(rows) < min_samples:
        report["reason"] = f"En az {min_samples} çözülmüş sinyal gerekli; mevcut {len(rows)}"
        return report
    X = np.array([[r["features"].get(name) if r["features"].get(name) is not None else np.nan
                   for name in FEATURE_NAMES] for r in rows], dtype=float)
    split = max(int(len(rows) * 0.8), len(rows) - max(30, len(rows) // 5))
    split = min(max(1, split), len(rows) - 1)
    models: dict[str, Any] = {}
    trained_targets = 0
    for hours, targets in TARGETS.items():
        for name, field in targets.items():
            valid = [i for i, row in enumerate(rows) if row.get(field) is not None]
            if len(valid) < min_samples:
                report["targets"][f"{hours}h_{name}"] = {"status": "skipped", "reason": "yetersiz etiket", "samples": len(valid)}
                continue
            indices = np.array(valid)
            y = np.array([int(bool(rows[i][field])) for i in valid], dtype=int)
            if len(np.unique(y)) < 2 or min(np.bincount(y)) < 6:
                report["targets"][f"{hours}h_{name}"] = {"status": "skipped", "reason": "iki sınıf için yeterli örnek yok",
                                                               "class_counts": np.bincount(y).tolist()}
                continue
            train_idx = indices[indices < split]
            test_idx = indices[indices >= split]
            if len(test_idx) < 10 or len(train_idx) < 30 or len(np.unique(y[indices < split])) < 2:
                report["targets"][f"{hours}h_{name}"] = {"status": "skipped", "reason": "zaman bazlı train/test bölümü yetersiz"}
                continue
            train_positions = np.searchsorted(indices, train_idx)
            test_positions = np.searchsorted(indices, test_idx)
            # Yukarıdaki positions, y ve X[indices] ile aynı sıradadır.
            Xv = X[indices]
            walk_forward = []
            splitter = TimeSeriesSplit(n_splits=3)
            for wf_train, wf_test in splitter.split(train_positions):
                if len(np.unique(y[wf_train])) < 2:
                    continue
                estimator = _estimator()
                estimator.fit(Xv[wf_train], y[wf_train])
                p = estimator.predict_proba(Xv[wf_test])[:, 1]
                walk_forward.append(_metrics(y[wf_test], p))
            calibrated = CalibratedClassifierCV(_estimator(), method="sigmoid", cv=3)
            calibrated.fit(Xv[train_positions], y[train_positions])
            probabilities = calibrated.predict_proba(Xv[test_positions])[:, 1]
            key = f"{hours}h_{name}"
            evaluation = _metrics(y[test_positions], probabilities)
            models[key] = calibrated
            report["targets"][key] = {"status": "trained", "field": field,
                                      "train_samples": len(train_idx), "out_of_sample": evaluation,
                                      "walk_forward": walk_forward,
                                      "calibration": "sigmoid, yalnız eğitim bölümünde 3-fold"}
            trained_targets += 1
    if not models:
        report["reason"] = "Hiçbir hedef zaman bazlı doğrulama koşullarını sağlamadı"
        return report
    trained_before = max(int(r["signal_time"]) for r in rows)
    bundle = {"version": 1, "feature_names": FEATURE_NAMES, "models": models,
              "trained_before": trained_before, "trained_at": int(time.time() * 1000),
              "training_samples": len(rows), "report": report}
    path = Path(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    joblib.dump(bundle, temporary)
    temporary.replace(path)
    report.update({"status": "available", "trained_targets": trained_targets,
                   "trained_before": trained_before, "model_path": str(path)})
    return report


class Predictor:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._mtime: int | None = None
        self._bundle: dict | None = None

    def _load(self) -> dict | None:
        path = Path(self.model_path)
        if not path.exists():
            return None
        mtime = path.stat().st_mtime_ns
        if self._bundle is None or self._mtime != mtime:
            self._bundle = joblib.load(path)
            self._mtime = mtime
        return self._bundle

    def predict(self, analysis: dict) -> tuple[str, dict | None, int | None]:
        bundle = self._load()
        if bundle is None:
            return "insufficient_training_data", None, None
        features = extract_features(analysis)
        vector = np.array([[features[name] if features[name] is not None else np.nan
                            for name in bundle["feature_names"]]], dtype=float)
        probabilities: dict[str, dict[str, float]] = {str(h): {} for h in (24, 48, 72)}
        for key, model in bundle["models"].items():
            hours, name = key.split("h_", 1)
            probabilities[hours][name] = round(float(model.predict_proba(vector)[0, 1]), 5)
        payload = {"horizons": probabilities, "model_version": bundle["version"],
                   "trained_before": bundle["trained_before"], "training_samples": bundle["training_samples"],
                   "out_of_sample": {key: value["out_of_sample"] for key, value in bundle["report"]["targets"].items()
                                     if value.get("status") == "trained"},
                   "warning": "Olasılıklar geçmiş modele aittir; kazanç garantisi değildir. Komisyon ve veri rejimi değişimi performansı bozabilir."}
        return "available", payload, int(bundle["trained_before"])
