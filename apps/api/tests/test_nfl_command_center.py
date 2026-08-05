from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.intelligence.nfl_command_center import build_nfl_command_center
from app.intelligence.prediction_change import PredictionSnapshot
from app.intelligence.snapshot_store import PredictionSnapshotStore
from app.main import app


def _item(*, status="qualified", edge=.08, confidence=72, market=True, readiness="ready", pick="Away", favorite="Away", quality=85):
    return {
        "game": {"game_id": f"{pick}-{status}", "away_team": "Away", "home_team": "Home", "start_time": "2026-09-01T20:00:00Z"},
        "prediction": {"pick": pick, "confidence": confidence, "metadata": {
            "season_phase": "regular", "data_readiness_label": readiness, "market_available": market,
            "qb_announced": True, "qb_confirmed": True,
            "qualified_consensus": {"status": status, "classification": "Strong value", "quality_score": quality, "quality_label": "Strong" if quality >= 70 else "Weak",
                "market_favorite": favorite, "model_probability": .62, "no_vig_market_probability": .54 if market else None,
                "model_market_edge": edge if market else None, "reasons": ["Market and model inputs are aligned."]},
        }},
    }


def test_empty_schedule_and_observation_invariant():
    result = build_nfl_command_center({"games": []}, generated_at=datetime.now(timezone.utc))
    assert result.game_count == 0
    assert result.system_status.status == "empty"
    assert result.affects_prediction is False


def test_opportunity_scoring_and_labels_are_deterministic():
    payload = {"games": [_item(), _item(status="watch", edge=.02, confidence=55, pick="Home")]}
    first = build_nfl_command_center(payload, generated_at=datetime.now(timezone.utc))
    second = build_nfl_command_center(payload, generated_at=datetime.now(timezone.utc))
    assert [item.opportunity_score for item in first.all_games] == [item.opportunity_score for item in second.all_games]
    assert first.opportunities[0].opportunity_score >= first.opportunities[1].opportunity_score
    assert first.opportunities[0].opportunity_label in {"Priority", "Strong", "Watch", "Limited"}


def test_hold_missing_market_and_limited_readiness_are_cautions():
    result = build_nfl_command_center({"games": [_item(status="hold"), _item(market=False, pick="Home"), _item(readiness="limited", pick="Other")]})
    assert len(result.games_to_avoid) == 3
    assert all(item.affects_prediction is False for item in result.games_to_avoid)


def test_market_disagreement_and_featured_upset_candidate():
    result = build_nfl_command_center({"games": [_item(pick="Away", favorite="Home")]})
    assert result.market_disagreements[0].game_id == "Away-qualified"
    assert result.featured_picks["upset_candidate"] is not None


def test_degraded_snapshot_store_keeps_game_intelligence():
    result = build_nfl_command_center({"games": [_item()]}, snapshot_available=False)
    assert result.game_count == 1
    assert result.system_status.status == "degraded"
    assert result.major_changes == ()


def _snapshot(minute: int, pick: str) -> PredictionSnapshot:
    return PredictionSnapshot(
        game_id="Away-qualified", captured_at=datetime(2026, 9, 1, 12, minute, tzinfo=timezone.utc),
        pick=pick, model_probability=.62, displayed_confidence=72,
        raw_confidence=74, confidence_cap=72, readiness_label="ready",
        season_phase="regular", away_qb_status="confirmed", home_qb_status="confirmed",
        away_moneyline=-120, home_moneyline=110, market_pick_probability=.54,
        model_market_edge=.08, qualified_consensus_status="qualified",
        qualified_consensus_classification="Strong value",
        qualified_consensus_quality_score=85, model_version="test-v1",
    )


def test_major_changes_are_bounded_and_prioritized():
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot(0, "Away")); store.add_snapshot(_snapshot(1, "Home"))
    result = build_nfl_command_center({"games": [_item()]}, store.get_changes_many(("Away-qualified",)))
    assert result.major_changes[0].significance == "major"
    assert len(result.major_changes[0].changes) <= 3
    assert result.major_changes[0].changes[0].field == "pick"


def test_command_center_endpoint_contract(monkeypatch):
    monkeypatch.setattr("app.main.sports_home", lambda _sport: {"games": [_item()]})
    monkeypatch.setattr("app.main.nfl_snapshot_store.get_changes_many", lambda _ids: {})
    response = TestClient(app).get("/api/sports/nfl/command-center")
    assert response.status_code == 200
    assert response.json()["affects_prediction"] is False
