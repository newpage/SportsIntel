from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


TEAM_HEALTH_VERSION = "team-health-v1"


@dataclass(frozen=True, slots=True)
class TeamHealth:
    team: str
    overall_score: float
    overall_label: str
    confidence: float
    healthy: int
    questionable: int
    out: int
    player_count: int
    coverage: str
    affects_prediction: bool = False
    model_version: str = TEAM_HEALTH_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TeamHealthEngine:
    """Create an observation-only team-health summary.

    Version 1 intentionally uses only the quarterback context already
    available in the NFL provider. Future versions can consume the full
    Player Intelligence collection without changing the API contract.
    """

    _HEALTHY_STATUSES = {
        "active",
        "available",
        "confirmed",
        "expected",
        "healthy",
        "probable",
        "starting",
    }
    _QUESTIONABLE_STATUSES = {"questionable"}
    _OUT_STATUSES = {
        "doubtful",
        "inactive",
        "out",
        "suspended",
    }

    @staticmethod
    def _label(score: float, *, known: bool) -> str:
        if not known:
            return "Unknown"
        if score >= 95:
            return "Excellent"
        if score >= 85:
            return "Good"
        if score >= 70:
            return "Fair"
        if score >= 50:
            return "Poor"
        return "Critical"

    @classmethod
    def from_qb_context(
        cls,
        *,
        team: str,
        qb_context: Any,
    ) -> TeamHealth:
        qb = qb_context if isinstance(qb_context, dict) else {}
        name = str(qb.get("name") or "").strip()
        status = str(qb.get("status") or "").strip().lower()
        confirmed = qb.get("confirmed") is True
        known = bool(name)

        if not known:
            score = 50.0
            confidence = 0.0
            healthy = questionable = out = 0
        elif confirmed or status in cls._HEALTHY_STATUSES:
            score = 100.0 if confirmed else 90.0
            confidence = 0.85 if confirmed else 0.65
            healthy, questionable, out = 1, 0, 0
        elif status in cls._QUESTIONABLE_STATUSES:
            score = 60.0
            confidence = 0.65
            healthy, questionable, out = 0, 1, 0
        elif status in cls._OUT_STATUSES:
            score = 0.0 if status in {"out", "inactive", "suspended"} else 30.0
            confidence = 0.75
            healthy, questionable, out = 0, 0, 1
        else:
            score = 50.0
            confidence = 0.35
            healthy = questionable = out = 0

        return TeamHealth(
            team=team,
            overall_score=score,
            overall_label=cls._label(score, known=known),
            confidence=confidence,
            healthy=healthy,
            questionable=questionable,
            out=out,
            player_count=1 if known else 0,
            coverage="quarterback_only" if known else "no_player_data",
        )
