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


def _legacy_engine():
    from app import engine
    return engine


def _game_from_seed(game: dict[str, Any]) -> SportGame:
    return SportGame(
        sport="nfl",
        game_id=str(game["game_id"]),
        away_team=str(game["away_team"]),
        home_team=str(game["home_team"]),
        start_time="TBD",
        status=GameStatus.UNKNOWN,
        metadata={
            "data_mode": "seeded",
            "schedule_confirmed": False,
            "legacy_seed": game,
        },
    )


def _prediction_from_legacy(prediction: Any) -> SportPrediction:
    payload = prediction.model_dump() if hasattr(prediction, "model_dump") else prediction.dict()

    factors = [
        {
            "factor_id": "power_rating",
            "name": "Team Power Rating",
            "category": "team_strength",
            "score": payload.get("projected_margin", 0),
            "weight": 1.0,
            "reliability": 0.55,
            "explanation": next(
                (reason for reason in payload.get("reasons", []) if "power rating" in reason.lower()),
                "Existing NFL engine power-rating contribution.",
            ),
            "direction": "home" if payload.get("winner") == payload.get("home_team") else "away",
            "usage": "active",
            "version": "legacy-nfl-v1",
            "contributes_to": ["moneyline", "spread"],
            "used_in_confidence": True,
        },
        {
            "factor_id": "recent_form",
            "name": "Recent Form",
            "category": "team_form",
            "score": 0.0,
            "weight": 1.0,
            "reliability": 0.45,
            "explanation": next(
                (reason for reason in payload.get("reasons", []) if "recent form" in reason.lower()),
                "Existing NFL engine recent-form contribution.",
            ),
            "direction": "neutral",
            "usage": "active",
            "version": "legacy-nfl-v1",
            "contributes_to": ["moneyline", "spread", "total"],
            "used_in_confidence": True,
        },
        {
            "factor_id": "news_impact",
            "name": "Yahoo News Impact",
            "category": "availability",
            "score": float(payload.get("news_impact", 0)),
            "weight": 1.0,
            "reliability": 0.6,
            "explanation": next(
                (reason for reason in payload.get("reasons", []) if "yahoo" in reason.lower()),
                "No material Yahoo news adjustment is currently applied.",
            ),
            "direction": "neutral",
            "usage": "active",
            "version": "legacy-nfl-v1",
            "contributes_to": ["moneyline", "spread", "total"],
            "used_in_confidence": True,
        },
    ]

    markets = [
        MarketPrediction(
            market_type=MarketType.MONEYLINE,
            selection=payload.get("winner"),
            confidence=payload.get("confidence"),
            projected_value=payload.get("win_probability"),
            recommendation="Model pick",
            factor_ids=("power_rating", "recent_form", "news_impact"),
        ),
        MarketPrediction(
            market_type=MarketType.SPREAD,
            selection=payload.get("spread_pick"),
            confidence=None,
            line=payload.get("market_spread"),
            projected_value=payload.get("projected_margin"),
            factor_ids=("power_rating", "recent_form", "news_impact"),
        ),
        MarketPrediction(
            market_type=MarketType.TOTAL,
            selection=payload.get("total_pick"),
            confidence=None,
            line=payload.get("market_total"),
            projected_value=payload.get("projected_total"),
            factor_ids=("recent_form", "news_impact"),
        ),
    ]

    return SportPrediction(
        sport="nfl",
        game_id=str(payload["game_id"]),
        pick=payload.get("winner"),
        confidence=payload.get("confidence"),
        recommendation="Existing NFL model",
        factors=factors,
        timeline=[],
        markets=markets,
        explanation={
            "title": "Why SportsIntel Likes This Pick",
            "summary": payload.get("reasons", ["Existing NFL model output."])[0]
            if payload.get("reasons")
            else "Existing NFL model output.",
            "reasons": payload.get("reasons", []),
        },
        model_version="legacy-nfl-v1",
        metadata={
            "data_mode": "seeded",
            "schedule_confirmed": False,
            "survivor_score": payload.get("survivor_score"),
            "news": payload.get("news", []),
            "legacy_prediction": payload,
        },
    )


class NFLProvider(SportProvider):
    sport_key = "nfl"
    display_name = "National Football League"
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

    def schedule(self, target_date: date | None = None) -> list[SportGame]:
        engine = _legacy_engine()
        return [_game_from_seed(game) for game in engine.GAMES]

    def predict(self, game: SportGame) -> SportPrediction:
        engine = _legacy_engine()
        seed = game.metadata.get("legacy_seed")

        if not isinstance(seed, dict):
            seed = next(
                (item for item in engine.GAMES if str(item.get("game_id")) == game.game_id),
                None,
            )

        if not isinstance(seed, dict):
            raise KeyError(f"NFL game not found: {game.game_id}")

        return _prediction_from_legacy(engine.predict(seed))

    def health(self) -> dict[str, Any]:
        payload = super().health()
        payload.update(
            {
                "adapter": "legacy-nfl-seeded-v1",
                "status": "available",
                "import_mode": "lazy",
                "data_available": True,
                "data_mode": "seeded",
                "schedule_confirmed": False,
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
