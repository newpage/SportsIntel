from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


TEAM_INTELLIGENCE_VERSION = "team-intelligence-v1"


@dataclass(frozen=True, slots=True)
class TeamIntelligence:
    team: str
    side: str
    rating: float
    rating_advantage: float
    health_score: float
    health_label: str
    quarterback_status: str
    quarterback_confirmed: bool
    market_probability: float | None
    model_probability: float
    market_edge: float | None
    readiness_score: float
    readiness_label: str
    season_phase: str
    confidence: float
    affects_prediction: bool = False
    model_version: str = TEAM_INTELLIGENCE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_team_intelligence(
    *,
    team: str,
    side: str,
    rating: float,
    opponent_rating: float,
    home_field_rating: float,
    health: dict[str, Any],
    quarterback: dict[str, Any],
    market_probability: float | None,
    model_probability: float,
    market_edge: float | None,
    readiness_score: float,
    readiness_label: str,
    season_phase: str,
    confidence: float,
) -> TeamIntelligence:
    is_home = side == "home"
    adjusted_rating = rating + (home_field_rating if is_home else 0.0)
    opponent_adjusted = opponent_rating + (
        home_field_rating if not is_home else 0.0
    )

    return TeamIntelligence(
        team=team,
        side=side,
        rating=round(rating, 2),
        rating_advantage=round(adjusted_rating - opponent_adjusted, 2),
        health_score=float(health.get("overall_score") or 50.0),
        health_label=str(health.get("overall_label") or "Unknown"),
        quarterback_status=str(quarterback.get("status") or "not announced"),
        quarterback_confirmed=quarterback.get("confirmed") is True,
        market_probability=(
            round(float(market_probability), 4)
            if isinstance(market_probability, (int, float))
            else None
        ),
        model_probability=round(float(model_probability), 4),
        market_edge=(
            round(float(market_edge), 4)
            if isinstance(market_edge, (int, float))
            else None
        ),
        readiness_score=round(float(readiness_score), 2),
        readiness_label=readiness_label,
        season_phase=season_phase,
        confidence=round(float(confidence), 2),
    )
