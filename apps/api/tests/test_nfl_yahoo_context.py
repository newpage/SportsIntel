import json

from app.sport_providers.nfl import _yahoo_context_from_html


def _flight_html(game: dict) -> str:
    chunk = f'66:["component",{{"game":{json.dumps(game, separators=(",", ":"))}}}]'
    return (
        "<script>self.__next_f.push("
        + json.dumps([1, chunk])
        + ")</script>"
    )


def test_yahoo_context_extracts_venue_and_observation_only_injuries() -> None:
    html = _flight_html(
        {
            "gameId": "nfl.g.123",
            "venue": {"displayName": "Example Stadium", "city": "Example"},
            "awayTeam": {
                "injuredPlayers": [
                    {
                        "displayName": "Away Quarterback",
                        "positionIds": ["QUARTERBACK"],
                        "injury": {"typeName": "Questionable", "description": "Knee"},
                    }
                ]
            },
            "homeTeam": {"injuredPlayers": []},
        }
    )

    context = _yahoo_context_from_html(html, "nfl.g.123")

    assert context["venue"] == "Example Stadium"
    assert context["away_injuries"][0]["name"] == "Away Quarterback"
    assert context["away_qb_injuries"][0]["status"] == "Questionable"
    assert context["injuries_affect_prediction"] is False


def test_yahoo_context_fails_closed_for_unrecognized_page() -> None:
    assert _yahoo_context_from_html("<html></html>", "nfl.g.123") == {}
