# Outcome, performans ve backtest metodolojisi

## Zaman ve giriş

Canlı sinyalin referans zamanı son kapalı 15m mumun close time'ıdır. Tarihsel replay her adımda yalnız o zamana kadar kapanmış serileri engine'e verir ve **bir sonraki 15m mumun open fiyatından** girer. Bu, sinyal mumunun kapanışını bilmeden aynı fiyattan girme look-ahead'ini önler.

24/48/72 saat horizon'ları sırasıyla 96/192/288 adet 15m mum demektir. Endpoint yakınında kapalı mum yoksa veya beklenen kapsama <%80 ise sonuç çözülmez. Eksik mum “0 getiri” sayılmaz.

## Ölçülen alanlar

- `price_{24,48,72}h`: horizon endpoint fiyatı
- `return_pct`, `net_return_pct`: brüt ve `ROUND_TRIP_COST_PCT` sonrası getiri
- `mfe_pct`, `mae_pct`: giriş sonrası horizon'a kadar maksimum olumlu/olumsuz hareket
- `target_5_hit`, `target_10_hit`, `target_15_hit`: herhangi bir anda hedefe ulaşma
- `up10_before_stop3`, `up10_before_stop5`: +%10'un ilgili stop'tan önce gelmesi
- `triple_barrier_stop3`, `triple_barrier_stop5`: target/stop/timeout/ambiguous sonucu
- `bars_observed`, `coverage_ratio`, `resolved_at`: kanıt kapsamı ve sonucun ne zaman bilindiği

Aynı mumun high ve low değeri iki bariyeri birden kesiyorsa mum içi sıra bilinmez. Sonuç `ambiguous` olarak saklanır. Win-rate ve eğitim etiketi muhafazakâr `stop-first` kabul eder; ambiguity oranı raporda ayrıdır. Bu yaklaşım iyimser sonuç üretmez ama gerçek tick sırasını bildiğini iddia etmez.

## Performans raporu

Rapor overall, piyasa, coin ve strateji kırılımlarını içerir:

- örneklem `n`, win rate, average/median net return;
- target hit rate ve stop-before-target oranı;
- MFE/MAE, ambiguity ve coverage;
- Wilson score güven aralığı ve yetersiz örneklem durumu.

Küçük `n` ile yüksek yüzde “kanıtlanmış edge” olarak sunulmaz. Hiç çözülmüş sinyal yoksa rapor empty/insufficient döner; sıfır getirili sentetik satır üretilmez.

## ML hedefleri

Her horizon için ayrı hedefler:

1. +%5 herhangi bir anda;
2. +%10 herhangi bir anda;
3. +%15 herhangi bir anda;
4. +%10, −%5 stop'tan önce.

Dolayısıyla “+%10 gerçekleşti” ile “+%10 stop öncesi gerçekleşti” karıştırılmaz. Modeller ayrı eğitilir, zaman sıralı holdout/walk-forward ve kalibrasyon metrikleri model kartına yazılır. Eğitim verisi azsa model dosyası ve rastgele olasılık üretilmez.

## Replay komutları

```bash
python scripts/backtest.py --market spot --symbol BTCUSDT --limit 1000 --step-bars 4
python scripts/backtest.py --market futures --symbol ETHUSDT --limit 1000 --step-bars 4 --output data/eth-replay.json
```

`--step-bars 4`, 15m primary üzerinde saatte bir analiz demektir. Minimum 180, maksimum 1000 mum alınır. 72h outcome için sinyal sonrası 288 kapalı 15m mum gerekir; veri setinin sonundaki sinyaller açık kalır ve istatistiğe resolved gibi eklenmez.

## Bilinen sınırlar

- Public historical klines, geçmiş her andaki order-book snapshot'ını veya o andaki funding/long-short tick'ini vermez. Replay bu alanları `unavailable` bırakır; bugünkü değeri geçmişe kopyalamaz.
- OHLCV replay, gerçek emir defteri kaymasını, queue priority'yi ve tick-by-tick likidasyonu simüle etmez.
- Round-trip cost sabit bir yaklaşıktır; gerçek fee/slippage raporu değildir.
- Tek sembol CLI araştırma aracıdır. Çok coinli portföy equity curve, korelasyonlu pozisyon limiti ve otomatik trade execution içermez.
- Binance erişimi yoksa komut `data_unavailable` ve exit code `2` verir. Test fixture'ları backtest kanıtı olarak raporlanmaz.
