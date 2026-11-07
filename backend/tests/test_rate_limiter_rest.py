from app.collectors.binance_rest import BinanceAPIError, BinanceRestClient
from app.collectors.models import Market
from app.collectors.rate_limiter import WeightLimiter
from tests.helpers import expect_raises, kline_row, no_sleep, run


class FakeResp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeHTTP:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    async def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make(responses, market=Market.SPOT, sleeps=None):
    async def sleep(d):
        if sleeps is not None:
            sleeps.append(d)

    return BinanceRestClient(market, "https://x.test", http=FakeHTTP(responses), limiter=WeightLimiter(10_000), sleep=sleep, clock_ms=lambda: 1_700_000_000_000 + 10**7)


def test_limiter_blocks_until_window_frees():
    now = [0.0]
    sleeps = []

    async def fake_sleep(d):
        sleeps.append(d)
        now[0] += d

    async def go():
        lim = WeightLimiter(10, window_s=60, clock=lambda: now[0], sleep=fake_sleep)
        await lim.acquire(6)
        await lim.acquire(4)
        await lim.acquire(5)  # pencere dolu: beklemeli
    run(go())
    assert sleeps and abs(sum(sleeps) - 60) < 0.5


def test_limiter_rejects_oversize():
    expect_raises(ValueError, lambda: run(WeightLimiter(5).acquire(6)))


def test_klines_success_and_url():
    c = make([FakeResp(200, [kline_row(1_700_000_000_000)])])
    out = run(c.klines("BTCUSDT", "15m", limit=1))
    assert len(out) == 1 and out[0].is_closed
    url, params = c._http.calls[0]
    assert url == "https://x.test/api/v3/klines" and params["symbol"] == "BTCUSDT"


def test_futures_paths():
    c = make([FakeResp(200, {"symbol": "BTCUSDT", "openInterest": "1", "time": 2})], market=Market.FUTURES)
    run(c.open_interest("BTCUSDT"))
    assert c._http.calls[0][0].endswith("/fapi/v1/openInterest")
    spot = make([])
    expect_raises(ValueError, lambda: run(spot.open_interest("BTCUSDT")))


def test_retry_on_429_uses_retry_after():
    sleeps = []
    c = make([FakeResp(429, {"msg": "slow"}, {"Retry-After": "7"}), FakeResp(200, [])], sleeps=sleeps)
    assert run(c._get("/x")) == []
    assert sleeps == [7.0]


def test_retry_on_5xx_then_give_up():
    sleeps = []
    c = make([FakeResp(503)] * 4, sleeps=sleeps)
    e = expect_raises(BinanceAPIError, lambda: run(c._get("/x")))
    assert e.status == 503 and len(c._http.calls) == 4 and sleeps == [1.0, 2.0, 4.0]


def test_region_block_not_retried():
    c = make([FakeResp(451, {"msg": "restricted"})])
    e = expect_raises(BinanceAPIError, lambda: run(c._get("/x")), contains="bölge")
    assert e.status == 451 and len(c._http.calls) == 1


def test_ip_ban_418_not_retried():
    c = make([FakeResp(418)])
    expect_raises(BinanceAPIError, lambda: run(c._get("/x")), contains="engellendi")
    assert len(c._http.calls) == 1


def test_api_error_message_parsed():
    c = make([FakeResp(400, {"code": -1121, "msg": "Invalid symbol."})])
    e = expect_raises(BinanceAPIError, lambda: run(c._get("/x")))
    assert e.code == -1121 and "Invalid symbol" in e.message


def test_network_error_retried_then_reported():
    c = make([OSError("down")] * 4)
    expect_raises(BinanceAPIError, lambda: run(c._get("/x")), contains="Ağ hatası")
    assert len(c._http.calls) == 4
