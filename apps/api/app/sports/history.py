from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FactorSnapshot:
    factor_id: str
    name: str
    score: float
    weight: float
    reliability: float
    direction: str
    used_in_confidence: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PredictionHistoryEvent:
    timestamp: str
    confidence: int
    pick: str | None
    reason: str
    factor_engine_version: str | None = None
    factor_snapshot: dict[str, FactorSnapshot] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["factor_snapshot"] = {
            key: value.to_dict()
            for key, value in self.factor_snapshot.items()
        }
        return payload
