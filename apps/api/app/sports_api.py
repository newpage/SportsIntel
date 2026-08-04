from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException

from app.sports import SportProvider, sports_registry



SPORT_CATALOG: dict[str, dict[str, Any]] = {
    "mlb": {
        "sport": "mlb",
        "display_name": "Major League Baseball",
        "status": "available",
        "endpoint": "/api/sports/mlb",
        "legacy_endpoint": "/api/mlb",
        "capabilities": {
            "moneyline": True,
            "spread": True,
            "totals": True,
            "player_props": False,
            "live": False,
            "standings": False,
            "injuries": False,
            "weather": False,
        },
    },
    "nfl": {
        "sport": "nfl",
        "display_name": "National Football League",
        "status": "available",
        "endpoint": "/api/sports/nfl",
        "legacy_endpoint": None,
        "capabilities": {
            "moneyline": True,
            "spread": True,
            "totals": True,
            "player_props": False,
            "live": False,
            "standings": False,
            "injuries": False,
            "weather": False,
        },
    },
}


def sports_catalog() -> dict[str, Any]:
    sports = []
    for sport_key, definition in SPORT_CATALOG.items():
        item = dict(definition)
        item["registered"] = sports_registry.contains(sport_key)
        sports.append(item)

    return {
        "platform": "SportsIntel",
        "sports": sports,
        "registered_sports": list(sports_registry.keys()),
        "available_count": sum(
            1 for item in sports if item["status"] == "available"
        ),
        "planned_count": sum(
            1 for item in sports if item["status"] == "planned"
        ),
    }


def sport_capabilities(sport: str) -> dict[str, Any]:
    sport_key = sport.strip().lower()
    definition = SPORT_CATALOG.get(sport_key)

    if definition is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown sport: {sport_key}",
        )

    payload = dict(definition)
    payload["registered"] = sports_registry.contains(sport_key)

    if payload["registered"]:
        provider = sports_registry.get(sport_key)
        payload["capabilities"] = provider.capabilities.to_dict()
        payload["provider"] = provider.health()
    else:
        payload["provider"] = None

    return payload


def _ensure_provider(sport: str) -> SportProvider:
    sport_key = sport.strip().lower()

    if sports_registry.contains(sport_key):
        return sports_registry.get(sport_key)

    if sport_key == "mlb":
        from app.sport_providers.mlb import register_mlb_provider
        return register_mlb_provider(sports_registry)

    if sport_key == "nfl":
        from app.sport_providers.nfl import register_nfl_provider
        return register_nfl_provider(sports_registry)

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
