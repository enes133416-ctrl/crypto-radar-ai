from app.collectors.models import INTERVAL_MS, Market, SymbolInfo
from app.services.analysis_engine import AnalysisEngine
from tests.analysis_fixtures import T0, book, make_candles, ticker


def dataset(symbol="TESTUSDT", market=Market.SPOT):
    closes = [100 + i * 0.03 for i in range(240)]
    return {i: make_candles(symbol, i, closes, market) for i in ("15m", "1h", "4h", "1d")}


def test_engine_end_to_end_uses_closed_data_and_explains_score():
    candles = dataset()
    btc = dataset("BTCUSDT")
    eth = dataset("ETHUSDT")
    now = candles["15m"][-1].close_time + 60_000
    info = SymbolInfo(Market.SPOT, "TESTUSDT", "TEST", "USDT", "TRADING", onboard_date_ms=T0 - 100 * 86_400_000)
    result = AnalysisEngine().analyze(Market.SPOT, "TESTUSDT", candles, ticker(), book(), symbol_info=info,
                                     btc_candles=btc, eth_candles=eth, now_ms=now)
    assert result.risk.eligible and result.price == candles["15m"][-1].close
    assert len(result.strategies) == 5 and result.score.total > 0
    assert len(result.score.components) == 7 and result.ai_probabilities is None
    assert result.scenario["type"] == "analysis_only" and result.signal_valid_until_ms > now


def test_engine_missing_history_returns_ineligible_no_fake_score():
    result = AnalysisEngine().analyze(Market.SPOT, "TESTUSDT", {"15m": []}, ticker())
    assert not result.risk.eligible and result.score.total == 0 and not result.strategies
    assert result.ai_status == "insufficient_training_data"


def test_engine_discards_open_candle_and_detects_gap():
    candles = dataset()
    from dataclasses import replace
    original = candles["15m"][-1].close
    candles["15m"][-1] = replace(candles["15m"][-1], close=original * 2, is_closed=False)
    now = candles["15m"][-2].close_time + 60_000
    result = AnalysisEngine().analyze(Market.SPOT, "TESTUSDT", candles, ticker(), book(), now_ms=now)
    assert result.price == candles["15m"][-2].close
    del candles["15m"][100]
    result = AnalysisEngine().analyze(Market.SPOT, "TESTUSDT", candles, ticker(), book(), now_ms=now)
    assert "CANDLE_GAPS" in {f.code for f in result.risk.flags} and not result.risk.eligible
