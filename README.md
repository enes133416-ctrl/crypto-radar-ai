# Crypto Radar AI

Binance Spot + USDⓈ-M Futures için analiz amaçlı kripto tarayıcı. **Otomatik emir göndermez. Yatırım tavsiyesi değildir; kâr garantisi yoktur.**

Durum: Aşama 2 (Binance veri toplama) — strateji/skor motoru henüz yok.

Veri toplama: Spot ve Futures için coin keşfi (24s hacim filtresi), REST mum geçmişi, WebSocket canlı mumlar, otomatik yeniden bağlanma ve kopma sonrası boşluk onarımı.
Uç noktalar: `/api/health`, `/api/data-status`, `/api/symbols?market=spot`, `/api/klines/spot/BTCUSDT?interval=15m`.
Gerçek bağlantı kontrolü (backend klasöründe): `PYTHONPATH=. python ../scripts/check_binance.py`
Binance bazı ülkelerde/sunucularda HTTP 451 ile erişimi engeller; bu durumda durum ekranında açık hata görünür, sahte veri gösterilmez.

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
