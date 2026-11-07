"""Stratejilerin ortak, açıklanabilir sonuç modeli."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class StrategyName(str, Enum):
    VOLUME_EXPLOSION = "volume_explosion"
    CONSOLIDATION_BREAKOUT = "consolidation_breakout"
    RELATIVE_STRENGTH = "relative_strength"
    OVERSOLD_REVERSAL = "oversold_reversal"
    MOMENTUM_CONTINUATION = "momentum_continuation"


@dataclass
class StrategyResult:
    name: StrategyName
    triggered: bool
    score: float
    direction: str = "neutral"
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    metrics: dict[str, float | bool | str | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = round(max(0.0, min(100.0, self.score)), 2)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["name"] = self.name.value
        return out
