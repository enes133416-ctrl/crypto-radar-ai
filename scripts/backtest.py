"""Binance kapalı mumlarıyla tarihsel replay.

Örnek (backend/): PYTHONPATH=. python ../scripts/backtest.py --symbol BTCUSDT --market spot
Order book geçmişi olmadığı varsayımı raporda açıkça tutulur.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.backtesting.replay import HistoricalBacktester
from app.collectors.binance_rest import BinanceAPIError, BinanceRestClient
from app.collectors.models import Market
from app.config import get_settings
from app.services.analysis_engine import AnalysisEngine, risk_config_from_settings


async def run(args: argparse.Namespace) -> dict:
    settings = get_settings()
    market = Market(args.market)
    base = settings.binance_spot_rest if market == Market.SPOT else settings.binance_futures_rest
    client = BinanceRestClient(market, base)
    symbols = {args.symbol.upper(), "BTCUSDT", "ETHUSDT"}
    candles: dict[str, dict[str, list]] = {symbol: {} for symbol in symbols}
    try:
        for symbol in symbols:
            for interval in settings.tracked_intervals:
                candles[symbol][interval] = [c for c in await client.klines(symbol, interval, args.limit) if c.is_closed]
        engine = AnalysisEngine(risk_config_from_settings(settings, live=False))
        tester = HistoricalBacktester(engine, cost_pct=settings.round_trip_cost_pct)
        return tester.run(market, args.symbol.upper(), candles[args.symbol.upper()],
                          btc=candles["BTCUSDT"], eth=candles["ETHUSDT"], step_bars=args.step_bars)
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Look-ahead içermeyen Crypto Radar tarihsel replay")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--market", choices=["spot", "futures"], default="spot")
    parser.add_argument("--limit", type=int, default=1000, help="Zaman dilimi başına 180..1000 mum")
    parser.add_argument("--step-bars", type=int, default=4, help="Analiz adımı; 4 = 15m kaynağında 1 saat")
    parser.add_argument("--output", default="", help="JSON rapor yolu; boşsa stdout")
    args = parser.parse_args()
    if not 180 <= args.limit <= 1000:
        parser.error("--limit 180..1000 olmalı")
    try:
        result = asyncio.run(run(args))
    except BinanceAPIError as exc:
        result = {"status": "data_unavailable", "reason": str(exc),
                  "note": "Gerçek Binance kapalı mumları alınamadığı için backtest üretilmedi; sentetik sonuç kullanılmadı."}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"Rapor yazıldı: {path} · sinyal={len(result['signals'])}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
