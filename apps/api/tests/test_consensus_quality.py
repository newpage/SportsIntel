from app.intelligence.consensus_quality import build_consensus_quality


def test_consensus_quality_penalizes_preseason_and_missing_qbs() -> None:
    result = build_consensus_quality(
        market_available=True,
        market_hold=0.045,
        readiness_label="limited",
        quarterbacks_announced=False,
        season_phase="preseason",
    )

    assert result.score == 45
    assert result.label == "Limited"
    assert result.status == "caution"
    assert result.affects_prediction is False


def test_consensus_quality_rewards_complete_regular_season_data() -> None:
    result = build_consensus_quality(
        market_available=True,
        market_hold=0.035,
        readiness_label="strong",
        quarterbacks_announced=True,
        season_phase="regular",
    )

    assert result.score == 100
    assert result.label == "Strong"
    assert result.status == "qualified"


def test_consensus_quality_holds_without_market() -> None:
    result = build_consensus_quality(
        market_available=False,
        market_hold=None,
        readiness_label="limited",
        quarterbacks_announced=False,
        season_phase="preseason",
    )

    assert result.score == 0
    assert result.label == "Unavailable"
    assert result.status == "hold"
