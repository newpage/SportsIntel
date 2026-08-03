from app.models import Prediction
from app.news import news_for_teams, team_news_impact


GAMES = [
    {
        "game_id": "nyj-at-buf",
        "away_team": "New York Jets",
        "home_team": "Buffalo Bills",
        "home_rating": 91,
        "away_rating": 76,
        "market_spread": -6.5,
        "market_total": 45.5,
        "pace_total": 47.0,
    },
    {
        "game_id": "det-at-gb",
        "away_team": "Detroit Lions",
        "home_team": "Green Bay Packers",
        "home_rating": 84,
        "away_rating": 89,
        "market_spread": 2.5,
        "market_total": 48.5,
        "pace_total": 51.0,
    },
    {
        "game_id": "kc-at-lac",
        "away_team": "Kansas City Chiefs",
        "home_team": "Los Angeles Chargers",
        "home_rating": 82,
        "away_rating": 94,
        "market_spread": 5.5,
        "market_total": 47.5,
        "pace_total": 46.0,
    },
]


def predict(game: dict) -> Prediction:
    news = news_for_teams(game["away_team"], game["home_team"])
    home_news_impact = team_news_impact(game["home_team"], news)
    away_news_impact = team_news_impact(game["away_team"], news)

    adjusted_home_rating = game["home_rating"] + home_news_impact
    adjusted_away_rating = game["away_rating"] + away_news_impact
    rating_gap = adjusted_home_rating - adjusted_away_rating

    projected_margin = round(rating_gap * 0.45 + 2.2, 1)
    home_probability = max(0.12, min(0.88, 0.5 + projected_margin / 22))
    winner = game["home_team"] if projected_margin >= 0 else game["away_team"]
    win_probability = home_probability if projected_margin >= 0 else 1 - home_probability

    market_spread = game["market_spread"]
    model_edge = projected_margin + market_spread
    spread_pick = (
        f'{game["home_team"]} {market_spread:+g}'
        if model_edge >= 0
        else f'{game["away_team"]} {-market_spread:+g}'
    )

    projected_total = round(game["pace_total"] + abs(rating_gap) * 0.08, 1)
    total_pick = "OVER" if projected_total > game["market_total"] else "UNDER"
    confidence = round(min(94, 62 + abs(projected_margin) * 2.1))
    survivor_score = round(min(98, win_probability * 100 - max(0, adjusted_home_rating - 88) * 0.15))

    reasons = [
        f"Model projects {winner} by {abs(projected_margin):.1f} points.",
        f"Estimated win probability is {win_probability:.0%}.",
        f"Model total is {projected_total:.1f} versus market {game['market_total']:.1f}.",
    ]

    material_news = [item for item in news if item.impact != 0]
    if material_news:
        headline = material_news[0]
        direction = "helps" if (
            headline.impact > 0 and headline.matched_team == winner
        ) or (
            headline.impact < 0 and headline.matched_team != winner
        ) else "adds risk to"
        reasons.insert(0, f"Yahoo update {direction} the pick: {headline.title}")

    return Prediction(
        game_id=game["game_id"],
        away_team=game["away_team"],
        home_team=game["home_team"],
        winner=winner,
        win_probability=round(win_probability, 3),
        projected_margin=projected_margin,
        market_spread=market_spread,
        projected_total=projected_total,
        market_total=game["market_total"],
        confidence=confidence,
        survivor_score=survivor_score,
        spread_pick=spread_pick,
        total_pick=total_pick,
        reasons=reasons,
        news=news,
        news_impact=home_news_impact - away_news_impact,
    )


def all_predictions() -> list[Prediction]:
    return [predict(game) for game in GAMES]
