from app.intelligence import TeamHealthEngine


def test_unknown_qb_produces_unknown_health() -> None:
    health = TeamHealthEngine.from_qb_context(
        team="Test Team",
        qb_context={
            "name": None,
            "status": "not announced",
            "confirmed": False,
        },
    )

    assert health.overall_label == "Unknown"
    assert health.overall_score == 50.0
    assert health.confidence == 0.0
    assert health.player_count == 0
    assert health.affects_prediction is False


def test_confirmed_qb_produces_excellent_health() -> None:
    health = TeamHealthEngine.from_qb_context(
        team="Test Team",
        qb_context={
            "name": "Test Quarterback",
            "status": "starting",
            "confirmed": True,
        },
    )

    assert health.overall_label == "Excellent"
    assert health.overall_score == 100.0
    assert health.healthy == 1
    assert health.coverage == "quarterback_only"


def test_questionable_qb_is_counted() -> None:
    health = TeamHealthEngine.from_qb_context(
        team="Test Team",
        qb_context={
            "name": "Test Quarterback",
            "status": "questionable",
            "confirmed": False,
        },
    )

    assert health.overall_score == 60.0
    assert health.questionable == 1
    assert health.out == 0
