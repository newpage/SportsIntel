from app.intelligence.consensus import build_consensus_line


def test_consensus_agreement_and_value() -> None:
    result = build_consensus_line(
        model_pick="Arizona",
        away_team="Carolina",
        home_team="Arizona",
        model_probability=0.62,
        away_market_probability=0.5218,
        home_market_probability=0.4782,
    )

    assert result.market_favorite == "Carolina"
    assert result.agreement == "split"
    assert result.classification == "Strong value"
    assert result.edge == 0.1418
    assert result.affects_prediction is False


def test_consensus_handles_missing_market() -> None:
    result = build_consensus_line(
        model_pick="Houston",
        away_team="LA Chargers",
        home_team="Houston",
        model_probability=0.576,
        away_market_probability=None,
        home_market_probability=None,
    )

    assert result.market_favorite is None
    assert result.agreement == "unavailable"
    assert result.classification == "Market unavailable"
    assert result.edge is None
