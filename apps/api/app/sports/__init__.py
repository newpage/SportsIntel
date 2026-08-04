"""Sport-neutral platform contracts for SportsIntel."""

from app.sports.models import GameStatus, SportCapabilities, SportGame, SportKeyParticipant, SportPrediction
from app.sports.provider import SportProvider
from app.sports.registry import SportRegistry, sports_registry

__all__ = [
    "GameStatus",
    "SportCapabilities",
    "SportGame",
    "SportKeyParticipant",
    "SportPrediction",
    "SportProvider",
    "SportRegistry",
    "sports_registry",
]
