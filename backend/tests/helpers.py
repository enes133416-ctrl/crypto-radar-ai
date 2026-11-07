import asyncio


def expect_raises(exc_type, fn, *args, contains: str | None = None, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type as e:
        if contains:
            assert contains in str(e), f"Mesaj '{contains}' içermiyor: {e}"
        return e
    raise AssertionError(f"{exc_type.__name__} bekleniyordu")


def run(coro):
    return asyncio.run(coro)


async def no_sleep(_):
    return None


def kline_row(open_time=1_700_000_000_000, step=900_000, o=100, h=105, l=99, c=104, v=10, q=1030, n=50):
    return [open_time, str(o), str(h), str(l), str(c), str(v), open_time + step - 1, str(q), n, "4", "410", "0"]


def ws_kline(symbol="BTCUSDT", interval="15m", t=1_700_000_000_000, closed=False, c=104.0):
    return {"stream": f"{symbol.lower()}@kline_{interval}", "data": {"e": "kline", "E": t + 5, "s": symbol, "k": {
        "t": t, "T": t + 899_999, "s": symbol, "i": interval, "o": "100", "c": str(c), "h": "105", "l": "99",
        "v": "10", "n": 50, "x": closed, "q": "1030", "V": "4", "Q": "410"}}}
