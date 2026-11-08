from __future__ import annotations

import time

from app.backtesting.labels import first_barrier, outcome_values
from app.backtesting.performance import performance_report, wilson_interval
from app.collectors.models import INTERVAL_MS, Market
from app.database.sqlite import Database
from tests.analysis_fixtures import T0, make_candles
from tests.helpers import kline_row, run
from app.collectors.parsers import parse_kline_row


def test_triple_barrier_distinguishes_any_target_and_before_stop():
    candles = make_candles("XUSDT", "15m", [100, 105, 110])
    # Yardımcı mumların high değeri yaklaşık 110.3; +10 hedefi gerçekleşir, -5 gerçekleşmez.
    assert first_barrier(candles, 100, 10, 5).result == "target"
    reverse = make_candles("XUSDT", "15m", [100, 94, 112])
    result = first_barrier(reverse, 100, 10, 5)
    assert result.result == "stop"


def test_same_candle_two_barriers_is_conservative():
    from app.collectors.models import Candle
    candle = Candle(Market.SPOT, "XUSDT", "15m", T0, T0 + 899999, 100, 112, 89, 101,
                    10, 1000, 10, 5, 500, True)
    assert first_barrier([candle], 100).result == "ambiguous"


def test_outcome_needs_full_horizon_and_writes_separate_labels():
    signal = {"signal_time": T0 - 1, "entry_price": 100.0}
    rows = make_candles("XUSDT", "15m", [100] * (72 * 4 + 1))
    values, resolved = outcome_values(signal, rows, T0 + 72 * 3_600_000 + 900_000)
    assert resolved and values["price_72h"] == 100
    assert values["hit10_24h"] == 0 and values["stop5_before_up10_72h"] == 0
    short, resolved_short = outcome_values(signal, rows[:10], T0 + 72 * 3_600_000 + 900_000)
    assert not resolved_short and "price_24h" not in short


def test_database_roundtrip_dedup_and_performance():
    db = Database("sqlite:///:memory:")
    candle = parse_kline_row(kline_row(T0), Market.SPOT, "XUSDT", "15m", T0 + 2_000_000)
    assert db.save_candles([candle]) == 1
    loaded = db.candles_after(Market.SPOT, "XUSDT", "15m", T0 - 1)
    assert len(loaded) == 1 and loaded[0].is_closed
    kwargs = dict(market="spot", symbol="XUSDT", strategy="volume_explosion", signal_time=T0,
                  valid_until=T0 + 1000, score=80, entry_price=100,
                  features={"score": 80}, analysis={"symbol": "XUSDT"}, cooldown_ms=1000)
    signal_id = db.insert_signal(**kwargs)
    assert signal_id is not None and db.insert_signal(**kwargs) is None
    db.update_outcome(signal_id, {"price_72h": 110, "hit10_72h": 1,
                                 "up10_before_stop5_72h": 1, "max_up_72h": 12,
                                 "max_down_72h": -2, "net_return_72h": 9.85}, True)
    rows = db.signals()
    assert rows[0]["status"] == "resolved" and rows[0]["features"]["score"] == 80
    report = performance_report(rows)
    assert report["summary"]["hit10_any"]["rate"] == 1.0
    assert report["by_score_band"]["75-84"]["signal_count"] == 1
    assert report["small_sample_warning"]
    assert wilson_interval(0, 0) == [None, None]
    db.close()
