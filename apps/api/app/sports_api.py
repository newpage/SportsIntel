from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException

from app.sports import SportProvider, sports_registry


def _ensure_provider(sport: str) -> SportProvider:
    sport_key = sport.strip().lower()

    if sports_registry.contains(sport_key):
        return sports_registry.get(sport_key)

    if sport_key == "mlb":
        from app.sport_providers.mlb import register_mlb_provider
        return register_mlb_provider(sports_registry)

    raise HTTPException(status_code=404, detail=f"Unsupported sport: {sport_key}")


def sports_home(sport: str, target_date: date | None = None) -> dict[str, Any]:
    provider = _ensure_provider(sport)
    games = provider.schedule(target_date)

    items = []
    for game in games:
        prediction = provider.predict(game)
        items.append({
            "game": game.to_dict(),
            "prediction": prediction.to_dict(),
        })

    return {
        "sport": provider.sport_key,
        "display_name": provider.display_name,
        "date": target_date.isoformat() if target_date else date.today().isoformat(),
        "capabilities": provider.capabilities.to_dict(),
        "game_count": len(items),
        "games": items,
        "provider": provider.health(),
    }
