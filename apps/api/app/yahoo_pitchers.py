from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

import httpx


YAHOO_MLB_SCOREBOARD_API = os.getenv(
    "YAHOO_MLB_SCOREBOARD_API",
    "https://api-secure.sports.yahoo.com/v1/editorial/s/scoreboard",
)

TEAM_ALIASES = {
    "Arizona Diamondbacks": {"arizona", "diamondbacks", "ari"},
    "Athletics": {"athletics", "ath"},
    "Atlanta Braves": {"atlanta", "braves", "atl"},
    "Baltimore Orioles": {"baltimore", "orioles", "bal"},
    "Boston Red Sox": {"boston", "red sox", "bos"},
    "Chicago Cubs": {"chicago cubs", "cubs", "chc"},
    "Chicago White Sox": {"chicago white sox", "white sox", "cws"},
    "Cincinnati Reds": {"cincinnati", "reds", "cin"},
    "Cleveland Guardians": {"cleveland", "guardians", "cle"},
    "Colorado Rockies": {"colorado", "rockies", "col"},
    "Detroit Tigers": {"detroit", "tigers", "det"},
    "Houston Astros": {"houston", "astros", "hou"},
    "Kansas City Royals": {"kansas city", "royals", "kc"},
    "Los Angeles Angels": {"los angeles angels", "angels", "laa"},
    "Los Angeles Dodgers": {"los angeles dodgers", "dodgers", "lad"},
    "Miami Marlins": {"miami", "marlins", "mia"},
    "Milwaukee Brewers": {"milwaukee", "brewers", "mil"},
    "Minnesota Twins": {"minnesota", "twins", "min"},
    "New York Mets": {"new york mets", "mets", "nym"},
    "New York Yankees": {"new york yankees", "yankees", "nyy"},
    "Philadelphia Phillies": {"philadelphia", "phillies", "phi"},
    "Pittsburgh Pirates": {"pittsburgh", "pirates", "pit"},
    "San Diego Padres": {"san diego", "padres", "sd"},
    "San Francisco Giants": {"san francisco", "giants", "sf"},
    "Seattle Mariners": {"seattle", "mariners", "sea"},
    "St. Louis Cardinals": {"st louis", "cardinals", "stl"},
    "Tampa Bay Rays": {"tampa bay", "rays", "tb"},
    "Texas Rangers": {"texas", "rangers", "tex"},
    "Toronto Blue Jays": {"toronto", "blue jays", "tor"},
    "Washington Nationals": {"washington", "nationals", "was"},
}


def _normalize(value: str) -> str:
    value = value.lower().replace(".", " ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _all_strings(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for nested in value.values():
            values.extend(_all_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(_all_strings(nested))
    return values


def _game_contains_team(yahoo_game: dict, mlb_team_name: str) -> bool:
    haystack = " | ".join(_normalize(item) for item in _all_strings(yahoo_game))
    aliases = TEAM_ALIASES.get(mlb_team_name, {_normalize(mlb_team_name)})
    return any(_normalize(alias) in haystack for alias in aliases)


def _clean_person_name(value: str | None) -> str | None:
    if not value:
        return None
    value = " ".join(value.split()).strip(" :-")
    if not value or value.upper() in {"TBD", "N/A", "NA"}:
        return None
    if len(value) > 80 or not re.search(r"[A-Za-z]", value):
        return None
    return value


def _name_from_mapping(value: Any) -> str | None:
    if not isinstance(value, dict):
        return _clean_person_name(value) if isinstance(value, str) else None

    for key in ("full_name", "display_name", "player_name", "name", "short_name"):
        candidate = value.get(key)
        if isinstance(candidate, str):
            cleaned = _clean_person_name(candidate)
            if cleaned:
                return cleaned

    first = value.get("first_name") or value.get("first")
    last = value.get("last_name") or value.get("last")
    if isinstance(first, str) and isinstance(last, str):
        return _clean_person_name(f"{first} {last}")

    for key in ("player", "athlete", "person"):
        candidate = _name_from_mapping(value.get(key))
        if candidate:
            return candidate

    for key, nested in value.items():
        if "name" in str(key).lower():
            candidate = _name_from_mapping(nested)
            if candidate:
                return candidate

    return None


def _stats_from_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    stats: dict[str, str] = {}
    raw_stats = value.get("stats")
    if isinstance(raw_stats, list):
        for stat in raw_stats:
            if not isinstance(stat, dict):
                continue
            key = str(stat.get("abbr") or stat.get("name") or "").strip().upper()
            stat_value = stat.get("value")
            if key and stat_value not in (None, ""):
                stats[key] = str(stat_value)

    for key in ("era", "whip", "wins", "losses", "record", "handedness", "throws"):
        raw = value.get(key)
        if raw not in (None, ""):
            stats[key.upper()] = str(raw)

    return stats


def _pitcher_details(value: Any) -> dict:
    if not isinstance(value, dict):
        return {"name": _name_from_mapping(value), "stats": {}}

    return {
        "name": _name_from_mapping(value),
        "player_id": value.get("player_id") or value.get("id"),
        "stats": _stats_from_mapping(value),
    }


def _extract_ordered_pitchers(yahoo_game: dict) -> tuple[dict, dict]:
    raw = yahoo_game.get("starting_pitchers")
    if not isinstance(raw, list):
        return {}, {}

    details = [_pitcher_details(item) for item in raw]
    details = [item for item in details if item.get("name")]
    if len(details) >= 2:
        return details[0], details[1]
    if len(details) == 1:
        return details[0], {}
    return {}, {}


def _fetch_yahoo_scoreboard(
    target_date: date,
) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    try:
        response = httpx.get(
            YAHOO_MLB_SCOREBOARD_API,
            params={"leagues": "mlb", "date": target_date.isoformat()},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; SportsIntel/1.0; "
                    "+https://sportsintel.discovera.ai)"
                ),
                "Accept": "application/json",
            },
            follow_redirects=True,
            timeout=12,
        )
        response.raise_for_status()
        scoreboard = response.json().get("service", {}).get("scoreboard", {})
        games = scoreboard.get("games", {})
        byline = scoreboard.get("gamebyline", {})
        players = scoreboard.get("players", {})
        return (
            [game for game in games.values() if isinstance(game, dict)],
            {str(key): value for key, value in byline.items() if isinstance(value, dict)},
            {str(key): value for key, value in players.items() if isinstance(value, dict)},
        )
    except (httpx.HTTPError, ValueError, AttributeError):
        return [], {}, {}


def _merge_details(
    primary: dict,
    secondary: Any,
    players: dict[str, dict],
) -> dict:
    secondary_details = _pitcher_details(secondary)
    player_id = primary.get("player_id") or secondary_details.get("player_id")
    player = players.get(str(player_id), {}) if player_id else {}

    return {
        "name": (
            primary.get("name")
            or secondary_details.get("name")
            or _clean_person_name(player.get("display_name"))
        ),
        "player_id": player_id,
        "stats": {
            **secondary_details.get("stats", {}),
            **primary.get("stats", {}),
            **(
                {"THROWS": str(player.get("throw"))}
                if player.get("throw") not in (None, "")
                else {}
            ),
        },
    }


def _stat_value(details: dict, *names: str) -> str | None:
    stats = details.get("stats", {})
    for name in names:
        value = stats.get(name.upper())
        if value not in (None, ""):
            return str(value)
    return None


def _display_stats(details: dict) -> dict:
    wins = _stat_value(details, "W", "WINS")
    losses = _stat_value(details, "L", "LOSSES")
    record = _stat_value(details, "RECORD")
    if not record and wins is not None and losses is not None:
        record = f"{wins}-{losses}"

    return {
        "record": record,
        "era": _stat_value(details, "ERA"),
        "whip": _stat_value(details, "WHIP"),
        "throws": _stat_value(details, "THROWS", "HANDEDNESS"),
    }


def _source_label(away_source: str, home_source: str) -> str:
    sources = {away_source, home_source}
    if sources == {"mlb"}:
        return "MLB"
    if sources == {"yahoo"}:
        return "Yahoo Sports fallback"
    if "yahoo" in sources and "mlb" in sources:
        return "MLB + Yahoo Sports"
    if "yahoo" in sources:
        return "Yahoo Sports fallback"
    if "mlb" in sources:
        return "MLB"
    return "Unavailable"


def _status(
    away_pitcher: str | None,
    home_pitcher: str | None,
    used_yahoo: bool,
) -> dict:
    count = int(bool(away_pitcher)) + int(bool(home_pitcher))
    if count == 2:
        return {
            "code": "probable" if used_yahoo else "confirmed",
            "label": "Probable" if used_yahoo else "Confirmed",
            "message": (
                "Both probable starters are available; at least one is supplied by Yahoo Sports."
                if used_yahoo
                else "Both probable starting pitchers have been announced."
            ),
        }
    if count == 1:
        return {
            "code": "partial",
            "label": "Partially Available",
            "message": "One probable starter is available; the other is still pending.",
        }
    return {
        "code": "pending",
        "label": "Not Yet Announced",
        "message": "Neither MLB nor Yahoo Sports currently lists a probable starter.",
    }


def apply_yahoo_probable_pitchers(games: list[dict]) -> None:
    """Fill missing pitchers and attach Yahoo pitcher stats without changing confidence."""
    yahoo_games, game_byline, players = _fetch_yahoo_scoreboard(date.today())

    for game in games:
        away_source = "mlb" if game.get("away_pitcher") else "unavailable"
        home_source = "mlb" if game.get("home_pitcher") else "unavailable"
        away_details: dict = {}
        home_details: dict = {}

        matching_yahoo_game = next(
            (
                yahoo_game
                for yahoo_game in yahoo_games
                if _game_contains_team(yahoo_game, game["away_team"])
                and _game_contains_team(yahoo_game, game["home_team"])
            ),
            None,
        )

        if matching_yahoo_game:
            away_details, home_details = _extract_ordered_pitchers(matching_yahoo_game)
            yahoo_game_id = str(matching_yahoo_game.get("gameid", ""))
            byline = game_byline.get(yahoo_game_id, {})
            away_details = _merge_details(
                away_details,
                byline.get("away_pitcher"),
                players,
            )
            home_details = _merge_details(
                home_details,
                byline.get("home_pitcher"),
                players,
            )

            if not game.get("away_pitcher") and away_details.get("name"):
                game["away_pitcher"] = away_details["name"]
                away_source = "yahoo"

            if not game.get("home_pitcher") and home_details.get("name"):
                game["home_pitcher"] = home_details["name"]
                home_source = "yahoo"

        game["away_pitcher_source"] = away_source
        game["home_pitcher_source"] = home_source
        game["pitcher_source_label"] = _source_label(away_source, home_source)
        game["away_pitcher_stats"] = _display_stats(away_details)
        game["home_pitcher_stats"] = _display_stats(home_details)
        game["pitcher_status"] = _status(
            game.get("away_pitcher"),
            game.get("home_pitcher"),
            "yahoo" in {away_source, home_source},
        )
