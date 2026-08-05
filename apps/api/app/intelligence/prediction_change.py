from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.sports.models import SportPrediction


PREDICTION_COMPARISON_VERSION = "nfl-prediction-comparison-v1"

ChangeDirection = Literal[
    "increased",
    "decreased",
    "changed",
    "added",
    "removed",
]
ChangeSignificance = Literal["none", "minor", "notable", "major"]
QualifiedConsensusStatus = Literal[
    "qualified",
    "watch",
    "caution",
    "hold",
    "unavailable",
]


class PredictionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    game_id: str = Field(min_length=1)
    captured_at: datetime
    pick: str = Field(min_length=1)
    model_probability: float = Field(ge=0.0, le=1.0)
    displayed_confidence: int = Field(ge=0, le=100)
    raw_confidence: int = Field(ge=0, le=100)
    confidence_cap: int = Field(ge=0, le=100)
    readiness_label: str = Field(min_length=1)
    season_phase: str = Field(min_length=1)
    away_qb_status: str = Field(min_length=1)
    home_qb_status: str = Field(min_length=1)
    away_moneyline: float | None = None
    home_moneyline: float | None = None
    market_pick_probability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    model_market_edge: float | None = None
    qualified_consensus_status: QualifiedConsensusStatus
    qualified_consensus_classification: str = Field(min_length=1)
    qualified_consensus_quality_score: int = Field(ge=0, le=100)
    model_version: str = Field(min_length=1)


class PredictionChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    label: str
    previous_value: Any
    current_value: Any
    direction: ChangeDirection
    significance: ChangeSignificance
    explanation: str


class PredictionComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    changed: bool
    significance: ChangeSignificance
    change_count: int = Field(ge=0)
    changes: tuple[PredictionChange, ...]
    summary: str
    affects_prediction: Literal[False] = False
    model_version: str = PREDICTION_COMPARISON_VERSION


class PredictionComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous: PredictionSnapshot
    current: PredictionSnapshot

    @model_validator(mode="after")
    def snapshots_match(self) -> PredictionComparisonRequest:
        if self.previous.game_id != self.current.game_id:
            raise ValueError("Prediction snapshots must use the same game_id")
        _validate_chronology(self.previous, self.current)
        return self


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"NFL prediction is missing {field_name}")
    return value


def _required_number(value: Any, field_name: str) -> int | float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"NFL prediction is missing {field_name}")
    return value


def _optional_number(value: Any) -> int | float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _validate_chronology(
    previous: PredictionSnapshot,
    current: PredictionSnapshot,
) -> None:
    try:
        chronology_is_valid = current.captured_at > previous.captured_at
    except TypeError:
        chronology_is_valid = False
    if not chronology_is_valid:
        raise ValueError(
            "current.captured_at must be later than previous.captured_at"
        )


def build_prediction_snapshot(
    prediction: SportPrediction,
    *,
    captured_at: datetime,
) -> PredictionSnapshot:
    """Create a deterministic comparison snapshot from an NFL prediction."""
    if prediction.sport.strip().lower() != "nfl":
        raise ValueError("Prediction snapshots are supported for NFL only")

    metadata = _mapping(prediction.metadata)
    away_qb = _mapping(metadata.get("away_qb"))
    home_qb = _mapping(metadata.get("home_qb"))
    qualified_consensus = _mapping(metadata.get("qualified_consensus"))

    return PredictionSnapshot(
        game_id=prediction.game_id,
        captured_at=captured_at,
        pick=_required_string(prediction.pick, "pick"),
        model_probability=float(
            _required_number(
                metadata.get("model_pick_probability"),
                "model_pick_probability",
            )
        ),
        displayed_confidence=int(
            _required_number(prediction.confidence, "displayed confidence")
        ),
        raw_confidence=int(
            _required_number(metadata.get("raw_confidence"), "raw_confidence")
        ),
        confidence_cap=int(
            _required_number(metadata.get("confidence_cap"), "confidence_cap")
        ),
        readiness_label=_required_string(
            metadata.get("data_readiness_label"),
            "data_readiness_label",
        ),
        season_phase=_required_string(
            metadata.get("season_phase"),
            "season_phase",
        ),
        away_qb_status=_required_string(
            away_qb.get("status") or "not announced",
            "away_qb_status",
        ),
        home_qb_status=_required_string(
            home_qb.get("status") or "not announced",
            "home_qb_status",
        ),
        away_moneyline=_optional_number(metadata.get("away_moneyline")),
        home_moneyline=_optional_number(metadata.get("home_moneyline")),
        market_pick_probability=_optional_number(
            metadata.get("market_pick_probability")
        ),
        model_market_edge=_optional_number(metadata.get("market_edge")),
        qualified_consensus_status=_required_string(
            qualified_consensus.get("status"),
            "qualified_consensus.status",
        ),
        qualified_consensus_classification=_required_string(
            qualified_consensus.get("classification"),
            "qualified_consensus.classification",
        ),
        qualified_consensus_quality_score=int(
            _required_number(
                qualified_consensus.get("quality_score"),
                "qualified_consensus.quality_score",
            )
        ),
        model_version=_required_string(
            prediction.model_version or metadata.get("rating_version"),
            "model_version",
        ),
    )


def _direction(previous: Any, current: Any) -> ChangeDirection:
    if previous is None:
        return "added"
    if current is None:
        return "removed"
    if (
        isinstance(previous, (int, float))
        and not isinstance(previous, bool)
        and isinstance(current, (int, float))
        and not isinstance(current, bool)
    ):
        return "increased" if current > previous else "decreased"
    return "changed"


def _qb_downgrade_is_major(previous: Any, current: Any) -> bool:
    previous_status = str(previous).strip().lower()
    current_status = str(current).strip().lower()
    was_expected = any(
        value in previous_status for value in ("expected", "confirmed")
    )
    is_unavailable = any(
        value in current_status
        for value in ("out", "inactive", "doubtful")
    )
    return was_expected and is_unavailable


def _change(
    *,
    field: str,
    label: str,
    previous: Any,
    current: Any,
    significance: ChangeSignificance,
    explanation: str,
) -> PredictionChange:
    return PredictionChange(
        field=field,
        label=label,
        previous_value=previous,
        current_value=current,
        direction=_direction(previous, current),
        significance=significance,
        explanation=explanation,
    )


def _difference_meets(
    previous: int | float | None,
    current: int | float | None,
    threshold: float,
) -> bool:
    if previous is None or current is None:
        return previous != current
    return abs(float(current) - float(previous)) + 1e-9 >= threshold


def _optional_value_explanation(
    *,
    label: str,
    previous: int | float | None,
    current: int | float | None,
    movement_explanation: str,
) -> str:
    if previous is None and current is not None:
        return f"{label} became available."
    if previous is not None and current is None:
        return f"{label} became unavailable."
    return movement_explanation


def compare_prediction_snapshots(
    previous: PredictionSnapshot,
    current: PredictionSnapshot,
) -> PredictionComparison:
    """Compare two snapshots without changing either prediction."""
    if previous.game_id != current.game_id:
        raise ValueError("Prediction snapshots must use the same game_id")
    _validate_chronology(previous, current)

    changes: list[PredictionChange] = []

    if previous.pick != current.pick:
        changes.append(
            _change(
                field="pick",
                label="Selected team",
                previous=previous.pick,
                current=current.pick,
                significance="major",
                explanation=(
                    f"The selected team changed from {previous.pick} "
                    f"to {current.pick}."
                ),
            )
        )

    confidence_delta = current.displayed_confidence - previous.displayed_confidence
    if abs(confidence_delta) >= 1:
        significance: ChangeSignificance = (
            "notable" if abs(confidence_delta) >= 3 else "minor"
        )
        changes.append(
            _change(
                field="displayed_confidence",
                label="Displayed confidence",
                previous=previous.displayed_confidence,
                current=current.displayed_confidence,
                significance=significance,
                explanation=(
                    f"Displayed confidence moved {confidence_delta:+d} points."
                ),
            )
        )

    if _difference_meets(
        previous.model_probability,
        current.model_probability,
        0.01,
    ):
        delta = current.model_probability - previous.model_probability
        changes.append(
            _change(
                field="model_probability",
                label="Model probability",
                previous=previous.model_probability,
                current=current.model_probability,
                significance="minor",
                explanation=f"Model probability moved {delta * 100:+.1f} points.",
            )
        )

    if previous.confidence_cap != current.confidence_cap:
        changes.append(
            _change(
                field="confidence_cap",
                label="Confidence cap",
                previous=previous.confidence_cap,
                current=current.confidence_cap,
                significance="minor",
                explanation="The active confidence guardrail changed.",
            )
        )

    if previous.readiness_label != current.readiness_label:
        changes.append(
            _change(
                field="readiness_label",
                label="Data readiness",
                previous=previous.readiness_label,
                current=current.readiness_label,
                significance="notable",
                explanation="The prediction's data-readiness level changed.",
            )
        )

    for field, label in (
        ("away_qb_status", "Away quarterback status"),
        ("home_qb_status", "Home quarterback status"),
    ):
        previous_status = getattr(previous, field)
        current_status = getattr(current, field)
        if previous_status != current_status:
            qb_significance: ChangeSignificance = (
                "major"
                if _qb_downgrade_is_major(previous_status, current_status)
                else "minor"
            )
            changes.append(
                _change(
                    field=field,
                    label=label,
                    previous=previous_status,
                    current=current_status,
                    significance=qb_significance,
                    explanation=(
                        f"{label} changed from {previous_status} "
                        f"to {current_status}."
                    ),
                )
            )

    for field, label in (
        ("away_moneyline", "Away moneyline"),
        ("home_moneyline", "Home moneyline"),
    ):
        previous_value = getattr(previous, field)
        current_value = getattr(current, field)
        if _difference_meets(previous_value, current_value, 10.0):
            changes.append(
                _change(
                    field=field,
                    label=label,
                    previous=previous_value,
                    current=current_value,
                    significance="minor",
                    explanation=_optional_value_explanation(
                        label=label,
                        previous=previous_value,
                        current=current_value,
                        movement_explanation=(
                            f"{label} moved by at least 10 "
                            "American-odds points."
                        ),
                    ),
                )
            )

    if _difference_meets(
        previous.market_pick_probability,
        current.market_pick_probability,
        0.01,
    ):
        changes.append(
            _change(
                field="market_pick_probability",
                label="No-vig market probability",
                previous=previous.market_pick_probability,
                current=current.market_pick_probability,
                significance="minor",
                explanation=_optional_value_explanation(
                    label="No-vig market probability",
                    previous=previous.market_pick_probability,
                    current=current.market_pick_probability,
                    movement_explanation=(
                        "No-vig market probability moved by at least 1 point."
                    ),
                ),
            )
        )

    if _difference_meets(
        previous.model_market_edge,
        current.model_market_edge,
        0.02,
    ):
        if (
            previous.model_market_edge is not None
            and current.model_market_edge is not None
        ):
            edge_delta = current.model_market_edge - previous.model_market_edge
            edge_significance: ChangeSignificance = (
                "notable" if abs(edge_delta) + 1e-9 >= 0.05 else "minor"
            )
        else:
            edge_delta = None
            edge_significance = "minor"
        changes.append(
            _change(
                field="model_market_edge",
                label="Model-market edge",
                previous=previous.model_market_edge,
                current=current.model_market_edge,
                significance=edge_significance,
                explanation=_optional_value_explanation(
                    label="Model-market edge",
                    previous=previous.model_market_edge,
                    current=current.model_market_edge,
                    movement_explanation=(
                        f"Model-market edge moved "
                        f"{edge_delta * 100:+.1f} points."
                        if edge_delta is not None
                        else "Model-market edge availability changed."
                    ),
                ),
            )
        )

    previous_status = previous.qualified_consensus_status
    current_status = current.qualified_consensus_status
    if previous_status != current_status:
        consensus_status_significance: ChangeSignificance = (
            "major"
            if "hold" in {previous_status.lower(), current_status.lower()}
            else "minor"
        )
        changes.append(
            _change(
                field="qualified_consensus_status",
                label="Qualified consensus status",
                previous=previous_status,
                current=current_status,
                significance=consensus_status_significance,
                explanation=(
                    f"Qualified consensus moved from {previous_status} "
                    f"to {current_status}."
                ),
            )
        )

    previous_classification = previous.qualified_consensus_classification
    current_classification = current.qualified_consensus_classification
    if previous_classification != current_classification:
        changes.append(
            _change(
                field="qualified_consensus_classification",
                label="Consensus classification",
                previous=previous_classification,
                current=current_classification,
                significance="notable",
                explanation=(
                    f"Consensus classification changed from "
                    f"{previous_classification} to {current_classification}."
                ),
            )
        )

    if _difference_meets(
        previous.qualified_consensus_quality_score,
        current.qualified_consensus_quality_score,
        10.0,
    ):
        changes.append(
            _change(
                field="qualified_consensus_quality_score",
                label="Consensus quality score",
                previous=previous.qualified_consensus_quality_score,
                current=current.qualified_consensus_quality_score,
                significance="minor",
                explanation="Consensus quality moved by at least 10 points.",
            )
        )

    significance_rank = {"none": 0, "minor": 1, "notable": 2, "major": 3}
    overall_significance: ChangeSignificance = max(
        (change.significance for change in changes),
        key=lambda value: significance_rank[value],
        default="none",
    )
    change_count = len(changes)
    summary = (
        "No meaningful NFL prediction changes were detected."
        if not changes
        else (
            f"Detected {change_count} meaningful NFL prediction "
            f"change{'s' if change_count != 1 else ''}; highest significance "
            f"is {overall_significance}."
        )
    )

    return PredictionComparison(
        changed=bool(changes),
        significance=overall_significance,
        change_count=change_count,
        changes=tuple(changes),
        summary=summary,
    )
