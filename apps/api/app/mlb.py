from datetime import date
import os
import time

import feedparser
import httpx


SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
YAHOO_MLB_RSS_URL = "https://sports.yahoo.com/mlb/rss/"
_CACHE: tuple[float, dict] | None = None
CACHE_SECONDS = 300


def _pct(record: dict) -> float:
    try:
        return float(record.get("pct", ".500"))
    except (TypeError, ValueError):
        return 0.5


def _predict(game: dict) -> dict:
    away = game["teams"]["away"]
    home = game["teams"]["home"]
    away_name = away["team"]["name"]
    home_name = home["team"]["name"]
    away_pct = _pct(away.get("leagueRecord", {}))
    home_pct = _pct(home.get("leagueRecord", {}))

    adjusted_home = home_pct + 0.015
    winner = home_name if adjusted_home >= away_pct else away_name
    gap = abs(adjusted_home - away_pct)
    confidence = round(min(84, 58 + gap * 95))
    probability = min(0.72, 0.52 + gap * 1.45)

    return {
        "game_id": f'mlb-{game["gamePk"]}',
        "away_team": away_name,
        "home_team": home_name,
        "start_time": game["gameDate"],
        "status": game["status"]["detailedState"],
        "winner": winner,
        "win_probability": round(probability, 3),
        "confidence": confidence,
        "moneyline_pick": winner,
        "run_line_pick": f"{winner} -1.5",
        "total_pick": "UNDER 8.5" if gap > 0.12 else "OVER 8.5",
        "reasons": [
            f"{winner} has the stronger season record after a small home-field adjustment.",
            f"Current team-record gap is {gap:.3f}.",
            "This first MLB model intentionally uses only team record and home field.",
        ],
    }


def _news() -> list[dict]:
    feed = feedparser.parse(os.getenv("YAHOO_MLB_RSS_URL", YAHOO_MLB_RSS_URL))
    return [
        {
            "title": entry.get("title", "MLB update"),
            "link": entry.get("link", ""),
            "published": entry.get("published"),
        }
        for entry in feed.entries[:6]
    ]


def mlb_home() -> dict:
    global _CACHE
    now = time.monotonic()
    if _CACHE and _CACHE[0] > now:
        return _CACHE[1]

    response = httpx.get(
        SCHEDULE_URL,
        params={"sportId": 1, "date": date.today().isoformat()},
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()

    games = [
        _predict(game)
        for day in payload.get("dates", [])
        for game in day.get("games", [])
    ]
    games.sort(key=lambda game: game["start_time"])

    result = {
        "sport": "MLB",
        "date": date.today().isoformat(),
        "games": games,
        "best_pick": max(games, key=lambda game: game["confidence"]) if games else None,
        "latest_news": _news(),
    }
    _CACHE = (now + CACHE_SECONDS, result)
    return result
