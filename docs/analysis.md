# Aşama 3 — Analiz motoru

## Veri akışı ve doğruluk sınırları

1. `MarketDataService`, Spot ve Futures verisini ayrı `CandleStore` anahtarlarında tutar.
2. `AnalysisEngine`, her seriyi sembol/piyasa/zaman dilimi açısından yeniden doğrular, `is_closed=false` mumları atar ve kapanış zamanına göre sıralar. Açık mum fiyatı veya hacmi göstergeye sızdırılmaz.
3. Her zaman dilimi kendi `IndicatorSnapshot` değerini üretir. EMA200 gibi göstergeler yeterli geçmiş yoksa `None` döner; sıfır veya tahmini değer yazılmaz.
4. Beş strateji bağımsız sonuç üretir. `triggered`, `score`, `reasons`, `risks` ve `metrics` alanları arayüzde açıklanabilir.
5. Risk kontrolleri hard filtreleri belirler; skor bundan sonra hesaplanır. Hard filtresi olan coin `eligible=false` olur.
6. Sonuç, sinyalin veri zamanını (`as_of_close_time`) ve oluşturulma zamanını ayrı taşır. Fiyat/AI olasılığı uydurulmaz.

## Göstergelerin stratejideki rolü

- **RSI 7/14/21:** Dönüşte tek başına alım nedeni değildir. Önceki aşırı satım, RSI toparlanması ve en az üç ek kanıt aranır. Devam stratejisinde RSI > 80 geç kalma riskidir.
- **MACD histogramı:** Dönüşte negatif momentumun zayıflamasını, devamda mevcut yönü kontrol eder.
- **EMA 9/21/50/200:** Kısa/orta/uzun trend hizası ve fiyatın EMA21'den ATR cinsinden aşırı uzaklaşması için kullanılır.
- **Bollinger Band Width:** Önceki 60 değerin medyanına göre sıkışmayı ölçer. Dar bant tek başına kırılım sinyali değildir.
- **ATR / ATR%:** Fiyat yapısı, aşırı volatilite hard filtresi, uzama riski ve yalnız analiz amaçlı geçersizlik senaryosunda kullanılır.
- **ADX / DMI:** ADX ≥ 20 ve +DI > -DI koşulu trendin yönü/gücü içindir; ADX tek başına yön göstermez.
- **Stochastic RSI:** Anlık görünümde aşırı bölgeleri izlemek için hesaplanır; tek başına strateji tetiklemez.
- **OBV ve rolling VWAP20:** Hacim-fiyat uyumu ve son 20 mumun hacim ağırlıklı konumu içindir. VWAP20 seans VWAP'i diye sunulmaz.
- **Destek/direnç:** Son mum hariç önceki 20 mumdan hesaplanır; böylece kırılımı test eden mum kendi direncini değiştirmez.
- **Pivot / mum formasyonları:** Önceki kapalı mumdan pivot, R1, S1; yutan boğa ve çekiç yalnız dönüş doğrulamasıdır.

## Stratejiler

### A — Volume Explosion
15m kaynağında 1h/4h/24h gibi kaynak zaman diliminin desteklediği pencereler hesaplanır. 15m mumdan 5m hacim türetilmez; ilgili alan `null` olur. Son pencere, kendisi hariç önceki eşit pencerelerin ortalamasına bölünür. Ayrıca son mum z-score'u ve taker alıcı payı kullanılır. Hacim ≥ 2.5x olsa bile fiyat ilgili pencerede %5'i aşmışsa erken sinyal tetiklenmez. 10x hacim veya çok yüksek z-score sürdürülebilirlik riski üretir.

### B — Consolidation Breakout
Kapanış önceki direnç üstünde, mum üst bölgede ve hacim ≥ 1.3x olmalıdır. Bant sıkışması puanı artırır. Hacimsiz direnç aşımı `triggered=false` ve sahte kırılım riskidir.

### C — Relative Strength
Ortak 15m serilerinde 1h/4h/24h getirileri BTC ve ETH ile karşılaştırılır. Benchmark yoksa sonuç yükseliş gibi gösterilmez. Coin yükselirken benchmark düşüyorsa dayanıklılık ayrıca kaydedilir. TOTAL3/piyasa medyanı için API girişi vardır; Binance'tan doğrudan TOTAL3 alınmadığı için otomatik değer uydurulmaz.

### D — Oversold Reversal
Önce RSI ≤ 35 ve toparlanma gerekir. MACD dönüşü, pozitif uyumsuzluk adayı, destek tepkisi, taker alıcı dönüşü ve mum formasyonundan en az üç doğrulama aranır. EMA50 altı ana trend riski korunur.

### E — Momentum Continuation
EMA hizası, MACD, ADX/DMI, RSI, higher-high/higher-low, hacim ve üst zaman dilimi uyumu birlikte değerlendirilir. ATR ile 4 birimden fazla EMA21 uzaması veya RSI > 80 sinyali geç/aşırı uzamış sayar.

## Order book ve Futures

`OrderFlowAnalysis`, REST depth özetindeki spread, iki tarafın USDT derinliği, imbalance ve kapanmış mumlardaki taker buy oranını birleştirir. Order book yoksa `available=false` olur. Tek REST anlık görüntüsüyle ani emir değişimi veya büyük emirin gerçekliği ölçülemez; **spoofing tespiti iddia edilmez**. Bu akış için ayrı depth WebSocket'i sonraki geliştirme kapsamındadır.

Futures detail isteğinde son funding oranı alınır. %0.10 uyarı, %0.30 hard filtredir (varsayılanlar). Open interest ve long/short istatistik collector uçları Aşama 2'de vardır; tarihsel OI değişim stratejisi henüz skora eklenmemiştir ve eksik veri yerine sentetik değer kullanılmaz.

## BTC rejimi

15m/1h/4h/1d ağırlıkları sırasıyla 0.15/0.25/0.35/0.25'tir. EMA21/50, fiyat, MACD ve RSI 0–100 trend puanına çevrilir. 4h veya 1d ATR% ≥ 6 ya da çok zayıf puan `high_volatility_risk_off` üretir. Eksik BTC serileri confidence değerini düşürür; bilinmeyen rejim boğa kabul edilmez.

## Zorunlu risk kontrolleri

Varsayılan hard filtreler: 24s hacim < 5M USDT, spread > %0.30, zayıf order book tarafı < 50k USDT, 15m ATR% > 12, yetersiz mum, mum boşluğu, eski veri, kritik funding, 30 günden yeni Futures listelemesi ve Spot/Futures fiyat farkı > %2. Eşikler `.env` üzerinden değiştirilebilir. Her filtre kodu loglanır ve API yanıtında açıklanır.

Order book/funding erişim hatası warning ve veri kalitesi cezasıdır; değerler doğrulanmış gibi gösterilmez. 24s aşırı hareket, aşırı hacim, satıcı akışı ve ask derinliği de warning üretir.

## 100 puan

| Bileşen | Maksimum |
|---|---:|
| Hacim ve sermaye girişi | 20 |
| Momentum ve teknik göstergeler | 20 |
| Çoklu zaman dilimi uyumu | 15 |
| Volatilite ve fiyat yapısı | 10 |
| Order book ve işlem akışı | 15 |
| BTC ve piyasa rejimi | 10 |
| Geçmiş benzerlik | 10 |

Skor aralıkları: 85+ `very_strong`, 75+ `strong`, 65+ `watch`, 50+ `weak`, altı `unsuitable`. Warning başına en fazla toplam 10 puan ceza uygulanır. Geçmiş benzerlik motoru Aşama 5'e kadar `insufficient_training_data` durumunda nötr **5/10** kullanır; bu bir geçmiş başarı ölçümü değildir. AI +%5/+%10/+%15 ve zarar olasılıkları bu aşamada kesinlikle `null` döner.

## API ve kaynak kullanımı

- `GET /api/market-regime?market=spot`
- `GET /api/analysis/spot/BTCUSDT?fetch_orderbook=true`
- `GET /api/analysis/futures/BTCUSDT` (funding dahil)
- `GET /api/scan?market=spot&min_score=50&eligible_only=true&limit=100`

`/api/scan` her coin için REST depth çağırmaz; bu, Binance rate limitini korumak içindir. Sonuçta `orderbook_scope=detail_only` yazar. Detay çağrısı güncel derinlik kontrolünü yapar. Analiz senaryosundaki referans/hedef/geçersizlik değerleri emir önerisi değildir, otomatik işlem yapılmaz ve komisyon/slippage içermez.
