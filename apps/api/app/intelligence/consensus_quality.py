from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CONSENSUS_QUALITY_VERSION = "consensus-quality-v1"


@dataclass(frozen=True, slots=True)
class ConsensusQuality:
    score: int
    label: str
    status: str
    reasons: tuple[str, ...]
    market_hold: float | None
    readiness_label: str
    quarterbacks_announced: bool
    season_phase: str
    affects_prediction: bool = False
    model_version: str = CONSENSUS_QUALITY_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def build_consensus_quality(
    *,
    market_available: bool,
    market_hold: float | None,
    readiness_label: str,
    quarterbacks_announced: bool,
    season_phase: str,
) -> ConsensusQuality:
    if not market_available:
        return ConsensusQuality(
            score=0,
            label="Unavailable",
            status="hold",
            reasons=("A complete two-sided moneyline market is unavailable.",),
            market_hold=None,
            readiness_label=readiness_label,
            quarterbacks_announced=quarterbacks_announced,
            season_phase=season_phase,
        )

    score = 100
    reasons: list[str] = []

    if market_hold is None:
        score -= 15
        reasons.append("Sportsbook hold could not be verified.")
    elif market_hold > 0.08:
        score -= 25
        reasons.append("Sportsbook hold is high, reducing market reliability.")
    elif market_hold > 0.05:
        score -= 10
        reasons.append("Sportsbook hold is elevated.")
    else:
        reasons.append("Sportsbook hold is within the preferred range.")

    normalized_readiness = readiness_label.strip().lower()
    if normalized_readiness in {"limited", "unknown"}:
        score -= 25
        reasons.append("Model data readiness is limited.")
    elif normalized_readiness == "developing":
        score -= 10
        reasons.append("Model data readiness is still developing.")
    else:
        reasons.append("Model data readiness is strong.")

    if not quarterbacks_announced:
        score -= 15
        reasons.append("Starting quarterbacks are not fully announced.")

    normalized_phase = season_phase.strip().lower()
    if normalized_phase == "preseason":
        score -= 15
        reasons.append("Preseason participation uncertainty applies.")

    score = max(0, min(100, score))

    if score >= 80:
        label = "Strong"
        status = "qualified"
    elif score >= 60:
        label = "Moderate"
        status = "watch"
    elif score >= 40:
        label = "Limited"
        status = "caution"
    else:
        label = "Weak"
        status = "hold"

    return ConsensusQuality(
        score=score,
        label=label,
        status=status,
        reasons=tuple(reasons),
        market_hold=(round(float(market_hold), 4) if market_hold is not None else None),
        readiness_label=readiness_label,
        quarterbacks_announced=quarterbacks_announced,
        season_phase=season_phase,
    )
