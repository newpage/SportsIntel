from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from app.sports.models import SportCapabilities, SportGame, SportPrediction


class SportProvider(ABC):
    """Contract implemented by each sport integration."""

    sport_key: str
    display_name: str
    capabilities: SportCapabilities

    @abstractmethod
    def schedule(self, target_date: date | None = None) -> list[SportGame]:
        """Return games for the requested date."""

    def standings(self) -> list[dict[str, Any]]:
        return []

    def enrich(self, games: list[SportGame]) -> list[SportGame]:
        return games

    @abstractmethod
    def predict(self, game: SportGame) -> SportPrediction:
        """Return a prediction using the shared prediction contract."""

    def health(self) -> dict[str, Any]:
        return {
            "sport": self.sport_key,
            "display_name": self.display_name,
            "capabilities": self.capabilities.to_dict(),
            "status": "available",
        }
