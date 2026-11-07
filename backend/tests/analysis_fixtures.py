from __future__ import annotations

from app.collectors.models import INTERVAL_MS, Candle, Market, OrderBookSummary, Ticker24h

T0 = 1_700_000_000_000


def make_candles(symbol: str, interval: str, closes: list[float], market: Market = Market.SPOT,
                 volume: float = 100.0, buy_ratio: float = 0.6, volumes: list[float] | None = None) -> list[Candle]:
    step = INTERVAL_MS[interval]
    out = []
    previous = closes[0]
    for i, close in enumerate(closes):
        open_price = previous if i else close * 0.999
        vol = volumes[i] if volumes else volume
        out.append(Candle(market, symbol, interval, T0 + i * step, T0 + (i + 1) * step - 1,
                          open_price, max(open_price, close) * 1.003, min(open_price, close) * 0.997,
                          close, vol, vol * close, 100, vol * buy_ratio, vol * close * buy_ratio, True))
        previous = close
    return out


def flat_then_breakout(symbol: str = "TESTUSDT") -> list[Candle]:
    closes = [100 + (0.08 if i % 2 else -0.08) for i in range(119)] + [103.0]
    volumes = [100.0] * 119 + [500.0]
    return make_candles(symbol, "15m", closes, volumes=volumes)


def ticker(symbol: str = "TESTUSDT", market: Market = Market.SPOT, quote_volume: float = 20_000_000) -> Ticker24h:
    return Ticker24h(market, symbol, 100, 2, 105, 95, 200_000, quote_volume, 1000, T0 + 100_000_000)


def book(symbol: str = "TESTUSDT", market: Market = Market.SPOT) -> OrderBookSummary:
    return OrderBookSummary(market, symbol, 99.99, 100.01, 0.02, 200_000, 180_000, 0.0526)
