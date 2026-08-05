from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import psycopg
import pytest

from app.intelligence.prediction_change import PredictionSnapshot
from app.intelligence.snapshot_store import (
    PostgresPredictionSnapshotStore,
    SnapshotStoreUnavailable,
)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
CAPTURED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _snapshot(
    *,
    game_id: str = "nfl-postgres-123",
    minute: int = 0,
    away_moneyline: float | None = 120,
    displayed_confidence: int = 60,
    status: str = "watch",
) -> PredictionSnapshot:
    return PredictionSnapshot(
        game_id=game_id,
        captured_at=CAPTURED_AT + timedelta(minutes=minute),
        pick="Arizona Cardinals",
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
        qualified_consensus_status=status,
        qualified_consensus_classification="Strong value",
        qualified_consensus_quality_score=65,
        model_version="nfl-provisional-ratings-v1",
    )


@pytest.fixture
def postgres_store() -> PostgresPredictionSnapshotStore:
    assert TEST_DATABASE_URL is not None
    schema = (
        Path(__file__).parents[3]
        / "db/init/001_nfl_prediction_snapshots.sql"
    ).read_text()
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        connection.execute(schema)
        connection.execute("TRUNCATE nfl_prediction_snapshots RESTART IDENTITY")
    store = PostgresPredictionSnapshotStore(TEST_DATABASE_URL)
    yield store
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        connection.execute("TRUNCATE nfl_prediction_snapshots RESTART IDENTITY")


def test_postgres_first_insert_and_observation_only(postgres_store) -> None:
    result = postgres_store.add_snapshot(_snapshot())

    assert result.stored is True
    assert result.snapshot_count == 1
    assert result.affects_prediction is False
    assert postgres_store.get_latest("nfl-postgres-123") == _snapshot()


def test_postgres_consecutive_deduplication_and_reversion(postgres_store) -> None:
    first = postgres_store.add_snapshot(_snapshot(minute=0, status="watch"))
    duplicate = postgres_store.add_snapshot(_snapshot(minute=1, status="watch"))
    hold = postgres_store.add_snapshot(_snapshot(minute=2, status="hold"))
    reversion = postgres_store.add_snapshot(_snapshot(minute=3, status="watch"))

    assert first.stored is True
    assert duplicate.stored is False
    assert hold.stored is True
    assert reversion.stored is True
    assert postgres_store.get_snapshot_count("nfl-postgres-123") == 3
    assert [item.qualified_consensus_status for item in postgres_store.get_history(
        "nfl-postgres-123", 10
    )] == ["watch", "hold", "watch"]


def test_postgres_latest_previous_history_and_comparison(postgres_store) -> None:
    first = _snapshot(minute=0)
    second = _snapshot(minute=1, displayed_confidence=63)
    postgres_store.add_snapshot(first)
    postgres_store.add_snapshot(second)

    assert postgres_store.get_latest("nfl-postgres-123") == second
    assert postgres_store.get_previous("nfl-postgres-123") == first
    assert postgres_store.get_history("nfl-postgres-123", 2) == (
        second,
        first,
    )
    comparison = postgres_store.get_latest_comparison("nfl-postgres-123")
    changes = postgres_store.get_changes("nfl-postgres-123")
    assert comparison is not None
    assert comparison.significance == "notable"
    assert comparison.affects_prediction is False
    assert changes is not None
    assert changes.snapshot_store_type == "postgres"
    assert changes.snapshot_persistence is True
    assert changes.affects_prediction is False


def test_postgres_retains_newest_twenty(postgres_store) -> None:
    for minute in range(25):
        postgres_store.add_snapshot(
            _snapshot(minute=minute, away_moneyline=100 + minute)
        )

    history = postgres_store.get_history("nfl-postgres-123", 20)

    assert len(history) == 20
    assert history[0].captured_at == CAPTURED_AT + timedelta(minutes=24)
    assert history[-1].captured_at == CAPTURED_AT + timedelta(minutes=5)


def test_postgres_clear_game_and_clear_all(postgres_store) -> None:
    postgres_store.add_snapshot(_snapshot(game_id="nfl-one"))
    postgres_store.add_snapshot(_snapshot(game_id="nfl-two"))

    assert postgres_store.clear_game("nfl-one") == 1
    cleared = postgres_store.clear_all()

    assert cleared.removed_games == 1
    assert cleared.removed_snapshots == 1


def test_postgres_concurrent_equivalent_insert_is_deduplicated(
    postgres_store,
) -> None:
    snapshots = [_snapshot(minute=minute) for minute in range(20)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(postgres_store.add_snapshot, snapshots))

    assert postgres_store.get_snapshot_count("nfl-postgres-123") == 1


def test_postgres_concurrent_changed_inserts_are_chronological(
    postgres_store,
) -> None:
    snapshots = [
        _snapshot(minute=minute, away_moneyline=100 + minute)
        for minute in range(20)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(postgres_store.add_snapshot, reversed(snapshots)))

    history = postgres_store.get_history("nfl-postgres-123", 20)
    assert [item.captured_at for item in history] == sorted(
        (item.captured_at for item in snapshots),
        reverse=True,
    )


def test_postgres_transaction_rolls_back_on_prune_failure(
    postgres_store,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        postgres_store,
        "_prune_history",
        lambda cursor, game_id: (_ for _ in ()).throw(
            RuntimeError("forced prune failure")
        ),
    )

    with pytest.raises(SnapshotStoreUnavailable):
        postgres_store.add_snapshot(_snapshot())

    assert postgres_store.get_snapshot_count("nfl-postgres-123") == 0


def test_postgres_diagnostics_report_persistence(postgres_store) -> None:
    postgres_store.add_snapshot(_snapshot())
    diagnostics = postgres_store.diagnostics()
    health = postgres_store.health()

    assert diagnostics.snapshot_store_type == "postgres"
    assert diagnostics.snapshot_persistence is True
    assert diagnostics.games_with_snapshot_history == 1
    assert health.database_reachable is True
    assert health.snapshot_table_reachable is True
    assert health.retained_snapshot_count == 1
    assert health.last_successful_snapshot_write_time is not None
