# Crypto Radar AI

Binance **Spot + USDⓈ-M Futures** piyasalarını tarayan, beş stratejiyi ve zorunlu risk kontrollerini birleştiren gerçek zamanlı fırsat terminali. FastAPI, SQLite, React, TypeScript ve Lightweight Charts kullanır.

**Bu proje otomatik alım-satım yapmaz.** Sinyal, AI olasılığı ve 3R senaryosu yalnız analizdir; emir API'si veya özel API anahtarı kullanılmaz. Geçmiş performans gelecek kazanç garantisi değildir.

## Özellikler

- Public Binance REST/WS ile 15m–1d kapalı mumlar, 24s ticker, order book, funding, open interest, taker ve global long/short oranları.
- Hacim Patlaması, Breakout, Relative Strength, Oversold Reversal ve Trend Momentum stratejileri.
- Likidite, spread, derinlik, veri kalitesi, ATR/volatilite ve Spot–Futures farkı kontrolleri; order book yoksa canlı sinyal üretilmez.
- Dashboard, Live/Early/Breakout/Spot/Futures Scanner, AI Predictions, Historical Performance, Market Overview, Settings ve coin detayları.
- 24/48/72 saat sonuçları, MFE/MAE, +%5/+%10/+%15, +%10'un −%3/−%5'ten önce gelmesi ve Triple Barrier etiketleri.
- Ayrı hedef/horizon modelleri, walk-forward değerlendirme, olasılık kalibrasyonu, model kartı ve tahmin logları.
- Yalnız o anda sonucu bilinen geçmiş sinyallerle nearest-neighbor benzerlik ve örneklem sayıları.
- SQLite kalıcılığı, periyodik discovery/ticker yenileme, scanner, signal tracking, polling, CORS ve basit API rate limit.
- Backend/frontend birim ve entegrasyon testleri, Playwright E2E senaryoları, CI, Docker ve temiz ZIP komutu.

> İlk açılışta model veya sinyal yoksa arayüz bunu açıkça gösterir. Rastgele olasılık, sahte mum, demo başarısı veya mock veri canlı veri gibi sunulmaz. `DEMO_MODE` yalnız açık etiket içindir; sentetik piyasa verisi üretmez.

## Hızlı başlangıç

Gereksinimler: Python 3.11+ (CI/Docker 3.12), Node.js 22+, npm.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # tam transitive lock
cp .env.example .env               # Windows: copy .env.example .env

cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

İkinci terminalde, depo kökünden:

```bash
cd frontend
npm ci
npm run dev
```

- Arayüz: http://localhost:5173
- API/Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/health
- Data status: http://localhost:8000/api/data-status

Vite, tarayıcıdaki `/api` isteklerini backend'e proxy eder. İlk discovery/backfill coin sayısına ve Binance erişimine bağlı olarak birkaç dakika sürebilir. Bu sürede API `starting`/veri-yok durumunu döndürür; eski veya uydurma sinyal göstermez.

### Tek komutla production build

```bash
cd frontend && npm ci && npm run build && cd ..
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`frontend/dist` varsa FastAPI onu `/` altında serve eder; SPA route'ları desteklenir. Tek origin kullanımında ek CORS ayarı gerekmez.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

http://localhost:8000 açılır. Frontend imaj içinde build edilir, `radar_data` volume'u SQLite ve model dosyasını korur. Konteyner non-root kullanıcıyla çalışır ve healthcheck içerir.

> Docker Hub imajı yayınlanmadı; Compose yerel Docker build yapar. Bu depo içinde Docker daemon bulunmayan ortamda imaj çalıştırması doğrulanmamıştır.

## Yapılandırma

Tüm ayarlar `.env.example` içinde açıklanmıştır. Gerçek `.env`, `.env.*`, `data/`, `*.db` ve `*.joblib` Git dışındadır.

| Ayar | Varsayılan | Anlamı |
|---|---:|---|
| `RUN_MODE` | `local` | `local` veya `cloud` |
| `DATABASE_URL` | `sqlite:///./data/crypto_radar.db` | Kalıcı SQLite yolu |
| `COLLECTOR_ENABLED` | `true` | Gerçek Binance collector yaşam döngüsü |
| `SCANNER_ENABLED` | `true` | Sürekli tarayıcı ve sinyal/outcome worker'ları |
| `MAX_SYMBOLS_PER_MARKET` | `80` | Piyasa başına discovery üst sınırı |
| `BACKFILL_LIMIT` | `600` | Zaman dilimi başına REST kline sayısı, 1–1000 |
| `SCAN_INTERVAL_SECONDS` | `60` | Cache'li canlı tarama aralığı |
| `DISCOVERY_INTERVAL_SECONDS` | `300` | Evren/ticker yenileme aralığı |
| `SCAN_ORDERBOOK_CONCURRENCY` | `12` | Paralel order-book istek sınırı |
| `SIGNAL_MIN_SCORE` | `50` | Minimum fırsat skoru |
| `SIGNAL_COOLDOWN_HOURS` | `4` | Aynı coin/market için yeni sinyal bekleme süresi |
| `MIN_QUOTE_VOLUME_24H` | `10000000` | Minimum 24s quote hacim |
| `MAX_SPREAD_PCT` | `0.15` | Maksimum spread yüzdesi |
| `MIN_ORDERBOOK_DEPTH_QUOTE` | `100000` | Zorunlu zayıf-taraf derinliği |
| `ROUND_TRIP_COST_PCT` | `0.15` | Net performanstan düşülen gidiş-dönüş maliyeti |
| `ML_MIN_SAMPLES` | `200` | Her model için minimum gerçek çözülmüş örnek |
| `CORS_ORIGINS` | localhost listesi | Ayrı frontend origin'leri, virgülle ayrılır |
| `API_RATE_LIMIT_PER_MINUTE` | `240` | IP başına basit API limiti |

Public veri için `BINANCE_API_KEY` veya secret gerekmez. Binance bölgesel olarak engelliyse alternatif public REST hostunu `BINANCE_SPOT_REST` / `BINANCE_FUTURES_REST` ile verebilirsiniz; WS discovery/klines ayrıca REST üzerinden beslenir.

## ML eğitimi

Model eğitimi sunucu açılırken rastgele veriyle yapılmaz. Önce scanner gerçek sinyalleri kaydetmeli ve 24/48/72 saat sonuçları çözülmelidir:

```bash
python scripts/train_model.py
```

Yeterli veri yoksa komut `insufficient_training_data` raporu verir ve model üretmez. Yeterli veri varsa ayrı `24/48/72 × +5/+10/+15/+10-before-stop5` hedefleri eğitilir; zaman sıralı holdout, walk-forward kontrolleri ve sigmoid kalibrasyon raporlanır. Model ve model kartı `data/models/` altında tutulur, Git'e eklenmez.

## Gerçek backtest

```bash
python scripts/backtest.py --market spot --symbol BTCUSDT --limit 1000 --step-bars 4
python scripts/backtest.py --market futures --symbol ETHUSDT --output data/backtest-eth.json
```

Her analiz yalnız o andaki kapalı mum dilimini görür; giriş sonraki 15m mumun açılışındadır ve maliyet uygulanır. Tarihsel order-book/funding tick verisi public klines ile geri getirilemediğinden bu alanlar replay'de `unavailable` olarak raporlanır; canlı likidite sonucu taklit edilmez. Binance erişilemezse exit code `2` ve `data_unavailable` döner, sentetik rapor üretilmez.

Metodoloji: [docs/BACKTESTING.md](docs/BACKTESTING.md).

## Testler

```bash
# Backend
cd backend && ../.venv/bin/python -m pytest -q && cd ..

# Frontend unit/component + production build
cd frontend && npm test && npm run build

# Gerçek browser E2E; bir kez browser kurun
npx playwright install --with-deps chromium
npm run test:e2e
```

Vitest yalnız `frontend/tests/` dosyalarını çalıştırır; Playwright dosyaları ayrıdır. E2E gerçek Chromium'da Vite arayüzünü açar ve kontrollü API route fixture'larıyla tablet/mobil navigasyon, filtre/grafik ve API hata durumlarını sınar. Bunlar UI test fixture'larıdır; canlı Binance veya gerçek model başarısı değildir. Gerçek FastAPI entegrasyonu backend testleri ve production SPA/API smoke kontrolüyle ayrıca sınanır.

CI workflow'ları:

- `.github/workflows/test.yml`: her push/PR'da backend, frontend/build ve Chromium E2E.
- `.github/workflows/live-smoke.yml`: manuel gerçek Binance REST kontrolü; runner bölgesi engellenirse açık başarısızlık verir.
- `.github/workflows/pages.yml`: main'e push veya manuel çalıştırmada statik frontend'i Pages'e deploy eder.

## Ücretsiz yayınlama

En basit ücretsiz mimari: **Render Web Service** (tek Dockerfile, frontend+backend) ve frontend'i isteğe bağlı Cloudflare/GitHub Pages'e ayırmak.

Render Free önemli sınırları: 15 dakika istek gelmezse uyku, aylık 750 workspace saati, 0.1 CPU/512 MB ve **ephemeral dosya sistemi**. Uyku scanner'ı durdurur; yeniden başlatmada boş/ephemeral SQLite ile sinyal ve model kaybolabilir. Bu nedenle ücretsiz Render “7/24 kalıcı scanner” değildir. Gerçek süreklilik için diskli ücretli servis veya dış kalıcı veritabanı/worker gerekir. Uptime ping'leri sadece web isteği geldiğinde uyanmayı tetikler ve ücretsiz donanım sınırlarını kaldırmaz.

Ayrı frontend/backend için:

1. Backend'i Dockerfile ile yayınlayın ve gerçek HTTPS origin'ini alın.
2. Backend `CORS_ORIGINS=https://frontend-domain` ayarlayın.
3. Frontend build'de `VITE_API_BASE=https://backend-domain` kullanın.
4. Pages workflow için repo variable `API_BASE_URL` tanımlayın; Pages kaynağını GitHub Actions seçin.

Hugging Face güncel dokümanında Static Spaces ücretsizdir; Gradio/Docker compute Space oluşturma ücretli plan gerektirebilir. Bu yüzden “ücretsiz Docker backend” varsayılmamalıdır. Ayrıntılar ve alternatifler: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Yayınlama ortamları bu depo içinden deploy edilip doğrulanmamıştır.

## API özeti

- `GET /api/health`, `/api/data-status`, `/api/dashboard`
- `GET /api/scan?market=all&min_score=50&eligible_only=true`
- `GET /api/early-signals`, `/api/breakouts`, `/api/signals`
- `GET /api/analysis/{market}/{symbol}`
- `GET /api/klines/{market}/{symbol}?interval=15m&limit=300`
- `GET /api/predictions`, `/api/performance`, `/api/market-regime`, `/api/settings`

Scanner sorguları `market`, `min_score`, `eligible_only`, `strategy`, `new_only`, `risk`, `min_ai_up10`, `early_only`, `breakout_only` ve `limit` destekler. Frontend filtreleri bu gerçek endpoint parametreleri üzerinden çalışır. Başlangıç sürerken analiz endpoint'leri `503` ve yeniden deneme bilgisi verir. Başarısız external veri `null`/error olarak kalır; HTTP 200 ile uydurma fallback dönmez.

## Mimari ve teslim

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/BACKTESTING.md](docs/BACKTESTING.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/VERIFICATION.md](docs/VERIFICATION.md)

Temiz teslim ZIP'i:

```bash
python scripts/create_zip.py
```

`crypto-radar-ai.zip`; `.git`, `.env`, virtualenv, node_modules, build, cache, veritabanı, model ve büyük/geçici dosyaları içermez. Script gerekli dosyaları, secret desenlerini, boyutları ve ZIP bütünlüğünü doğrular.
