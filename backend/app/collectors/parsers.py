"""Binance JSON yanıtlarını doğrulayarak modellere çevirir. Bozuk veri DataError fırlatır; asla uydurma değer üretmez."""
from __future__ import annotations

import json
import logging
from typing import Any

from .models import (
    Candle, FundingRate, Market, OpenInterest, OrderBookSummary, SymbolInfo, TakerRatio, Ticker24h,
)

log = logging.getLogger(__name__)

# Stabil/stabil pariteleri analiz için anlamsız olduğundan elenir.
STABLE_BASES = {"USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "USDE", "EUR", "EURI", "AEUR", "UST", "USD1", "XUSD"}


class DataError(ValueError):
    """Binance'ten gelen veri beklenen biçimde değil."""


def _f(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise DataError(f"'{field}' sayıya çevrilemedi: {value!r}") from None


def _i(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise DataError(f"'{field}' tamsayıya çevrilemedi: {value!r}") from None


def _validate_candle(c: Candle) -> Candle:
    if c.open_time >= c.close_time:
        raise DataError(f"{c.symbol} mum zamanı tutarsız")
    if min(c.open, c.high, c.low, c.close) <= 0:
        raise DataError(f"{c.symbol} mumunda sıfır/negatif fiyat")
    if c.high < c.low or c.high < max(c.open, c.close) or c.low > min(c.open, c.close):
        raise DataError(f"{c.symbol} mumunda high/low tutarsız")
    if c.volume < 0 or c.quote_volume < 0:
        raise DataError(f"{c.symbol} mumunda negatif hacim")
    return c


def parse_kline_row(row: Any, market: Market, symbol: str, interval: str, now_ms: int, safety_ms: int = 2000) -> Candle:
    """REST kline satırı. close_time, şimdiden (güvenlik payıyla) küçükse mum 'kapalı' sayılır."""
    if not isinstance(row, (list, tuple)) or len(row) < 11:
        raise DataError(f"Geçersiz kline satırı: {row!r}")
    close_time = _i(row[6], "closeTime")
    return _validate_candle(Candle(
        market=market, symbol=symbol, interval=interval,
        open_time=_i(row[0], "openTime"), close_time=close_time,
        open=_f(row[1], "open"), high=_f(row[2], "high"), low=_f(row[3], "low"), close=_f(row[4], "close"),
        volume=_f(row[5], "volume"), quote_volume=_f(row[7], "quoteVolume"), trades=_i(row[8], "trades"),
        taker_buy_base=_f(row[9], "takerBuyBase"), taker_buy_quote=_f(row[10], "takerBuyQuote"),
        is_closed=close_time < now_ms - safety_ms,
    ))


def parse_ws_kline(payload: Any, market: Market) -> Candle:
    """WebSocket kline mesajı (birleşik {'stream','data'} veya ham). 'x' alanı mumun kapandığını bildirir."""
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except ValueError:
            raise DataError("WebSocket mesajı JSON değil") from None
    if not isinstance(payload, dict):
        raise DataError("WebSocket mesajı sözlük değil")
    data = payload.get("data", payload)
    if not isinstance(data, dict) or data.get("e") != "kline" or not isinstance(data.get("k"), dict):
        raise DataError("Kline olmayan WebSocket mesajı")
    k = data["k"]
    try:
        return _validate_candle(Candle(
            market=market, symbol=str(k["s"]), interval=str(k["i"]),
            open_time=_i(k["t"], "t"), close_time=_i(k["T"], "T"),
            open=_f(k["o"], "o"), high=_f(k["h"], "h"), low=_f(k["l"], "l"), close=_f(k["c"], "c"),
            volume=_f(k["v"], "v"), quote_volume=_f(k["q"], "q"), trades=_i(k["n"], "n"),
            taker_buy_base=_f(k["V"], "V"), taker_buy_quote=_f(k["Q"], "Q"),
            is_closed=bool(k["x"]),
        ))
    except KeyError as e:
        raise DataError(f"WebSocket kline alanı eksik: {e}") from None


def parse_exchange_info(data: Any, market: Market, quote: str = "USDT") -> list[SymbolInfo]:
    if not isinstance(data, dict) or not isinstance(data.get("symbols"), list):
        raise DataError("exchangeInfo yanıtında 'symbols' yok")
    out: list[SymbolInfo] = []
    for s in data["symbols"]:
        try:
            if s.get("status") != "TRADING" or s.get("quoteAsset") != quote:
                continue
            if s.get("baseAsset") in STABLE_BASES:
                continue
            contract = s.get("contractType")
            if market == Market.FUTURES and contract != "PERPETUAL":
                continue
            if market == Market.SPOT and s.get("isSpotTradingAllowed") is False:
                continue
            out.append(SymbolInfo(
                market=market, symbol=s["symbol"], base_asset=s["baseAsset"], quote_asset=s["quoteAsset"],
                status=s["status"], contract_type=contract, onboard_date_ms=s.get("onboardDate"),
            ))
        except (KeyError, AttributeError):
            log.warning("exchangeInfo: bozuk sembol kaydı atlandı: %r", s)
    return out


def parse_tickers(data: Any, market: Market) -> list[Ticker24h]:
    if not isinstance(data, list):
        raise DataError("ticker/24hr yanıtı liste değil")
    out: list[Ticker24h] = []
    for t in data:
        try:
            out.append(Ticker24h(
                market=market, symbol=t["symbol"], last_price=_f(t["lastPrice"], "lastPrice"),
                price_change_pct=_f(t["priceChangePercent"], "priceChangePercent"),
                high=_f(t["highPrice"], "highPrice"), low=_f(t["lowPrice"], "lowPrice"),
                volume=_f(t["volume"], "volume"), quote_volume=_f(t["quoteVolume"], "quoteVolume"),
                trades=_i(t.get("count", 0), "count"), close_time=_i(t["closeTime"], "closeTime"),
            ))
        except (KeyError, TypeError, DataError):
            log.warning("ticker: bozuk kayıt atlandı: %r", t)
    return out


def parse_depth(data: Any, market: Market, symbol: str, levels: int = 20) -> OrderBookSummary:
    if not isinstance(data, dict) or not data.get("bids") or not data.get("asks"):
        raise DataError(f"{symbol} order book boş veya geçersiz")
    bids = [(_f(p, "bidPrice"), _f(q, "bidQty")) for p, q in data["bids"][:levels]]
    asks = [(_f(p, "askPrice"), _f(q, "askQty")) for p, q in data["asks"][:levels]]
    best_bid, best_ask = bids[0][0], asks[0][0]
    if best_bid <= 0 or best_ask <= 0 or best_ask < best_bid:
        raise DataError(f"{symbol} order book tutarsız (bid={best_bid}, ask={best_ask})")
    mid = (best_bid + best_ask) / 2
    bid_depth = sum(p * q for p, q in bids)
    ask_depth = sum(p * q for p, q in asks)
    total = bid_depth + ask_depth
    return OrderBookSummary(
        market=market, symbol=symbol, best_bid=best_bid, best_ask=best_ask,
        spread_pct=(best_ask - best_bid) / mid * 100, bid_depth_quote=bid_depth, ask_depth_quote=ask_depth,
        imbalance=(bid_depth - ask_depth) / total if total > 0 else 0.0,
    )


def parse_open_interest(data: Any) -> OpenInterest:
    try:
        return OpenInterest(symbol=data["symbol"], open_interest=_f(data["openInterest"], "openInterest"), time=_i(data["time"], "time"))
    except (KeyError, TypeError):
        raise DataError("openInterest yanıtı geçersiz") from None


def parse_funding_rates(data: Any) -> list[FundingRate]:
    if not isinstance(data, list):
        raise DataError("fundingRate yanıtı liste değil")
    try:
        return [FundingRate(symbol=d["symbol"], funding_time=_i(d["fundingTime"], "fundingTime"), funding_rate=_f(d["fundingRate"], "fundingRate")) for d in data]
    except (KeyError, TypeError):
        raise DataError("fundingRate kaydı geçersiz") from None


def parse_taker_ratio(data: Any, symbol: str) -> list[TakerRatio]:
    if not isinstance(data, list):
        raise DataError("takerlongshortRatio yanıtı liste değil")
    try:
        return [TakerRatio(symbol=symbol, buy_sell_ratio=_f(d["buySellRatio"], "buySellRatio"), buy_volume=_f(d["buyVol"], "buyVol"),
                           sell_volume=_f(d["sellVol"], "sellVol"), timestamp=_i(d["timestamp"], "timestamp")) for d in data]
    except (KeyError, TypeError):
        raise DataError("takerlongshortRatio kaydı geçersiz") from None
