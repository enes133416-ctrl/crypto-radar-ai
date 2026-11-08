from app.collectors.models import Market, OrderBookSummary
from app.indicators.snapshot import compute_snapshot
from app.services.market_regime import Regime, classify_market_regime
from app.strategies.order_flow import analyze_order_flow
from app.strategies.volume import analyze_volume
from tests.analysis_fixtures import make_candles


def test_order_flow_alignment_and_no_spoofing_claim():
    rows = make_candles("XUSDT", "15m", [100 + i * 0.01 for i in range(120)])
    book = OrderBookSummary(Market.SPOT, "XUSDT", 100, 100.01, 0.01, 200_000, 100_000, 1 / 3)
    result = analyze_order_flow(book, analyze_volume(rows))
    assert result.available and result.flow_alignment and result.score > 70
    assert any("spoofing" in risk for risk in result.risks)


def test_missing_orderbook_explicitly_unavailable():
    rows = make_candles("XUSDT", "15m", [100] * 120)
    result = analyze_order_flow(None, analyze_volume(rows))
    assert not result.available and result.spread_pct is None


def _snap(interval, closes):
    return compute_snapshot(make_candles("BTCUSDT", interval, closes), {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}[interval])


def test_market_regime_bull_bear_and_missing():
    bull = {i: _snap(i, [100 + n * 0.2 for n in range(240)]) for i in ("15m", "1h", "4h", "1d")}
    result = classify_market_regime(bull)
    assert result.regime in (Regime.BULLISH, Regime.STRONG_BULLISH) and result.confidence == 1
    bear = {i: _snap(i, [150 - n * 0.2 for n in range(240)]) for i in bull}
    assert classify_market_regime(bear).regime in (Regime.BEARISH, Regime.RISK_OFF)
    unknown = classify_market_regime({})
    assert unknown.regime == Regime.UNKNOWN and unknown.score is None


def test_high_atr_forces_risk_off_even_in_uptrend():
    from dataclasses import replace
    snapshots = {i: _snap(i, [100 + n * 0.2 for n in range(240)]) for i in ("15m", "1h", "4h", "1d")}
    snapshots["4h"] = replace(snapshots["4h"], atr_pct=8)
    result = classify_market_regime(snapshots)
    assert result.regime == Regime.RISK_OFF and result.risks
