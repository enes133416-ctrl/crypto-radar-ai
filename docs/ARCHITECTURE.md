# Mimari

## Veri akışı

```text
Binance public REST/WS
       │
       ▼
Collectors → parsers → validation → Memory MarketDataService ──► AnalysisService
       │                                  │                         │
       │                                  │                         ├─ AnalysisEngine
       │                                  │                         │  ├─ 5 timeframe
       │                                  │                         │  ├─ 5 strategy
       │                                  │                         │  ├─ mandatory risk
       │                                  │                         │  └─ 8-component score
       │                                  │                         ├─ SimilarityEngine
       │                                  │                         └─ ModelManager
       ▼                                  ▼                         │
SQLite candles ◄──────────────── periodic backfill                  ▼
       │                                                    Scanner cache/signals
       ├──────────────► SignalTracker → outcomes/performance          │
       └──────────────► Model training examples                       ▼
                                                              FastAPI JSON + SPA
                                                                      │
                                                                 React polling
```

## Collector ve scanner

`MarketDataService` Spot ve Futures evrenlerini `exchangeInfo` + `ticker/24hr` ile kurar; stablecoin, leveraged token ve zorunlu quote-volume filtresi uygular. Sembol sayısı `MAX_SYMBOLS_PER_MARKET` ile sınırlıdır. Discovery ve ticker belirli aralıklarla yenilenir. REST kline backfill'i kapalı mumları SQLite'a upsert eder; başarısız request kayıtlı `DataError`/API hatası üretir, sentetik fallback yoktur.

`ScannerService` her turda evreni cache üzerinden analiz eder. Canlı taramada order book zorunludur; bounded semaphore paralelliği sınırlar. Futures funding zorunlu alandır; open interest ve long/short ayrı denenir, erişilemeyen alan `null`/status olarak kalır. Aynı analiz sonucu kısa TTL ile dashboard, scanner ve coin endpoint'leri arasında paylaşılır.

## Sinyal yaşam döngüsü

1. Beş stratejiden en az biri tetiklenmeli, toplam skor eşiği geçmeli ve risk `eligible` olmalıdır.
2. Coin/market cooldown ve kalıcı `signals` satırı uygulanır.
3. `SignalTracker`, 15m kapanışlarıyla 24/48/72 saat yolu izler. MFE/MAE ve hedef öncelikleri aynı yürüyüşten çıkar.
4. Beklenen mum kapsaması <%80 veya endpoint mumu yoksa outcome `partial` kalır; erken çözüm yazılmaz.
5. Her horizon için fiyat sonucu, hedefler, Triple Barrier ve maliyetli net getiri kaydedilir.
6. Tahmin yapılırken model/feature/version/as_of tahmin loguna yazılır.

Triple Barrier: üst +%10, alt −%3 ve −%5 ayrı izlenir. Aynı mumda iki bariyer varsa sonuç `ambiguous`; performans ve eğitim muhafazakâr biçimde stop-first sayar, ambiguity ayrıca raporlanır.

## Skor ve risk

Skor bileşenleri: `volume_capital_flow(20)`, `momentum_technical(20)`, `multi_timeframe(15)`, `volatility_structure(10)`, `orderbook_trade_flow(15)`, `btc_market_regime(10)` ve `historical_similarity(10)`; risk penalty ayrıca düşülür. Benzerlik verisi yoksa son bileşen açıkça nötr 5/10'dur ve başarı ölçümü değildir. Her strateji kendi nedenlerini/risklerini döndürür.

Hard filter örnekleri: yetersiz ticker veya order book, yüksek spread, düşük derinlik/hacim, kalitesiz mum serisi, aşırı Spot–Futures farkı ve Futures funding eksikliği. AI olasılığı hard filter'ı aşmaz.

## ML ve zaman güvenliği

Feature listesi modelde sabittir. Her hedef/horizon için ayrı pipeline vardır; eğitim yalnız çözülmüş kalıcı sinyalleri kullanır. Zaman sıralı train/test, walk-forward split, sınıf kontrolü ve sigmoid calibration uygulanır. Yetersiz sınıf/örneklem durumunda hedef `insufficient` olur ve olasılık `null` döner.

Similarity komşusu yalnız `resolved_at < as_of` olan örneklerden seçilebilir. Feature standardizasyonu yalnız geçmiş eğitim örneklerine fit edilir. Böylece canlı/backtest tahmininde gelecek outcome sızıntısı önlenir.

## API ve frontend

React tarayıcıda backend IP'si/localhost çağırmaz; aynı origin `/api` kullanır. Vite geliştirmede proxy yapar, production'da FastAPI `frontend/dist` SPA'sını serve eder. Ayrı deploy'da `VITE_API_BASE` ve backend `CORS_ORIGINS` birlikte ayarlanır.

UI loading, empty, error ve insufficient-data durumlarını ayırır. Eksik AI değeri `—` gösterilir. “+%10 herhangi bir zamanda” ile “+%10 stop öncesi” ayrı metriklerdir. Grafik yalnız backend'in kapalı mumlarından oluşur.

## Güvenlik ve operasyon

- Binance yalnız public market data; trade/order endpoint yok.
- `.env` ve model/DB dosyaları Git dışında; settings endpoint'i gizli dosya yollarını döndürmez.
- CORS allowlist ve IP başına basit API rate limit vardır. Bu limit dağıtık production WAF yerine geçmez.
- `/api/health` process durumunu, `/api/data-status` collector freshness/universe/hata durumunu verir.
- External veri başlangıçta yoksa analiz endpoint'i controlled `503` döndürür; health ayakta kalır.
- SQLite tek worker için uygundur. Çoklu worker/container için ortak kalıcı DB ve tek scheduler liderliği gerekir; aksi halde duplicate scan/signal riski vardır.
