"""Tek anlık order book ve mum-taker akışı; spoofing tespiti iddiası içermez."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.collectors.models import OrderBookSummary
from app.strategies.volume import VolumeMetrics


@dataclass
class OrderFlowAnalysis:
    available: bool
    score: float
    spread_pct: float | None = None
    depth_quote: float | None = None
    imbalance: float | None = None
    taker_buy_ratio: float | None = None
    flow_alignment: bool | None = None
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_order_flow(book: OrderBookSummary | None, volume: VolumeMetrics) -> OrderFlowAnalysis:
    if book is None:
        return OrderFlowAnalysis(False, 35.0, taker_buy_ratio=volume.taker_buy_ratio,
                                 risks=["Order book anlık görüntüsü yok; spread/derinlik doğrulanamadı"])
    depth = min(book.bid_depth_quote, book.ask_depth_quote)
    # Dengeli akış tek başına alım gerekçesi değildir; skor 0-100 ölçeğinde normalize edilir.
    imbalance_component = max(0.0, min(35.0, (book.imbalance + 0.2) * 87.5))
    spread_component = max(0.0, 25.0 * (1 - book.spread_pct / 0.5))
    taker = volume.taker_buy_ratio
    taker_component = max(0.0, min(25.0, ((taker or 0.5) - 0.4) * 250))
    alignment = book.imbalance > 0 and taker is not None and taker > 0.5
    depth_component = 15.0 if depth >= 100_000 else 10.0 if depth >= 50_000 else 0.0
    result = OrderFlowAnalysis(True, min(100, imbalance_component + spread_component + taker_component + depth_component),
                               book.spread_pct, depth, book.imbalance, taker, alignment)
    if book.imbalance > 0.15:
        result.reasons.append(f"Bid derinliği ask tarafından güçlü (imbalance {book.imbalance:.2f})")
    if taker is not None and taker >= 0.52:
        result.reasons.append(f"Son mumlarda aktif alıcı payı %{taker * 100:.1f}")
    if alignment:
        result.reasons.append("Order book dengesi ile gerçekleşen işlem akışı aynı yönde")
    if book.imbalance < -0.2:
        result.risks.append("Ask derinliği baskın; yakın satış likiditesi yükselişi sınırlayabilir")
    if taker is not None and taker < 0.48:
        result.risks.append("Aktif satıcı işlemleri baskın")
    result.risks.append("Tek anlık derinlik spoofing/sahte likidite kanıtı değildir")
    return result
