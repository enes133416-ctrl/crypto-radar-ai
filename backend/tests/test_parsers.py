from app.collectors.models import Market
from app.collectors.parsers import (
    DataError, parse_depth, parse_exchange_info, parse_kline_row, parse_tickers, parse_ws_kline,
    parse_open_interest, parse_funding_rates, parse_long_short_ratio, parse_taker_ratio,
)
from tests.helpers import expect_raises, kline_row, ws_kline

T0 = 1_700_000_000_000


def test_kline_closed_vs_open():
    closed = parse_kline_row(kline_row(T0), Market.SPOT, "BTCUSDT", "15m", now_ms=T0 + 2_000_000)
    assert closed.is_closed and closed.close == 104.0 and closed.quote_volume == 1030.0
    live = parse_kline_row(kline_row(T0), Market.SPOT, "BTCUSDT", "15m", now_ms=T0 + 60_000)
    assert not live.is_closed


def test_kline_safety_margin_keeps_just_closed_candle_open():
    row = kline_row(T0)
    c = parse_kline_row(row, Market.SPOT, "BTCUSDT", "15m", now_ms=row[6] + 500)
    assert not c.is_closed


def test_kline_invalid_rows_rejected():
    expect_raises(DataError, parse_kline_row, [1, 2, 3], Market.SPOT, "X", "15m", T0)
    bad_hl = kline_row(T0, h=90, l=99)
    expect_raises(DataError, parse_kline_row, bad_hl, Market.SPOT, "X", "15m", T0 + 10**7, contains="high/low")
    nan_row = kline_row(T0)
    nan_row[1] = "abc"
    expect_raises(DataError, parse_kline_row, nan_row, Market.SPOT, "X", "15m", T0 + 10**7)


def test_ws_kline_open_and_closed():
    o = parse_ws_kline(ws_kline(closed=False), Market.FUTURES)
    assert o.symbol == "BTCUSDT" and o.interval == "15m" and not o.is_closed and o.market == Market.FUTURES
    c = parse_ws_kline(ws_kline(closed=True), Market.SPOT)
    assert c.is_closed


def test_ws_kline_non_kline_and_garbage():
    expect_raises(DataError, parse_ws_kline, {"result": None, "id": 1}, Market.SPOT, contains="Kline olmayan")
    expect_raises(DataError, parse_ws_kline, "not json", Market.SPOT, contains="JSON")


def test_exchange_info_filters():
    spot = {"symbols": [
        {"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
        {"symbol": "ETHBTC", "status": "TRADING", "baseAsset": "ETH", "quoteAsset": "BTC"},
        {"symbol": "OLDUSDT", "status": "BREAK", "baseAsset": "OLD", "quoteAsset": "USDT"},
        {"symbol": "USDCUSDT", "status": "TRADING", "baseAsset": "USDC", "quoteAsset": "USDT"},
        {"broken": True},
    ]}
    out = parse_exchange_info(spot, Market.SPOT)
    assert [s.symbol for s in out] == ["BTCUSDT"]
    fut = {"symbols": [
        {"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT", "contractType": "PERPETUAL", "onboardDate": 1},
        {"symbol": "BTCUSDT_240628", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT", "contractType": "CURRENT_QUARTER"},
    ]}
    assert [s.symbol for s in parse_exchange_info(fut, Market.FUTURES)] == ["BTCUSDT"]
    expect_raises(DataError, parse_exchange_info, {"nope": 1}, Market.SPOT)


def test_tickers_skip_bad_records():
    good = {"symbol": "BTCUSDT", "lastPrice": "100", "priceChangePercent": "1.5", "highPrice": "110", "lowPrice": "90",
            "volume": "5", "quoteVolume": "500", "count": 10, "closeTime": 123}
    out = parse_tickers([good, {"symbol": "BAD"}], Market.SPOT)
    assert len(out) == 1 and out[0].price_change_pct == 1.5
    expect_raises(DataError, parse_tickers, {"x": 1}, Market.SPOT)


def test_depth_summary():
    d = parse_depth({"bids": [["99", "10"], ["98", "10"]], "asks": [["101", "5"], ["102", "5"]]}, Market.SPOT, "X")
    assert d.best_bid == 99 and d.best_ask == 101
    assert abs(d.spread_pct - 2.0) < 1e-9
    assert d.imbalance > 0  # bid tarafı daha derin
    expect_raises(DataError, parse_depth, {"bids": [], "asks": []}, Market.SPOT, "X")
    expect_raises(DataError, parse_depth, {"bids": [["105", "1"]], "asks": [["100", "1"]]}, Market.SPOT, "X", contains="tutarsız")


def test_futures_stats_parsers():
    oi = parse_open_interest({"symbol": "BTCUSDT", "openInterest": "123.4", "time": 5})
    assert oi.open_interest == 123.4
    fr = parse_funding_rates([{"symbol": "BTCUSDT", "fundingTime": 1, "fundingRate": "0.0001"}])
    assert fr[0].funding_rate == 0.0001
    tr = parse_taker_ratio([{"buySellRatio": "1.2", "buyVol": "10", "sellVol": "8", "timestamp": 9}], "BTCUSDT")
    assert tr[0].buy_sell_ratio == 1.2
    ls = parse_long_short_ratio([{"longShortRatio": "1.5", "longAccount": "0.6", "shortAccount": "0.4", "timestamp": 10}], "BTCUSDT")
    assert ls[0].long_short_ratio == 1.5 and ls[0].long_account == 0.6
    expect_raises(DataError, parse_long_short_ratio, {"symbol": "BTCUSDT"}, "BTCUSDT")
    expect_raises(DataError, parse_open_interest, {"symbol": "X"})
