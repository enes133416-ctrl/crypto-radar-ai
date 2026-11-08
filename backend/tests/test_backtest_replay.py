from __future__ import annotations

from app.backtesting.replay import HistoricalBacktester
from app.collectors.models import Market
from tests.analysis_fixtures import make_candles


class ReplayEngine:
    def __init__(self):
        self.cutoffs = []

    def analyze(self, market, symbol, candles, *args, **kwargs):
        cutoff = kwargs["now_ms"]
        self.cutoffs.append(cutoff)
        assert all(c.close_time <= cutoff for rows in candles.values() for c in rows)
        analysis = {"market": market.value, "symbol": symbol, "score": {"total": 80},
                    "risk": {"eligible": True}, "snapshots": {}, "volume": None, "order_flow": None,
                    "regime": {"regime": "unknown"}, "mtf_agreement": 0,
                    "strategies": [{"name": "volume_explosion", "triggered": True, "score": 80}]}
        return type("Result", (), {"to_dict": lambda self: analysis})()


def test_historical_replay_uses_only_past_slices_and_next_open():
    primary = make_candles("XUSDT", "15m", [100 + i * 0.01 for i in range(700)])
    candles = {"15m": primary, "1h": make_candles("XUSDT", "1h", [100 + i * 0.04 for i in range(200)]),
               "4h": make_candles("XUSDT", "4h", [100 + i * 0.1 for i in range(80)]),
               "1d": make_candles("XUSDT", "1d", [100 + i * 0.2 for i in range(30)])}
    engine = ReplayEngine()
    result = HistoricalBacktester(engine, cooldown_bars=16).run(Market.SPOT, "XUSDT", candles, step_bars=200)
    assert result["signals"], "Replay tetiklenen sinyalleri kaydetmeli"
    first = result["signals"][0]
    assert first["signal_time"] == primary[120].close_time
    assert first["entry_price"] == primary[121].open
    assert first["price_72h"] is not None
    assert all(cutoff == primary[index].close_time for cutoff, index in zip(engine.cutoffs, (120, 320, 520)))
    assert "Tarihsel order book/funding tick verisi yoktur" in " ".join(result["assumptions"])
