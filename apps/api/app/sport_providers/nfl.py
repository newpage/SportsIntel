from __future__ import annotations

from datetime import date, timedelta
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


YAHOO_SCOREBOARD_URL = os.getenv(
    "NFL_YAHOO_SCOREBOARD_URL",
    "https://api-secure.sports.yahoo.com/v1/editorial/s/scoreboard",
)
NFL_SCOREBOARD_URL = os.getenv(
    "NFL_SCOREBOARD_URL",
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
)
CACHE_SECONDS = 300
SCHEDULE_LOOKAHEAD_DAYS = 14
_CACHE: tuple[float, list[SportGame]] | None = None
_LAST_ERROR: str | None = None
_LAST_SOURCE: str | None = None
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


def _reference_id(value: Any, prefix: str) -> str | None:
    if isinstance(value, str):
        return value if value.startswith(prefix) else None
    if isinstance(value, list):
        for item in value:
            found = _reference_id(item, prefix)
            if found:
                return found
    if isinstance(value, dict):
        for item in value.values():
            found = _reference_id(item, prefix)
            if found:
                return found
    return None



def _indexed_collection(value: Any, id_prefix: str) -> dict[str, dict[str, Any]]:
    if isinstance(value, dict):
        return {
            str(key): item
            for key, item in value.items()
            if isinstance(item, dict)
        }

    if not isinstance(value, list):
        return {}

    indexed: dict[str, dict[str, Any]] = {}
    for position, item in enumerate(value):
        if not isinstance(item, dict):
            continue

        item_id = (
            item.get("gameid")
            or item.get("game_id")
            or item.get("team_id")
            or item.get("id")
            or _reference_id(item, id_prefix)
            or f"{id_prefix}{position}"
        )
        indexed[str(item_id)] = item

    return indexed


def _collection_item(collection: Any, item_id: str, id_prefix: str) -> dict[str, Any]:
    return _indexed_collection(collection, id_prefix).get(item_id, {})

def _yahoo_team_name(teams: Any, value: Any) -> str | None:
    team_id = _reference_id(value, "nfl.t.")
    team = _collection_item(teams, team_id, "nfl.t.") if team_id else {}

    if isinstance(value, dict):
        team = {**value, **team}

    for key in (
        "display_name",
        "full_name",
        "name",
        "short_name",
        "nickname",
        "team_name",
    ):
        candidate = team.get(key)
        if candidate:
            return str(candidate)

    city = team.get("city") or team.get("location") or team.get("team_location")
    nickname = team.get("nickname") or team.get("team_nickname")
    if city and nickname:
        return f"{city} {nickname}"

    return None



def _record_value(record: Any) -> str | None:
    if isinstance(record, str):
        value = record.strip()
        return value or None

    if not isinstance(record, dict):
        return None

    for key in (
        "record",
        "display_record",
        "overall_record",
        "summary",
        "value",
    ):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    wins = losses = ties = None
    stats = record.get("stats")
    if isinstance(stats, list):
        for stat in stats:
            if not isinstance(stat, dict):
                continue

            label = str(
                stat.get("abbr")
                or stat.get("name")
                or stat.get("stat_type")
                or ""
            ).strip().lower()
            value = stat.get("value")

            if label in {"w", "wins", "win"}:
                wins = value
            elif label in {"l", "losses", "loss"}:
                losses = value
            elif label in {"t", "ties", "tie"}:
                ties = value

    if wins is not None and losses is not None:
        result = f"{wins}-{losses}"
        if ties not in (None, "", 0, "0"):
            result += f"-{ties}"
        return result

    return None


def _yahoo_team_record(
    scoreboard: dict[str, Any],
    team_value: Any,
) -> str | None:
    team_id = _reference_id(team_value, "nfl.t.")
    if not team_id:
        return None

    record = _collection_item(
        scoreboard.get("teamrecord", {}),
        team_id,
        "nfl.t.",
    )
    return _record_value(record)


def _yahoo_game(
    game_id: str,
    payload: dict[str, Any],
    scoreboard: dict[str, Any],
) -> SportGame | None:
    teams = scoreboard.get("teams", {})
    byline = _collection_item(
        scoreboard.get("gamebyline", {}),
        game_id,
        "nfl.g.",
    )

    away_value = (
        payload.get("away_team")
        or payload.get("away_team_id")
        or byline.get("away_team")
        or byline.get("away_team_id")
    )
    home_value = (
        payload.get("home_team")
        or payload.get("home_team_id")
        or byline.get("home_team")
        or byline.get("home_team_id")
    )

    away_team = _yahoo_team_name(teams, away_value)
    home_team = _yahoo_team_name(teams, home_value)
    if not away_team or not home_team:
        return None

    away_record = _yahoo_team_record(scoreboard, away_value)
    home_record = _yahoo_team_record(scoreboard, home_value)

    status_text = (
        payload.get("status")
        or payload.get("status_type")
        or payload.get("game_status")
        or ""
    )
    status = _status(str(status_text))
    if payload.get("is_final") or payload.get("completed"):
        status = GameStatus.FINAL

    return SportGame(
        sport="nfl",
        game_id=f"nfl-yahoo-{game_id}",
        away_team=away_team,
        home_team=home_team,
        start_time=str(
            payload.get("start_time")
            or payload.get("start_time_iso")
            or payload.get("date")
            or "TBD"
        ),
        status=status,
        away_score=_score(
            payload.get("away_score")
            or byline.get("away_score")
        ),
        home_score=_score(
            payload.get("home_score")
            or byline.get("home_score")
        ),
        venue=(
            payload.get("venue")
            or payload.get("venue_name")
            or byline.get("venue")
        ),
        metadata={
            "data_mode": "live_schedule",
            "schedule_confirmed": True,
            "source": "Yahoo Sports",
            "source_game_id": game_id,
            "status_detail": status_text,
            "away_record": away_record,
            "home_record": home_record,
            "record_source": (
                "Yahoo Sports"
                if away_record or home_record
                else None
            ),
            "records_affect_prediction": False,
        },
    )


def _fetch_yahoo_schedule(target_date: date | None = None) -> list[SportGame]:
    start_date = target_date or date.today()
    days = 1 if target_date is not None else SCHEDULE_LOOKAHEAD_DAYS + 1
    games_by_id: dict[str, SportGame] = {}

    with httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://sports.yahoo.com/",
        },
        timeout=15,
        follow_redirects=True,
    ) as client:
        for offset in range(days):
            query_date = start_date + timedelta(days=offset)
            response = client.get(
                YAHOO_SCOREBOARD_URL,
                params={
                    "leagues": "nfl",
                    "date": query_date.isoformat(),
                    "lang": "en-US",
                    "region": "US",
                },
            )
            response.raise_for_status()
            scoreboard = (
                response.json()
                .get("service", {})
                .get("scoreboard", {})
            )
            raw_games = _indexed_collection(
                scoreboard.get("games", {}),
                "nfl.g.",
            )

            for game_id, payload in raw_games.items():
                game = _yahoo_game(str(game_id), payload, scoreboard)
                if game:
                    games_by_id[game.game_id] = game

    games = list(games_by_id.values())
    games.sort(key=lambda item: str(item.start_time))
    return games


def _fetch_espn_schedule(target_date: date | None = None) -> list[SportGame]:
    params: dict[str, str | int] = {"limit": 100}
    if target_date is not None:
        params["dates"] = target_date.strftime("%Y%m%d")

    response = httpx.get(
        NFL_SCOREBOARD_URL,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
        },
        timeout=15,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()

    games = [
        game
        for event in payload.get("events", [])
        if (game := _game_from_event(event)) is not None
    ]
    games.sort(key=lambda item: str(item.start_time))
    return games


def _fetch_schedule(target_date: date | None = None) -> list[SportGame]:
    global _CACHE, _LAST_ERROR, _LAST_SOURCE

    now = time.monotonic()
    if target_date is None and _CACHE and _CACHE[0] > now:
        return _CACHE[1]

    errors: list[str] = []

    for source_name, loader in (
        ("Yahoo Sports", _fetch_yahoo_schedule),
        ("ESPN scoreboard", _fetch_espn_schedule),
    ):
        try:
            games = loader(target_date)
            if games:
                _LAST_ERROR = None
                _LAST_SOURCE = source_name
                if target_date is None:
                    _CACHE = (now + CACHE_SECONDS, games)
                return games
            errors.append(f"{source_name}: no games returned")
        except Exception as exc:
            errors.append(f"{source_name}: {type(exc).__name__}: {exc}")

    _LAST_SOURCE = None
    _LAST_ERROR = " | ".join(errors)
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
                "schedule_source": _LAST_SOURCE,
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
