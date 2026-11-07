import asyncio

from app.collectors.candle_store import CandleStore
from app.collectors.models import Market
from app.collectors.parsers import parse_ws_kline
from app.config.settings import load_settings
from app.services.market_data import MarketDataService
from app.websocket.manager import ReconnectingStream, build_stream_url, chunked
from tests.helpers import no_sleep, run, ws_kline

T0 = 1_700_000_000_000
STEP = 900_000


def candle(i, closed=True, symbol="BTCUSDT"):
    return parse_ws_kline(ws_kline(symbol=symbol, t=T0 + i * STEP, closed=closed), Market.SPOT)


def test_store_keeps_open_and_closed_separate():
    s = CandleStore()
    s.apply(candle(0, closed=False))
    assert s.closed(Market.SPOT, "BTCUSDT", "15m") == []
    assert s.open_candle(Market.SPOT, "BTCUSDT", "15m") is not None
    s.apply(candle(0, closed=True))
    assert len(s.closed(Market.SPOT, "BTCUSDT", "15m")) == 1
    assert s.open_candle(Market.SPOT, "BTCUSDT", "15m") is None


def test_store_dedupes_and_orders_backfill():
    s = CandleStore()
    for i in (3, 1, 2, 2):
        s.apply(candle(i))
    times = [c.open_time for c in s.closed(Market.SPOT, "BTCUSDT", "15m")]
    assert times == sorted(set(times)) and len(times) == 3


def test_store_gap_detection():
    s = CandleStore()
    for i in (0, 1, 4):
        s.apply(candle(i))
    assert s.find_gaps(Market.SPOT, "BTCUSDT", "15m") == [(T0 + 2 * STEP, T0 + 3 * STEP)]


def test_store_max_candles():
    s = CandleStore(max_candles=5)
    for i in range(10):
        s.apply(candle(i))
    assert len(s.closed(Market.SPOT, "BTCUSDT", "15m")) == 5


def test_stream_url_and_chunk():
    assert build_stream_url("wss://h:9443/", ["a@kline_1m", "b@kline_1m"]) == "wss://h:9443/stream?streams=a@kline_1m/b@kline_1m"
    assert chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


class FakeWS:
    def __init__(self, items):
        self.items = list(items)

    async def recv(self):
        if not self.items:
            raise ConnectionError("closed by server")
        item = self.items.pop(0)
        if item == "HANG":
            await asyncio.sleep(10)
        return item


class FakeConn:
    def __init__(self, ws):
        self.ws = ws

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, *a):
        return False


def test_stream_reconnects_and_repairs():
    received, repairs = [], []
    plans = [FakeWS(["m1", "m2"]), FakeWS(["m3"]), FakeWS(["m4"])]
    attempts = []

    def connect(url):
        attempts.append(url)
        if len(attempts) == 2:
            raise OSError("connect refused")  # 2. deneme başarısız
        return FakeConn(plans.pop(0))

    holder = {}

    async def on_msg(raw):
        received.append(raw)
        if raw == "m4":
            holder["s"].stop()

    async def on_reco():
        repairs.append(len(received))

    s = ReconnectingStream("t", "wss://x", on_msg, on_reco, connect=connect, sleep=no_sleep, backoff_base=0.0)
    holder["s"] = s
    run(s.run())
    assert received == ["m1", "m2", "m3", "m4"]
    assert len(repairs) == 2 and repairs[0] == 2  # kopma sonrası her başarılı yeniden bağlantıda onarım
    assert s.reconnect_count == 2 and s.message_count == 4


def test_stream_detects_stale_connection():
    plans = [FakeWS(["HANG"]), FakeWS(["ok"])]
    got = []
    holder = {}

    async def on_msg(raw):
        got.append(raw)
        holder["s"].stop()

    s = ReconnectingStream("t", "wss://x", on_msg, connect=lambda u: FakeConn(plans.pop(0)), sleep=no_sleep, backoff_base=0.0, stale_after=0.05)
    holder["s"] = s
    run(s.run())
    assert got == ["ok"] and s.reconnect_count == 1


def test_stream_message_error_does_not_kill_connection():
    got = []
    holder = {}

    async def on_msg(raw):
        if raw == "bad":
            raise ValueError("boom")
        got.append(raw)
        holder["s"].stop()

    s = ReconnectingStream("t", "wss://x", on_msg, connect=lambda u: FakeConn(FakeWS(["bad", "good"])), sleep=no_sleep)
    holder["s"] = s
    run(s.run())
    assert got == ["good"] and s.error_count == 1


class FakeClient:
    def __init__(self, market):
        self.market = market

    async def close(self):
        pass


def test_service_ws_handling_and_streams():
    settings = load_settings({"TRACKED_INTERVALS": "15m,1h"})
    svc = MarketDataService(settings, {Market.SPOT: FakeClient(Market.SPOT)})
    run(svc.handle_ws_message(Market.SPOT, ws_kline(closed=True)))
    run(svc.handle_ws_message(Market.SPOT, {"result": None, "id": 1}))  # abonelik yanıtı sessizce yok sayılır
    run(svc.handle_ws_message(Market.SPOT, "garbage"))  # bozuk mesaj reddedilir, çökmez
    assert len(svc.store.closed(Market.SPOT, "BTCUSDT", "15m")) == 1
    from app.collectors.models import SymbolInfo
    svc.universe[Market.SPOT] = [SymbolInfo(Market.SPOT, "BTCUSDT", "BTC", "USDT", "TRADING")]
    streams = svc._build_streams(Market.SPOT)
    assert len(streams) == 1 and "btcusdt@kline_15m/btcusdt@kline_1h" in streams[0].url
    assert svc.status()["series_with_data"] == 1


def test_service_discovery_filters_by_volume():
    from app.collectors.models import SymbolInfo, Ticker24h

    class C(FakeClient):
        async def exchange_info(self):
            return [SymbolInfo(Market.SPOT, s, s[:-4], "USDT", "TRADING") for s in ("AAAUSDT", "BBBUSDT", "CCCUSDT")]

        async def tickers_24h(self):
            mk = lambda s, q: Ticker24h(Market.SPOT, s, 1, 0, 1, 1, 1, q, 1, 1)
            return [mk("AAAUSDT", 9e6), mk("BBBUSDT", 1e6), mk("CCCUSDT", 2e7)]

    svc = MarketDataService(load_settings({"MIN_QUOTE_VOLUME_24H": "5000000"}), {Market.SPOT: C(Market.SPOT)})
    out = run(svc.discover(Market.SPOT))
    assert [s.symbol for s in out] == ["CCCUSDT", "AAAUSDT"]  # hacme göre sıralı, düşük hacimli elendi
