from app.models import Prediction
from app.news import news_for_teams, team_news_impact


HOME_FIELD_POINTS = 1.8

GAMES = [
    {
        "game_id": "nyj-at-buf",
        "away_team": "New York Jets",
        "home_team": "Buffalo Bills",
        "home_rating": 91,
        "away_rating": 76,
        "home_form": 3,
        "away_form": -2,
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
        "home_form": 1,
        "away_form": 3,
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
        "home_form": 1,
        "away_form": 4,
        "market_spread": 5.5,
        "market_total": 47.5,
        "pace_total": 46.0,
    },
]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _market_home_margin(market_spread: float) -> float:
    """Convert a home-team spread into the market's expected home margin.

    A home spread of -6.5 means the market expects the home team to win by 6.5.
    A home spread of +2.5 means the market expects the home team to lose by 2.5.
    """
    return -market_spread


def _pick_reasons(
    game: dict,
    winner: str,
    projected_margin: float,
    win_probability: float,
    projected_total: float,
    market_home_margin: float,
    power_margin: float,
    form_margin: float,
    news_margin: float,
    news: list,
) -> list[str]:
    reasons: list[str] = []

    material_news = sorted(
        (item for item in news if item.impact != 0),
        key=lambda item: abs(item.impact),
        reverse=True,
    )
    if material_news:
        headline = material_news[0]
        helps_pick = (
            headline.impact > 0 and headline.matched_team == winner
        ) or (
            headline.impact < 0 and headline.matched_team != winner
        )
        direction = "supports" if helps_pick else "adds risk to"
        reasons.append(
            f"Yahoo {headline.category.lower().replace('_', ' ')} update "
            f"{direction} the pick: {headline.title}"
        )

    if abs(power_margin) >= 2:
        stronger_team = game["home_team"] if power_margin > 0 else game["away_team"]
        reasons.append(f"{stronger_team} owns the stronger base power rating.")

    if abs(form_margin) >= 0.5:
        form_team = game["home_team"] if form_margin > 0 else game["away_team"]
        reasons.append(f"Recent form favors {form_team}.")

    if abs(news_margin) >= 1:
        news_team = game["home_team"] if news_margin > 0 else game["away_team"]
        reasons.append(f"Current Yahoo news impact favors {news_team}.")

    model_market_gap = projected_margin - market_home_margin
    if abs(model_market_gap) <= 1.5:
        reasons.append("The model and market are closely aligned.")
    else:
        edge_team = game["home_team"] if model_market_gap > 0 else game["away_team"]
        reasons.append(
            f"The model sees about {abs(model_market_gap):.1f} points of spread value on {edge_team}."
        )

    reasons.extend(
        [
            f"Model projects {winner} by {abs(projected_margin):.1f} points.",
            f"Estimated win probability is {win_probability:.0%}.",
            f"Model total is {projected_total:.1f} versus market {game['market_total']:.1f}.",
        ]
    )
    return reasons[:5]


def predict(game: dict) -> Prediction:
    news = news_for_teams(game["away_team"], game["home_team"])
    home_news_impact = team_news_impact(game["home_team"], news)
    away_news_impact = team_news_impact(game["away_team"], news)

    power_margin = (game["home_rating"] - game["away_rating"]) * 0.42
    form_margin = (game.get("home_form", 0) - game.get("away_form", 0)) * 0.35
    news_margin = (home_news_impact - away_news_impact) * 0.55

    projected_margin = round(
        power_margin + form_margin + news_margin + HOME_FIELD_POINTS,
        1,
    )
    market_spread = game["market_spread"]
    market_home_margin = _market_home_margin(market_spread)
    market_gap = projected_margin - market_home_margin

    home_probability = _clamp(0.5 + projected_margin / 24, 0.10, 0.90)
    winner = game["home_team"] if projected_margin >= 0 else game["away_team"]
    win_probability = home_probability if projected_margin >= 0 else 1 - home_probability

    spread_pick = (
        f'{game["home_team"]} {market_spread:+g}'
        if market_gap >= 0
        else f'{game["away_team"]} {-market_spread:+g}'
    )

    offensive_form = (game.get("home_form", 0) + game.get("away_form", 0)) * 0.35
    projected_total = round(
        game["pace_total"] + offensive_form - abs(news_margin) * 0.15,
        1,
    )
    total_edge = projected_total - game["market_total"]
    total_pick = "OVER" if total_edge >= 0 else "UNDER"

    prediction_strength = abs(projected_margin)
    market_agreement = max(0.0, 5.0 - abs(market_gap))
    news_stability_penalty = min(5.0, abs(home_news_impact) + abs(away_news_impact))
    confidence = round(
        _clamp(
            58
            + prediction_strength * 2.0
            + market_agreement * 1.5
            - news_stability_penalty,
            55,
            94,
        )
    )
    survivor_score = round(
        _clamp(
            win_probability * 100
            + min(4.0, market_agreement)
            - news_stability_penalty * 0.5,
            50,
            98,
        )
    )

    reasons = _pick_reasons(
        game=game,
        winner=winner,
        projected_margin=projected_margin,
        win_probability=win_probability,
        projected_total=projected_total,
        market_home_margin=market_home_margin,
        power_margin=power_margin,
        form_margin=form_margin,
        news_margin=news_margin,
        news=news,
    )

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
