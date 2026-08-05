from __future__ import annotations

from threading import RLock
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.intelligence.prediction_change import (
    ChangeSignificance,
    PredictionComparison,
    PredictionSnapshot,
    compare_prediction_snapshots,
)


SNAPSHOT_RETENTION_LIMIT = 20


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
    snapshot_store_type: Literal["memory"] = "memory"
    snapshot_persistence: Literal[False] = False
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
    snapshot_store_type: Literal["memory"] = "memory"
    snapshot_persistence: Literal[False] = False
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
    snapshot_store_type: Literal["memory"] = "memory"
    snapshot_persistence: Literal[False] = False


class PredictionSnapshotStoreProtocol(Protocol):
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

    def clear_game(self, game_id: str) -> int:
        ...

    def clear_all(self) -> SnapshotClearAllResponse:
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
            if any(_equivalent(existing, snapshot) for existing in history):
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


nfl_snapshot_store = PredictionSnapshotStore()
