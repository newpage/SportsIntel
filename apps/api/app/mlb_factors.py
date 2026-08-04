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




def _model_coverage(factors: list[dict]) -> dict:
    active = [factor for factor in factors if factor.get("used_in_confidence")]
    observation_only = [
        factor for factor in factors if not factor.get("used_in_confidence")
    ]
    reliable = [
        float(factor.get("reliability", 0.0))
        for factor in factors
        if factor.get("reliability") is not None
    ]
    average_reliability = (
        round(sum(reliable) / len(reliable), 3)
        if reliable
        else 0.0
    )

    planned_categories = [
        "Bullpen",
        "Offense",
        "Defense",
        "Weather",
        "Injuries",
        "Market",
    ]

    return {
        "active_factors": len(active),
        "observation_only_factors": len(observation_only),
        "total_factors": len(factors),
        "average_reliability": average_reliability,
        "coverage_percent": round(
            min(100, (len(active) / 10) * 100)
        ),
        "status": (
            "Foundation"
            if len(active) < 5
            else "Developing"
            if len(active) < 8
            else "Broad"
        ),
        "missing_planned_areas": planned_categories,
        "summary": (
            f"{len(active)} factors currently influence confidence and "
            f"{len(observation_only)} factor is observation-only."
            if len(observation_only) == 1
            else (
                f"{len(active)} factors currently influence confidence and "
                f"{len(observation_only)} factors are observation-only."
            )
        ),
    }




def _record_pct(record: str | None) -> float:
    if not record or "-" not in record:
        return 0.5
    try:
        wins_text, losses_text = record.split("-", 1)
        wins = int(wins_text)
        losses = int(losses_text)
    except (TypeError, ValueError):
        return 0.5

    games = wins + losses
    return wins / games if games else 0.5


def _shadow_score(game: dict, factors: list[dict]) -> dict:
    away_team = game["away_team"]
    home_team = game["home_team"]

    away_record_pct = _record_pct(game.get("away_record"))
    home_record_pct = _record_pct(game.get("home_record"))
    season_edge = home_record_pct - away_record_pct

    away_momentum = game.get("away_momentum", {})
    home_momentum = game.get("home_momentum", {})
    momentum_edge = (
        float(home_momentum.get("win_pct", 0.5))
        - float(away_momentum.get("win_pct", 0.5))
    ) * 0.025

    away_split = game.get("away_split", {})
    home_split = game.get("home_split", {})
    venue_edge = (
        float(home_split.get("home_pct", 0.5))
        - float(away_split.get("away_pct", 0.5))
    ) * 0.02

    home_field_edge = 0.015

    pitcher_factor = next(
        (
            factor
            for factor in factors
            if factor.get("factor_id") == "starting_pitcher"
        ),
        {},
    )
    raw_pitcher_score = float(pitcher_factor.get("score", 0.0))
    pitcher_reliability = float(
        pitcher_factor.get("reliability", 0.0)
    )
    pitcher_edge = max(
        -0.015,
        min(0.015, raw_pitcher_score * 0.005),
    ) * pitcher_reliability

    total_home_edge = (
        season_edge
        + momentum_edge
        + venue_edge
        + home_field_edge
        + pitcher_edge
    )
    shadow_pick = home_team if total_home_edge >= 0 else away_team
    shadow_confidence = round(
        min(90, max(55, 58 + abs(total_home_edge) * 95))
    )

    official_pick = game.get("winner")
    official_confidence = int(game.get("confidence", 0))

    contributions = [
        {
            "factor_id": "season_record",
            "name": "Season Performance",
            "edge": round(season_edge, 4),
        },
        {
            "factor_id": "recent_momentum",
            "name": "Recent Team Momentum",
            "edge": round(momentum_edge, 4),
        },
        {
            "factor_id": "venue_split",
            "name": "Home and Away Performance",
            "edge": round(venue_edge, 4),
        },
        {
            "factor_id": "home_field",
            "name": "Home Field",
            "edge": round(home_field_edge, 4),
        },
        {
            "factor_id": "starting_pitcher",
            "name": "Starting Pitcher",
            "edge": round(pitcher_edge, 4),
        },
    ]

    return {
        "mode": "shadow",
        "official_model_unchanged": True,
        "pick": shadow_pick,
        "confidence": shadow_confidence,
        "agrees_with_official_pick": shadow_pick == official_pick,
        "confidence_difference": (
            shadow_confidence - official_confidence
        ),
        "home_edge": round(total_home_edge, 4),
        "away_edge": round(-total_home_edge, 4),
        "contributions": contributions,
        "summary": (
            f"Shadow model agrees with the official pick on {shadow_pick}."
            if shadow_pick == official_pick
            else (
                f"Shadow model prefers {shadow_pick}, while the official "
                f"model prefers {official_pick}."
            )
        ),
    }


def attach_mlb_prediction_factors(games: list[dict]) -> None:
    for game in games:
        game["prediction_factors"] = build_mlb_prediction_factors(game)
        game["factor_model_coverage"] = _model_coverage(
            game["prediction_factors"]
        )
        game["factor_shadow_score"] = _shadow_score(
            game,
            game["prediction_factors"],
        )
        game["factor_engine_version"] = "mlb-factors-v1"
        game["factor_engine_affects_confidence"] = False
