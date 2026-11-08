from __future__ import annotations

import time

from app.collectors.models import Market
from app.config.settings import load_settings
from app.risk.filters import RiskConfig
from app.services.analysis_engine import AnalysisEngine
from app.services.scanner import ScannerService
from tests.analysis_fixtures import T0, book, make_candles, ticker


def test_live_risk_requires_orderbook_and_funding():
    engine = AnalysisEngine(RiskConfig(require_orderbook=True, require_funding=True))
    candles = {i: make_candles("XUSDT", i, [100 + j * 0.01 for j in range(240)])
               for i in ("15m", "1h", "4h", "1d")}
    result = engine.analyze(Market.FUTURES, "XUSDT", candles, ticker("XUSDT", Market.FUTURES),
                            now_ms=T0 + 100 * 86_400_000)
    codes = {f["code"] for f in result.risk.to_dict()["flags"]}
    assert "ORDERBOOK_UNAVAILABLE" in codes and "FUNDING_UNAVAILABLE" in codes
    assert not result.risk.eligible


def test_scanner_query_early_breakout_ai_and_risk_filters():
    settings = load_settings({})
    scanner = ScannerService(settings, None, None, None)  # yalnız saf sorgu; ağ/DB kullanılmaz
    engine = AnalysisEngine()
    candles = {i: make_candles("XUSDT", i, [100 + j * 0.01 for j in range(240)])
               for i in ("15m", "1h", "4h", "1d")}
    item = engine.analyze(Market.SPOT, "XUSDT", candles, ticker("XUSDT"), book("XUSDT"),
                          now_ms=candles["15m"][-1].close_time)
    item.as_of_close_time = int(time.time() * 1000)
    item.strategies[0].triggered = True
    item.strategies[0].metrics["price_change_pct"] = 3.0
    item.strategies[1].triggered = True
    item.ai_probabilities = {"horizons": {"72": {"up10": 0.8}}}
    item.ai_status = "available"
    scanner._results[Market.SPOT] = [item]
    assert scanner.query(Market.SPOT, early_only=True)["count"] == 1
    assert scanner.query(Market.SPOT, breakout_only=True)["count"] == 1
    assert scanner.query(Market.SPOT, strategy="volume_explosion")["count"] == 1
    assert scanner.query(Market.SPOT, min_ai_up10=90)["count"] == 0
    assert scanner.query(Market.SPOT, new_only=True)["count"] == 1
    scanner.stop()


def test_invalid_settings_rejected():
    try:
        load_settings({"TRACKED_INTERVALS": "2m"})
        assert False, "Geçersiz interval kabul edilmemeli"
    except ValueError as exc:
        assert "Desteklenmeyen" in str(exc)
