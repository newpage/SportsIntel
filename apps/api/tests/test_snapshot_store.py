from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import logging

from fastapi.testclient import TestClient
import pytest

import app.main as main_module
import app.sports_api as sports_api
from app.intelligence.prediction_change import PredictionSnapshot
from app.intelligence.snapshot_store import (
    PostgresPredictionSnapshotStore,
    PredictionSnapshotStore,
    SnapshotStoreUnavailable,
    create_prediction_snapshot_store,
    nfl_snapshot_store,
)
from app.main import app
from app.sports import SportCapabilities, SportGame, SportPrediction


CAPTURED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _snapshot(
    *,
    game_id: str = "nfl-123",
    minute: int = 0,
    away_moneyline: float | None = 120,
    displayed_confidence: int = 60,
    pick: str = "Arizona Cardinals",
    qualified_consensus_status: str = "watch",
) -> PredictionSnapshot:
    return PredictionSnapshot(
        game_id=game_id,
        captured_at=CAPTURED_AT + timedelta(minutes=minute),
        pick=pick,
        model_probability=0.62,
        displayed_confidence=displayed_confidence,
        raw_confidence=64,
        confidence_cap=60,
        readiness_label="limited",
        season_phase="preseason",
        away_qb_status="confirmed",
        home_qb_status="expected",
        away_moneyline=away_moneyline,
        home_moneyline=-110,
        market_pick_probability=0.52,
        model_market_edge=0.10,
        qualified_consensus_status=qualified_consensus_status,
        qualified_consensus_classification="Strong value",
        qualified_consensus_quality_score=65,
        model_version="nfl-provisional-ratings-v1",
    )


def _prediction(game_id: str, *, available: bool = True) -> SportPrediction:
    return SportPrediction(
        sport="nfl",
        game_id=game_id,
        pick="Arizona Cardinals" if available else None,
        confidence=60 if available else None,
        model_version="nfl-provisional-ratings-v1",
        metadata={
            "prediction_available": available,
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


class _NFLProvider:
    sport_key = "nfl"
    display_name = "National Football League"
    capabilities = SportCapabilities(moneyline=True)

    def __init__(self, *, available: bool = True, game_count: int = 2) -> None:
        self.available = available
        self.games = [
            SportGame(
                sport="nfl",
                game_id=f"nfl-auto-{index}",
                away_team=f"Away {index}",
                home_team=f"Home {index}",
                start_time="2026-09-01T20:00:00Z",
            )
            for index in range(game_count)
        ]

    def schedule(self, target_date=None):
        return self.games

    def predict(self, game: SportGame) -> SportPrediction:
        return _prediction(game.game_id, available=self.available)

    def health(self):
        return {"status": "available"}


def test_first_snapshot_is_stored() -> None:
    store = PredictionSnapshotStore()

    result = store.add_snapshot(_snapshot())

    assert result.stored is True
    assert result.snapshot_count == 1
    assert result.previous_snapshot is None
    assert result.affects_prediction is False


def test_consecutive_equivalent_snapshots_are_deduplicated() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot())

    result = store.add_snapshot(_snapshot(minute=1))

    assert result.stored is False
    assert result.snapshot_count == 1


def test_state_reversion_stores_all_versions_and_final_state() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot(minute=0, qualified_consensus_status="watch"))
    store.add_snapshot(_snapshot(minute=1, qualified_consensus_status="hold"))

    result = store.add_snapshot(
        _snapshot(minute=2, qualified_consensus_status="watch")
    )
    history = store.get_history("nfl-123", 10)

    assert result.stored is True
    assert result.snapshot_count == 3
    assert [item.qualified_consensus_status for item in history] == [
        "watch",
        "hold",
        "watch",
    ]
    assert store.get_latest("nfl-123") == history[0]


def test_state_reversion_compares_previous_state_and_is_major() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot(minute=0, qualified_consensus_status="watch"))
    hold = _snapshot(minute=1, qualified_consensus_status="hold")
    final_watch = _snapshot(minute=2, qualified_consensus_status="watch")
    store.add_snapshot(hold)
    store.add_snapshot(final_watch)

    result = store.get_latest_comparison("nfl-123")

    assert store.get_previous("nfl-123") == hold
    assert store.get_latest("nfl-123") == final_watch
    assert result is not None
    assert result.significance == "major"
    assert any(
        change.field == "qualified_consensus_status"
        and change.previous_value == "hold"
        and change.current_value == "watch"
        and change.significance == "major"
        for change in result.changes
    )


def test_changed_snapshot_is_appended() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot())

    result = store.add_snapshot(_snapshot(minute=1, away_moneyline=130))

    assert result.stored is True
    assert result.snapshot_count == 2
    assert result.latest_comparison is not None
    assert result.latest_comparison.changed is True


def test_store_retains_latest_twenty_snapshots() -> None:
    store = PredictionSnapshotStore()
    for minute in range(25):
        store.add_snapshot(
            _snapshot(minute=minute, away_moneyline=100 + minute)
        )

    history = store.get_history("nfl-123", 20)

    assert len(history) == 20
    assert history[0].captured_at == CAPTURED_AT + timedelta(minutes=24)
    assert history[-1].captured_at == CAPTURED_AT + timedelta(minutes=5)


def test_store_retention_still_works_after_state_reversions() -> None:
    store = PredictionSnapshotStore()
    for minute in range(25):
        status = "watch" if minute % 2 == 0 else "hold"
        store.add_snapshot(
            _snapshot(
                minute=minute,
                qualified_consensus_status=status,
            )
        )

    history = store.get_history("nfl-123", 20)

    assert len(history) == 20
    assert history[0].captured_at == CAPTURED_AT + timedelta(minutes=24)
    assert history[0].qualified_consensus_status == "watch"
    assert history[-1].captured_at == CAPTURED_AT + timedelta(minutes=5)
    assert history[-1].qualified_consensus_status == "hold"


def test_history_is_chronological_and_newest_first() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot(minute=2, away_moneyline=140))
    store.add_snapshot(_snapshot(minute=0, away_moneyline=120))
    store.add_snapshot(_snapshot(minute=1, away_moneyline=130))

    history = store.get_history("nfl-123", 10)

    assert [item.away_moneyline for item in history] == [140, 130, 120]


def test_latest_and_previous_retrieval() -> None:
    store = PredictionSnapshotStore()
    first = _snapshot()
    second = _snapshot(minute=1, away_moneyline=130)
    store.add_snapshot(first)
    store.add_snapshot(second)

    assert store.get_latest("nfl-123") == second
    assert store.get_previous("nfl-123") == first


def test_latest_comparison() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot())
    store.add_snapshot(_snapshot(minute=1, displayed_confidence=63))

    result = store.get_latest_comparison("nfl-123")

    assert result is not None
    assert result.significance == "notable"
    assert result.affects_prediction is False


def test_clear_game_and_clear_all() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot(game_id="nfl-1"))
    store.add_snapshot(_snapshot(game_id="nfl-2"))

    assert store.clear_game("nfl-1") == 1
    result = store.clear_all()

    assert result.removed_games == 1
    assert result.removed_snapshots == 1
    assert store.get_latest("nfl-2") is None


def test_concurrent_insertion_is_thread_safe() -> None:
    store = PredictionSnapshotStore()
    snapshots = [
        _snapshot(minute=minute, away_moneyline=100 + minute)
        for minute in range(40)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(store.add_snapshot, snapshots))

    history = store.get_history("nfl-123", 20)

    assert len(history) == 20
    assert history[0].captured_at == CAPTURED_AT + timedelta(minutes=39)
    assert history[-1].captured_at == CAPTURED_AT + timedelta(minutes=20)


def test_concurrent_equivalent_insertion_is_deduplicated() -> None:
    store = PredictionSnapshotStore()
    snapshots = [_snapshot(minute=minute) for minute in range(40)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(store.add_snapshot, snapshots))

    history = store.get_history("nfl-123", 20)

    assert len(history) == 1
    assert store.get_snapshot_count("nfl-123") == 1


def test_nfl_endpoint_automatically_captures_shared_timestamp(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sports_api,
        "_ensure_provider",
        lambda sport: _NFLProvider(),
    )

    response = TestClient(app).get("/api/sports/nfl")

    assert response.status_code == 200
    first = nfl_snapshot_store.get_latest("nfl-auto-0")
    second = nfl_snapshot_store.get_latest("nfl-auto-1")
    assert first is not None
    assert second is not None
    assert first.captured_at == second.captured_at


def test_unavailable_prediction_is_not_captured(monkeypatch) -> None:
    monkeypatch.setattr(
        sports_api,
        "_ensure_provider",
        lambda sport: _NFLProvider(available=False, game_count=1),
    )

    response = TestClient(app).get("/api/sports/nfl")

    assert response.status_code == 200
    assert nfl_snapshot_store.get_latest("nfl-auto-0") is None


def test_snapshot_failure_does_not_break_nfl_response(
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.setattr(
        sports_api,
        "_ensure_provider",
        lambda sport: _NFLProvider(game_count=1),
    )
    monkeypatch.setattr(
        sports_api,
        "build_prediction_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("capture failed")
        ),
    )

    with caplog.at_level(logging.ERROR):
        response = TestClient(app).get("/api/sports/nfl")

    assert response.status_code == 200
    assert "game_id=nfl-auto-0" in caplog.text
    assert "capture failed" in caplog.text


def test_database_snapshot_failure_does_not_break_nfl_response(
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.setattr(
        sports_api,
        "_ensure_provider",
        lambda sport: _NFLProvider(game_count=1),
    )
    monkeypatch.setattr(
        sports_api.nfl_snapshot_store,
        "add_snapshot",
        lambda snapshot: (_ for _ in ()).throw(
            SnapshotStoreUnavailable("database unavailable")
        ),
    )

    with caplog.at_level(logging.ERROR):
        response = TestClient(app).get("/api/sports/nfl")

    assert response.status_code == 200
    assert "game_id=nfl-auto-0" in caplog.text
    assert "database unavailable" in caplog.text


def test_history_endpoint_and_invalid_limit() -> None:
    nfl_snapshot_store.add_snapshot(_snapshot())
    nfl_snapshot_store.add_snapshot(
        _snapshot(minute=1, away_moneyline=130)
    )
    client = TestClient(app)

    response = client.get("/api/sports/nfl/nfl-123/history?limit=1")
    invalid = client.get("/api/sports/nfl/nfl-123/history?limit=21")

    assert response.status_code == 200
    assert response.json()["snapshot_count"] == 2
    assert len(response.json()["snapshots"]) == 1
    assert invalid.status_code == 422


def test_history_endpoint_returns_not_found() -> None:
    response = TestClient(app).get(
        "/api/sports/nfl/missing/history"
    )

    assert response.status_code == 404


def test_history_endpoint_returns_service_error_on_store_outage(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        main_module.nfl_snapshot_store,
        "get_history",
        lambda game_id, limit: (_ for _ in ()).throw(
            SnapshotStoreUnavailable("credential-bearing raw error")
        ),
    )

    response = TestClient(app).get("/api/sports/nfl/nfl-123/history")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "NFL snapshot history service is unavailable"
    }
    assert "credential-bearing" not in response.text


def test_changes_endpoint_with_zero_one_and_multiple_snapshots() -> None:
    client = TestClient(app)
    empty = client.get("/api/sports/nfl/nfl-123/changes")

    nfl_snapshot_store.add_snapshot(_snapshot())
    single = client.get("/api/sports/nfl/nfl-123/changes")

    nfl_snapshot_store.add_snapshot(
        _snapshot(minute=1, displayed_confidence=63)
    )
    multiple = client.get("/api/sports/nfl/nfl-123/changes")

    assert empty.status_code == 404
    assert single.status_code == 200
    assert single.json()["changed"] is False
    assert single.json()["latest_comparison"] is None
    assert single.json()["summary"] == (
        "No prior snapshot is available for comparison."
    )
    assert multiple.status_code == 200
    assert multiple.json()["changed"] is True
    assert multiple.json()["significance"] == "notable"


def test_clear_endpoints() -> None:
    nfl_snapshot_store.add_snapshot(_snapshot(game_id="nfl-1"))
    nfl_snapshot_store.add_snapshot(_snapshot(game_id="nfl-2"))
    client = TestClient(app)

    per_game = client.delete("/api/sports/nfl/nfl-1/history")
    clear_all = client.post("/api/sports/nfl/history/clear")

    assert per_game.status_code == 200
    assert per_game.json()["removed_snapshots"] == 1
    assert clear_all.status_code == 200
    assert clear_all.json()["removed_games"] == 1
    assert clear_all.json()["removed_snapshots"] == 1


def test_review_snapshot_diagnostics(monkeypatch) -> None:
    nfl_snapshot_store.add_snapshot(_snapshot(game_id="nfl-major"))
    nfl_snapshot_store.add_snapshot(
        _snapshot(
            game_id="nfl-major",
            minute=1,
            pick="Carolina Panthers",
        )
    )
    nfl_snapshot_store.add_snapshot(_snapshot(game_id="nfl-notable"))
    nfl_snapshot_store.add_snapshot(
        _snapshot(
            game_id="nfl-notable",
            minute=1,
            displayed_confidence=63,
        )
    )
    nfl_snapshot_store.add_snapshot(_snapshot(game_id="nfl-single"))
    monkeypatch.setattr(
        main_module,
        "sports_home",
        lambda sport: {"date": "2026-09-01", "games": []},
    )

    response = TestClient(app).get("/api/sports/nfl/review")
    payload = response.json()

    assert response.status_code == 200
    assert payload["games_with_snapshot_history"] == 3
    assert payload["games_with_multiple_snapshots"] == 2
    assert payload["games_with_meaningful_changes"] == 2
    assert payload["major_change_count"] == 1
    assert payload["notable_change_count"] == 1
    assert payload["snapshot_store_type"] == "memory"
    assert payload["snapshot_persistence"] is False


def test_store_configuration_defaults_and_explicit_selection() -> None:
    default_store = create_prediction_snapshot_store({})
    memory_store = create_prediction_snapshot_store(
        {"NFL_SNAPSHOT_STORE": "memory", "DATABASE_URL": "ignored"}
    )
    postgres_store = create_prediction_snapshot_store(
        {"DATABASE_URL": "postgresql://example.invalid/sportsintel"}
    )

    assert isinstance(default_store, PredictionSnapshotStore)
    assert isinstance(memory_store, PredictionSnapshotStore)
    assert isinstance(postgres_store, PostgresPredictionSnapshotStore)
    assert postgres_store.store_type == "postgres"
    assert postgres_store.persistence_enabled is True


def test_explicit_postgres_configuration_requires_database_url() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        create_prediction_snapshot_store({"NFL_SNAPSHOT_STORE": "postgres"})


def test_memory_store_health_is_nonpersistent() -> None:
    store = PredictionSnapshotStore()
    store.add_snapshot(_snapshot())

    health = store.health()

    assert health.snapshot_store_type == "memory"
    assert health.snapshot_persistence is False
    assert health.retained_snapshot_count == 1
    assert health.database_reachable is False
