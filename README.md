# Crypto Radar AI

Binance Spot + USDⓈ-M Futures için analiz amaçlı kripto tarayıcı. **Otomatik emir göndermez. Yatırım tavsiyesi değildir; kâr garantisi yoktur.**

Durum: Aşama 1 (proje temeli) — tarama motoru henüz yok.

## Yerel kurulum (Windows)
Gereksinim: Python 3.12+, Node.js 20+.

Backend (`crypto-radar-ai/backend` klasöründe):
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example ..\.env
uvicorn app.main:app --reload
```
macOS/Linux: `source .venv/bin/activate` ve `cp ../.env.example ../.env`.

Frontend (`crypto-radar-ai/frontend` klasöründe, yeni terminalde):
```
npm install
npm run dev
```
Tarayıcı: http://localhost:5173 — backend: http://localhost:8000/api/health

## Testler
- Backend (`backend/` içinde): `pytest`
- Frontend (`frontend/` içinde): `npm test`

## Güvenlik
`.env` dosyasını GitHub'a yüklemeyin. Binance herkese açık veriler için API key gerekmez; key'inizi asla frontend koduna koymayın.
