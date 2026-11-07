from dataclasses import replace

from app.collectors.models import FundingRate, Market, OrderBookSummary
from app.indicators.snapshot import compute_snapshot
from app.risk.filters import RiskConfig, assess_risk
from app.scoring.opportunity import calculate_score, score_label
from app.services.market_regime import MarketRegime, Regime
from app.strategies.models import StrategyName, StrategyResult
from app.strategies.order_flow import OrderFlowAnalysis
from app.strategies.volume import analyze_volume
from tests.analysis_fixtures import book, make_candles, ticker


def _inputs(market=Market.SPOT):
    rows = make_candles("TESTUSDT", "15m", [100 + i * 0.02 for i in range(120)], market)
    snaps = {"15m": compute_snapshot(rows, 900_000)}
    for interval, ms in (("1h", 3_600_000), ("4h", 14_400_000), ("1d", 86_400_000)):
        snaps[interval] = compute_snapshot(make_candles("TESTUSDT", interval, [100 + i * 0.02 for i in range(80)], market), ms)
    return rows, snaps, analyze_volume(rows)


def test_liquidity_spread_depth_are_hard_prefilters():
    rows, snaps, volume = _inputs()
    low = assess_risk(Market.SPOT, "TESTUSDT", ticker(quote_volume=100), snaps, volume, book())
    assert not low.eligible and "LOW_LIQUIDITY" in {f.code for f in low.flags}
    wide = replace(book(), spread_pct=1.0)
    shallow = replace(book(), bid_depth_quote=10)
    result = assess_risk(Market.SPOT, "TESTUSDT", ticker(), snaps, volume, wide)
    assert not result.eligible and "WIDE_SPREAD" in {f.code for f in result.flags}
    result = assess_risk(Market.SPOT, "TESTUSDT", ticker(), snaps, volume, shallow)
    assert not result.eligible and "SHALLOW_ORDERBOOK" in {f.code for f in result.flags}


def test_data_quality_stale_gap_and_funding_filters():
    rows, snaps, volume = _inputs(Market.FUTURES)
    now = rows[-1].close_time + 46 * 60_000
    funding = FundingRate("TESTUSDT", now, 0.004)
    result = assess_risk(Market.FUTURES, "TESTUSDT", ticker(market=Market.FUTURES), snaps, volume,
                         book(market=Market.FUTURES), funding, now_ms=now,
                         last_close_time_ms=rows[-1].close_time, has_recent_gaps=True)
    codes = {f.code for f in result.flags}
    assert not result.eligible and {"STALE_DATA", "CANDLE_GAPS", "CRITICAL_FUNDING"} <= codes


def test_missing_data_and_cross_market_mismatch():
    rows, snaps, volume = _inputs()
    result = assess_risk(Market.SPOT, "TESTUSDT", ticker(), {"15m": snaps["15m"]}, volume,
                         spot_futures_price_diff_pct=3)
    assert not result.eligible and "MTF_DATA_MISSING" in {f.code for f in result.flags}
    assert "CROSS_MARKET_MISMATCH" in {f.code for f in result.flags}


def test_new_listing_and_extreme_atr_are_hard_filters():
    from app.collectors.models import SymbolInfo
    rows, snaps, volume = _inputs(Market.FUTURES)
    now = rows[-1].close_time + 1
    info = SymbolInfo(Market.FUTURES, "TESTUSDT", "TEST", "USDT", "TRADING", "PERPETUAL", now - 5 * 86_400_000)
    result = assess_risk(Market.FUTURES, "TESTUSDT", ticker(market=Market.FUTURES), snaps, volume,
                         book(market=Market.FUTURES), FundingRate("TESTUSDT", now, 0), info, now)
    assert not result.eligible and "NEW_LISTING" in {f.code for f in result.flags}
    snaps["15m"] = replace(snaps["15m"], atr_pct=20)
    result = assess_risk(Market.FUTURES, "TESTUSDT", ticker(market=Market.FUTURES), snaps, volume,
                         book(market=Market.FUTURES), FundingRate("TESTUSDT", now, 0), now_ms=now)
    assert not result.eligible and "EXTREME_ATR" in {f.code for f in result.flags}


def test_score_components_total_100_and_labels():
    rows, snaps, volume = _inputs()
    strategies = [StrategyResult(name, True, 100) for name in StrategyName]
    risk = assess_risk(Market.SPOT, "TESTUSDT", ticker(), snaps, volume, book())
    regime = MarketRegime(Regime.STRONG_BULLISH, 100, 1, {})
    flow = OrderFlowAnalysis(True, 100)
    result = calculate_score(strategies, volume, flow, regime, risk, 1, historical_similarity_score=100)
    assert result.total == 100 and sum(c.maximum for c in result.components) == 100
    assert [score_label(s) for s in (90, 80, 70, 60, 40)] == ["very_strong", "strong", "watch", "weak", "unsuitable"]


def test_unavailable_similarity_is_neutral_not_performance_claim():
    rows, snaps, volume = _inputs()
    strategies = [StrategyResult(name, False, 50) for name in StrategyName]
    risk = assess_risk(Market.SPOT, "TESTUSDT", ticker(), snaps, volume, book())
    result = calculate_score(strategies, volume, OrderFlowAnalysis(True, 50),
                             MarketRegime(Regime.NEUTRAL, 50, 1, {}), risk, 0.5)
    similarity = next(c for c in result.components if c.name == "historical_similarity")
    assert similarity.points == 5 and result.historical_similarity_status == "insufficient_training_data"
    assert "performans iddiası değil" in similarity.explanation


def test_hard_filter_cannot_be_promoted_even_with_perfect_strategies():
    rows, snaps, volume = _inputs()
    strategies = [StrategyResult(name, True, 100) for name in StrategyName]
    risk = assess_risk(Market.SPOT, "TESTUSDT", ticker(quote_volume=1), snaps, volume, book())
    result = calculate_score(strategies, volume, OrderFlowAnalysis(True, 100),
                             MarketRegime(Regime.STRONG_BULLISH, 100, 1, {}), risk, 1, 100)
    assert not risk.eligible and not result.eligible and result.total > 85  # skor ayrı, promosyon uygunluğu zorunlu filtreye bağlı
