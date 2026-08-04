from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any


NFL_REVIEW_VERSION = "nfl-review-v3"


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



def _game(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("game")
    return value if isinstance(value, dict) else {}


def _attention_item(item: dict[str, Any]) -> dict[str, Any]:
    game = _game(item)
    meta = _metadata(item)
    prediction = item.get("prediction")
    prediction = prediction if isinstance(prediction, dict) else {}

    reasons: list[str] = []
    priority = 0

    if meta.get("qb_announced") is not True:
        reasons.append("Starting quarterbacks are not fully announced")
        priority += 3

    readiness = str(meta.get("data_readiness_label") or "unknown").lower()
    if readiness in {"limited", "unknown"}:
        reasons.append(f"Data readiness is {readiness}")
        priority += 3
    elif readiness == "developing":
        reasons.append("Data readiness is still developing")
        priority += 1

    signal = str(meta.get("market_signal_label") or "Market unavailable")
    if signal == "Large disagreement":
        reasons.append("Model and market show a large disagreement")
        priority += 3
    elif signal == "Notable difference":
        reasons.append("Model and market show a notable difference")
        priority += 2
    elif meta.get("market_available") is not True:
        reasons.append("Complete two-sided moneyline is unavailable")
        priority += 1

    if meta.get("confidence_guardrail_applied") is True:
        reasons.append("Confidence guardrail reduced the displayed confidence")
        priority += 2

    if meta.get("season_phase") == "preseason":
        reasons.append("Preseason participation uncertainty applies")
        priority += 1

    if priority >= 8:
        level = "high"
        disposition = "hold"
        disposition_label = "Hold for review"
        recommended_action = (
            "Do not promote this lean until the highest-priority data gaps "
            "or disagreements are reviewed."
        )
    elif priority >= 4:
        level = "medium"
        disposition = "watch"
        disposition_label = "Watch closely"
        recommended_action = (
            "Keep the lean visible, but review new quarterback, market, and "
            "availability information before game time."
        )
    else:
        level = "low"
        disposition = "ready"
        disposition_label = "Ready for review"
        recommended_action = (
            "No major review blocker is currently detected. Continue normal "
            "pregame monitoring."
        )

    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")

    return {
        "game_id": game.get("game_id") or game.get("id"),
        "matchup": f"{away} at {home}",
        "away_team": away,
        "home_team": home,
        "pick": prediction.get("pick"),
        "confidence": prediction.get("confidence"),
        "priority_score": priority,
        "priority_level": level,
        "reasons": reasons,
        "review_required": priority >= 4,
        "disposition": disposition,
        "disposition_label": disposition_label,
        "recommended_action": recommended_action,
    }


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

    attention_queue = sorted(
        (_attention_item(item) for item in items),
        key=lambda item: (
            item["priority_score"],
            item.get("confidence") or 0,
        ),
        reverse=True,
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
        "attention": {
            "review_required_games": sum(
                1 for item in attention_queue if item["review_required"]
            ),
            "high_priority_games": sum(
                1 for item in attention_queue if item["priority_level"] == "high"
            ),
            "disposition_counts": dict(
                sorted(
                    Counter(
                        item["disposition"] for item in attention_queue
                    ).items()
                )
            ),
            "queue": attention_queue,
        },
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
