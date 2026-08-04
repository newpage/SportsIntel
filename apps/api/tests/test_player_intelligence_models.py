from app.intelligence import (
    AvailabilityStatus,
    IntelligenceSource,
    PlayerIdentity,
    PlayerIntelligence,
    PlayerIntelligenceCollection,
    PlayerUnit,
    StarterStatus,
)


def test_player_intelligence_serializes() -> None:
    source = IntelligenceSource(
        name="manual test",
        source_type="test",
        reliability=0.9,
    )
    player = PlayerIntelligence(
        identity=PlayerIdentity(
            sport="nfl",
            player_id="nfl.test.qb",
            display_name="Test Quarterback",
            team="Test Team",
            position="QB",
            unit=PlayerUnit.OFFENSE,
        ),
        availability_status=AvailabilityStatus.EXPECTED,
        starter_status=StarterStatus.EXPECTED,
        starter_probability=0.92,
        availability_score=90,
        health_score=88,
        impact_score=95,
        confidence=0.8,
        explanation="Test intelligence object.",
        sources=(source,),
    )

    payload = player.to_dict()

    assert payload["expected_starter"] is True
    assert payload["affects_prediction"] is False
    assert payload["impact_score"] == 95.0
    assert payload["identity"]["position"] == "QB"


def test_collection_filters_key_players() -> None:
    player = PlayerIntelligence(
        identity=PlayerIdentity(
            sport="nfl",
            player_id="nfl.test.edge",
            display_name="Test Edge",
            team="Test Team",
            position="EDGE",
            unit=PlayerUnit.DEFENSE,
        ),
        impact_score=82,
    )

    collection = PlayerIntelligenceCollection(
        sport="nfl",
        team="Test Team",
        players=(player,),
    )

    assert collection.key_players()[0].identity.position == "EDGE"
