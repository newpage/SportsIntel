from __future__ import annotations

from datetime import date
from typing import Any

from app.sports import (
    GameStatus,
    MarketPrediction,
    MarketType,
    SportCapabilities,
    SportGame,
    SportPrediction,
    SportProvider,
    SportRegistry,
    sports_registry,
)


def _legacy_mlb_module():
    """Import the production MLB module only when the provider is used."""
    from app import mlb

    return mlb


def _status(value: str | None, completed: bool) -> GameStatus:
    if completed:
        return GameStatus.FINAL

    normalized = (value or "").strip().lower()
    if normalized in {"in progress", "live", "manager challenge"}:
        return GameStatus.LIVE
    if "postpon" in normalized:
        return GameStatus.POSTPONED
    if "cancel" in normalized:
        return GameStatus.CANCELLED
    if normalized:
        return GameStatus.SCHEDULED
    return GameStatus.UNKNOWN


def _game_from_payload(payload: dict[str, Any]) -> SportGame:
    return SportGame(
        sport="mlb",
        game_id=str(payload["game_id"]),
        away_team=str(payload["away_team"]),
        home_team=str(payload["home_team"]),
        start_time=payload["start_time"],
        status=_status(
            payload.get("status"),
            bool(payload.get("completed")),
        ),
        away_score=payload.get("away_score"),
        home_score=payload.get("home_score"),
        venue=payload.get("venue"),
        metadata={
            "legacy_payload": payload,
            "legacy_endpoint": "/api/mlb",
        },
    )


def _prediction_from_payload(payload: dict[str, Any]) -> SportPrediction:
    factor_ids = tuple(
        factor.get("factor_id")
        for factor in payload.get("prediction_factors", [])
        if factor.get("factor_id")
    )

    markets = [
        MarketPrediction(
            market_type=MarketType.MONEYLINE,
            selection=payload.get("moneyline_pick"),
            confidence=payload.get("confidence"),
            recommendation=payload.get("recommendation"),
            factor_ids=factor_ids,
        ),
        MarketPrediction(
            market_type=MarketType.SPREAD,
            selection=payload.get("run_line_pick"),
            confidence=None,
            factor_ids=factor_ids,
        ),
        MarketPrediction(
            market_type=MarketType.TOTAL,
            selection=payload.get("total_pick"),
            confidence=None,
            factor_ids=factor_ids,
        ),
    ]

    return SportPrediction(
        sport="mlb",
        game_id=str(payload["game_id"]),
        pick=payload.get("winner"),
        confidence=payload.get("confidence"),
        recommendation=payload.get("recommendation"),
        factors=list(payload.get("prediction_factors", [])),
        timeline=list(payload.get("prediction_timeline", [])),
        markets=markets,
        explanation=dict(payload.get("confidence_details", {})),
        model_version=payload.get("factor_engine_version"),
        shadow_prediction=payload.get("factor_shadow_score"),
        metadata={
            "legacy_payload": payload,
            "legacy_endpoint": "/api/mlb",
        },
    )


class MLBProvider(SportProvider):
    """Lazy adapter around the existing production MLB implementation."""

    sport_key = "mlb"
    display_name = "Major League Baseball"
    capabilities = SportCapabilities(
        moneyline=True,
        spread=True,
        totals=True,
        player_props=False,
        live=False,
        standings=False,
        injuries=False,
        weather=False,
    )

    def _payload(self) -> dict[str, Any]:
        return _legacy_mlb_module().mlb_home()

    def schedule(self, target_date: date | None = None) -> list[SportGame]:
        if target_date is not None and target_date != date.today():
            return []

        return [
            _game_from_payload(game)
            for game in self._payload().get("games", [])
        ]

    def predict(self, game: SportGame) -> SportPrediction:
        legacy = game.metadata.get("legacy_payload")

        if not isinstance(legacy, dict):
            legacy = next(
                (
                    item
                    for item in self._payload().get("games", [])
                    if str(item.get("game_id")) == game.game_id
                ),
                None,
            )

        if not isinstance(legacy, dict):
            raise KeyError(f"MLB game not found: {game.game_id}")

        return _prediction_from_payload(legacy)

    def health(self) -> dict[str, Any]:
        payload = super().health()
        payload.update(
            {
                "adapter": "legacy-mlb-lazy-v1",
                "legacy_endpoint": "/api/mlb",
                "import_mode": "lazy",
            }
        )
        return payload


def register_mlb_provider(
    registry: SportRegistry | None = None,
    *,
    replace: bool = False,
) -> MLBProvider:
    """Explicitly register MLB without coupling it to the sports core."""
    target = registry or sports_registry
    provider = MLBProvider()

    if target.contains(provider.sport_key):
        if not replace:
            return target.get(provider.sport_key)  # type: ignore[return-value]

    target.register(provider, replace=replace)
    return provider
