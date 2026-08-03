from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_HISTORY_PATH = Path(os.getenv("PREDICTION_HISTORY_FILE", "/app/data/prediction_history.json"))
_LOCK = threading.Lock()
_MAX_EVENTS_PER_GAME = 24


def _load() -> dict[str, list[dict]]:
    if not _HISTORY_PATH.exists():
        return {}
    try:
        payload = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(payload: dict[str, list[dict]]) -> None:
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = _HISTORY_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(_HISTORY_PATH)


def _event_reason(game: dict, previous: dict | None) -> str | None:
    if previous is None:
        return "Initial SportsIntel prediction."

    previous_confidence = int(previous.get("confidence", game["confidence"]))
    confidence_change = int(game["confidence"]) - previous_confidence
    previous_pitcher_status = previous.get("pitcher_status")
    current_pitcher_status = game.get("pitcher_status", {}).get("code")

    reasons: list[str] = []
    if confidence_change:
        direction = "increased" if confidence_change > 0 else "decreased"
        suffix = "" if abs(confidence_change) == 1 else "s"
        reasons.append(f"Confidence {direction} by {abs(confidence_change)} point{suffix}.")

    if previous_pitcher_status != current_pitcher_status:
        label = game.get("pitcher_status", {}).get("label", "Updated")
        reasons.append(f"Probable pitcher status changed to {label}.")

    return " ".join(reasons) or None


def attach_prediction_history(games: list[dict]) -> None:
    with _LOCK:
        history = _load()
        changed = False

        for game in games:
            game_id = game["game_id"]
            events = history.setdefault(game_id, [])
            previous = events[-1] if events else None
            reason = _event_reason(game, previous)

            if reason:
                events.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": int(game["confidence"]),
                    "pitcher_status": game.get("pitcher_status", {}).get("code"),
                    "pitcher_status_label": game.get("pitcher_status", {}).get("label"),
                    "reason": reason,
                })
                history[game_id] = events[-_MAX_EVENTS_PER_GAME:]
                changed = True

            current_events = history.get(game_id, [])
            if len(current_events) >= 2:
                game["confidence_change"] = int(current_events[-1]["confidence"]) - int(current_events[-2]["confidence"])
            else:
                game["confidence_change"] = 0

            game["prediction_timeline"] = list(reversed(current_events[-8:]))

        if changed:
            _save(history)
