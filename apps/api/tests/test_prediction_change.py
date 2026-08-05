from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.intelligence.prediction_change import (
    PredictionComparisonRequest,
    PredictionSnapshot,
    build_prediction_snapshot,
    compare_prediction_snapshots,
)
from app.main import app
from app.sports.models import SportPrediction


CAPTURED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _snapshot(**overrides: object) -> PredictionSnapshot:
    values: dict[str, object] = {
        "game_id": "nfl-123",
        "captured_at": CAPTURED_AT,
        "pick": "Arizona Cardinals",
        "model_probability": 0.62,
        "displayed_confidence": 60,
        "raw_confidence": 64,
        "confidence_cap": 60,
        "readiness_label": "limited",
        "season_phase": "preseason",
        "away_qb_status": "confirmed",
        "home_qb_status": "expected",
        "away_moneyline": 120,
        "home_moneyline": -110,
        "market_pick_probability": 0.52,
        "model_market_edge": 0.10,
        "qualified_consensus_status": "watch",
        "qualified_consensus_classification": "Strong value",
        "qualified_consensus_quality_score": 65,
        "model_version": "nfl-provisional-ratings-v1",
    }
    values.update(overrides)
    return PredictionSnapshot.model_validate(values)


def _current(**overrides: object) -> PredictionSnapshot:
    values = {"captured_at": CAPTURED_AT + timedelta(hours=1), **overrides}
    return _snapshot(**values)


def test_build_prediction_snapshot_uses_existing_metadata() -> None:
    prediction = SportPrediction(
        sport="nfl",
        game_id="nfl-123",
        pick="Arizona Cardinals",
        confidence=60,
        model_version="nfl-provisional-ratings-v1",
        metadata={
            "model_pick_probability": 0.62,
            "raw_confidence": 64,
            "confidence_cap": 60,
            "data_readiness_label": "limited",
            "season_phase": "preseason",
            "away_qb": {"status": "confirmed"},
            "home_qb": {"status": "expected"},
            "away_moneyline": 120,
            "home_moneyline": -110,
            "market_pick_probability": 0.52,
            "market_edge": 0.10,
            "qualified_consensus": {
                "status": "watch",
                "classification": "Strong value",
                "quality_score": 65,
            },
        },
    )

    result = build_prediction_snapshot(
        prediction,
        captured_at=CAPTURED_AT,
    )

    assert result.game_id == prediction.game_id
    assert result.pick == prediction.pick
    assert result.model_probability == 0.62
    assert result.displayed_confidence == prediction.confidence
    assert result.qualified_consensus_status == "watch"


def test_no_changes() -> None:
    result = compare_prediction_snapshots(_snapshot(), _current())

    assert result.changed is False
    assert result.significance == "none"
    assert result.change_count == 0
    assert result.changes == ()


def test_minor_moneyline_movement() -> None:
    result = compare_prediction_snapshots(
        _snapshot(),
        _current(away_moneyline=130),
    )

    assert result.changed is True
    assert result.significance == "minor"
    assert result.change_count == 1
    assert result.changes[0].field == "away_moneyline"
    assert result.changes[0].direction == "increased"


def test_notable_confidence_and_edge_movement() -> None:
    result = compare_prediction_snapshots(
        _snapshot(),
        _current(displayed_confidence=63, model_market_edge=0.15),
    )

    assert result.significance == "notable"
    assert {change.field for change in result.changes} == {
        "displayed_confidence",
        "model_market_edge",
    }


def test_detects_remaining_required_thresholds() -> None:
    result = compare_prediction_snapshots(
        _snapshot(),
        _current(
            model_probability=0.63,
            confidence_cap=64,
            readiness_label="developing",
            away_qb_status="expected",
            home_moneyline=-120,
            market_pick_probability=0.53,
            qualified_consensus_status="caution",
            qualified_consensus_classification="Value",
            qualified_consensus_quality_score=75,
        ),
    )

    assert result.significance == "notable"
    assert {change.field for change in result.changes} == {
        "model_probability",
        "confidence_cap",
        "readiness_label",
        "away_qb_status",
        "home_moneyline",
        "market_pick_probability",
        "qualified_consensus_status",
        "qualified_consensus_classification",
        "qualified_consensus_quality_score",
    }


def test_major_pick_change() -> None:
    result = compare_prediction_snapshots(
        _snapshot(),
        _current(pick="Carolina Panthers"),
    )

    assert result.significance == "major"
    assert result.changes[0].field == "pick"


def test_major_quarterback_downgrade() -> None:
    result = compare_prediction_snapshots(
        _snapshot(),
        _current(home_qb_status="out"),
    )

    assert result.significance == "major"
    assert result.changes[0].field == "home_qb_status"


def test_consensus_status_moving_to_hold_is_major() -> None:
    result = compare_prediction_snapshots(
        _snapshot(),
        _current(qualified_consensus_status="hold"),
    )

    assert result.significance == "major"
    assert result.changes[0].field == "qualified_consensus_status"


def test_comparison_remains_observation_only() -> None:
    result = compare_prediction_snapshots(
        _snapshot(),
        _current(displayed_confidence=61),
    )

    assert result.affects_prediction is False


def test_compare_endpoint_rejects_invalid_request() -> None:
    previous = _snapshot().model_dump(mode="json")
    current = _current(game_id="nfl-456").model_dump(mode="json")

    response = TestClient(app).post(
        "/api/sports/nfl/compare",
        json={"previous": previous, "current": current},
    )

    assert response.status_code == 422
    assert "same game_id" in response.text


def test_compare_endpoint_returns_typed_result() -> None:
    previous = _snapshot().model_dump(mode="json")
    current = _current(away_moneyline=135).model_dump(mode="json")

    response = TestClient(app).post(
        "/api/sports/nfl/compare",
        json={"previous": previous, "current": current},
    )

    assert response.status_code == 200
    assert response.json()["significance"] == "minor"
    assert response.json()["affects_prediction"] is False


@pytest.mark.parametrize(
    "current_time",
    [
        CAPTURED_AT,
        CAPTURED_AT - timedelta(minutes=1),
    ],
)
def test_request_model_rejects_nonsequential_timestamps(
    current_time: datetime,
) -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "current.captured_at must be later than previous.captured_at"
        ),
    ):
        PredictionComparisonRequest(
            previous=_snapshot(),
            current=_snapshot(captured_at=current_time),
        )


def test_direct_comparison_rejects_reversed_timestamps() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "current.captured_at must be later than previous.captured_at"
        ),
    ):
        compare_prediction_snapshots(
            _snapshot(captured_at=CAPTURED_AT + timedelta(minutes=1)),
            _snapshot(),
        )


@pytest.mark.parametrize(
    ("previous_value", "current_value", "direction", "message"),
    [
        (None, 120, "added", "Away moneyline became available."),
        (120, None, "removed", "Away moneyline became unavailable."),
    ],
)
def test_moneyline_availability_changes(
    previous_value: int | None,
    current_value: int | None,
    direction: str,
    message: str,
) -> None:
    result = compare_prediction_snapshots(
        _snapshot(away_moneyline=previous_value),
        _current(away_moneyline=current_value),
    )

    assert result.change_count == 1
    assert result.changes[0].direction == direction
    assert result.changes[0].explanation == message


@pytest.mark.parametrize(
    ("previous_value", "current_value", "direction", "message"),
    [
        (None, 0.52, "added", "No-vig market probability became available."),
        (0.52, None, "removed", "No-vig market probability became unavailable."),
    ],
)
def test_market_probability_availability_changes(
    previous_value: float | None,
    current_value: float | None,
    direction: str,
    message: str,
) -> None:
    result = compare_prediction_snapshots(
        _snapshot(market_pick_probability=previous_value),
        _current(market_pick_probability=current_value),
    )

    assert result.change_count == 1
    assert result.changes[0].direction == direction
    assert result.changes[0].explanation == message


@pytest.mark.parametrize(
    ("previous_value", "current_value", "direction", "message"),
    [
        (None, 0.10, "added", "Model-market edge became available."),
        (0.10, None, "removed", "Model-market edge became unavailable."),
    ],
)
def test_model_market_edge_availability_changes(
    previous_value: float | None,
    current_value: float | None,
    direction: str,
    message: str,
) -> None:
    result = compare_prediction_snapshots(
        _snapshot(model_market_edge=previous_value),
        _current(model_market_edge=current_value),
    )

    assert result.change_count == 1
    assert result.changes[0].direction == direction
    assert result.changes[0].explanation == message
