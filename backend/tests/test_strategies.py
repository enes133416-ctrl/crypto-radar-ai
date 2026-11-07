from app.indicators.snapshot import compute_snapshot
from app.strategies.breakout import consolidation_breakout
from app.strategies.momentum import momentum_continuation
from app.strategies.relative_strength import relative_strength
from app.strategies.reversal import oversold_reversal
from app.strategies.volume import analyze_volume
from tests.analysis_fixtures import flat_then_breakout, make_candles


def test_breakout_requires_close_volume_and_prior_resistance():
    rows = flat_then_breakout()
    volume = analyze_volume(rows)
    result = consolidation_breakout(rows, compute_snapshot(rows, 900_000), volume)
    assert result.triggered and result.metrics["breakout"]
    assert result.metrics["volume_ratio"] > 1.3
    weak_rows = flat_then_breakout("WEAKUSDT")
    from dataclasses import replace
    weak_rows[-1] = replace(weak_rows[-1], quote_volume=100 * weak_rows[-1].close, volume=100)
    weak_volume = analyze_volume(weak_rows)
    weak = consolidation_breakout(weak_rows, compute_snapshot(weak_rows, 900_000), weak_volume)
    assert not weak.triggered and any("sahte kırılım" in r for r in weak.risks)


def test_relative_strength_multiple_horizons_and_resilience():
    own = make_candles("ALTUSDT", "15m", [100 + i * 0.15 for i in range(120)])
    btc = make_candles("BTCUSDT", "15m", [100 - i * 0.03 for i in range(120)])
    eth = make_candles("ETHUSDT", "15m", [100 - i * 0.02 for i in range(120)])
    result = relative_strength("ALTUSDT", own, btc, eth)
    assert result.triggered and result.metrics["resilient"]
    weak = relative_strength("ALTUSDT", btc, own, eth)
    assert not weak.triggered and weak.score < result.score


def test_relative_strength_no_benchmark_is_not_fake_bullish():
    own = make_candles("ALTUSDT", "15m", [100 + i for i in range(120)])
    result = relative_strength("ALTUSDT", own)
    assert not result.triggered and result.score == 0


def test_oversold_reversal_needs_confirmations():
    closes = [120 - i * 0.8 for i in range(55)] + [77, 79, 82]
    rows = make_candles("ALTUSDT", "15m", closes, buy_ratio=0.65)
    result = oversold_reversal(rows, compute_snapshot(rows, 900_000), analyze_volume(rows))
    assert result.triggered and result.metrics["confirmations"] >= 3
    falling = make_candles("ALTUSDT", "15m", [120 - i * 0.8 for i in range(58)], buy_ratio=0.4)
    no_turn = oversold_reversal(falling, compute_snapshot(falling, 900_000), analyze_volume(falling))
    assert not no_turn.triggered


def test_momentum_continuation_and_overextension_risk():
    import math
    rows = make_candles("ALTUSDT", "15m", [100 + i * 0.1 + math.sin(i / 2 + 0.5) for i in range(240)])
    snap = compute_snapshot(rows, 900_000)
    volume = analyze_volume(rows)
    result = momentum_continuation(snap, volume, {"1h": "bullish", "4h": "bullish", "1d": "bullish"})
    assert result.triggered and result.score >= 85
    conflict = momentum_continuation(snap, volume, {"1h": "bullish", "4h": "bearish"})
    assert not conflict.triggered and any("uyum" in r for r in conflict.risks)
    extended = rows[:-1] + [__import__("dataclasses").replace(rows[-1], close=rows[-1].close * 1.3,
                                                             high=rows[-1].close * 1.31, open=rows[-1].open)]
    ext_snap = compute_snapshot(extended, 900_000)
    ext = momentum_continuation(ext_snap, analyze_volume(extended), {"1h": "bearish"})
    assert not ext.triggered and any("aşırı" in r or "geç" in r for r in ext.risks)
