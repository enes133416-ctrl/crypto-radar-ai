"""Çözülmüş sinyallerden ayrı, zaman-güvenli ML eğitimi.

Kullanım (backend/ içinde): PYTHONPATH=. python ../scripts/train_model.py
Sunucu scanner'ı bu komutu kendiliğinden çalıştırmaz.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.database.sqlite import Database
from app.ml.model import train_models


def main() -> int:
    settings = get_settings()
    db = Database(settings.database_url)
    try:
        rows = db.resolved_training_rows()
        report = train_models(rows, settings.model_path, settings.ml_min_samples)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        # Yetersiz gerçek eğitim verisi beklenen, dürüst bir sonuçtur; komut hatası değildir.
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
