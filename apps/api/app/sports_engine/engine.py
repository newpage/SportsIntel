from collections.abc import Callable, Iterable

from app.sports_engine.factor import PredictionFactor


FactorProvider = Callable[[dict], Iterable[PredictionFactor]]


def collect_factors(
    context: dict,
    providers: Iterable[FactorProvider],
) -> list[PredictionFactor]:
    """Collect factors from sport-specific providers."""
    factors: list[PredictionFactor] = []
    for provider in providers:
        factors.extend(provider(context))
    return factors


def prediction_rank_key(game: dict) -> tuple[int, int, int]:
    """Return the existing SportsIntel game-ranking key."""
    confirmed_context = int(bool(game.get("away_pitcher"))) + int(
        bool(game.get("home_pitcher"))
    )
    return (
        int(game.get("rating", 0)),
        int(game.get("confidence", 0)),
        confirmed_context,
    )


def rank_predictions(games: Iterable[dict]) -> list[dict]:
    """Rank predictions strongest-to-weakest without mutating input."""
    return sorted(games, key=prediction_rank_key, reverse=True)
