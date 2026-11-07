"""Binance veri modelleri (piyasa türü, mum, ticker, order book özeti vb.)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Market(str, Enum):
    SPOT = "spot"
    FUTURES = "futures"


INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
}
SUPPORTED_INTERVALS: tuple[str, ...] = tuple(INTERVAL_MS)


@dataclass(frozen=True)
class Candle:
    market: Market
    symbol: str
    interval: str
    open_time: int  # ms
    close_time: int  # ms
    open: float
    high: float
    low: float
    close: float
    volume: float  # baz varlık hacmi
    quote_volume: float  # USDT hacmi
    trades: int
    taker_buy_base: float
    taker_buy_quote: float
    is_closed: bool  # False ise henüz tamamlanmamış mum


@dataclass(frozen=True)
class SymbolInfo:
    market: Market
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    contract_type: str | None = None
    onboard_date_ms: int | None = None


@dataclass(frozen=True)
class Ticker24h:
    market: Market
    symbol: str
    last_price: float
    price_change_pct: float
    high: float
    low: float
    volume: float
    quote_volume: float
    trades: int
    close_time: int


@dataclass(frozen=True)
class OrderBookSummary:
    market: Market
    symbol: str
    best_bid: float
    best_ask: float
    spread_pct: float
    bid_depth_quote: float
    ask_depth_quote: float
    imbalance: float  # (bid-ask)/(bid+ask), -1..+1


@dataclass(frozen=True)
class OpenInterest:
    symbol: str
    open_interest: float
    time: int


@dataclass(frozen=True)
class FundingRate:
    symbol: str
    funding_time: int
    funding_rate: float


@dataclass(frozen=True)
class TakerRatio:
    symbol: str
    buy_sell_ratio: float
    buy_volume: float
    sell_volume: float
    timestamp: int
