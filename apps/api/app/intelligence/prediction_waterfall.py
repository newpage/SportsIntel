from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PREDICTION_WATERFALL_VERSION = "prediction-waterfall-v1"


@dataclass(frozen=True, slots=True)
class WaterfallStep:
    step_id: str
    label: str
    kind: str
    value: float
    affects_confidence: bool
    explanation: str
    direction: str = "neutral"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PredictionWaterfall:
    starting_confidence: float
    final_confidence: float
    total_adjustment: float
    steps: tuple[WaterfallStep, ...]
    reconciles: bool
    model_version: str = PREDICTION_WATERFALL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "starting_confidence": self.starting_confidence,
            "final_confidence": self.final_confidence,
            "total_adjustment": self.total_adjustment,
            "steps": [step.to_dict() for step in self.steps],
            "reconciles": self.reconciles,
            "model_version": self.model_version,
        }


def build_prediction_waterfall(
    *,
    raw_confidence: float,
    final_confidence: float,
    readiness_cap: float,
    final_cap: float,
    rating_gap: float,
    home_field_rating: float,
    season_phase: str,
    qb_announced: bool,
    away_health: dict[str, Any],
    home_health: dict[str, Any],
    market_signal_label: str,
    market_available: bool,
) -> PredictionWaterfall:
    after_readiness = min(raw_confidence, readiness_cap)
    readiness_adjustment = round(after_readiness - raw_confidence, 2)
    after_context = min(after_readiness, final_cap)
    context_adjustment = round(after_context - after_readiness, 2)

    away_health_label = str(away_health.get("overall_label") or "Unknown")
    home_health_label = str(home_health.get("overall_label") or "Unknown")

    steps = (
        WaterfallStep(
            step_id="baseline_confidence",
            label="Baseline model",
            kind="baseline",
            value=round(raw_confidence, 2),
            affects_confidence=True,
            explanation=(
                f"Baseline confidence from a {abs(rating_gap):.1f}-point "
                "adjusted team-rating gap."
            ),
        ),
        WaterfallStep(
            step_id="home_field",
            label="Home field",
            kind="observation",
            value=round(home_field_rating, 2),
            affects_confidence=False,
            explanation=(
                "Home field is already included in the baseline rating gap."
            ),
            direction="home",
        ),
        WaterfallStep(
            step_id="data_readiness",
            label="Data-readiness guardrail",
            kind="adjustment",
            value=readiness_adjustment,
            affects_confidence=True,
            explanation=(
                f"Confidence is limited to {readiness_cap:.0f}% based on "
                "the available data coverage."
            ),
            direction="negative" if readiness_adjustment < 0 else "neutral",
        ),
        WaterfallStep(
            step_id="season_context",
            label="Season context",
            kind="adjustment",
            value=context_adjustment,
            affects_confidence=True,
            explanation=(
                f"{season_phase.title()} context sets the final confidence "
                f"cap at {final_cap:.0f}%."
            ),
            direction="negative" if context_adjustment < 0 else "neutral",
        ),
        WaterfallStep(
            step_id="quarterback_context",
            label="Quarterback context",
            kind="observation",
            value=0.0,
            affects_confidence=False,
            explanation=(
                "Both expected quarterbacks are available for review."
                if qb_announced
                else "Starting quarterbacks are not yet announced."
            ),
        ),
        WaterfallStep(
            step_id="team_health",
            label="Team health",
            kind="observation",
            value=0.0,
            affects_confidence=False,
            explanation=(
                f"Away health: {away_health_label}; "
                f"home health: {home_health_label}."
            ),
        ),
        WaterfallStep(
            step_id="market_comparison",
            label="Market comparison",
            kind="observation",
            value=0.0,
            affects_confidence=False,
            explanation=(
                market_signal_label
                if market_available
                else "A complete moneyline market is not available."
            ),
        ),
    )

    total_adjustment = round(final_confidence - raw_confidence, 2)
    reconciled = round(raw_confidence + total_adjustment, 2) == round(
        final_confidence,
        2,
    )

    return PredictionWaterfall(
        starting_confidence=round(raw_confidence, 2),
        final_confidence=round(final_confidence, 2),
        total_adjustment=total_adjustment,
        steps=steps,
        reconciles=reconciled,
    )
