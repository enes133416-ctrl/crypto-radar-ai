from fastapi.testclient import TestClient

from app.collectors.candle_store import CandleStore
from app.collectors.models import Market, SymbolInfo
from app.collectors.parsers import parse_ws_kline
from app.config.settings import load_settings
from app.main import app
from app.services.market_data import MarketDataService
from tests.helpers import ws_kline


def test_health_ok():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_endpoints_503_when_collector_off():
    app.state.market_data = None
    c = TestClient(app)
    assert c.get("/api/data-status").json() == {"enabled": False, "scanner": None}
    assert c.get("/api/symbols").status_code == 503


def test_klines_endpoint_with_service():
    svc = MarketDataService(load_settings({}), {Market.SPOT: object()})
    svc.universe[Market.SPOT] = [SymbolInfo(Market.SPOT, "BTCUSDT", "BTC", "USDT", "TRADING")]
    svc.store.apply(parse_ws_kline(ws_kline(closed=True), Market.SPOT))
    app.state.market_data = svc
    c = TestClient(app)
    r = c.get("/api/klines/spot/btcusdt?interval=15m")
    assert r.status_code == 200 and len(r.json()["closed"]) == 1 and r.json()["open_candle"] is None
    assert c.get("/api/klines/spot/btcusdt?interval=2m").status_code == 400
    assert c.get("/api/klines/foo/btcusdt").status_code == 400
    assert c.get("/api/klines/spot/ETHUSDT?interval=15m").status_code == 404
    assert c.get("/api/symbols?market=spot").json()["count"] == 1
    app.state.market_data = None
