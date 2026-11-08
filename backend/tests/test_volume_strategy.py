from dataclasses import replace

import pytest

from app.strategies.volume import analyze_volume, volume_explosion
from tests.analysis_fixtures import make_candles


def test_volume_ratio_uses_equal_windows_not_open_candles():
    closes = [100.0] * 120  # quote-volume oranını fiyat değişiminden izole et
    volumes = [100.0] * 116 + [300.0] * 4
    metrics = analyze_volume(make_candles("XUSDT", "15m", closes, volumes=volumes))
    assert metrics.windows["1h"].ratio == pytest.approx(3.0)
    assert metrics.windows["5m"].ratio is None  # 15m kaynaktan 5m hacim uydurulmaz
    assert metrics.windows["1h"].quote_volume > metrics.windows["1h"].baseline_average


def test_volume_zscore_and_taker_flow():
    rows = make_candles("XUSDT", "15m", [100] * 120, volumes=[100] * 119 + [500], buy_ratio=0.65)
    metrics = analyze_volume(rows)
    assert metrics.latest_zscore > 3 and metrics.taker_buy_ratio == pytest.approx(0.65)
    assert metrics.taker_imbalance > 0 and metrics.obv_volume_alignment is None  # tüm mumlar doji; OBV uydurulmaz


def test_volume_explosion_early_vs_already_pumped():
    closes = [100] * 116 + [100.1, 100.2, 100.3, 100.4]
    volumes = [100] * 116 + [400] * 4
    result = volume_explosion(analyze_volume(make_candles("XUSDT", "15m", closes, volumes=volumes)))
    assert result.triggered and result.score > 50
    pumped = volume_explosion(analyze_volume(make_candles("XUSDT", "15m", closes[:-1] + [115], volumes=volumes)))
    assert not pumped.triggered and any("erken" in r for r in pumped.risks)


def test_open_candle_rejected():
    row = make_candles("XUSDT", "15m", [100] * 30)
    with pytest.raises(ValueError, match="kapanmış"):
        analyze_volume([replace(row[-1], is_closed=False)])
