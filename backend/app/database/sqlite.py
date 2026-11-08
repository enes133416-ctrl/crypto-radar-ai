"""Küçük, bağımlılıksız SQLite kalıcılık katmanı.

Tek bağlantı ve RLock kullanılır; FastAPI/async collector aynı process içinde güvenle
erişir. Şema SQL sütunlarından oluşur, analizin tamamı da denetlenebilir JSON olarak saklanır.
PostgreSQL'e geçişte servisler yalnız bu repository arayüzüne bağımlıdır.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from app.collectors.models import Candle, Market

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS candles (
    market TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
    open_time INTEGER NOT NULL, close_time INTEGER NOT NULL,
    open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
    volume REAL NOT NULL, quote_volume REAL NOT NULL, trades INTEGER NOT NULL,
    taker_buy_base REAL NOT NULL, taker_buy_quote REAL NOT NULL, is_closed INTEGER NOT NULL,
    PRIMARY KEY(market, symbol, interval, open_time)
);
CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(market,symbol,interval,close_time);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL, symbol TEXT NOT NULL, strategy TEXT NOT NULL,
    signal_time INTEGER NOT NULL, created_at INTEGER NOT NULL, valid_until INTEGER,
    score REAL NOT NULL, entry_price REAL NOT NULL, features_json TEXT NOT NULL,
    analysis_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    outcome_updated_at INTEGER, resolved_at INTEGER,
    price_24h REAL, price_48h REAL, price_72h REAL,
    max_up_24h REAL, max_up_48h REAL, max_up_72h REAL,
    max_down_24h REAL, max_down_48h REAL, max_down_72h REAL,
    net_return_24h REAL, net_return_48h REAL, net_return_72h REAL,
    hit5_24h INTEGER, hit10_24h INTEGER, hit15_24h INTEGER,
    hit5_48h INTEGER, hit10_48h INTEGER, hit15_48h INTEGER,
    hit5_72h INTEGER, hit10_72h INTEGER, hit15_72h INTEGER,
    up10_before_stop3_24h INTEGER, up10_before_stop5_24h INTEGER,
    up10_before_stop3_48h INTEGER, up10_before_stop5_48h INTEGER,
    up10_before_stop3_72h INTEGER, up10_before_stop5_72h INTEGER,
    stop3_before_up10_24h INTEGER, stop5_before_up10_24h INTEGER,
    stop3_before_up10_48h INTEGER, stop5_before_up10_48h INTEGER,
    stop3_before_up10_72h INTEGER, stop5_before_up10_72h INTEGER,
    ambiguous_barriers INTEGER NOT NULL DEFAULT 0,
    UNIQUE(market,symbol,strategy,signal_time)
);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status,signal_time);
CREATE INDEX IF NOT EXISTS idx_signals_report ON signals(signal_time,market,strategy,score);
CREATE TABLE IF NOT EXISTS prediction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id INTEGER,
    model_trained_before INTEGER NOT NULL, probabilities_json TEXT NOT NULL,
    created_at INTEGER NOT NULL, FOREIGN KEY(signal_id) REFERENCES signals(id)
);
CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
"""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def database_path(url: str) -> str:
    if url in {"sqlite:///:memory:", "sqlite://", ":memory:"}:
        return ":memory:"
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError("Bu sürüm DATABASE_URL için sqlite:/// yolu bekler")
    path = url[len(prefix):]
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return path


class Database:
    def __init__(self, url: str = "sqlite:///./data/crypto_radar.db"):
        self.url = url
        self.path = database_path(url)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def save_candles(self, candles: Iterable[Candle]) -> int:
        rows = [(
            c.market.value, c.symbol, c.interval, c.open_time, c.close_time, c.open, c.high,
            c.low, c.close, c.volume, c.quote_volume, c.trades, c.taker_buy_base,
            c.taker_buy_quote, int(c.is_closed),
        ) for c in candles]
        if not rows:
            return 0
        sql = """INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(market,symbol,interval,open_time) DO UPDATE SET
        close_time=excluded.close_time,open=excluded.open,high=excluded.high,low=excluded.low,
        close=excluded.close,volume=excluded.volume,quote_volume=excluded.quote_volume,
        trades=excluded.trades,taker_buy_base=excluded.taker_buy_base,
        taker_buy_quote=excluded.taker_buy_quote,is_closed=excluded.is_closed"""
        with self._lock, self._conn:
            self._conn.executemany(sql, rows)
        return len(rows)

    def candles_after(self, market: Market, symbol: str, interval: str, after_ms: int,
                      until_ms: int | None = None) -> list[Candle]:
        sql = """SELECT * FROM candles WHERE market=? AND symbol=? AND interval=?
        AND close_time>? AND is_closed=1"""
        params: list[Any] = [market.value, symbol, interval, after_ms]
        if until_ms is not None:
            sql += " AND open_time<=?"
            params.append(until_ms)
        sql += " ORDER BY open_time"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_candle(r) for r in rows]

    @staticmethod
    def _row_candle(r: sqlite3.Row) -> Candle:
        return Candle(Market(r["market"]), r["symbol"], r["interval"], r["open_time"], r["close_time"],
                      r["open"], r["high"], r["low"], r["close"], r["volume"], r["quote_volume"],
                      r["trades"], r["taker_buy_base"], r["taker_buy_quote"], bool(r["is_closed"]))

    def insert_signal(self, *, market: str, symbol: str, strategy: str, signal_time: int,
                      valid_until: int | None, score: float, entry_price: float,
                      features: dict, analysis: dict, probabilities: dict | None = None,
                      model_trained_before: int | None = None, cooldown_ms: int = 0) -> int | None:
        now = int(time.time() * 1000)
        with self._lock, self._conn:
            recent = self._conn.execute(
                """SELECT id,signal_time FROM signals WHERE market=? AND symbol=? AND strategy=?
                AND signal_time>? ORDER BY signal_time DESC LIMIT 1""",
                (market, symbol, strategy, signal_time - cooldown_ms),
            ).fetchone()
            if recent:
                return None
            try:
                cur = self._conn.execute(
                    """INSERT INTO signals(market,symbol,strategy,signal_time,created_at,valid_until,
                    score,entry_price,features_json,analysis_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (market, symbol, strategy, signal_time, now, valid_until, score, entry_price,
                     _json(features), _json(analysis)),
                )
            except sqlite3.IntegrityError:
                return None
            signal_id = int(cur.lastrowid)
            if probabilities is not None and model_trained_before is not None:
                self._conn.execute(
                    "INSERT INTO prediction_logs(signal_id,model_trained_before,probabilities_json,created_at) VALUES (?,?,?,?)",
                    (signal_id, model_trained_before, _json(probabilities), now),
                )
            return signal_id

    def update_outcome(self, signal_id: int, values: dict[str, Any], resolved: bool) -> None:
        allowed = {c[1] for c in self._conn.execute("PRAGMA table_info(signals)").fetchall()}
        fields = {k: v for k, v in values.items() if k in allowed}
        fields["outcome_updated_at"] = int(time.time() * 1000)
        fields["status"] = "resolved" if resolved else "partial"
        if resolved:
            fields["resolved_at"] = int(time.time() * 1000)
        assignments = ",".join(f"{key}=?" for key in fields)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE signals SET {assignments} WHERE id=?", (*fields.values(), signal_id))

    def signals(self, *, status: str | None = None, market: str | None = None,
                strategy: str | None = None, symbol: str | None = None,
                limit: int = 1000) -> list[dict[str, Any]]:
        clauses, params = [], []
        for column, value in (("status", status), ("market", market), ("strategy", strategy), ("symbol", symbol)):
            if value is not None:
                clauses.append(f"{column}=?")
                params.append(value)
        sql = "SELECT * FROM signals"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY signal_time DESC LIMIT ?"
        params.append(max(1, min(limit, 100_000)))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._signal_dict(r) for r in rows]

    @staticmethod
    def _signal_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for source, target in (("features_json", "features"), ("analysis_json", "analysis")):
            result[target] = json.loads(result.pop(source))
        return result

    def resolved_training_rows(self, before_ms: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM signals WHERE status='resolved'"
        params: list[Any] = []
        if before_ms is not None:
            sql += " AND signal_time<? AND resolved_at<?"
            params.extend([before_ms, before_ms])
        sql += " ORDER BY signal_time"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._signal_dict(r) for r in rows]

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {status: int(self._conn.execute("SELECT COUNT(*) FROM signals WHERE status=?", (status,)).fetchone()[0])
                    for status in ("open", "partial", "resolved")}
