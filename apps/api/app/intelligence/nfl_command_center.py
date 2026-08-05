from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.intelligence.prediction_change import PredictionChange
from app.intelligence.snapshot_store import SnapshotChangesResponse


class CommandCenterGame(BaseModel):
    model_config = ConfigDict(frozen=True)
    game_id: str
    away_team: str
    home_team: str
    start_time: str
    pick: str | None
    market_favorite: str | None
    displayed_confidence: int | None = Field(default=None, ge=0, le=100)
    model_probability: float | None
    market_probability: float | None
    model_market_edge: float | None
    readiness_label: str
    season_phase: str
    market_available: bool
    quarterback_available: bool
    qualified_consensus_status: str
    qualified_consensus_classification: str
    qualified_consensus_quality_score: int | None
    qualified_consensus_quality_label: str
    opportunity_score: int = Field(ge=0, le=100)
    opportunity_label: Literal["Priority", "Strong", "Watch", "Limited"]
    reasons: tuple[str, ...] = ()
    affects_prediction: Literal[False] = False


class CommandCenterChange(BaseModel):
    model_config = ConfigDict(frozen=True)
    game_id: str
    matchup: str
    significance: Literal["major", "notable"]
    summary: str
    changes: tuple[PredictionChange, ...]
    captured_at: datetime


class CommandCenterSystemStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Literal["ready", "degraded", "empty"]
    snapshot_history: Literal["available", "unavailable"]
    message: str


class NflCommandCenterResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    generated_at: datetime
    season_phase: str
    game_count: int = Field(ge=0)
    market_coverage_count: int = Field(ge=0)
    snapshot_history_count: int = Field(ge=0)
    data_readiness_summary: dict[str, int]
    system_status: CommandCenterSystemStatus
    opportunities: tuple[CommandCenterGame, ...]
    major_changes: tuple[CommandCenterChange, ...]
    games_to_avoid: tuple[CommandCenterGame, ...]
    market_disagreements: tuple[CommandCenterGame, ...]
    featured_picks: dict[str, CommandCenterGame | None]
    all_games: tuple[CommandCenterGame, ...]
    affects_prediction: Literal[False] = False


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _label(score: int) -> Literal["Priority", "Strong", "Watch", "Limited"]:
    if score >= 80:
        return "Priority"
    if score >= 65:
        return "Strong"
    if score >= 50:
        return "Watch"
    return "Limited"


def _opportunity_score(meta: Mapping[str, Any], confidence: float | None) -> int:
    qualified = _mapping(meta.get("qualified_consensus"))
    status_points = {
        "qualified": 25, "watch": 18, "caution": 10,
        "hold": 0, "unavailable": 5,
    }.get(str(qualified.get("status", "unavailable")).lower(), 5)
    quality = max(0.0, min(100.0, _number(qualified.get("quality_score")) or 0.0)) * .20
    edge = max(0.0, _number(qualified.get("model_market_edge")) or 0.0)
    edge_points = min(edge / .10, 1.0) * 20
    confidence_points = max(0.0, min(100.0, confidence or 0.0)) * .15
    readiness = str(meta.get("data_readiness_label") or "unknown").lower()
    readiness_points = {"ready": 10, "complete": 10, "developing": 7, "limited": 3}.get(readiness, 4)
    market_points = 5 if meta.get("market_available") is True else 0
    qb_points = 5 if meta.get("qb_announced") is True else (2 if meta.get("qb_confirmed") is True else 0)
    preseason_penalty = 10 if meta.get("season_phase") == "preseason" else 0
    return round(max(0, min(100, status_points + quality + edge_points + confidence_points + readiness_points + market_points + qb_points - preseason_penalty)))


def _game_item(item: Mapping[str, Any]) -> CommandCenterGame:
    game = _mapping(item.get("game")); prediction = _mapping(item.get("prediction")); meta = _mapping(prediction.get("metadata")); qualified = _mapping(meta.get("qualified_consensus"))
    score = _opportunity_score(meta, _number(prediction.get("confidence")))
    return CommandCenterGame(
        game_id=str(game.get("game_id") or game.get("id") or "unknown"),
        away_team=str(game.get("away_team") or "Away"), home_team=str(game.get("home_team") or "Home"),
        start_time=str(game.get("start_time") or "TBD"), pick=prediction.get("pick") if isinstance(prediction.get("pick"), str) else None,
        market_favorite=qualified.get("market_favorite") if isinstance(qualified.get("market_favorite"), str) else None,
        displayed_confidence=int(prediction["confidence"]) if isinstance(prediction.get("confidence"), (int, float)) else None,
        model_probability=_number(qualified.get("model_probability")), market_probability=_number(qualified.get("no_vig_market_probability")),
        model_market_edge=_number(qualified.get("model_market_edge")), readiness_label=str(meta.get("data_readiness_label") or "unknown"),
        season_phase=str(meta.get("season_phase") or "unknown"), market_available=meta.get("market_available") is True,
        quarterback_available=meta.get("qb_announced") is True,
        qualified_consensus_status=str(qualified.get("status") or "unavailable"), qualified_consensus_classification=str(qualified.get("classification") or "Unavailable"),
        qualified_consensus_quality_score=int(qualified["quality_score"]) if isinstance(qualified.get("quality_score"), (int, float)) else None,
        qualified_consensus_quality_label=str(qualified.get("quality_label") or "Unavailable"),
        opportunity_score=score, opportunity_label=_label(score), reasons=tuple(str(reason) for reason in qualified.get("reasons", [])[:3]),
    )


def build_nfl_command_center(
    home_payload: Mapping[str, Any],
    snapshot_changes: Mapping[str, SnapshotChangesResponse] | None = None,
    *, snapshot_available: bool = True,
    generated_at: datetime | None = None,
) -> NflCommandCenterResponse:
    raw_games = home_payload.get("games")
    items = raw_games if isinstance(raw_games, list) else []
    games = tuple(_game_item(item) for item in items if isinstance(item, Mapping))
    changes = snapshot_changes or {}
    change_items: list[CommandCenterChange] = []
    for game in games:
        result = changes.get(game.game_id)
        comparison = result.latest_comparison if result else None
        if comparison and comparison.significance in {"major", "notable"}:
            change_items.append(CommandCenterChange(
                game_id=game.game_id, matchup=f"{game.away_team} at {game.home_team}", significance=comparison.significance,
                summary=comparison.summary, changes=tuple(comparison.changes[:3]), captured_at=result.current_snapshot.captured_at,
            ))
    change_items.sort(key=lambda value: (value.significance == "major", value.captured_at), reverse=True)
    opportunities = tuple(sorted((game for game in games if game.qualified_consensus_status not in {"hold", "unavailable"}), key=lambda game: game.opportunity_score, reverse=True))
    avoid = tuple(game for game in games if game.qualified_consensus_status in {"hold", "caution"} or not game.market_available or game.readiness_label.lower() in {"limited", "unknown"} or not game.quarterback_available or game.season_phase == "preseason" or game.qualified_consensus_quality_label.lower() in {"weak", "low"} or game.model_market_edge is None or game.model_market_edge <= 0)
    disagreements = tuple(game for game in games if (game.pick and game.market_favorite and game.pick != game.market_favorite) or "disagreement" in game.qualified_consensus_classification.lower() or (game.model_market_edge is not None and abs(game.model_market_edge) >= .03))
    usable = [game for game in games if game.qualified_consensus_status != "hold"]
    featured: dict[str, CommandCenterGame | None] = {
        "strongest_qualified": max((game for game in games if game.qualified_consensus_status == "qualified"), key=lambda game: game.opportunity_score, default=None),
        "highest_confidence": max(usable, key=lambda game: game.displayed_confidence or 0, default=None),
        "largest_positive_edge": max((game for game in usable if (game.model_market_edge or 0) > 0), key=lambda game: game.model_market_edge or 0, default=None),
        "upset_candidate": max((game for game in usable if game.pick and game.market_favorite and game.pick != game.market_favorite and game.market_probability is not None and game.readiness_label.lower() != "limited"), key=lambda game: game.opportunity_score, default=None),
    }
    readiness = Counter(game.readiness_label for game in games)
    phases = Counter(str(_mapping(_mapping(item.get("prediction")).get("metadata")).get("season_phase") or "unknown") for item in items if isinstance(item, Mapping))
    status = "empty" if not games else ("ready" if snapshot_available else "degraded")
    return NflCommandCenterResponse(
        generated_at=generated_at or datetime.now(timezone.utc), season_phase=phases.most_common(1)[0][0] if phases else "unknown",
        game_count=len(games), market_coverage_count=sum(game.market_probability is not None for game in games), snapshot_history_count=len(changes),
        data_readiness_summary=dict(sorted(readiness.items())), system_status=CommandCenterSystemStatus(status=status, snapshot_history="available" if snapshot_available else "unavailable", message="Command Center intelligence is current." if snapshot_available else "Game intelligence is available; snapshot change history is temporarily unavailable."),
        opportunities=opportunities, major_changes=tuple(change_items), games_to_avoid=avoid, market_disagreements=disagreements,
        featured_picks=featured, all_games=games,
    )
