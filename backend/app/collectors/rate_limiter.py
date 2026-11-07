"""Kayan pencere 'ağırlık' sınırlayıcı (Binance IP ağırlık limitlerine uymak için)."""
from __future__ import annotations

import asyncio
import time
from collections import deque


class WeightLimiter:
    def __init__(self, max_weight: int, window_s: float = 60.0, clock=time.monotonic, sleep=asyncio.sleep):
        self.max_weight = max_weight
        self.window_s = window_s
        self._clock = clock
        self._sleep = sleep
        self._events: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    def _used(self, now: float) -> int:
        while self._events and self._events[0][0] <= now - self.window_s:
            self._events.popleft()
        return sum(w for _, w in self._events)

    async def acquire(self, weight: int = 1) -> None:
        if weight > self.max_weight:
            raise ValueError("İstek ağırlığı pencere sınırından büyük")
        async with self._lock:
            while True:
                now = self._clock()
                if self._used(now) + weight <= self.max_weight:
                    self._events.append((now, weight))
                    return
                wait = self._events[0][0] + self.window_s - now
                await self._sleep(max(wait, 0.01))
