from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    EXPECTED = "expected"
    QUESTIONABLE = "questionable"
    DOUBTFUL = "doubtful"
    OUT = "out"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class StarterStatus(str, Enum):
    CONFIRMED = "confirmed"
    EXPECTED = "expected"
    BACKUP = "backup"
    NOT_EXPECTED = "not_expected"
    UNKNOWN = "unknown"


class PlayerUnit(str, Enum):
    OFFENSE = "offense"
    DEFENSE = "defense"
    SPECIAL_TEAMS = "special_teams"
    UNKNOWN = "unknown"


class IntelligenceUsage(str, Enum):
    OBSERVATION_ONLY = "observation_only"
    CONFIDENCE_ONLY = "confidence_only"
    ACTIVE = "active"


def _bounded_score(value: float, field_name: str) -> float:
    number = float(value)
    if not 0.0 <= number <= 100.0:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return round(number, 2)


def _bounded_probability(value: float, field_name: str) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return round(number, 4)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class IntelligenceSource:
    name: str
    source_type: str
    reliability: float = 0.5
    reference: str | None = None
    observed_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("source name is required")
        if not self.source_type.strip():
            raise ValueError("source_type is required")
        object.__setattr__(
            self,
            "reliability",
            _bounded_probability(self.reliability, "reliability"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PlayerIdentity:
    sport: str
    player_id: str
    display_name: str
    team: str
    position: str
    unit: PlayerUnit = PlayerUnit.UNKNOWN
    jersey_number: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "sport",
            "player_id",
            "display_name",
            "team",
            "position",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["unit"] = self.unit.value
        return payload


@dataclass(frozen=True, slots=True)
class PlayerIntelligence:
    identity: PlayerIdentity
    availability_status: AvailabilityStatus = AvailabilityStatus.UNKNOWN
    starter_status: StarterStatus = StarterStatus.UNKNOWN
    starter_probability: float = 0.0
    availability_score: float = 50.0
    health_score: float = 50.0
    impact_score: float = 50.0
    confidence: float = 0.0
    usage: IntelligenceUsage = IntelligenceUsage.OBSERVATION_ONLY
    explanation: str = ""
    sources: tuple[IntelligenceSource, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "starter_probability",
            _bounded_probability(
                self.starter_probability,
                "starter_probability",
            ),
        )
        object.__setattr__(
            self,
            "availability_score",
            _bounded_score(self.availability_score, "availability_score"),
        )
        object.__setattr__(
            self,
            "health_score",
            _bounded_score(self.health_score, "health_score"),
        )
        object.__setattr__(
            self,
            "impact_score",
            _bounded_score(self.impact_score, "impact_score"),
        )
        object.__setattr__(
            self,
            "confidence",
            _bounded_probability(self.confidence, "confidence"),
        )

    @property
    def expected_starter(self) -> bool:
        return self.starter_status in {
            StarterStatus.CONFIRMED,
            StarterStatus.EXPECTED,
        }

    @property
    def affects_prediction(self) -> bool:
        return self.usage == IntelligenceUsage.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "availability_status": self.availability_status.value,
            "starter_status": self.starter_status.value,
            "starter_probability": self.starter_probability,
            "expected_starter": self.expected_starter,
            "availability_score": self.availability_score,
            "health_score": self.health_score,
            "impact_score": self.impact_score,
            "confidence": self.confidence,
            "usage": self.usage.value,
            "affects_prediction": self.affects_prediction,
            "explanation": self.explanation,
            "sources": [source.to_dict() for source in self.sources],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class PlayerIntelligenceCollection:
    sport: str
    team: str
    players: tuple[PlayerIntelligence, ...] = ()
    generated_at: str = field(default_factory=_utc_now)
    model_version: str = "player-intelligence-v1"

    def __post_init__(self) -> None:
        if not self.sport.strip():
            raise ValueError("sport is required")
        if not self.team.strip():
            raise ValueError("team is required")

        mismatched = [
            player.identity.display_name
            for player in self.players
            if player.identity.team != self.team
            or player.identity.sport != self.sport
        ]
        if mismatched:
            raise ValueError(
                "all players must match collection sport and team: "
                + ", ".join(mismatched)
            )

    def by_position(self, position: str) -> tuple[PlayerIntelligence, ...]:
        normalized = position.strip().upper()
        return tuple(
            player
            for player in self.players
            if player.identity.position.upper() == normalized
        )

    def key_players(self, minimum_impact: float = 70.0) -> tuple[PlayerIntelligence, ...]:
        threshold = _bounded_score(minimum_impact, "minimum_impact")
        return tuple(
            sorted(
                (
                    player
                    for player in self.players
                    if player.impact_score >= threshold
                ),
                key=lambda player: player.impact_score,
                reverse=True,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "team": self.team,
            "players": [player.to_dict() for player in self.players],
            "player_count": len(self.players),
            "generated_at": self.generated_at,
            "model_version": self.model_version,
        }
