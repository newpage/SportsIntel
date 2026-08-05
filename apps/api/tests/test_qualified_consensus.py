from app.intelligence.consensus import ConsensusLine, build_consensus_line
from app.intelligence.consensus_quality import (
    ConsensusQuality,
    build_consensus_quality,
)
from app.intelligence.qualified_consensus import build_qualified_consensus


def _consensus(
    *,
    model_probability: float = 0.62,
    market_probability: float = 0.48,
) -> ConsensusLine:
    return build_consensus_line(
        model_pick="Arizona",
        away_team="Carolina",
        home_team="Arizona",
        model_probability=model_probability,
        away_market_probability=1 - market_probability,
        home_market_probability=market_probability,
    )


def _quality(
    *,
    readiness_label: str = "strong",
    quarterbacks_announced: bool = True,
    season_phase: str = "regular",
    market_available: bool = True,
) -> ConsensusQuality:
    return build_consensus_quality(
        market_available=market_available,
        market_hold=0.035 if market_available else None,
        readiness_label=readiness_label,
        quarterbacks_announced=quarterbacks_announced,
        season_phase=season_phase,
    )


def test_qualified_strong_value_signal() -> None:
    result = build_qualified_consensus(
        consensus=_consensus(),
        quality=_quality(),
    )

    assert result.status == "qualified"
    assert result.classification == "Strong value"
    assert result.quality_score == 100
    assert result.no_vig_market_probability == 0.48
    assert result.model_market_edge == 0.14


def test_caution_signal_combines_classification_and_quality() -> None:
    result = build_qualified_consensus(
        consensus=_consensus(model_probability=0.54, market_probability=0.51),
        quality=_quality(
            readiness_label="limited",
            quarterbacks_announced=False,
            season_phase="preseason",
        ),
    )

    assert result.status == "caution"
    assert result.classification == "Value"
    assert result.quality_label == "Limited"
    assert result.reasons


def test_hold_signal_due_to_weak_data() -> None:
    quality = build_consensus_quality(
        market_available=True,
        market_hold=0.09,
        readiness_label="limited",
        quarterbacks_announced=False,
        season_phase="preseason",
    )
    result = build_qualified_consensus(
        consensus=_consensus(),
        quality=quality,
    )

    assert result.status == "hold"
    assert result.quality_label == "Weak"
    assert "Model data readiness is limited." in result.reasons


def test_unavailable_market() -> None:
    consensus = build_consensus_line(
        model_pick="Arizona",
        away_team="Carolina",
        home_team="Arizona",
        model_probability=0.62,
        away_market_probability=None,
        home_market_probability=None,
    )
    result = build_qualified_consensus(
        consensus=consensus,
        quality=_quality(market_available=False),
    )

    assert result.status == "unavailable"
    assert result.market_favorite is None
    assert result.no_vig_market_probability is None
    assert result.model_market_edge is None


def test_qualified_consensus_remains_observation_only() -> None:
    result = build_qualified_consensus(
        consensus=_consensus(),
        quality=_quality(),
    )

    assert result.affects_prediction is False
