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

    preferred_keys = (
        "full_name",
        "display_name",
        "player_name",
        "name",
        "short_name",
    )
    for key in preferred_keys:
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
        nested = value.get(key)
        candidate = _name_from_mapping(nested)
        if candidate:
            return candidate

    for key, nested in value.items():
        if "name" in str(key).lower():
            candidate = _name_from_mapping(nested)
            if candidate:
                return candidate

    return None


def _extract_ordered_pitchers(yahoo_game: dict) -> tuple[str | None, str | None]:
    raw = yahoo_game.get("starting_pitchers")
    if not isinstance(raw, list):
        return None, None

    names = [_name_from_mapping(item) for item in raw]
    names = [name for name in names if name]
    if len(names) >= 2:
        return names[0], names[1]
    if len(names) == 1:
        return names[0], None
    return None, None


def _fetch_yahoo_games(target_date: date) -> list[dict]:
    try:
        response = httpx.get(
            YAHOO_MLB_SCOREBOARD_API,
            params={
                "leagues": "mlb",
                "date": target_date.isoformat(),
            },
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
        payload = response.json()
        games = (
            payload.get("service", {})
            .get("scoreboard", {})
            .get("games", {})
        )
        return [game for game in games.values() if isinstance(game, dict)]
    except (httpx.HTTPError, ValueError, AttributeError):
        return []


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
    """Fill missing MLB probable pitchers from Yahoo without changing confidence."""
    yahoo_games = _fetch_yahoo_games(date.today())

    for game in games:
        away_source = "mlb" if game.get("away_pitcher") else "unavailable"
        home_source = "mlb" if game.get("home_pitcher") else "unavailable"

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
            yahoo_away, yahoo_home = _extract_ordered_pitchers(matching_yahoo_game)

            if not game.get("away_pitcher") and yahoo_away:
                game["away_pitcher"] = yahoo_away
                away_source = "yahoo"

            if not game.get("home_pitcher") and yahoo_home:
                game["home_pitcher"] = yahoo_home
                home_source = "yahoo"

        game["away_pitcher_source"] = away_source
        game["home_pitcher_source"] = home_source
        game["pitcher_source_label"] = _source_label(away_source, home_source)
        game["pitcher_status"] = _status(
            game.get("away_pitcher"),
            game.get("home_pitcher"),
            "yahoo" in {away_source, home_source},
        )
