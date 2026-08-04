from __future__ import annotations

from datetime import date

from app.sports import (
    SportCapabilities,
    SportGame,
    SportPrediction,
    SportProvider,
    SportRegistry,
    sports_registry,
)


class NFLProvider(SportProvider):
    """NFL provider placeholder used to validate multi-sport architecture."""

    sport_key = "nfl"
    display_name = "National Football League"
    capabilities = SportCapabilities(
        moneyline=False,
        spread=False,
        totals=False,
        player_props=False,
        live=False,
        standings=False,
        injuries=False,
        weather=False,
    )

    def schedule(self, target_date: date | None = None) -> list[SportGame]:
        return []

    def predict(self, game: SportGame) -> SportPrediction:
        raise NotImplementedError(
            "NFL prediction data is not available yet."
        )

    def health(self) -> dict:
        payload = super().health()
        payload.update(
            {
                "adapter": "nfl-stub-v1",
                "status": "planned",
                "import_mode": "lazy",
                "data_available": False,
            }
        )
        return payload


def register_nfl_provider(
    registry: SportRegistry | None = None,
    *,
    replace: bool = False,
) -> NFLProvider:
    target = registry or sports_registry
    provider = NFLProvider()

    if target.contains(provider.sport_key):
        if not replace:
            return target.get(provider.sport_key)  # type: ignore[return-value]

    target.register(provider, replace=replace)
    return provider
