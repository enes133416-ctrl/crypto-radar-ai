"""Otomatik yeniden bağlanan WebSocket akışı (üstel geri çekilme, durgunluk tespiti, kopma sonrası onarım çağrısı)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

log = logging.getLogger(__name__)


def default_connect(url: str):
    import websockets  # yalnızca gerçek bağlantıda gerekir

    return websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=2 ** 22)


def build_stream_url(base_ws: str, streams: list[str]) -> str:
    return f"{base_ws.rstrip('/')}/stream?streams={'/'.join(streams)}"


def chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


class ReconnectingStream:
    def __init__(self, name: str, url: str, on_message: Callable[[str], Awaitable[None]],
                 on_reconnect: Callable[[], Awaitable[None]] | None = None, connect=default_connect,
                 backoff_base: float = 1.0, backoff_max: float = 60.0, stale_after: float = 60.0,
                 sleep=asyncio.sleep, clock=time.time):
        self.name, self.url = name, url
        self.on_message, self.on_reconnect = on_message, on_reconnect
        self._connect = connect
        self.backoff_base, self.backoff_max, self.stale_after = backoff_base, backoff_max, stale_after
        self._sleep, self._clock = sleep, clock
        self._stop = False
        self.connected = False
        self.reconnect_count = 0
        self.message_count = 0
        self.error_count = 0
        self.last_message_at: float | None = None
        self.last_error: str | None = None

    def stop(self) -> None:
        self._stop = True

    def status(self) -> dict:
        age = None if self.last_message_at is None else round(self._clock() - self.last_message_at, 1)
        return {"name": self.name, "connected": self.connected, "reconnects": self.reconnect_count,
                "messages": self.message_count, "last_message_age_s": age, "last_error": self.last_error}

    async def run(self) -> None:
        attempt = 0
        needs_repair = False
        while not self._stop:
            try:
                async with self._connect(self.url) as ws:
                    self.connected = True
                    self.last_error = None
                    if needs_repair:
                        self.reconnect_count += 1
                        if self.on_reconnect:
                            try:
                                await self.on_reconnect()
                            except Exception as e:  # onarım hatası akışı durdurmasın
                                log.warning("%s: kopma sonrası onarım başarısız: %s", self.name, e)
                        needs_repair = False
                    while not self._stop:
                        raw = await asyncio.wait_for(ws.recv(), self.stale_after)
                        self.last_message_at = self._clock()
                        self.message_count += 1
                        attempt = 0
                        try:
                            await self.on_message(raw)
                        except Exception as e:
                            self.error_count += 1
                            log.warning("%s: mesaj işlenemedi: %s", self.name, e)
            except asyncio.CancelledError:
                self.connected = False
                raise
            except asyncio.TimeoutError:
                self.last_error = f"Veri akışı {self.stale_after:.0f} sn boyunca durdu"
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
            self.connected = False
            needs_repair = True
            if self._stop:
                break
            delay = min(self.backoff_max, self.backoff_base * 2 ** attempt)
            attempt += 1
            log.warning("%s: bağlantı koptu (%s); %.1fs sonra yeniden bağlanılacak", self.name, self.last_error, delay)
            await self._sleep(delay)
