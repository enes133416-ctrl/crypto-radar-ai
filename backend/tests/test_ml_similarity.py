from __future__ import annotations

from app.ml.features import FEATURE_NAMES, extract_features
from app.ml.model import TARGETS, Predictor, train_models
from app.ml.similarity import SimilarityAnalyzer


def training_rows(count=90):
    rows = []
    for i in range(count):
        features = {name: float((i % 11) + j) for j, name in enumerate(FEATURE_NAMES)}
        row = {"id": i + 1, "status": "resolved", "signal_time": 1_000_000 + i * 1000,
               "resolved_at": 1_000_000 + i * 1000 + 72 * 3_600_000,
               "symbol": "XUSDT", "market": "spot", "strategy": "volume_explosion", "score": 70,
               "features": features}
        for targets in TARGETS.values():
            for field in targets.values():
                row[field] = int((i + len(field)) % 3 != 0)
        for hours in (24, 48, 72):
            row[f"net_return_{hours}h"] = 2.0
        rows.append(row)
    return rows


def test_training_is_insufficient_without_resolved_samples(tmp_path):
    report = train_models([], str(tmp_path / "model.joblib"), min_samples=200)
    assert report["status"] == "insufficient_training_data"
    predictor = Predictor(str(tmp_path / "missing.joblib"))
    assert predictor.predict({})[0] == "insufficient_training_data"


def test_training_walk_forward_calibration_and_prediction(tmp_path):
    path = tmp_path / "model.joblib"
    rows = training_rows()
    report = train_models(rows, str(path), min_samples=60)
    assert report["status"] == "available" and report["trained_targets"] > 0
    assert all(value.get("out_of_sample") for value in report["targets"].values() if value["status"] == "trained")
    status, probabilities, cutoff = Predictor(str(path)).predict({})
    assert status == "available" and cutoff == max(r["signal_time"] for r in rows)
    assert probabilities["horizons"]
    assert all(0 <= p <= 1 for values in probabilities["horizons"].values() for p in values.values())


def test_similarity_excludes_unresolved_future_and_returns_intervals():
    rows = training_rows(20)
    as_of = rows[-1]["signal_time"] + 1000
    # Yalnız ilk 15 satırın sonucu as_of anında biliniyor.
    for i, row in enumerate(rows):
        row["resolved_at"] = 1 if i < 15 else as_of + 10_000
    result = SimilarityAnalyzer(min_neighbors=10, neighbors=10).analyze(rows[0]["features"], rows, as_of)
    assert result["status"] == "available" and result["samples"] == 10
    assert result["horizons"]["72"]["wilson_95"][0] is not None
    assert len(result["neighbors"]) == 10


def test_feature_extraction_has_stable_schema_and_no_nan():
    features = extract_features({})
    assert list(features) == FEATURE_NAMES
    assert features["regime_score"] == 40 and features["triggered_strategy_count"] == 0
    assert all(value is None for name, value in features.items()
               if name not in {"regime_score", "triggered_strategy_count"})
