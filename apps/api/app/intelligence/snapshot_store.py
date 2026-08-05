from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import logging
import os
from threading import RLock
from typing import Any, Literal, Protocol

import psycopg
from psycopg.rows import dict_row

from pydantic import BaseModel, ConfigDict, Field

from app.intelligence.prediction_change import (
    ChangeSignificance,
    PredictionComparison,
    PredictionSnapshot,
    compare_prediction_snapshots,
)


SNAPSHOT_RETENTION_LIMIT = 20
SnapshotStoreType = Literal["memory", "postgres"]

logger = logging.getLogger(__name__)


class SnapshotStoreUnavailable(RuntimeError):
    """Raised when the configured snapshot store cannot serve a request."""


class SnapshotStoreResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: str
    stored: bool
    snapshot_count: int = Field(ge=0)
    current_snapshot: PredictionSnapshot
    previous_snapshot: PredictionSnapshot | None = None
    latest_comparison: PredictionComparison | None = None
    affects_prediction: Literal[False] = False


class SnapshotHistoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: str
    snapshot_count: int = Field(ge=0)
    snapshots: tuple[PredictionSnapshot, ...]
    snapshot_store_type: SnapshotStoreType = "memory"
    snapshot_persistence: bool = False
    affects_prediction: Literal[False] = False


class SnapshotChangesResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: str
    snapshot_count: int = Field(ge=1)
    current_snapshot: PredictionSnapshot
    previous_snapshot: PredictionSnapshot | None = None
    latest_comparison: PredictionComparison | None = None
    changed: bool
    significance: ChangeSignificance
    summary: str
    snapshot_store_type: SnapshotStoreType = "memory"
    snapshot_persistence: bool = False
    affects_prediction: Literal[False] = False


class SnapshotClearGameResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: str
    removed_snapshots: int = Field(ge=0)
    affects_prediction: Literal[False] = False


class SnapshotClearAllResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    removed_games: int = Field(ge=0)
    removed_snapshots: int = Field(ge=0)
    affects_prediction: Literal[False] = False


class SnapshotStoreDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    games_with_snapshot_history: int = Field(ge=0)
    games_with_multiple_snapshots: int = Field(ge=0)
    games_with_meaningful_changes: int = Field(ge=0)
    major_change_count: int = Field(ge=0)
    notable_change_count: int = Field(ge=0)
    snapshot_store_type: SnapshotStoreType = "memory"
    snapshot_persistence: bool = False


class SnapshotStoreHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_store_type: SnapshotStoreType
    snapshot_persistence: bool
    database_reachable: bool
    snapshot_table_reachable: bool
    retained_snapshot_count: int | None = Field(default=None, ge=0)
    last_successful_snapshot_write_time: datetime | None = None


class PredictionSnapshotStoreProtocol(Protocol):
    store_type: SnapshotStoreType
    persistence_enabled: bool

    def add_snapshot(self, snapshot: PredictionSnapshot) -> SnapshotStoreResult:
        ...

    def get_latest(self, game_id: str) -> PredictionSnapshot | None:
        ...

    def get_previous(self, game_id: str) -> PredictionSnapshot | None:
        ...

    def get_history(
        self,
        game_id: str,
        limit: int = 10,
    ) -> tuple[PredictionSnapshot, ...]:
        ...

    def get_snapshot_count(self, game_id: str) -> int:
        ...

    def get_latest_comparison(
        self,
        game_id: str,
    ) -> PredictionComparison | None:
        ...

    def get_changes(self, game_id: str) -> SnapshotChangesResponse | None:
        ...

    def get_changes_many(
        self, game_ids: tuple[str, ...]
    ) -> dict[str, SnapshotChangesResponse]:
        ...

    def clear_game(self, game_id: str) -> int:
        ...

    def clear_all(self) -> SnapshotClearAllResponse:
        ...

    def diagnostics(self) -> SnapshotStoreDiagnostics:
        ...

    def health(self) -> SnapshotStoreHealth:
        ...


def _equivalent(
    left: PredictionSnapshot,
    right: PredictionSnapshot,
) -> bool:
    return left.model_dump(exclude={"captured_at"}) == right.model_dump(
        exclude={"captured_at"}
    )


class PredictionSnapshotStore:
    """Thread-safe, process-local NFL snapshot history."""

    store_type: Literal["memory"] = "memory"
    persistence_enabled = False

    def __init__(self, *, retention_limit: int = SNAPSHOT_RETENTION_LIMIT) -> None:
        if retention_limit < 1 or retention_limit > SNAPSHOT_RETENTION_LIMIT:
            raise ValueError(
                f"retention_limit must be between 1 and "
                f"{SNAPSHOT_RETENTION_LIMIT}"
            )
        self._retention_limit = retention_limit
        self._history: dict[str, list[PredictionSnapshot]] = {}
        self._lock = RLock()

    def _latest_comparison_unlocked(
        self,
        game_id: str,
    ) -> PredictionComparison | None:
        history = self._history.get(game_id, [])
        if len(history) < 2:
            return None
        return compare_prediction_snapshots(history[-2], history[-1])

    def add_snapshot(self, snapshot: PredictionSnapshot) -> SnapshotStoreResult:
        with self._lock:
            history = self._history.setdefault(snapshot.game_id, [])
            if history and _equivalent(history[-1], snapshot):
                current = history[-1]
                previous = history[-2] if len(history) > 1 else None
                return SnapshotStoreResult(
                    game_id=snapshot.game_id,
                    stored=False,
                    snapshot_count=len(history),
                    current_snapshot=current,
                    previous_snapshot=previous,
                    latest_comparison=self._latest_comparison_unlocked(
                        snapshot.game_id
                    ),
                )

            history.append(snapshot)
            history.sort(key=lambda item: item.captured_at)
            if len(history) > self._retention_limit:
                del history[:-self._retention_limit]

            current = history[-1]
            previous = history[-2] if len(history) > 1 else None
            return SnapshotStoreResult(
                game_id=snapshot.game_id,
                stored=snapshot in history,
                snapshot_count=len(history),
                current_snapshot=current,
                previous_snapshot=previous,
                latest_comparison=self._latest_comparison_unlocked(
                    snapshot.game_id
                ),
            )

    def get_latest(self, game_id: str) -> PredictionSnapshot | None:
        with self._lock:
            history = self._history.get(game_id, [])
            return history[-1] if history else None

    def get_previous(self, game_id: str) -> PredictionSnapshot | None:
        with self._lock:
            history = self._history.get(game_id, [])
            return history[-2] if len(history) > 1 else None

    def get_history(
        self,
        game_id: str,
        limit: int = 10,
    ) -> tuple[PredictionSnapshot, ...]:
        if limit < 1 or limit > self._retention_limit:
            raise ValueError(
                f"limit must be between 1 and {self._retention_limit}"
            )
        with self._lock:
            history = self._history.get(game_id, [])
            return tuple(reversed(history[-limit:]))

    def get_snapshot_count(self, game_id: str) -> int:
        with self._lock:
            return len(self._history.get(game_id, []))

    def get_latest_comparison(
        self,
        game_id: str,
    ) -> PredictionComparison | None:
        with self._lock:
            return self._latest_comparison_unlocked(game_id)

    def get_changes(self, game_id: str) -> SnapshotChangesResponse | None:
        with self._lock:
            history = self._history.get(game_id, [])
            if not history:
                return None

            comparison = self._latest_comparison_unlocked(game_id)
            return SnapshotChangesResponse(
                game_id=game_id,
                snapshot_count=len(history),
                current_snapshot=history[-1],
                previous_snapshot=history[-2] if len(history) > 1 else None,
                latest_comparison=comparison,
                changed=comparison.changed if comparison else False,
                significance=comparison.significance if comparison else "none",
                summary=(
                    comparison.summary
                    if comparison
                    else "No prior snapshot is available for comparison."
                ),
            )

    def get_changes_many(
        self, game_ids: tuple[str, ...]
    ) -> dict[str, SnapshotChangesResponse]:
        with self._lock:
            return {
                game_id: result
                for game_id in game_ids
                if (result := self.get_changes(game_id)) is not None
            }

    def clear_game(self, game_id: str) -> int:
        with self._lock:
            return len(self._history.pop(game_id, []))

    def clear_all(self) -> SnapshotClearAllResponse:
        with self._lock:
            removed_games = len(self._history)
            removed_snapshots = sum(
                len(history) for history in self._history.values()
            )
            self._history.clear()
            return SnapshotClearAllResponse(
                removed_games=removed_games,
                removed_snapshots=removed_snapshots,
            )

    def diagnostics(self) -> SnapshotStoreDiagnostics:
        with self._lock:
            multiple = 0
            meaningful = 0
            major = 0
            notable = 0

            for game_id, history in self._history.items():
                if len(history) < 2:
                    continue
                multiple += 1
                comparison = self._latest_comparison_unlocked(game_id)
                if comparison is None:
                    continue
                if comparison.changed:
                    meaningful += 1
                major += sum(
                    change.significance == "major"
                    for change in comparison.changes
                )
                notable += sum(
                    change.significance == "notable"
                    for change in comparison.changes
                )

            return SnapshotStoreDiagnostics(
                games_with_snapshot_history=len(self._history),
                games_with_multiple_snapshots=multiple,
                games_with_meaningful_changes=meaningful,
                major_change_count=major,
                notable_change_count=notable,
            )

    def health(self) -> SnapshotStoreHealth:
        with self._lock:
            retained = sum(len(history) for history in self._history.values())
        return SnapshotStoreHealth(
            snapshot_store_type="memory",
            snapshot_persistence=False,
            database_reachable=False,
            snapshot_table_reachable=False,
            retained_snapshot_count=retained,
            last_successful_snapshot_write_time=None,
        )


_SNAPSHOT_COLUMNS = (
    "game_id, captured_at, pick, model_probability, displayed_confidence, "
    "raw_confidence, confidence_cap, readiness_label, season_phase, "
    "away_qb_status, home_qb_status, away_moneyline, home_moneyline, "
    "market_pick_probability, model_market_edge, qualified_consensus_status, "
    "qualified_consensus_classification, qualified_consensus_quality_score, "
    "model_version"
)


class PostgresPredictionSnapshotStore:
    """Durable NFL snapshot history backed by structured PostgreSQL rows."""

    store_type: Literal["postgres"] = "postgres"
    persistence_enabled = True

    def __init__(
        self,
        database_url: str,
        *,
        retention_limit: int = SNAPSHOT_RETENTION_LIMIT,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        if not database_url:
            raise ValueError("database_url is required for postgres snapshot storage")
        if retention_limit < 1 or retention_limit > SNAPSHOT_RETENTION_LIMIT:
            raise ValueError(
                f"retention_limit must be between 1 and "
                f"{SNAPSHOT_RETENTION_LIMIT}"
            )
        self._retention_limit = retention_limit
        self._connection_factory = connection_factory or (
            lambda: psycopg.connect(database_url, row_factory=dict_row)
        )

    def _connect(self):
        try:
            return self._connection_factory()
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot store is unavailable"
            ) from exc

    @staticmethod
    def _snapshot_from_row(row: Mapping[str, Any]) -> PredictionSnapshot:
        return PredictionSnapshot.model_validate(
            {key: row[key] for key in PredictionSnapshot.model_fields}
        )

    def _fetch_history_cursor(
        self,
        cursor,
        game_id: str,
        limit: int,
    ) -> tuple[PredictionSnapshot, ...]:
        cursor.execute(
            f"SELECT {_SNAPSHOT_COLUMNS} "
            "FROM nfl_prediction_snapshots WHERE game_id = %s "
            "ORDER BY captured_at DESC, id DESC LIMIT %s",
            (game_id, limit),
        )
        return tuple(self._snapshot_from_row(row) for row in cursor.fetchall())

    def _prune_history(self, cursor, game_id: str) -> None:
        cursor.execute(
            "DELETE FROM nfl_prediction_snapshots WHERE id IN ("
            "SELECT id FROM nfl_prediction_snapshots WHERE game_id = %s "
            "ORDER BY captured_at DESC, id DESC OFFSET %s)",
            (game_id, self._retention_limit),
        )

    def add_snapshot(self, snapshot: PredictionSnapshot) -> SnapshotStoreResult:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (snapshot.game_id,),
                    )
                    existing = self._fetch_history_cursor(
                        cursor, snapshot.game_id, 2
                    )
                    if existing and _equivalent(existing[0], snapshot):
                        return SnapshotStoreResult(
                            game_id=snapshot.game_id,
                            stored=False,
                            snapshot_count=self._count_cursor(
                                cursor, snapshot.game_id
                            ),
                            current_snapshot=existing[0],
                            previous_snapshot=(
                                existing[1] if len(existing) > 1 else None
                            ),
                            latest_comparison=self._comparison(existing),
                        )

                    values = snapshot.model_dump()
                    cursor.execute(
                        "INSERT INTO nfl_prediction_snapshots ("
                        f"{_SNAPSHOT_COLUMNS}) VALUES ("
                        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                        "%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "RETURNING id",
                        tuple(
                            values[field]
                            for field in PredictionSnapshot.model_fields
                        ),
                    )
                    inserted_id = int(cursor.fetchone()["id"])
                    self._prune_history(cursor, snapshot.game_id)
                    cursor.execute(
                        "SELECT EXISTS(SELECT 1 FROM nfl_prediction_snapshots "
                        "WHERE id = %s) AS retained",
                        (inserted_id,),
                    )
                    stored = bool(cursor.fetchone()["retained"])
                    history = self._fetch_history_cursor(
                        cursor, snapshot.game_id, 2
                    )
                    return SnapshotStoreResult(
                        game_id=snapshot.game_id,
                        stored=stored,
                        snapshot_count=self._count_cursor(
                            cursor, snapshot.game_id
                        ),
                        current_snapshot=history[0],
                        previous_snapshot=(
                            history[1] if len(history) > 1 else None
                        ),
                        latest_comparison=self._comparison(history),
                    )
        except SnapshotStoreUnavailable:
            raise
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot write failed"
            ) from exc

    @staticmethod
    def _comparison(
        newest_first: tuple[PredictionSnapshot, ...],
    ) -> PredictionComparison | None:
        if len(newest_first) < 2:
            return None
        return compare_prediction_snapshots(newest_first[1], newest_first[0])

    @staticmethod
    def _count_cursor(cursor, game_id: str) -> int:
        cursor.execute(
            "SELECT COUNT(*) AS count FROM nfl_prediction_snapshots "
            "WHERE game_id = %s",
            (game_id,),
        )
        return int(cursor.fetchone()["count"])

    def get_history(
        self,
        game_id: str,
        limit: int = 10,
    ) -> tuple[PredictionSnapshot, ...]:
        if limit < 1 or limit > self._retention_limit:
            raise ValueError(
                f"limit must be between 1 and {self._retention_limit}"
            )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    return self._fetch_history_cursor(cursor, game_id, limit)
        except SnapshotStoreUnavailable:
            raise
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot history is unavailable"
            ) from exc

    def get_latest(self, game_id: str) -> PredictionSnapshot | None:
        history = self.get_history(game_id, 1)
        return history[0] if history else None

    def get_previous(self, game_id: str) -> PredictionSnapshot | None:
        history = self.get_history(game_id, 2)
        return history[1] if len(history) > 1 else None

    def get_snapshot_count(self, game_id: str) -> int:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    return self._count_cursor(cursor, game_id)
        except SnapshotStoreUnavailable:
            raise
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot count is unavailable"
            ) from exc

    def get_latest_comparison(
        self,
        game_id: str,
    ) -> PredictionComparison | None:
        return self._comparison(self.get_history(game_id, 2))

    def get_changes(self, game_id: str) -> SnapshotChangesResponse | None:
        history = self.get_history(game_id, 2)
        if not history:
            return None
        comparison = self._comparison(history)
        return SnapshotChangesResponse(
            game_id=game_id,
            snapshot_count=self.get_snapshot_count(game_id),
            current_snapshot=history[0],
            previous_snapshot=history[1] if len(history) > 1 else None,
            latest_comparison=comparison,
            changed=comparison.changed if comparison else False,
            significance=comparison.significance if comparison else "none",
            summary=(
                comparison.summary
                if comparison
                else "No prior snapshot is available for comparison."
            ),
            snapshot_store_type="postgres",
            snapshot_persistence=True,
        )

    def get_changes_many(
        self, game_ids: tuple[str, ...]
    ) -> dict[str, SnapshotChangesResponse]:
        if not game_ids:
            return {}
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"WITH ranked AS (SELECT {_SNAPSHOT_COLUMNS}, "
                        "COUNT(*) OVER (PARTITION BY game_id) AS snapshot_count, "
                        "ROW_NUMBER() OVER (PARTITION BY game_id ORDER BY "
                        "captured_at DESC, id DESC) AS row_number "
                        "FROM nfl_prediction_snapshots WHERE game_id = ANY(%s)) "
                        "SELECT * FROM ranked WHERE row_number <= 2 "
                        "ORDER BY game_id, row_number",
                        (list(game_ids),),
                    )
                    grouped: dict[str, list[Mapping[str, Any]]] = {}
                    for row in cursor.fetchall():
                        grouped.setdefault(str(row["game_id"]), []).append(row)
            results: dict[str, SnapshotChangesResponse] = {}
            for game_id, rows in grouped.items():
                history = tuple(self._snapshot_from_row(row) for row in rows)
                comparison = self._comparison(history)
                results[game_id] = SnapshotChangesResponse(
                    game_id=game_id,
                    snapshot_count=int(rows[0]["snapshot_count"]),
                    current_snapshot=history[0],
                    previous_snapshot=history[1] if len(history) > 1 else None,
                    latest_comparison=comparison,
                    changed=comparison.changed if comparison else False,
                    significance=comparison.significance if comparison else "none",
                    summary=(comparison.summary if comparison else "No prior snapshot is available for comparison."),
                    snapshot_store_type="postgres",
                    snapshot_persistence=True,
                )
            return results
        except SnapshotStoreUnavailable:
            raise
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot changes are unavailable"
            ) from exc

    def clear_game(self, game_id: str) -> int:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "DELETE FROM nfl_prediction_snapshots "
                        "WHERE game_id = %s RETURNING id",
                        (game_id,),
                    )
                    return len(cursor.fetchall())
        except SnapshotStoreUnavailable:
            raise
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot clear failed"
            ) from exc

    def clear_all(self) -> SnapshotClearAllResponse:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT COUNT(*) AS snapshots, "
                        "COUNT(DISTINCT game_id) AS games "
                        "FROM nfl_prediction_snapshots"
                    )
                    counts = cursor.fetchone()
                    cursor.execute("DELETE FROM nfl_prediction_snapshots")
                    return SnapshotClearAllResponse(
                        removed_games=int(counts["games"]),
                        removed_snapshots=int(counts["snapshots"]),
                    )
        except SnapshotStoreUnavailable:
            raise
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot clear failed"
            ) from exc

    def diagnostics(self) -> SnapshotStoreDiagnostics:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        f"SELECT {_SNAPSHOT_COLUMNS} "
                        "FROM nfl_prediction_snapshots "
                        "ORDER BY game_id, captured_at DESC, id DESC"
                    )
                    grouped: dict[str, list[PredictionSnapshot]] = {}
                    for row in cursor.fetchall():
                        snapshot = self._snapshot_from_row(row)
                        grouped.setdefault(snapshot.game_id, []).append(snapshot)

            comparisons = [
                self._comparison(tuple(history[:2]))
                for history in grouped.values()
                if len(history) > 1
            ]
            return SnapshotStoreDiagnostics(
                games_with_snapshot_history=len(grouped),
                games_with_multiple_snapshots=len(comparisons),
                games_with_meaningful_changes=sum(
                    comparison is not None and comparison.changed
                    for comparison in comparisons
                ),
                major_change_count=sum(
                    change.significance == "major"
                    for comparison in comparisons
                    if comparison is not None
                    for change in comparison.changes
                ),
                notable_change_count=sum(
                    change.significance == "notable"
                    for comparison in comparisons
                    if comparison is not None
                    for change in comparison.changes
                ),
                snapshot_store_type="postgres",
                snapshot_persistence=True,
            )
        except SnapshotStoreUnavailable:
            raise
        except Exception as exc:
            raise SnapshotStoreUnavailable(
                "PostgreSQL snapshot diagnostics are unavailable"
            ) from exc

    def health(self) -> SnapshotStoreHealth:
        try:
            connection = self._connect()
        except Exception:
            logger.error("PostgreSQL snapshot-store connection check failed")
            return SnapshotStoreHealth(
                snapshot_store_type="postgres",
                snapshot_persistence=True,
                database_reachable=False,
                snapshot_table_reachable=False,
                retained_snapshot_count=None,
                last_successful_snapshot_write_time=None,
            )

        try:
            with connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT COUNT(*) AS count, MAX(created_at) AS last_write "
                        "FROM nfl_prediction_snapshots"
                    )
                    row = cursor.fetchone()
            return SnapshotStoreHealth(
                snapshot_store_type="postgres",
                snapshot_persistence=True,
                database_reachable=True,
                snapshot_table_reachable=True,
                retained_snapshot_count=int(row["count"]),
                last_successful_snapshot_write_time=row["last_write"],
            )
        except Exception:
            logger.error("PostgreSQL snapshot table health check failed")
            return SnapshotStoreHealth(
                snapshot_store_type="postgres",
                snapshot_persistence=True,
                database_reachable=True,
                snapshot_table_reachable=False,
                retained_snapshot_count=None,
                last_successful_snapshot_write_time=None,
            )


def create_prediction_snapshot_store(
    environment: Mapping[str, str] | None = None,
    *,
    connection_factory: Callable[[], Any] | None = None,
) -> PredictionSnapshotStoreProtocol:
    config = os.environ if environment is None else environment
    configured = config.get("NFL_SNAPSHOT_STORE", "").strip().lower()
    database_url = config.get("DATABASE_URL", "").strip()
    if configured not in {"", "memory", "postgres"}:
        raise ValueError("NFL_SNAPSHOT_STORE must be 'postgres' or 'memory'")
    if configured == "postgres" and not database_url:
        raise ValueError(
            "DATABASE_URL is required when NFL_SNAPSHOT_STORE=postgres"
        )
    if configured == "postgres" or (not configured and database_url):
        logger.info("NFL snapshot store configured: postgres (persistent)")
        return PostgresPredictionSnapshotStore(
            database_url,
            connection_factory=connection_factory,
        )
    logger.info("NFL snapshot store configured: memory (process-local)")
    return PredictionSnapshotStore()


nfl_snapshot_store = create_prediction_snapshot_store()
