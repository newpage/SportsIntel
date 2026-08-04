from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class MarketType(StrEnum):
    MONEYLINE = "moneyline"
    SPREAD = "spread"
    TOTAL = "total"
    PLAYER_PROP = "player_prop"


@dataclass(frozen=True, slots=True)
class MarketPrediction:
    market_type: MarketType
    selection: str | None
    confidence: int | None
    line: float | None = None
    projected_value: float | None = None
    recommendation: str | None = None
    explanation: str | None = None
    factor_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["market_type"] = self.market_type.value
        payload["factor_ids"] = list(self.factor_ids)
        return payload
