from __future__ import annotations

from datetime import date, timedelta
from email.utils import parsedate_to_datetime
import json
import os
import time
from typing import Any

import httpx

from app.sport_providers.nfl_ratings import (
    HOME_FIELD_RATING,
    RATING_VERSION,
    normalize_team_name,
    team_rating,
)
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



def _qb_overrides() -> dict[str, dict[str, str]]:
    raw = os.getenv("NFL_QB_OVERRIDES_JSON", "").strip()
    if not raw:
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}

    result: dict[str, dict[str, str]] = {}
    for team, value in payload.items():
        if isinstance(value, str):
            result[str(team)] = {
                "name": value,
                "status": "expected",
                "source": "manual override",
            }
        elif isinstance(value, dict):
            name = str(value.get("name") or "").strip()
            if name:
                result[str(team)] = {
                    "name": name,
                    "status": str(value.get("status") or "expected").strip(),
                    "source": str(value.get("source") or "manual override").strip(),
                }

    return result


def _qb_context(
    scoreboard: dict[str, Any],
    game_id: str,
    team_name: str,
    side: str,
) -> dict[str, Any]:
    override = _qb_overrides().get(team_name)
    if override:
        return {
            "name": override.get("name"),
            "status": override.get("status") or "expected",
            "source": override.get("source") or "manual override",
            "confirmed": False,
        }

    byline = _collection_item(
        scoreboard.get("gamebyline", {}),
        game_id,
        "nfl.g.",
    )

    value = (
        byline.get(f"{side}_qb")
        or byline.get(f"{side}_quarterback")
        or byline.get(f"{side}_starter")
    )

    if isinstance(value, dict):
        name = (
            value.get("display_name")
            or value.get("full_name")
            or value.get("name")
        )
        status = str(value.get("status") or "expected")
        if name:
            return {
                "name": str(name),
                "status": status,
                "source": "Yahoo Sports",
                "confirmed": status.lower()
                in {"confirmed", "active", "starting"},
            }

    return {
        "name": None,
        "status": "not announced",
        "source": None,
        "confirmed": False,
    }



def _american_odds(value: Any) -> int | None:
    if value in (None, ""):
        return None

    if isinstance(value, str):
        cleaned = value.strip().replace("−", "-")
        if cleaned.upper() in {"EVEN", "EV", "PK"}:
            return 100
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        try:
            number = int(float(cleaned))
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        number = int(value)
    else:
        return None

    if number == 0:
        return None
    return number


def _implied_probability(american_odds: int | None) -> float | None:
    if american_odds is None:
        return None

    if american_odds > 0:
        return round(100 / (american_odds + 100), 4)

    return round(
        abs(american_odds) / (abs(american_odds) + 100),
        4,
    )


def _first_odds_value(
    payload: Any,
    keys: tuple[str, ...],
) -> int | None:
    normalized_keys = {key.lower() for key in keys}

    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in normalized_keys:
                parsed = _american_odds(value)
                if parsed is not None:
                    return parsed

        for value in payload.values():
            parsed = _first_odds_value(value, keys)
            if parsed is not None:
                return parsed

    if isinstance(payload, list):
        for value in payload:
            parsed = _first_odds_value(value, keys)
            if parsed is not None:
                return parsed

    return None



def _market_signal(
    edge: float | None,
    model_pick: str,
    market_pick_probability: float | None,
) -> dict[str, Any]:
    if edge is None or market_pick_probability is None:
        return {
            "code": "unavailable",
            "label": "Market unavailable",
            "severity": "none",
            "summary": "A complete moneyline market is not available.",
            "model_market_relationship": "unknown",
            "betting_recommendation": False,
        }

    magnitude = abs(edge)
    if magnitude < 0.02:
        code, label, severity = "aligned", "Market aligned", "low"
    elif magnitude < 0.05:
        code, label, severity = "small_difference", "Small difference", "low"
    elif magnitude < 0.08:
        code, label, severity = "notable_difference", "Notable difference", "medium"
    else:
        code, label, severity = "large_disagreement", "Large disagreement", "high"

    if edge > 0:
        relationship = "model_more_confident"
        summary = (
            f"SportsIntel is more confident in {model_pick} than "
            "the no-vig market."
        )
    elif edge < 0:
        relationship = "market_more_confident"
        summary = (
            f"The no-vig market is more confident in {model_pick} "
            "than SportsIntel."
        )
    else:
        relationship = "aligned"
        summary = f"SportsIntel and the no-vig market agree on {model_pick}."

    return {
        "code": code,
        "label": label,
        "severity": severity,
        "summary": summary,
        "model_market_relationship": relationship,
        "betting_recommendation": False,
    }


def _market_context(
    scoreboard: dict[str, Any],
    game_id: str,
) -> dict[str, Any]:
    odds = _collection_item(
        scoreboard.get("gameodds", {}),
        game_id,
        "nfl.g.",
    )

    if not odds:
        return {
            "available": False,
            "source": None,
            "away_moneyline": None,
            "home_moneyline": None,
            "away_implied_probability": None,
            "home_implied_probability": None,
            "away_no_vig_probability": None,
            "home_no_vig_probability": None,
            "market_hold": None,
        }

    away_moneyline = _first_odds_value(
        odds,
        (
            "away_moneyline",
            "away_ml",
            "awaymoneyline",
            "moneyline_away",
            "away_odds",
        ),
    )
    home_moneyline = _first_odds_value(
        odds,
        (
            "home_moneyline",
            "home_ml",
            "homemoneyline",
            "moneyline_home",
            "home_odds",
        ),
    )

    away_implied = _implied_probability(away_moneyline)
    home_implied = _implied_probability(home_moneyline)

    away_no_vig = None
    home_no_vig = None
    market_hold = None

    if away_implied is not None and home_implied is not None:
        total = away_implied + home_implied
        if total > 0:
            away_no_vig = round(away_implied / total, 4)
            home_no_vig = round(home_implied / total, 4)
            market_hold = round(total - 1, 4)

    return {
        "available": (
            away_moneyline is not None
            and home_moneyline is not None
        ),
        "source": "Yahoo Sports" if odds else None,
        "away_moneyline": away_moneyline,
        "home_moneyline": home_moneyline,
        "away_implied_probability": away_implied,
        "home_implied_probability": home_implied,
        "away_no_vig_probability": away_no_vig,
        "home_no_vig_probability": home_no_vig,
        "market_hold": market_hold,
        "raw": odds,
    }


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
    away_qb = _qb_context(scoreboard, game_id, away_team, "away")
    home_qb = _qb_context(scoreboard, game_id, home_team, "home")
    market = _market_context(scoreboard, game_id)

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
            "away_qb": away_qb,
            "home_qb": home_qb,
            "qb_affects_prediction": False,
            "market": market,
            "market_affects_prediction": False,
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


def _season_context(game: SportGame) -> dict[str, Any]:
    metadata = game.metadata or {}
    season = metadata.get("season")
    week = metadata.get("week")
    status_detail = str(metadata.get("status_detail") or "").lower()

    season_type = ""
    season_label = ""
    week_number: int | None = None

    if isinstance(season, dict):
        season_type = str(
            season.get("type")
            or season.get("slug")
            or season.get("name")
            or ""
        ).lower()
        season_label = str(
            season.get("displayName")
            or season.get("name")
            or ""
        )

    if isinstance(week, dict):
        raw_week = (
            week.get("number")
            or week.get("week")
            or week.get("value")
        )
        try:
            week_number = int(raw_week)
        except (TypeError, ValueError):
            week_number = None

    joined = " ".join(
        value
        for value in (
            season_type,
            season_label.lower(),
            status_detail,
        )
        if value
    )

    game_date = None
    raw_start = str(game.start_time or "").strip()

    if raw_start and raw_start != "TBD":
        try:
            game_date = date.fromisoformat(raw_start[:10])
        except ValueError:
            try:
                game_date = parsedate_to_datetime(raw_start).date()
            except (TypeError, ValueError, OverflowError):
                game_date = None

    calendar_preseason = bool(
        game_date
        and game_date.month == 8
        and game_date.day <= 31
    )

    is_preseason = (
        "preseason" in joined
        or season_type in {"1", "pre"}
        or calendar_preseason
    )

    if not is_preseason:
        return {
            "season_phase": "regular",
            "preseason_week": None,
            "prediction_type": "regular_pick",
            "prediction_label": "Moneyline Pick",
            "starter_certainty": "standard",
            "preseason_confidence_cap": None,
            "season_detection_source": (
                "schedule metadata"
                if joined and not calendar_preseason
                else "calendar fallback"
            ),
        }

    if week_number is None and game_date is not None:
        if game_date.day <= 6:
            week_number = 1
        elif game_date.day <= 13:
            week_number = 1
        elif game_date.day <= 20:
            week_number = 2
        else:
            week_number = 3

    if "hall of fame" in joined:
        cap = 55
        label = "Hall of Fame Game Lean"
    elif week_number == 1:
        cap = 57
        label = "Preseason Week 1 Lean"
    elif week_number == 2:
        cap = 58
        label = "Preseason Week 2 Lean"
    elif week_number == 3:
        cap = 60
        label = "Preseason Week 3 Lean"
    else:
        cap = 57
        label = "Preseason Lean"

    return {
        "season_phase": "preseason",
        "preseason_week": week_number,
        "prediction_type": "preseason_lean",
        "prediction_label": label,
        "starter_certainty": "low",
        "preseason_confidence_cap": cap,
        "season_detection_source": (
            "schedule metadata"
            if "preseason" in joined or season_type in {"1", "pre"}
            else "calendar fallback"
        ),
    }


def _moneyline_prediction(game: SportGame) -> SportPrediction:
    away_team_normalized = normalize_team_name(game.away_team)
    home_team_normalized = normalize_team_name(game.home_team)

    away_rating = team_rating(away_team_normalized)
    home_rating = team_rating(home_team_normalized)
    adjusted_home = home_rating + HOME_FIELD_RATING
    gap = adjusted_home - away_rating

    pick = game.home_team if gap >= 0 else game.away_team
    raw_confidence = round(
        min(68, max(53, 54 + abs(gap) * 1.35))
    )
    probability = round(
        min(0.68, max(0.52, 0.52 + abs(gap) / 45)),
        3,
    )

    away_qb = game.metadata.get("away_qb", {})
    home_qb = game.metadata.get("home_qb", {})
    qb_announced = bool(
        isinstance(away_qb, dict)
        and away_qb.get("name")
        and isinstance(home_qb, dict)
        and home_qb.get("name")
    )
    qb_confirmed = bool(
        qb_announced
        and away_qb.get("confirmed")
        and home_qb.get("confirmed")
    )
    records_available = bool(
        game.metadata.get("away_record")
        and game.metadata.get("home_record")
    )

    data_readiness_score = 60
    if qb_announced:
        data_readiness_score += 20
    if qb_confirmed:
        data_readiness_score += 10
    if records_available:
        data_readiness_score += 10

    if qb_confirmed:
        confidence_cap = 68
        readiness_label = "strong"
    elif qb_announced:
        confidence_cap = 64
        readiness_label = "developing"
    else:
        confidence_cap = 60
        readiness_label = "limited"

    season_context = _season_context(game)
    preseason_cap = season_context.get("preseason_confidence_cap")
    if isinstance(preseason_cap, int):
        confidence_cap = min(confidence_cap, preseason_cap)

    confidence = min(raw_confidence, confidence_cap)

    market = game.metadata.get("market", {})
    market_available = bool(
        isinstance(market, dict)
        and market.get("available")
    )
    model_pick_probability = probability

    if pick == game.away_team:
        market_pick_probability = (
            market.get("away_no_vig_probability")
            if market_available
            else None
        )
        pick_moneyline = (
            market.get("away_moneyline")
            if market_available
            else None
        )
    else:
        market_pick_probability = (
            market.get("home_no_vig_probability")
            if market_available
            else None
        )
        pick_moneyline = (
            market.get("home_moneyline")
            if market_available
            else None
        )

    market_edge = (
        round(model_pick_probability - market_pick_probability, 4)
        if isinstance(market_pick_probability, (int, float))
        else None
    )
    market_signal = _market_signal(
        market_edge,
        pick,
        market_pick_probability,
    )

    factors = [
        {
            "factor_id": "team_rating",
            "name": "Provisional Team Rating",
            "category": "team_strength",
            "score": round(gap, 3),
            "weight": 1.0,
            "reliability": 0.5,
            "explanation": (
                f"{away_team_normalized} rating: {away_rating:.1f}; "
                f"{home_team_normalized} rating: {home_rating:.1f}."
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
        {
            "factor_id": "quarterback_status",
            "name": "Quarterback Status",
            "category": "key_player",
            "score": 0.0,
            "weight": 0.0,
            "reliability": 0.35 if qb_announced else 0.0,
            "explanation": (
                (
                    f"{game.away_team}: {away_qb.get('name')} "
                    f"({away_qb.get('status')}); "
                    f"{game.home_team}: {home_qb.get('name')} "
                    f"({home_qb.get('status')})."
                )
                if qb_announced
                else "Starting quarterbacks are not yet confirmed."
            ),
            "direction": "neutral",
            "usage": "observation_only",
            "version": RATING_VERSION,
            "contributes_to": [],
            "used_in_confidence": False,
        },
        {
            "factor_id": "preseason_context",
            "name": "Preseason Context",
            "category": "season_phase",
            "score": 0.0,
            "weight": 0.0,
            "reliability": 1.0,
            "explanation": (
                "Confidence is reduced because preseason playing time "
                "and player participation are highly variable."
                if season_context["season_phase"] == "preseason"
                else "Regular-season context is active."
            ),
            "direction": "neutral",
            "usage": "observation_only",
            "version": RATING_VERSION,
            "contributes_to": [],
            "used_in_confidence": False,
        },
        {
            "factor_id": "market_moneyline",
            "name": "Market Moneyline",
            "category": "market",
            "score": market_edge or 0.0,
            "weight": 0.0,
            "reliability": 0.8 if market_available else 0.0,
            "explanation": (
                (
                    f"SportsIntel probability: "
                    f"{model_pick_probability * 100:.1f}%; "
                    f"market no-vig probability: "
                    f"{market_pick_probability * 100:.1f}%; "
                    f"edge: {market_edge * 100:+.1f}%."
                )
                if market_edge is not None
                else "Moneyline odds are not available for this game."
            ),
            "direction": (
                "positive"
                if market_edge is not None and market_edge > 0
                else "negative"
                if market_edge is not None and market_edge < 0
                else "neutral"
            ),
            "usage": "observation_only",
            "version": RATING_VERSION,
            "contributes_to": [],
            "used_in_confidence": False,
        },
    ]

    markets = [
        MarketPrediction(
            market_type=MarketType.MONEYLINE,
            selection=pick,
            confidence=confidence,
            line=pick_moneyline,
            projected_value=probability,
            recommendation=(
                market_signal["label"]
                if market_edge is not None
                else "Early model lean"
            ),
            explanation=(
                f"Model edge versus no-vig market: "
                f"{market_edge * 100:+.1f}%."
                if market_edge is not None
                else "Market moneyline is not available."
            ),
            factor_ids=(
                "team_rating",
                "home_field",
                "market_moneyline",
            ),
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
        recommendation=season_context["prediction_label"],
        factors=factors,
        timeline=[],
        markets=markets,
        explanation={
            "title": "Why SportsIntel Likes This Pick",
            "summary": (
                (
                    f"SportsIntel gives {pick} a preseason lean based on "
                    "provisional team strength and home field only."
                    if season_context["season_phase"] == "preseason"
                    else
                    f"SportsIntel gives {pick} an early edge based on "
                    "provisional team strength and home field only."
                )
            ),
            "reasons": [
                f"Adjusted rating gap is {abs(gap):.1f} points in favor of {pick}.",
                (
                    f"Confidence is capped at {confidence_cap}% because "
                    f"the current data-readiness level is {readiness_label}."
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
            "away_team_original": game.away_team,
            "away_team_normalized": away_team_normalized,
            "home_team_original": game.home_team,
            "home_team_normalized": home_team_normalized,
            "team_name_normalized": (
                away_team_normalized != game.away_team
                or home_team_normalized != game.home_team
            ),
            "away_rating": away_rating,
            "home_rating": home_rating,
            "home_field_rating": HOME_FIELD_RATING,
            "rating_gap": round(gap, 3),
            "away_qb": away_qb,
            "home_qb": home_qb,
            "qb_announced": qb_announced,
            "qb_confirmed": qb_confirmed,
            "qb_affects_prediction": False,
            "records_available": records_available,
            "data_readiness_score": data_readiness_score,
            "data_readiness_label": readiness_label,
            "raw_confidence": raw_confidence,
            "confidence_cap": confidence_cap,
            "confidence_guardrail_applied": (
                confidence < raw_confidence
            ),
            "season_phase": season_context["season_phase"],
            "preseason_week": season_context["preseason_week"],
            "prediction_type": season_context["prediction_type"],
            "prediction_label": season_context["prediction_label"],
            "starter_certainty": season_context["starter_certainty"],
            "preseason_confidence_cap": (
                season_context["preseason_confidence_cap"]
            ),
            "season_detection_source": (
                season_context["season_detection_source"]
            ),
            "market_available": market_available,
            "market_source": (
                market.get("source")
                if isinstance(market, dict)
                else None
            ),
            "away_moneyline": (
                market.get("away_moneyline")
                if isinstance(market, dict)
                else None
            ),
            "home_moneyline": (
                market.get("home_moneyline")
                if isinstance(market, dict)
                else None
            ),
            "away_market_probability": (
                market.get("away_no_vig_probability")
                if isinstance(market, dict)
                else None
            ),
            "home_market_probability": (
                market.get("home_no_vig_probability")
                if isinstance(market, dict)
                else None
            ),
            "market_hold": (
                market.get("market_hold")
                if isinstance(market, dict)
                else None
            ),
            "model_pick_probability": model_pick_probability,
            "market_pick_probability": market_pick_probability,
            "market_edge": market_edge,
            "market_signal_code": market_signal["code"],
            "market_signal_label": market_signal["label"],
            "market_signal_severity": market_signal["severity"],
            "market_signal_summary": market_signal["summary"],
            "model_market_relationship": market_signal["model_market_relationship"],
            "market_betting_recommendation": market_signal["betting_recommendation"],
            "market_affects_prediction": False,
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
