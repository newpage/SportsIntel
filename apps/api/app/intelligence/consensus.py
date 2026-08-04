from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CONSENSUS_VERSION = "consensus-line-v1"


@dataclass(frozen=True, slots=True)
class ConsensusLine:
    model_pick: str
    market_favorite: str | None
    agreement: str
    model_probability: float
    market_probability: float | None
    edge: float | None
    classification: str
    summary: str
    affects_prediction: bool = False
    model_version: str = CONSENSUS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_consensus_line(
    *,
    model_pick: str,
    away_team: str,
    home_team: str,
    model_probability: float,
    away_market_probability: float | None,
    home_market_probability: float | None,
) -> ConsensusLine:
    market_available = isinstance(
        away_market_probability,
        (int, float),
    ) and isinstance(home_market_probability, (int, float))

    if not market_available:
        return ConsensusLine(
            model_pick=model_pick,
            market_favorite=None,
            agreement="unavailable",
            model_probability=round(float(model_probability), 4),
            market_probability=None,
            edge=None,
            classification="Market unavailable",
            summary="A complete no-vig moneyline market is not available.",
        )

    away_probability = float(away_market_probability)
    home_probability = float(home_market_probability)
    market_favorite = (
        away_team
        if away_probability > home_probability
        else home_team
        if home_probability > away_probability
        else None
    )

    market_pick_probability = (
        away_probability if model_pick == away_team else home_probability
    )
    edge = round(float(model_probability) - market_pick_probability, 4)
    magnitude = abs(edge)
    agreement = (
        "agree"
        if market_favorite == model_pick
        else "split"
        if market_favorite is not None
        else "even_market"
    )

    if edge >= 0.08:
        classification = "Strong value"
    elif edge >= 0.03:
        classification = "Value"
    elif edge > -0.03:
        classification = "Neutral"
    elif edge > -0.08:
        classification = "Fade"
    else:
        classification = "Large disagreement"

    if market_favorite is None:
        summary = "The no-vig market is evenly split."
    elif agreement == "agree":
        summary = (
            f"SportsIntel and the market both favor {model_pick}; "
            f"the probability difference is {edge * 100:+.1f} points."
        )
    else:
        summary = (
            f"SportsIntel favors {model_pick}, while the market favors "
            f"{market_favorite}; the model difference is {edge * 100:+.1f} points."
        )

    return ConsensusLine(
        model_pick=model_pick,
        market_favorite=market_favorite,
        agreement=agreement,
        model_probability=round(float(model_probability), 4),
        market_probability=round(market_pick_probability, 4),
        edge=edge,
        classification=classification,
        summary=summary,
    )
