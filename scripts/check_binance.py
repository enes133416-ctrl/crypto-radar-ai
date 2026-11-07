"""Gerçek Binance bağlantısını doğrular. Çalıştırma (backend klasöründe):  PYTHONPATH=. python ../scripts/check_binance.py"""
import asyncio
import sys

from app.collectors.binance_rest import BinanceAPIError, BinanceRestClient
from app.collectors.models import Market
from app.config import get_settings


async def check(market: Market, base: str) -> bool:
    c = BinanceRestClient(market, base)
    await c.start()
    ok = True
    try:
        syms = await c.exchange_info()
        print(f"[{market.value}] exchangeInfo: {len(syms)} USDT sembolü")
        t = [x for x in await c.tickers_24h() if x.symbol == "BTCUSDT"][0]
        print(f"[{market.value}] BTCUSDT fiyat={t.last_price} 24h hacim={t.quote_volume:,.0f} USDT")
        k = await c.klines("BTCUSDT", "15m", limit=5)
        print(f"[{market.value}] klines: {len(k)} mum, son mum kapalı mı={k[-1].is_closed}")
        d = await c.depth("BTCUSDT")
        print(f"[{market.value}] depth: spread={d.spread_pct:.4f}% imbalance={d.imbalance:+.2f}")
        if market == Market.FUTURES:
            print(f"[futures] openInterest={(await c.open_interest('BTCUSDT')).open_interest}")
            print(f"[futures] fundingRate={(await c.funding_rates('BTCUSDT', 1))[-1].funding_rate}")
            print(f"[futures] takerRatio={(await c.taker_long_short_ratio('BTCUSDT', '5m', 1))[-1].buy_sell_ratio}")
    except (BinanceAPIError, Exception) as e:
        print(f"[{market.value}] HATA: {e}")
        ok = False
    finally:
        await c.close()
    return ok


async def main() -> int:
    s = get_settings()
    r1 = await check(Market.SPOT, s.binance_spot_rest)
    r2 = await check(Market.FUTURES, s.binance_futures_rest)
    return 0 if (r1 and r2) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
