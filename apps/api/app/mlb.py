from datetime import date, timedelta
import os
import time

import feedparser
import httpx


SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
YAHOO_MLB_RSS_URL = "https://sports.yahoo.com/mlb/rss/"
_CACHE: tuple[float, dict] | None = None
CACHE_SECONDS = 300



def recommendation(confidence: int) -> dict:
    if confidence >= 85:
        return {"rating":5,"stars":"★★★★★","recommendation":"Strong Bet","color":"green"}
    if confidence >= 78:
        return {"rating":4,"stars":"★★★★☆","recommendation":"Good Bet","color":"green"}
    if confidence >= 70:
        return {"rating":3,"stars":"★★★☆☆","recommendation":"Worth Considering","color":"yellow"}
    if confidence >= 60:
        return {"rating":2,"stars":"★★☆☆☆","recommendation":"Risky","color":"orange"}
    return {"rating":1,"stars":"★☆☆☆☆","recommendation":"Stay Away","color":"red"}

def _pct(record: dict) -> float:
    try:
        return float(record.get("pct", ".500"))
    except (TypeError, ValueError):
        return 0.5


def _pitcher(game: dict, side: str) -> str | None:
    probable = game.get("teams", {}).get(side, {}).get("probablePitcher")
    return probable.get("fullName") if probable else None


def _record(record: dict) -> str:
    wins = record.get("wins")
    losses = record.get("losses")
    return f"{wins}-{losses}" if wins is not None and losses is not None else "Record unavailable"


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

    away_score = away.get("score")
    home_score = home.get("score")
    completed = game["status"].get("abstractGameState") == "Final"
    actual_winner = None
    if completed and away_score is not None and home_score is not None:
        actual_winner = home_name if home_score > away_score else away_name

    rec = recommendation(confidence)

    return {
        **rec,
        "game_id": f'mlb-{game["gamePk"]}',
        "away_team": away_name,
        "home_team": home_name,
        "start_time": game["gameDate"],
        "status": game["status"]["detailedState"],
        "completed": completed,
        "away_score": away_score,
        "home_score": home_score,
        "actual_winner": actual_winner,
        "winner": winner,
        "win_probability": round(probability, 3),
        "away_record": _record(away.get("leagueRecord", {})),
        "home_record": _record(home.get("leagueRecord", {})),
        "away_pitcher": _pitcher(game, "away"),
        "home_pitcher": _pitcher(game, "home"),
        "confidence": confidence,
        "moneyline_pick": winner,
        "run_line_pick": f"{winner} -1.5",
        "total_pick": "UNDER 8.5" if gap > 0.12 else "OVER 8.5",
        "reasons": [
            f"{winner} has the stronger season record after a small home-field adjustment.",
            f"Current team-record gap is {gap:.3f}.",
            (
                f"Probable pitchers: {_pitcher(game, 'away') or 'TBD'} vs "
                f"{_pitcher(game, 'home') or 'TBD'}."
            ),
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


def mlb_game(game_id: str) -> dict | None:
    return next((game for game in mlb_home()["games"] if game["game_id"] == game_id), None)


def mlb_results(days: int = 7) -> dict:
    safe_days = max(1, min(days, 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=safe_days - 1)

    response = httpx.get(
        SCHEDULE_URL,
        params={
            "sportId": 1,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    games = [
        _predict(game)
        for day in payload.get("dates", [])
        for game in day.get("games", [])
    ]
    games.sort(key=lambda game: game["start_time"], reverse=True)

    return {
        "sport": "MLB",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": safe_days,
        "games": games,
    }
