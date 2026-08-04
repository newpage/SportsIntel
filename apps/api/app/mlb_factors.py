from __future__ import annotations

from app.sports_engine.factor import PredictionFactor


def _signed(value: float) -> float:
    return round(value, 3)


def build_mlb_prediction_factors(game: dict) -> list[dict]:
    """Describe the current MLB model without changing its confidence result."""
    away_team = game["away_team"]
    home_team = game["home_team"]
    winner = game["winner"]

    away_momentum = game.get("away_momentum", {})
    home_momentum = game.get("home_momentum", {})
    away_split = game.get("away_split", {})
    home_split = game.get("home_split", {})

    momentum_delta = (
        float(home_momentum.get("win_pct", 0.5))
        - float(away_momentum.get("win_pct", 0.5))
    )
    split_delta = (
        float(home_split.get("home_pct", 0.5))
        - float(away_split.get("away_pct", 0.5))
    )

    pitcher_advantage = game.get("pitcher_advantage") or {}
    pitcher_team = pitcher_advantage.get("team")
    pitcher_score = 0.0
    if pitcher_team == home_team:
        pitcher_score = float(pitcher_advantage.get("home_score", 0.0))
    elif pitcher_team == away_team:
        pitcher_score = -float(pitcher_advantage.get("away_score", 0.0))

    factors = [
        PredictionFactor(
            factor_id="season_record",
            name="Season Performance",
            category="team_strength",
            score=_signed(split_delta),
            weight=1.0,
            explanation=f"{winner} is favored by the current team-strength comparison.",
        ),
        PredictionFactor(
            factor_id="recent_momentum",
            name="Recent Team Momentum",
            category="team_form",
            score=_signed(momentum_delta),
            weight=0.025,
            explanation=(
                f"{away_team} is {away_momentum.get('record', 'Unavailable')} and "
                f"{home_team} is {home_momentum.get('record', 'Unavailable')} "
                "over their latest completed games."
            ),
        ),
        PredictionFactor(
            factor_id="venue_split",
            name="Home and Away Performance",
            category="venue",
            score=_signed(split_delta),
            weight=0.02,
            explanation=(
                f"{home_team} is {home_split.get('home_record', 'Unavailable')} at home; "
                f"{away_team} is {away_split.get('away_record', 'Unavailable')} on the road."
            ),
        ),
        PredictionFactor(
            factor_id="home_field",
            name="Home Field",
            category="venue",
            score=0.015,
            weight=1.0,
            explanation=f"{home_team} receives the model's existing small home-field adjustment.",
        ),
        PredictionFactor(
            factor_id="starting_pitcher",
            name="Starting Pitcher",
            category="pitching",
            score=_signed(pitcher_score),
            weight=0.0,
            explanation=(
                pitcher_advantage.get("summary")
                or "Pitcher data is displayed for comparison but is not yet used in confidence."
            ),
        ),
    ]

    output = []
    for factor in factors:
        item = factor.to_dict()
        item["direction"] = (
            home_team if factor.score > 0 else away_team if factor.score < 0 else "neutral"
        )
        item["reliability"] = (
            0.95
            if factor.factor_id != "starting_pitcher"
            else 0.9
            if game.get("away_pitcher_stats", {}).get("era")
            and game.get("home_pitcher_stats", {}).get("era")
            else 0.65
            if game.get("away_pitcher_stats", {}).get("era")
            or game.get("home_pitcher_stats", {}).get("era")
            else 0.35
        )
        item["used_in_confidence"] = factor.factor_id != "starting_pitcher"
        output.append(item)

    return output


def attach_mlb_prediction_factors(games: list[dict]) -> None:
    for game in games:
        game["prediction_factors"] = build_mlb_prediction_factors(game)
        game["factor_engine_version"] = "mlb-factors-v1"
        game["factor_engine_affects_confidence"] = False
