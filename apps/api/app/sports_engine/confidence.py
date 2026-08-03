from collections.abc import Iterable

from app.sports_engine.factor import PredictionFactor


def weighted_factor_score(factors: Iterable[PredictionFactor]) -> float:
    """Return the weighted sum of prediction factors."""
    return sum(factor.score * factor.weight for factor in factors)


def clamp_confidence(value: float, minimum: int = 55, maximum: int = 90) -> int:
    """Round and clamp confidence to the supported SportsIntel range."""
    return round(min(maximum, max(minimum, value)))


def recommendation_for_confidence(confidence: int) -> dict:
    """Map confidence to the current SportsIntel recommendation labels."""
    if confidence >= 85:
        return {
            "rating": 5,
            "stars": "★★★★★",
            "recommendation": "Strong Bet",
            "color": "green",
        }
    if confidence >= 78:
        return {
            "rating": 4,
            "stars": "★★★★☆",
            "recommendation": "Good Bet",
            "color": "green",
        }
    if confidence >= 70:
        return {
            "rating": 3,
            "stars": "★★★☆☆",
            "recommendation": "Worth Considering",
            "color": "yellow",
        }
    if confidence >= 60:
        return {
            "rating": 2,
            "stars": "★★☆☆☆",
            "recommendation": "Risky",
            "color": "orange",
        }
    return {
        "rating": 1,
        "stars": "★☆☆☆☆",
        "recommendation": "Stay Away",
        "color": "red",
    }
