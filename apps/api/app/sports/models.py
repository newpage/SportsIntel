from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.sports.history import PredictionHistoryEvent
from app.sports.markets import MarketPrediction


class GameStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SportCapabilities:
    moneyline: bool = False
    spread: bool = False
    totals: bool = False
    player_props: bool = False
    live: bool = False
    standings: bool = False
    injuries: bool = False
    weather: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SportKeyParticipant:
    role: str
    name: str | None = None
    team: str | None = None
    status: str | None = None
    source: str | None = None
    reliability: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SportGame:
    sport: str
    game_id: str
    away_team: str
    home_team: str
    start_time: datetime | str
    status: GameStatus = GameStatus.UNKNOWN
    away_score: int | float | None = None
    home_score: int | float | None = None
    venue: str | None = None
    key_participants: list[SportKeyParticipant] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        if isinstance(self.start_time, datetime):
            payload["start_time"] = self.start_time.isoformat()
        return payload


@dataclass(slots=True)
class SportPrediction:
    sport: str
    game_id: str
    pick: str | None
    confidence: int | None
    recommendation: str | None = None
    factors: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any] | PredictionHistoryEvent] = field(default_factory=list)
    markets: dict[str, Any] | list[MarketPrediction] = field(default_factory=dict)
    explanation: dict[str, Any] = field(default_factory=dict)
    model_version: str | None = None
    shadow_prediction: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timeline"] = [
            event.to_dict() if isinstance(event, PredictionHistoryEvent) else event
            for event in self.timeline
        ]
        if isinstance(self.markets, list):
            payload["markets"] = [
                market.to_dict() if isinstance(market, MarketPrediction) else market
                for market in self.markets
            ]
        return payload
