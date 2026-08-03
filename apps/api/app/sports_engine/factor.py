from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class PredictionFactor:
    """One explainable input to a sport prediction."""

    factor_id: str
    name: str
    score: float
    weight: float
    explanation: str
    category: str = "general"

    def to_dict(self) -> dict:
        return asdict(self)
