from fastapi.testclient import TestClient

from app.collectors.models import Market, SymbolInfo
from app.config.settings import load_settings
from app.main import app
from app.services.market_data import MarketDataService
from tests.analysis_fixtures import T0, book, make_candles, ticker


class AnalysisClient:
    def __init__(self):
        self.depth_calls = 0

    async def depth(self, symbol):
        self.depth_calls += 1
        return book(symbol)

    async def close(self):
        pass


def service():
    client = AnalysisClient()
    svc = MarketDataService(load_settings({}), {Market.SPOT: client})
    info = SymbolInfo(Market.SPOT, "TESTUSDT", "TEST", "USDT", "TRADING", onboard_date_ms=T0 - 100 * 86_400_000)
    btc_info = SymbolInfo(Market.SPOT, "BTCUSDT", "BTC", "USDT", "TRADING")
    svc.universe[Market.SPOT] = [info, btc_info]
    for symbol in ("TESTUSDT", "BTCUSDT"):
        for interval in ("15m", "1h", "4h", "1d"):
            svc.store.apply_many(make_candles(symbol, interval, [100 + i * 0.02 for i in range(240)]))
        svc.tickers.setdefault(Market.SPOT, {})[symbol] = ticker(symbol)
    return svc, client


def test_analysis_and_regime_endpoints():
    svc, client = service()
    app.state.market_data = svc
    try:
        http = TestClient(app)
        response = http.get("/api/analysis/spot/testusdt")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "TESTUSDT" and len(data["strategies"]) == 5
        assert data["order_flow"]["available"] and data["ai_probabilities"] is None
        assert client.depth_calls == 1
        assert http.get("/api/analysis/spot/NOPE").status_code == 404
        regime = http.get("/api/market-regime?market=spot")
        assert regime.status_code == 200 and regime.json()["regime"] in ("bullish", "strong_bullish")
    finally:
        app.state.market_data = None


def test_scan_does_not_call_depth_for_every_symbol_and_filters():
    svc, client = service()
    app.state.market_data = svc
    try:
        http = TestClient(app)
        response = http.get("/api/scan?market=spot&min_score=0&eligible_only=false&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data["scanned"] == 2 and data["count"] == 1 and data["total_matching"] == 2
        assert data["orderbook_scope"] == "unverified_preview" and client.depth_calls == 0
        assert http.get("/api/scan?min_score=101").status_code == 422
    finally:
        app.state.market_data = None
