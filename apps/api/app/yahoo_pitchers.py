from __future__ import annotations

import os
import re
from html.parser import HTMLParser

import httpx


YAHOO_MLB_SCOREBOARD_URL = os.getenv(
    "YAHOO_MLB_SCOREBOARD_URL",
    "https://sports.yahoo.com/mlb/scoreboard/",
)

TEAM_ABBREVIATIONS = {
    "Arizona Diamondbacks": "ARI",
    "Athletics": "ATH",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WAS",
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def _clean_pitcher_name(value: str) -> str | None:
    value = re.sub(r"\s+", " ", value).strip(" :-")
    if not value or value.upper() in {"TBD", "N/A"}:
        return None
    if len(value) > 60:
        return None
    return value


def _extract_pitchers(html: str) -> dict[str, str]:
    parser = _VisibleTextParser()
    parser.feed(html)
    parts = parser.parts
    pitchers: dict[str, str] = {}

    for index, part in enumerate(parts):
        if part not in {"(Away Pitcher)", "(Home Pitcher)"}:
            continue

        abbreviation = None
        for previous in range(index - 1, max(-1, index - 5), -1):
            match = re.search(r"\b([A-Z]{2,3}):?$", parts[previous])
            if match:
                abbreviation = match.group(1)
                break

        if not abbreviation:
            continue

        for following in range(index + 1, min(len(parts), index + 5)):
            candidate = _clean_pitcher_name(parts[following])
            if not candidate:
                continue
            if re.fullmatch(r"\d+-\d+", candidate):
                continue
            if "ERA" in candidate.upper():
                continue
            pitchers[abbreviation] = candidate
            break

    return pitchers


def _fetch_yahoo_pitchers() -> dict[str, str]:
    try:
        response = httpx.get(
            YAHOO_MLB_SCOREBOARD_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; SportsIntel/1.0; "
                    "+https://sportsintel.discovera.ai)"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            timeout=12,
        )
        response.raise_for_status()
        return _extract_pitchers(response.text)
    except (httpx.HTTPError, ValueError):
        return {}


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


def _status(away_pitcher: str | None, home_pitcher: str | None, used_yahoo: bool) -> dict:
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
        "message": "Neither source currently lists a probable starter.",
    }


def apply_yahoo_probable_pitchers(games: list[dict]) -> None:
    """Fill missing MLB probable pitchers from Yahoo without changing confidence."""
    if not any(not game.get("away_pitcher") or not game.get("home_pitcher") for game in games):
        for game in games:
            game["away_pitcher_source"] = "mlb"
            game["home_pitcher_source"] = "mlb"
            game["pitcher_source_label"] = "MLB"
        return

    yahoo_pitchers = _fetch_yahoo_pitchers()

    for game in games:
        away_source = "mlb" if game.get("away_pitcher") else "unavailable"
        home_source = "mlb" if game.get("home_pitcher") else "unavailable"

