# Deployment

Bu seçenekler dokümantasyondur; depo içinden hesap açılıp deploy doğrulaması yapılmamıştır. Sağlayıcı limitleri değişebilir. Kontrol tarihi: 2026-11-08.

## 1. Render: tek servis (önerilen basit yol)

Kök `Dockerfile` frontend'i build eder ve FastAPI aynı origin'de SPA + API serve eder.

1. GitHub reposunu Render'a bağlayın.
2. **Web Service → Docker** seçin, Dockerfile path `/Dockerfile` olsun.
3. `RUN_MODE=cloud`, `COLLECTOR_ENABLED=true`, `SCANNER_ENABLED=true` ayarlayın.
4. İsteğe bağlı `DATABASE_URL=sqlite:////app/data/crypto_radar.db` ve `MODEL_PATH=/app/data/models/opportunity_models.joblib` verin.
5. Health check path `/api/health` olsun.
6. Secret gerekmiyorsa API key alanı eklemeyin. Hiçbir Binance withdrawal/trade key'i kullanılmaz.

Ücretsiz planın önemli sonuçları:

- 15 dakika idle sonrası spin-down; ilk istekte cold start olur.
- Scanner uyurken tarama/outcome üretmez; bu nedenle 7/24 değildir.
- Aylık 750 workspace saati ve küçük compute (0.1 CPU/512 MB) vardır.
- Free web service'te persistent disk yoktur; container filesystem ephemeral'dır. Restart/deploy sonrası SQLite, model ve tahmin logları kaybolabilir.
- Uptime monitor/ping yalnız cold start'ı tetiklemeye yardımcı olur; sürekli arka plan scanner'ı veya kalıcı disk sağlamaz.

Kalıcı sinyal/model geçmişi ve gerçek 7/24 işlem için persistent diskli uygun plan + tek worker veya dış kalıcı veritabanı gerekir. Birden fazla instance aynı SQLite dosyasını paylaşmamalı ve birden fazla scanner liderliği olmamalıdır.

Kaynak: https://render.com/docs/free ve https://render.com/docs/compute-plans

## 2. Ayrı backend + statik frontend

Backend'i yukarıdaki Docker servisi olarak yayınlayın. Ardından:

```bash
cd frontend
VITE_API_BASE=https://your-backend.example npm run build
```

Backend environment:

```dotenv
RUN_MODE=cloud
CORS_ORIGINS=https://your-frontend.example
```

Tarayıcı kodunda localhost backend adresi yazmayın. Frontend `VITE_API_BASE` build-time değişkenidir; değiştirdikten sonra yeniden build gerekir. Backend HTTPS olmalıdır; HTTPS sayfadan HTTP API mixed-content olarak engellenir.

### GitHub Pages

`.github/workflows/pages.yml` hazırdır:

1. Repo **Settings → Pages → Source: GitHub Actions** seçin.
2. **Variables** altında `API_BASE_URL=https://your-backend.example` oluşturun.
3. Workflow'u manuel çalıştırın veya main'e push edin.
4. Backend CORS origin'ine Pages URL'sini ekleyin.

GitHub Pages yalnız statik dosya host eder; FastAPI scanner çalıştırmaz. Proje Pages URL'si alt path kullanıyorsa SPA deep-link fallback sınırlıdır; ana sayfa üzerinden navigasyon önerilir. Yayınlanan site için 1 GB boyut ve soft 100 GB/ay bandwidth gibi platform limitleri vardır.

Kaynak: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits

### Cloudflare Pages

- Build command: `cd frontend && npm ci && npm run build`
- Output directory: `frontend/dist`
- Environment: `VITE_API_BASE=https://your-backend.example`

Cloudflare Pages Free güncel dokümanında 500 build/ay, bir concurrent build ve 20 dakika build timeout listeler. Statik hosttur; Python scanner'ı Pages içinde çalıştırmaz. Worker proxy eklenecekse Worker Free request/CPU/memory limitleri ayrıca değerlendirilmelidir.

Kaynaklar: https://developers.cloudflare.com/pages/platform/limits/ ve https://developers.cloudflare.com/workers/platform/limits/

## 3. Hugging Face Spaces

Güncel Spaces dokümanı Static Spaces'i ücretsiz listeler; Gradio/Docker compute Space oluşturmak için paid plan gerektiğini belirtir. Bu nedenle FastAPI Docker backend'inin ücretsiz HF Spaces'te çalışacağı varsayılmamalıdır. Statik frontend için Static Space mümkündür, fakat yine ayrı backend ve CORS gerekir. Docker donanımı/diski de non-persistent olabilir.

Kaynak: https://huggingface.co/docs/hub/spaces-overview

## Environment checklist

```dotenv
RUN_MODE=cloud
COLLECTOR_ENABLED=true
SCANNER_ENABLED=true
DATABASE_URL=sqlite:////app/data/crypto_radar.db
MODEL_PATH=/app/data/models/opportunity_models.joblib
CORS_ORIGINS=https://your-frontend.example
API_RATE_LIMIT_PER_MINUTE=240
```

- Free hosting küçük CPU/RAM için `MAX_SYMBOLS_PER_MARKET=20` ve `SCAN_INTERVAL_SECONDS=120` ile başlayın; likidite hard filter'larını gevşetmeyin.
- Reverse proxy gerçek client IP header'ını güvenilir biçimde sağlamalıdır. Uygulamanın basit rate limit'i WAF/DDoS koruması değildir.
- TLS sağlayıcı tarafından verilmelidir; CORS origin wildcard + credentials kullanılmaz.
- Health endpoint'i external veri varlığından bağımsız process health verir. Gerçek collector durumunu `/api/data-status` ile izleyin.
- Backup için SQLite ve model dosyalarını birlikte, tutarlı bir zamanda dış depoya alın. Free/ephemeral planda bu adım kalıcılık garantisi değildir.

## Doğrulama

Deploy sonrası:

```bash
curl -fsS https://your-backend.example/api/health
curl -fsS https://your-backend.example/api/data-status
curl -fsS https://your-backend.example/api/dashboard
```

Binance'in hosting bölgesini engellemesi, 451/403 veya network timeout mümkündür. Bu durumda mock veri açmayın; `/api/data-status` hatasını izleyin, desteklenen public REST endpoint alternatifini ayarlayın veya başka region/provider kullanın.
