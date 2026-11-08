"""Teslim ZIP'i oluşturur ve içerik/gizli dosya kontrolü yapar.

Kök klasörde: python scripts/create_zip.py
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "crypto-radar-ai.zip"
EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "data", "__pycache__",
                 ".pytest_cache", ".mypy_cache", ".ruff_cache", "test-results", "playwright-report", ".idea", ".vscode"}
EXCLUDED_FILES = {".env", "crypto-radar-ai.zip", ".DS_Store"}
REQUIRED = ["README.md", ".env.example", "backend/app/main.py", "backend/requirements-lock.txt",
            "frontend/package.json", "frontend/package-lock.json", "docker-compose.yml", "Dockerfile"]


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    private_env = path.name.startswith(".env") and path.name != ".env.example"
    return path.is_file() and not private_env and not any(part in EXCLUDED_DIRS for part in relative.parts) and path.name not in EXCLUDED_FILES \
        and not path.name.endswith((".pyc", ".pyo", ".db", ".joblib", ".log"))


def main() -> int:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        print(f"Zorunlu dosyalar eksik: {missing}", file=sys.stderr)
        return 1
    files = [p for p in ROOT.rglob("*") if included(p)]
    if sum(p.stat().st_size for p in files) > 100_000_000:
        print("ZIP kaynak dosyaları toplam 100 MB sınırını aşıyor", file=sys.stderr)
        return 1
    # Gerçek secret'ları teslim etme. Örnek/dokümantasyondaki API key kelimeleri sorun değildir.
    secret_pattern = re.compile(rb"(?:api[_-]?secret|binance[_-]?secret|private[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{20,}", re.I)
    for path in files:
        if path.stat().st_size > 5_000_000:
            print(f"ZIP için fazla büyük dosya: {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        if path.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".json", ".md", ".yml", ".yaml", ".example", ".env"}:
            if secret_pattern.search(path.read_bytes()):
                print(f"Olası gizli anahtar: {path.relative_to(ROOT)}", file=sys.stderr)
                return 1
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            archive.write(path, Path("crypto-radar-ai") / path.relative_to(ROOT))
    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad:
            print(f"Bozuk ZIP üyesi: {bad}", file=sys.stderr)
            return 1
        names = archive.namelist()
        if any(("/.env" in name and not name.endswith("/.env.example")) or "node_modules/" in name for name in names):
            print("ZIP güvenlik kontrolü başarısız", file=sys.stderr)
            return 1
    print(f"Oluşturuldu: {OUTPUT} · {len(files)} dosya · {OUTPUT.stat().st_size / 1024:.1f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
