from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

from app.intelligence.consensus import ConsensusLine
from app.intelligence.consensus_quality import ConsensusQuality


QUALIFIED_CONSENSUS_VERSION = "qualified-consensus-v1"
QualifiedConsensusStatus = Literal[
    "qualified",
    "watch",
    "caution",
    "hold",
    "unavailable",
]


@dataclass(frozen=True, slots=True)
class QualifiedConsensus:
    classification: str
    quality_score: int
    quality_label: str
    status: QualifiedConsensusStatus
    model_pick: str
    market_favorite: str | None
    model_probability: float
    no_vig_market_probability: float | None
    model_market_edge: float | None
    explanation: str
    reasons: tuple[str, ...]
    affects_prediction: bool = False
    model_version: str = QUALIFIED_CONSENSUS_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def build_qualified_consensus(
    *,
    consensus: ConsensusLine,
    quality: ConsensusQuality,
) -> QualifiedConsensus:
    market_unavailable = (
        consensus.market_probability is None
        or consensus.agreement == "unavailable"
    )
    status = (
        "unavailable"
        if market_unavailable
        else cast(QualifiedConsensusStatus, quality.status)
    )

    if market_unavailable:
        explanation = (
            "Qualified consensus is unavailable because a complete no-vig "
            "moneyline market is not available."
        )
    else:
        explanation = (
            f"{consensus.classification} signal with {quality.label.lower()} "
            f"consensus quality ({quality.score}/100). {consensus.summary}"
        )

    return QualifiedConsensus(
        classification=consensus.classification,
        quality_score=quality.score,
        quality_label=quality.label,
        status=status,
        model_pick=consensus.model_pick,
        market_favorite=consensus.market_favorite,
        model_probability=consensus.model_probability,
        no_vig_market_probability=consensus.market_probability,
        model_market_edge=consensus.edge,
        explanation=explanation,
        reasons=quality.reasons,
    )
