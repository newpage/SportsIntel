from app.intelligence import build_team_intelligence


def test_build_team_intelligence_serializes_observation() -> None:
    intelligence = build_team_intelligence(
        team="Kansas City",
        side="home",
        rating=60.0,
        opponent_rating=55.0,
        home_field_rating=1.5,
        health={"overall_score": 90.0, "overall_label": "Good"},
        quarterback={"status": "expected", "confirmed": False},
        market_probability=0.58,
        model_probability=0.64,
        market_edge=0.06,
        readiness_score=80,
        readiness_label="developing",
        season_phase="preseason",
        confidence=58,
    )

    payload = intelligence.to_dict()

    assert payload["team"] == "Kansas City"
    assert payload["rating_advantage"] == 6.5
    assert payload["health_label"] == "Good"
    assert payload["market_edge"] == 0.06
    assert payload["affects_prediction"] is False


def test_away_rating_advantage_accounts_for_home_field() -> None:
    intelligence = build_team_intelligence(
        team="Philadelphia",
        side="away",
        rating=60.0,
        opponent_rating=58.0,
        home_field_rating=1.5,
        health={},
        quarterback={},
        market_probability=None,
        model_probability=0.53,
        market_edge=None,
        readiness_score=60,
        readiness_label="limited",
        season_phase="preseason",
        confidence=55,
    )

    assert intelligence.rating_advantage == 0.5
