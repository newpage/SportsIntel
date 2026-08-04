from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class FactorDirection(StrEnum):
    AWAY = "away"
    HOME = "home"
    NEUTRAL = "neutral"


class FactorUsage(StrEnum):
    ACTIVE = "active"
    OBSERVATION_ONLY = "observation_only"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class FactorSource:
    provider: str
    label: str | None = None
    retrieved_at: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PredictionFactor:
    factor_id: str
    name: str
    category: str
    score: float
    weight: float
    reliability: float
    explanation: str
    direction: FactorDirection = FactorDirection.NEUTRAL
    usage: FactorUsage = FactorUsage.ACTIVE
    version: str = "1"
    source: FactorSource | None = None
    contributes_to: tuple[str, ...] = ("moneyline",)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight * self.reliability

    @property
    def used_in_confidence(self) -> bool:
        return self.usage == FactorUsage.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["direction"] = self.direction.value
        payload["usage"] = self.usage.value
        payload["contributes_to"] = list(self.contributes_to)
        payload["weighted_score"] = self.weighted_score
        payload["used_in_confidence"] = self.used_in_confidence
        return payload
