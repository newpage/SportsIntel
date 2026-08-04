from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.sports.models import SportGame, SportPrediction
from app.sports.registry import SportRegistry, sports_registry


@dataclass(frozen=True, slots=True)
class PredictionRequest:
    sport: str
    game: SportGame
    options: dict[str, Any] = field(default_factory=dict)


class SportsPredictionService:
    """Routes prediction requests to the registered sport provider."""

    def __init__(self, registry: SportRegistry | None = None) -> None:
        self._registry = registry or sports_registry

    def predict(self, request: PredictionRequest) -> SportPrediction:
        provider = self._registry.get(request.sport)
        if provider.sport_key.lower() != request.game.sport.lower():
            raise ValueError("Prediction request sport does not match game sport")
        return provider.predict(request.game)
