from app.intelligence.nfl_review import build_nfl_review


def test_review_summarizes_nfl_games() -> None:
    payload = {
        "date": "2026-08-04",
        "games": [
            {
                "prediction": {
                    "confidence": 57,
                    "metadata": {
                        "data_readiness_label": "limited",
                        "market_signal_label": "Large disagreement",
                        "season_phase": "preseason",
                        "market_available": True,
                        "confidence_guardrail_applied": True,
                        "qb_announced": False,
                        "team_health": {"away": {}, "home": {}},
                        "team_intelligence": {"away": {}, "home": {}},
                        "prediction_waterfall": {"steps": []},
                    },
                }
            },
            {
                "prediction": {
                    "confidence": 55,
                    "metadata": {
                        "data_readiness_label": "limited",
                        "market_signal_label": "Market unavailable",
                        "season_phase": "preseason",
                        "market_available": False,
                        "confidence_guardrail_applied": False,
                        "qb_announced": False,
                        "team_health": {"away": {}, "home": {}},
                        "team_intelligence": {"away": {}, "home": {}},
                        "prediction_waterfall": {"steps": []},
                    },
                }
            },
        ],
    }

    review = build_nfl_review(payload)

    assert review["game_count"] == 2
    assert review["average_confidence"] == 56.0
    assert review["coverage"]["complete_games"] == 2
    assert review["context"]["preseason_games"] == 2
    assert review["context"]["market_available_games"] == 1
    assert review["status"] == "ready_for_review"


def test_review_handles_empty_schedule() -> None:
    review = build_nfl_review({"date": "2026-08-04", "games": []})

    assert review["game_count"] == 0
    assert review["average_confidence"] is None
    assert review["status"] == "partial"
