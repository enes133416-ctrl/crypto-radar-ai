"""Bellek içi mum deposu. Tamamlanmış ve devam eden mumları KESİNLİKLE ayrı tutar."""
from __future__ import annotations

import time
from collections import deque

from .models import INTERVAL_MS, Candle, Market

Key = tuple[Market, str, str]


class CandleStore:
    def __init__(self, max_candles: int = 1000):
        self.max_candles = max_candles
        self._closed: dict[Key, deque[Candle]] = {}
        self._open: dict[Key, Candle] = {}
        self.last_update: dict[Key, float] = {}

    def apply(self, c: Candle) -> None:
        key = (c.market, c.symbol, c.interval)
        self.last_update[key] = time.time()
        if not c.is_closed:
            cur = self._open.get(key)
            if cur is None or c.open_time >= cur.open_time:
                self._open[key] = c
            return
        dq = self._closed.setdefault(key, deque(maxlen=self.max_candles))
        if dq and dq[-1].open_time == c.open_time:
            dq[-1] = c
        elif not dq or dq[-1].open_time < c.open_time:
            dq.append(c)
        else:  # geriye dönük (backfill) mum: yerine yerleştir
            items = {x.open_time: x for x in dq}
            items[c.open_time] = c
            dq.clear()
            dq.extend(items[k] for k in sorted(items))
        cur = self._open.get(key)
        if cur is not None and cur.open_time <= c.open_time:
            del self._open[key]

    def apply_many(self, candles: list[Candle]) -> None:
        for c in candles:
            self.apply(c)

    def closed(self, market: Market, symbol: str, interval: str, n: int | None = None) -> list[Candle]:
        items = list(self._closed.get((market, symbol, interval), ()))
        return items[-n:] if n else items

    def open_candle(self, market: Market, symbol: str, interval: str) -> Candle | None:
        return self._open.get((market, symbol, interval))

    def last_closed_open_time(self, market: Market, symbol: str, interval: str) -> int | None:
        dq = self._closed.get((market, symbol, interval))
        return dq[-1].open_time if dq else None

    def find_gaps(self, market: Market, symbol: str, interval: str) -> list[tuple[int, int]]:
        """Tamamlanmış mumlar arasındaki eksik aralıklar: [(ilk_eksik_open_time, son_eksik_open_time)]."""
        step = INTERVAL_MS[interval]
        items = self._closed.get((market, symbol, interval), ())
        gaps, prev = [], None
        for c in items:
            if prev is not None and c.open_time - prev > step:
                gaps.append((prev + step, c.open_time - step))
            prev = c.open_time
        return gaps

    def age_seconds(self, market: Market, symbol: str, interval: str) -> float | None:
        ts = self.last_update.get((market, symbol, interval))
        return None if ts is None else time.time() - ts

    def series_count(self) -> int:
        return len(self._closed)
