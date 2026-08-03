from datetime import date, timedelta
import os
import time

import feedparser
import httpx

from app.prediction_history import attach_prediction_history
from app.yahoo_pitchers import apply_yahoo_probable_pitchers


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


def _pitcher_status(away_pitcher: str | None, home_pitcher: str | None) -> dict:
    confirmed_count = int(bool(away_pitcher)) + int(bool(home_pitcher))
    if confirmed_count == 2:
        return {
            "code": "confirmed",
            "label": "Confirmed",
            "message": "Both probable starting pitchers have been announced.",
        }
    if confirmed_count == 1:
        return {
            "code": "partial",
            "label": "Partially Confirmed",
            "message": "One probable starter has been announced; the other is still pending.",
        }
    return {
        "code": "pending",
        "label": "Not Yet Announced",
        "message": "Neither team has officially announced a probable starter yet.",
    }



def _recent_form() -> dict[int, dict]:
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=20)

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

    results: dict[int, list[bool]] = {}
    for day in response.json().get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue

            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})
            away_score = away.get("score")
            home_score = home.get("score")
            away_id = away.get("team", {}).get("id")
            home_id = home.get("team", {}).get("id")

            if None in (away_score, home_score, away_id, home_id):
                continue

            away_won = away_score > home_score
            results.setdefault(away_id, []).append(away_won)
            results.setdefault(home_id, []).append(not away_won)

    momentum: dict[int, dict] = {}
    for team_id, outcomes in results.items():
        recent = outcomes[-10:]
        wins = sum(recent)
        losses = len(recent) - wins
        win_pct = wins / len(recent) if recent else 0.5
        momentum[team_id] = {
            "wins": wins,
            "losses": losses,
            "games": len(recent),
            "record": f"{wins}-{losses}" if recent else "Unavailable",
            "win_pct": round(win_pct, 3),
            "label": (
                "Hot"
                if len(recent) >= 5 and win_pct >= 0.7
                else "Cold"
                if len(recent) >= 5 and win_pct <= 0.3
                else "Steady"
            ),
        }
    return momentum


def _team_momentum(momentum: dict[int, dict], team_id: int) -> dict:
    return momentum.get(
        team_id,
        {
            "wins": 0,
            "losses": 0,
            "games": 0,
            "record": "Unavailable",
            "win_pct": 0.5,
            "label": "Unknown",
        },
    )


_SPLITS_CACHE: tuple[float, dict[int, dict]] | None = None
SPLITS_CACHE_SECONDS = 1800


def _season_splits() -> dict[int, dict]:
    global _SPLITS_CACHE
    now = time.monotonic()
    if _SPLITS_CACHE and _SPLITS_CACHE[0] > now:
        return _SPLITS_CACHE[1]

    end_date = date.today() - timedelta(days=1)
    start_date = date(date.today().year, 3, 1)

    response = httpx.get(
        SCHEDULE_URL,
        params={
            "sportId": 1,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
        timeout=20,
    )
    response.raise_for_status()

    raw: dict[int, dict] = {}
    for day in response.json().get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue

            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})
            away_score = away.get("score")
            home_score = home.get("score")
            away_id = away.get("team", {}).get("id")
            home_id = home.get("team", {}).get("id")

            if None in (away_score, home_score, away_id, home_id):
                continue

            away_won = away_score > home_score
            raw.setdefault(
                away_id,
                {"home_wins": 0, "home_losses": 0, "away_wins": 0, "away_losses": 0},
            )
            raw.setdefault(
                home_id,
                {"home_wins": 0, "home_losses": 0, "away_wins": 0, "away_losses": 0},
            )

            if away_won:
                raw[away_id]["away_wins"] += 1
                raw[home_id]["home_losses"] += 1
            else:
                raw[away_id]["away_losses"] += 1
                raw[home_id]["home_wins"] += 1

    result: dict[int, dict] = {}
    for team_id, values in raw.items():
        home_games = values["home_wins"] + values["home_losses"]
        away_games = values["away_wins"] + values["away_losses"]
        result[team_id] = {
            **values,
            "home_record": f'{values["home_wins"]}-{values["home_losses"]}',
            "away_record": f'{values["away_wins"]}-{values["away_losses"]}',
            "home_pct": values["home_wins"] / home_games if home_games else 0.5,
            "away_pct": values["away_wins"] / away_games if away_games else 0.5,
        }

    _SPLITS_CACHE = (now + SPLITS_CACHE_SECONDS, result)
    return result


def _team_split(splits: dict[int, dict], team_id: int) -> dict:
    return splits.get(
        team_id,
        {
            "home_wins": 0,
            "home_losses": 0,
            "away_wins": 0,
            "away_losses": 0,
            "home_record": "Unavailable",
            "away_record": "Unavailable",
            "home_pct": 0.5,
            "away_pct": 0.5,
        },
    )

def _record(record: dict) -> str:
    wins = record.get("wins")
    losses = record.get("losses")
    return f"{wins}-{losses}" if wins is not None and losses is not None else "Record unavailable"


def _confidence_details(
    winner: str,
    home_name: str,
    away_name: str,
    gap: float,
    away_pitcher: str | None,
    home_pitcher: str | None,
    away_momentum: dict,
    home_momentum: dict,
    away_split: dict,
    home_split: dict,
) -> dict:
    record_impact = 5 if gap >= 0.15 else 4 if gap >= 0.08 else 3 if gap >= 0.04 else 2
    pitcher_status = _pitcher_status(away_pitcher, home_pitcher)
    pitchers_confirmed = pitcher_status["code"] == "confirmed"
    pitcher_impact = 4 if pitchers_confirmed else 3 if pitcher_status["code"] == "partial" else 2
    home_pick = winner == home_name
    momentum_gap = abs(home_momentum["win_pct"] - away_momentum["win_pct"])
    momentum_impact = 4 if momentum_gap >= 0.4 else 3 if momentum_gap >= 0.2 else 2
    momentum_leader = (
        home_name
        if home_momentum["win_pct"] > away_momentum["win_pct"]
        else away_name
        if away_momentum["win_pct"] > home_momentum["win_pct"]
        else None
    )
    split_gap = abs(home_split["home_pct"] - away_split["away_pct"])
    split_impact = 4 if split_gap >= 0.2 else 3 if split_gap >= 0.1 else 2

    factors = [
        {
            "title": "Season Performance",
            "impact": record_impact,
            "summary": (
                f"{winner} has the stronger season record."
                if gap >= 0.04
                else f"{home_name} and {away_name} have relatively similar season records."
            ),
        },
        {
            "title": "Recent Team Momentum",
            "impact": momentum_impact,
            "summary": (
                f"{momentum_leader} has the stronger recent form: "
                f"{away_name} {away_momentum['record']} vs "
                f"{home_name} {home_momentum['record']} over each team's latest games."
                if momentum_leader
                else (
                    f"Recent form is even: {away_name} {away_momentum['record']} vs "
                    f"{home_name} {home_momentum['record']}."
                )
            ),
        },
        {
            "title": "Home and Away Performance",
            "impact": split_impact,
            "summary": (
                f"{home_name} is {home_split['home_record']} at home, while "
                f"{away_name} is {away_split['away_record']} on the road."
            ),
        },
        {
            "title": "Starting Pitchers",
            "impact": pitcher_impact,
            "summary": (
                f"Both probable starters are confirmed: {away_pitcher} vs {home_pitcher}."
                if pitchers_confirmed
                else pitcher_status["message"]
            ),
        },
        {
            "title": "Home Field",
            "impact": 2,
            "summary": (
                f"{home_name} receives a small home-field adjustment."
                if home_pick
                else f"{winner} remains the model pick despite {home_name}'s home-field adjustment."
            ),
        },
        {
            "title": "Yahoo Sports News",
            "impact": 1,
            "summary": "No major Yahoo Sports headline adjustment is currently applied to this MLB prediction.",
        },
    ]

    risk = (
        " Confidence is limited because the probable pitchers are not fully confirmed."
        if not pitchers_confirmed
        else ""
    )
    return {
        "title": "Why SportsIntel Likes This Pick",
        "factors": factors,
        "summary": (
            f"SportsIntel favors {winner} based primarily on season performance, "
            f"with a small home-field adjustment.{risk}"
        ),
    }


def _predict(game: dict, momentum: dict[int, dict] | None = None) -> dict:
    away = game["teams"]["away"]
    home = game["teams"]["home"]
    away_name = away["team"]["name"]
    home_name = home["team"]["name"]
    away_team_id = away["team"]["id"]
    home_team_id = home["team"]["id"]
    away_pct = _pct(away.get("leagueRecord", {}))
    home_pct = _pct(home.get("leagueRecord", {}))

    momentum = momentum or {}
    away_momentum = _team_momentum(momentum, away_team_id)
    home_momentum = _team_momentum(momentum, home_team_id)
    splits = _season_splits()
    away_split = _team_split(splits, away_team_id)
    home_split = _team_split(splits, home_team_id)
    momentum_adjustment = (home_momentum["win_pct"] - away_momentum["win_pct"]) * 0.025
    split_adjustment = (home_split["home_pct"] - away_split["away_pct"]) * 0.02

    adjusted_home = home_pct + 0.015 + momentum_adjustment + split_adjustment
    winner = home_name if adjusted_home >= away_pct else away_name
    gap = abs(adjusted_home - away_pct)
    confidence = round(
        min(
            90,
            max(
                55,
                58
                + gap * 95
                + abs(momentum_adjustment) * 100
                + abs(split_adjustment) * 100,
            ),
        )
    )
    probability = min(0.72, 0.52 + gap * 1.45)

    away_score = away.get("score")
    home_score = home.get("score")
    completed = game["status"].get("abstractGameState") == "Final"
    actual_winner = None
    if completed and away_score is not None and home_score is not None:
        actual_winner = home_name if home_score > away_score else away_name

    away_pitcher = _pitcher(game, "away")
    home_pitcher = _pitcher(game, "home")
    pitcher_status = _pitcher_status(away_pitcher, home_pitcher)
    rec = recommendation(confidence)
    confidence_details = _confidence_details(
        winner=winner,
        home_name=home_name,
        away_name=away_name,
        gap=gap,
        away_pitcher=away_pitcher,
        home_pitcher=home_pitcher,
        away_momentum=away_momentum,
        home_momentum=home_momentum,
        away_split=away_split,
        home_split=home_split,
    )

    return {
        **rec,
        "confidence_details": confidence_details,
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
        "away_momentum": away_momentum,
        "home_momentum": home_momentum,
        "away_split": away_split,
        "home_split": home_split,
        "momentum_advantage": (
            home_name
            if home_momentum["win_pct"] > away_momentum["win_pct"]
            else away_name
            if away_momentum["win_pct"] > home_momentum["win_pct"]
            else None
        ),
        "away_pitcher": away_pitcher,
        "home_pitcher": home_pitcher,
        "pitcher_status": pitcher_status,
        "confidence": confidence,
        "moneyline_pick": winner,
        "run_line_pick": f"{winner} -1.5",
        "total_pick": "UNDER 8.5" if gap > 0.12 else "OVER 8.5",
        "reasons": [
            f"{winner} has the stronger season record after a small home-field adjustment.",
            f"Current team-record gap is {gap:.3f}.",
            (
                f"Recent form: {away_name} {away_momentum['record']} "
                f"vs {home_name} {home_momentum['record']}."
            ),
            (
                f"Venue splits: {home_name} {home_split['home_record']} at home; "
                f"{away_name} {away_split['away_record']} on the road."
            ),
            (
                f"Probable pitchers: {away_pitcher or 'Not yet announced'} vs "
                f"{home_pitcher or 'Not yet announced'}. "
                f"{pitcher_status['message']}"
            ),
        ],
    }


NEGATIVE_NEWS_TERMS = (
    "injury",
    "injured",
    "scratched",
    "suspended",
    "illness",
    "setback",
    "placed on il",
    "injured list",
    "shoulder",
    "elbow",
    "hamstring",
)

POSITIVE_NEWS_TERMS = (
    "returns",
    "activated",
    "cleared",
    "healthy",
    "reinstated",
    "available",
    "confirmed",
)


def _classify_news(title: str) -> dict:
    normalized = title.lower()
    if any(term in normalized for term in NEGATIVE_NEWS_TERMS):
        return {
            "impact": "negative",
            "impact_label": "Potential concern",
            "decision_note": "Review this update before relying on today's prediction.",
        }
    if any(term in normalized for term in POSITIVE_NEWS_TERMS):
        return {
            "impact": "positive",
            "impact_label": "Positive update",
            "decision_note": "This may reduce uncertainty around today's games.",
        }
    return {
        "impact": "neutral",
        "impact_label": "General update",
        "decision_note": "No direct prediction adjustment is currently applied.",
    }


def _news() -> list[dict]:
    feed = feedparser.parse(os.getenv("YAHOO_MLB_RSS_URL", YAHOO_MLB_RSS_URL))
    items = []
    for entry in feed.entries[:8]:
        title = entry.get("title", "MLB update")
        items.append(
            {
                "title": title,
                "link": entry.get("link", ""),
                "published": entry.get("published"),
                **_classify_news(title),
            }
        )

    return sorted(
        items,
        key=lambda item: {"negative": 0, "positive": 1, "neutral": 2}[item["impact"]],
    )[:6]

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

    momentum = _recent_form()
    games = [
        _predict(game, momentum)
        for day in payload.get("dates", [])
        for game in day.get("games", [])
    ]
    apply_yahoo_probable_pitchers(games)
    games.sort(key=lambda game: game["start_time"])
    attach_prediction_history(games)

    pick_of_day = max(
        games,
        key=lambda game: (
            game["rating"],
            game["confidence"],
            int(bool(game["away_pitcher"])) + int(bool(game["home_pitcher"])),
        ),
    ) if games else None

    for game in games:
        game["is_pick_of_day"] = bool(
            pick_of_day and game["game_id"] == pick_of_day["game_id"]
        )

    daily_card = sorted(
        games,
        key=lambda game: (
            game["rating"],
            game["confidence"],
            int(bool(game["away_pitcher"])) + int(bool(game["home_pitcher"])),
        ),
        reverse=True,
    )[:5]

    stay_away = min(
        games,
        key=lambda game: (
            game["rating"],
            game["confidence"],
            int(bool(game["away_pitcher"])) + int(bool(game["home_pitcher"])),
        ),
    ) if games else None

    if stay_away:
        missing_pitchers = not stay_away["away_pitcher"] or not stay_away["home_pitcher"]
        stay_away["stay_away_reason"] = (
            "At least one starting pitcher is not yet confirmed."
            if missing_pitchers
            else "This is the lowest-confidence matchup on today's board."
        )

    result = {
        "sport": "MLB",
        "date": date.today().isoformat(),
        "games": games,
        "best_pick": pick_of_day,
        "pick_of_day": pick_of_day,
        "daily_card": daily_card,
        "stay_away": stay_away,
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
