from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any


NFL_REVIEW_VERSION = "nfl-review-v1"


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    prediction = item.get("prediction")
    if not isinstance(prediction, dict):
        return {}
    metadata = prediction.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _confidence(item: dict[str, Any]) -> float | None:
    prediction = item.get("prediction")
    if not isinstance(prediction, dict):
        return None
    value = prediction.get("confidence")
    return float(value) if isinstance(value, (int, float)) else None


def build_nfl_review(home_payload: dict[str, Any]) -> dict[str, Any]:
    games = home_payload.get("games")
    items = games if isinstance(games, list) else []

    metadata = [_metadata(item) for item in items]
    confidences = [
        value
        for item in items
        if (value := _confidence(item)) is not None
    ]

    readiness_labels = Counter(
        str(meta.get("data_readiness_label") or "unknown")
        for meta in metadata
    )
    market_signals = Counter(
        str(meta.get("market_signal_label") or "Market unavailable")
        for meta in metadata
    )

    team_intelligence_covered = sum(
        1
        for meta in metadata
        if isinstance(meta.get("team_intelligence"), dict)
    )
    team_health_covered = sum(
        1
        for meta in metadata
        if isinstance(meta.get("team_health"), dict)
    )
    waterfall_covered = sum(
        1
        for meta in metadata
        if isinstance(meta.get("prediction_waterfall"), dict)
    )

    game_count = len(items)
    return {
        "sport": "nfl",
        "review_version": NFL_REVIEW_VERSION,
        "date": home_payload.get("date"),
        "game_count": game_count,
        "average_confidence": (
            round(mean(confidences), 2)
            if confidences
            else None
        ),
        "confidence_range": {
            "minimum": min(confidences) if confidences else None,
            "maximum": max(confidences) if confidences else None,
        },
        "coverage": {
            "team_health": team_health_covered,
            "team_intelligence": team_intelligence_covered,
            "prediction_waterfall": waterfall_covered,
            "complete_games": sum(
                1
                for meta in metadata
                if isinstance(meta.get("team_health"), dict)
                and isinstance(meta.get("team_intelligence"), dict)
                and isinstance(meta.get("prediction_waterfall"), dict)
            ),
        },
        "context": {
            "preseason_games": sum(
                1
                for meta in metadata
                if meta.get("season_phase") == "preseason"
            ),
            "market_available_games": sum(
                1
                for meta in metadata
                if meta.get("market_available") is True
            ),
            "guardrail_applied_games": sum(
                1
                for meta in metadata
                if meta.get("confidence_guardrail_applied") is True
            ),
            "quarterbacks_announced_games": sum(
                1
                for meta in metadata
                if meta.get("qb_announced") is True
            ),
        },
        "readiness_distribution": dict(sorted(readiness_labels.items())),
        "market_signal_distribution": dict(sorted(market_signals.items())),
        "prediction_impact": {
            "team_health": False,
            "team_intelligence": False,
            "market_signal": False,
            "review_summary": False,
        },
        "status": (
            "ready_for_review"
            if game_count > 0 and waterfall_covered == game_count
            else "partial"
        ),
    }
