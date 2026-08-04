from app.intelligence import build_prediction_waterfall


def test_prediction_waterfall_reconciles_guardrails() -> None:
    waterfall = build_prediction_waterfall(
        raw_confidence=68,
        final_confidence=57,
        readiness_cap=60,
        final_cap=57,
        rating_gap=10,
        home_field_rating=1.5,
        season_phase="preseason",
        qb_announced=False,
        away_health={"overall_label": "Good"},
        home_health={"overall_label": "Good"},
        market_signal_label="Large disagreement",
        market_available=True,
    )

    payload = waterfall.to_dict()

    assert payload["starting_confidence"] == 68
    assert payload["final_confidence"] == 57
    assert payload["total_adjustment"] == -11
    assert payload["reconciles"] is True

    adjustments = {
        step["step_id"]: step["value"]
        for step in payload["steps"]
        if step["kind"] == "adjustment"
    }
    assert adjustments["data_readiness"] == -8
    assert adjustments["season_context"] == -3


def test_observation_steps_do_not_change_confidence() -> None:
    waterfall = build_prediction_waterfall(
        raw_confidence=56,
        final_confidence=56,
        readiness_cap=60,
        final_cap=57,
        rating_gap=1.5,
        home_field_rating=1.5,
        season_phase="preseason",
        qb_announced=True,
        away_health={"overall_label": "Excellent"},
        home_health={"overall_label": "Good"},
        market_signal_label="Market aligned",
        market_available=True,
    )

    observation_steps = [
        step
        for step in waterfall.to_dict()["steps"]
        if step["kind"] == "observation"
    ]

    assert observation_steps
    assert all(step["affects_confidence"] is False for step in observation_steps)
