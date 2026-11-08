# Doğrulama kaydı

Tarih: 2026-11-08, Arena sandbox. Aşağıdaki satırlar yalnız gerçekten çalıştırılan komutları anlatır.

| Kontrol | Sonuç |
|---|---|
| `cd backend && ../.venv/bin/python -m pytest -q` | **79 passed**, 1 deprecation warning, 4.73 s |
| `cd frontend && npm test` | **7 passed**, 3 test files |
| `cd frontend && npm run build` | Başarılı; TypeScript + Vite, 1,602 module |
| `.venv/bin/python -m pip check` | `No broken requirements found.` |
| Script/module `py_compile` | Başarılı |
| Production SPA + API TestClient smoke | `/`, `/scanner/live`, health, data-status ve settings 200; scanner kapalıyken dashboard controlled 503 |
| `python scripts/train_model.py` | Komut çalıştı; gerçek resolved sample `0`, `insufficient_training_data`; model üretilmedi |
| `python scripts/backtest.py ...` | Binance TLS/ConnectError; `data_unavailable`, exit 2; sentetik sonuç üretilmedi |
| `scripts/check_binance.py` | Spot ve Futures `ConnectError`; canlı bağlantı doğrulanamadı |
| `npm run test:e2e` | 4 senaryo browser launch öncesinde başarısız; **0 başarılı E2E iddiası yok** |
| `python scripts/create_zip.py` + bağımsız archive kontrolü | **128 dosya**; bütünlük ve secret/cache/DB exclusion kontrolleri başarılı |
| Docker build/run | Sandbox'ta Docker binary yok; doğrulanamadı |
| Render/Pages/Cloudflare/HF deploy | Hesap/deploy yapılmadı; dokümantasyon sağlandı |

## Playwright blokajı

`frontend/e2e/terminal.spec.ts` satır 40, 46, 57 ve 65'teki dört test de browser launch'da durdu:

```text
browserType.launch: Executable doesn't exist at
/home/user/.cache/ms-playwright/chromium_headless_shell-1148/chrome-linux/headless_shell
```

Browser binary bu ortamda yoktur. Normal Playwright CDN indirmesi daha önce TLS `ECONNRESET` verdi; alternatif paketli Chromium da sistemde `libnss3.so` olmadığı için çalışmadı. CI bunu `npx playwright install --with-deps chromium` ile temiz Ubuntu runner'da kurar. Yerelde de aynı komut gereklidir. Testlerin page assertion'ları bu sandbox'ta çalışmadı.

## Network blokajı

Backtest örneğindeki temel hata:

```text
app.collectors.binance_rest.BinanceAPIError:
Ağ hatası (ConnectError); Binance'e ulaşılamadı
```

Alt neden `httpcore.ConnectError: TLS/SSL connection has been closed (EOF)`. Bu sandbox yalnız izinli GitHub/npm/PyPI hostlarına outbound erişim verdiğinden gerçek Binance REST/WS entegrasyonu burada kanıtlanamadı. Parser/collector testleri fixture kullanır; canlı piyasa kanıtı değildir.

## Kapsam notları

- Backend suite; strateji matematiği, mandatory risk, outcome persistence, ambiguity, performance, time-safe similarity, model insufficient-data, scanner cooldown/risk, API ve collector unit testlerini içerir.
- Frontend suite; API hata davranışı, scanner utility'leri ve component render/filter davranışını içerir.
- Replay testi, engine'e gelecek mum verilmediğini ve girişin sonraki mum open'ı olduğunu fixture ile doğrular. Bu gerçek Binance backtest sonucu değildir.
- Boş gerçek DB'de eğitim yapılmadığı için model doğruluğu/Brier/ROC-AUC canlı başarı olarak sunulmaz.
- Free hosting sınırları dokümante edildi; gerçek uptime, persistent disk veya 7/24 tarama garantisi verilmez.

Yeniden üretmek için README'deki komutları kullanın. Başarısız adımları “geçti” olarak raporlamayın; canlı bağlantı ve browser testlerini kendi ortamınızda ayrıca koşun.
