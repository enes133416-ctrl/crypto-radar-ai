import math

import pytest

from app.indicators.core import adx, atr, bollinger, ema, macd, obv, rolling_vwap, rsi, sma, stochastic_rsi
from app.indicators.snapshot import compute_snapshot
from tests.analysis_fixtures import make_candles


def test_sma_ema_warmup_and_known_values():
    assert sma([1, 2, 3, 4], 3) == [None, None, 2, 3]
    assert ema([1, 2, 3], 4) == [None] * 3
    values = ema([1, 2, 3, 4], 3)
    assert values[:2] == [None, None] and values[2] == 2 and values[3] == 3


def test_rsi_wilder_extremes_and_flat():
    assert rsi(list(range(1, 30)), 14)[-1] == 100
    assert rsi(list(range(30, 1, -1)), 14)[-1] == 0
    assert rsi([10] * 30, 14)[-1] == 50
    assert rsi([1, 2], 14) == [None, None]


def test_macd_alignment_and_bollinger_flat():
    values = list(range(1, 80))
    result = macd(values)
    assert len(result["macd"]) == len(values) == len(result["histogram"])
    assert result["histogram"][-1] is not None and result["macd"][-1] > 0
    bb = bollinger([10] * 25)
    assert bb["upper"][-1] == bb["lower"][-1] == 10 and bb["width"][-1] == 0


def test_atr_adx_trending_market():
    closes = [100 + i for i in range(60)]
    highs, lows = [c + 1 for c in closes], [c - 1 for c in closes]
    tr = atr(highs, lows, closes)
    dmi = adx(highs, lows, closes)
    assert tr[13] == 2 and tr[-1] == 2
    assert dmi["adx"][-1] > 90 and dmi["plus_di"][-1] > dmi["minus_di"][-1]


def test_stoch_obv_vwap():
    stoch = stochastic_rsi([100 + math.sin(i / 2) * 5 + i * 0.05 for i in range(80)])
    assert 0 <= stoch["k"][-1] <= 100 and stoch["d"][-1] is not None
    assert obv([1, 2, 2, 1], [10, 20, 30, 40]) == [0, 20, 20, -20]
    assert rolling_vwap([11, 21], [9, 19], [10, 20], [1, 3], 2)[-1] == pytest.approx(17.5)


def test_snapshot_has_all_families_and_rejects_open_candle():
    rows = make_candles("XUSDT", "15m", [100 + i * 0.2 for i in range(240)])
    snap = compute_snapshot(rows, 900_000)
    assert snap.ema200 is not None and snap.rsi7 == 100 and snap.adx > 0
    assert snap.support is not None and snap.resistance is not None and snap.pivot_r1 > snap.pivot
    assert snap.trend == "bullish" and snap.higher_highs and snap.higher_lows
    from dataclasses import replace
    with pytest.raises(ValueError, match="tamamlanmamış"):
        compute_snapshot([replace(rows[-1], is_closed=False)], 900_000)


def test_nan_input_rejected():
    with pytest.raises(ValueError, match="NaN"):
        sma([1, float("nan")], 2)
