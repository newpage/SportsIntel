from __future__ import annotations

from datetime import date
import os
import time
from typing import Any

import httpx

from app.sport_providers.nfl_ratings import HOME_FIELD_RATING, RATING_VERSION, team_rating
from app.sports import (
    GameStatus,
    MarketPrediction,
    MarketType,
    SportCapabilities,
    SportGame,
    SportPrediction,
    SportProvider,
    SportRegistry,
    sports_registry,
)


NFL_SCOREBOARD_URL = os.getenv(
    "NFL_SCOREBOARD_URL",
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
)
CACHE_SECONDS = 300
_CACHE: tuple[float, list[SportGame]] | None = None
_LAST_ERROR: str | None = None


def _status(value: str | None) -> GameStatus:
    normalized = (value or "").strip().lower()

    if normalized in {"in", "live"}:
        return GameStatus.LIVE
    if normalized in {"post", "final"}:
        return GameStatus.FINAL
    if "postpon" in normalized:
        return GameStatus.POSTPONED
    if "cancel" in normalized:
        return GameStatus.CANCELLED
    if normalized in {"pre", "scheduled"}:
        return GameStatus.SCHEDULED
    return GameStatus.UNKNOWN


def _competitor(
    competitors: list[dict[str, Any]],
    side: str,
) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in competitors
            if item.get("homeAway") == side
        ),
        None,
    )


def _score(value: Any) -> int | float | None:
    if value in (None, ""):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return int(number) if number.is_integer() else number


def _team_name(competitor: dict[str, Any] | None) -> str:
    if not competitor:
        return "Unknown Team"

    team = competitor.get("team", {})
    return (
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("name")
        or "Unknown Team"
    )


def _game_from_event(event: dict[str, Any]) -> SportGame | None:
    competition = next(
        iter(event.get("competitions", [])),
        None,
    )
    if not isinstance(competition, dict):
        return None

    competitors = competition.get("competitors", [])
    away = _competitor(competitors, "away")
    home = _competitor(competitors, "home")

    if not away or not home:
        return None

    status_type = (
        event.get("status", {})
        .get("type", {})
    )
    venue = competition.get("venue", {})

    return SportGame(
        sport="nfl",
        game_id=f'nfl-{event.get("id")}',
        away_team=_team_name(away),
        home_team=_team_name(home),
        start_time=event.get("date") or "TBD",
        status=_status(status_type.get("state")),
        away_score=_score(away.get("score")),
        home_score=_score(home.get("score")),
        venue=venue.get("fullName"),
        metadata={
            "data_mode": "live_schedule",
            "schedule_confirmed": True,
            "source": "ESPN scoreboard",
            "source_event_id": event.get("id"),
            "status_detail": status_type.get("detail"),
            "status_description": status_type.get("description"),
            "season": event.get("season", {}),
            "week": event.get("week", {}),
            "broadcasts": competition.get("broadcasts", []),
        },
    )


def _fetch_schedule(
    target_date: date | None = None,
) -> list[SportGame]:
    global _CACHE, _LAST_ERROR

    now = time.monotonic()
    if target_date is None and _CACHE and _CACHE[0] > now:
        return _CACHE[1]

    params: dict[str, str | int] = {"limit": 100}
    if target_date is not None:
        params["dates"] = target_date.strftime("%Y%m%d")

    try:
        response = httpx.get(
            NFL_SCOREBOARD_URL,
            params=params,
            headers={"User-Agent": "SportsIntel/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        games = [
            game
            for event in payload.get("events", [])
            if (game := _game_from_event(event)) is not None
        ]
        games.sort(key=lambda item: str(item.start_time))

        _LAST_ERROR = None
        if target_date is None:
            _CACHE = (now + CACHE_SECONDS, games)

        return games
    except Exception as exc:
        _LAST_ERROR = f"{type(exc).__name__}: {exc}"
        return []



def _moneyline_prediction(game: SportGame) -> SportPrediction:
    away_rating = team_rating(game.away_team)
    home_rating = team_rating(game.home_team)
    adjusted_home = home_rating + HOME_FIELD_RATING
    gap = adjusted_home - away_rating

    pick = game.home_team if gap >= 0 else game.away_team
    confidence = round(min(68, max(53, 54 + abs(gap) * 1.35)))
    probability = round(min(0.68, max(0.52, 0.52 + abs(gap) / 45)), 3)

    factors = [
        {
            "factor_id": "team_rating",
            "name": "Provisional Team Rating",
            "category": "team_strength",
            "score": round(gap, 3),
            "weight": 1.0,
            "reliability": 0.5,
            "explanation": (
                f"{game.away_team} rating: {away_rating:.1f}; "
                f"{game.home_team} rating: {home_rating:.1f}."
            ),
            "direction": "home" if gap > 0 else "away" if gap < 0 else "neutral",
            "usage": "active",
            "version": RATING_VERSION,
            "contributes_to": ["moneyline"],
            "used_in_confidence": True,
        },
        {
            "factor_id": "home_field",
            "name": "Home Field",
            "category": "venue",
            "score": HOME_FIELD_RATING,
            "weight": 1.0,
            "reliability": 0.7,
            "explanation": (
                f"{game.home_team} receives a provisional "
                f"{HOME_FIELD_RATING:.1f}-point home-field adjustment."
            ),
            "direction": "home",
            "usage": "active",
            "version": RATING_VERSION,
            "contributes_to": ["moneyline"],
            "used_in_confidence": True,
        },
    ]

    markets = [
        MarketPrediction(
            market_type=MarketType.MONEYLINE,
            selection=pick,
            confidence=confidence,
            projected_value=probability,
            recommendation="Early model lean",
            factor_ids=("team_rating", "home_field"),
        ),
        MarketPrediction(
            market_type=MarketType.SPREAD,
            selection=None,
            confidence=None,
            recommendation="Not available yet",
        ),
        MarketPrediction(
            market_type=MarketType.TOTAL,
            selection=None,
            confidence=None,
            recommendation="Not available yet",
        ),
    ]

    return SportPrediction(
        sport="nfl",
        game_id=game.game_id,
        pick=pick,
        confidence=confidence,
        recommendation="Early moneyline lean",
        factors=factors,
        timeline=[],
        markets=markets,
        explanation={
            "title": "Why SportsIntel Likes This Pick",
            "summary": (
                f"SportsIntel gives {pick} an early edge based on "
                "provisional team strength and home field only."
            ),
            "reasons": [
                f"Adjusted rating gap is {abs(gap):.1f} points in favor of {pick}.",
                (
                    "Confidence is intentionally capped because injuries, "
                    "quarterback status, recent form, and market data are not included yet."
                ),
            ],
        },
        model_version=RATING_VERSION,
        metadata={
            "data_mode": "live_schedule",
            "schedule_confirmed": True,
            "prediction_available": True,
            "prediction_scope": "moneyline_only",
            "rating_version": RATING_VERSION,
            "away_rating": away_rating,
            "home_rating": home_rating,
            "home_field_rating": HOME_FIELD_RATING,
            "rating_gap": round(gap, 3),
        },
    )


class NFLProvider(SportProvider):
    """Live NFL schedule provider with prediction-safe placeholders."""

    sport_key = "nfl"
    display_name = "National Football League"
    capabilities = SportCapabilities(
        moneyline=True,
        spread=False,
        totals=False,
        player_props=False,
        live=False,
        standings=False,
        injuries=False,
        weather=False,
    )

    def schedule(self, target_date: date | None = None) -> list[SportGame]:
        return _fetch_schedule(target_date)

    def predict(self, game: SportGame) -> SportPrediction:
        return _moneyline_prediction(game)

    def health(self) -> dict[str, Any]:
        payload = super().health()
        payload.update(
            {
                "adapter": "nfl-live-schedule-v1",
                "status": "available",
                "import_mode": "lazy",
                "data_available": True,
                "data_mode": "live_schedule",
                "schedule_confirmed": True,
                "prediction_available": True,
                "prediction_scope": "moneyline_only",
                "rating_version": RATING_VERSION,
                "cache_seconds": CACHE_SECONDS,
                "last_error": _LAST_ERROR,
            }
        )
        return payload


def register_nfl_provider(
    registry: SportRegistry | None = None,
    *,
    replace: bool = False,
) -> NFLProvider:
    target = registry or sports_registry
    provider = NFLProvider()

    if target.contains(provider.sport_key):
        if not replace:
            return target.get(provider.sport_key)  # type: ignore[return-value]

    target.register(provider, replace=replace)
    return provider
