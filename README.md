# Crypto Radar AI

Binance Spot + USDⓈ-M Futures için analiz amaçlı kripto tarayıcı. **Otomatik emir göndermez. Yatırım tavsiyesi değildir; kâr garantisi yoktur.**

Durum: Aşama 3 (analiz motoru) tamamlandı. Frontend henüz başlangıç iskeletindedir; AI/backtest Aşama 5'te geliştirilecektir.

Veri toplama: Spot ve Futures için coin keşfi (24s hacim filtresi), REST mum geçmişi, WebSocket canlı mumlar, otomatik yeniden bağlanma ve kopma sonrası boşluk onarımı.
Analiz: RSI/MACD/EMA/Bollinger/ATR/ADX/StochRSI/OBV/VWAP, beş bağımsız strateji, hacim anomalisi, order book/taker akışı, BTC piyasa rejimi, zorunlu risk filtreleri ve açıklanabilir 100 puan skoru. Yalnız kapanmış mumlar kullanılır.
Uç noktalar: `/api/health`, `/api/data-status`, `/api/symbols?market=spot`, `/api/klines/spot/BTCUSDT?interval=15m`, `/api/market-regime?market=spot`, `/api/analysis/spot/BTCUSDT`, `/api/scan?market=spot&min_score=50`.
`/api/scan` rate limit nedeniyle her sembol için REST order book çekmez; eksik derinlik kontrolünü açıkça bildirir. Coin detayı `/api/analysis/...` güncel order book ve Futures funding kontrolü yapar. AI olasılıkları eğitim verisi olmadan `null` ve `insufficient_training_data` döner.
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

## Analiz motoru
Strateji mantıkları, filtre eşikleri, skor bileşenleri ve bilinen sınırlar için [`docs/analysis.md`](docs/analysis.md) dosyasına bakın. Ayarların tamamı `.env.example` içindedir. Skor; likidite, spread, derinlik, veri yeterliliği ve güncellik kontrollerinden ayrıdır: hard filtreyi geçemeyen sonuç `eligible=false` olur ve varsayılan taramada öne çıkarılmaz.

## Güvenlik
`.env` dosyasını GitHub'a yüklemeyin. Binance herkese açık veriler için API key gerekmez; key'inizi asla frontend koduna koymayın.
