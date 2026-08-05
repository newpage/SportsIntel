from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.engine import all_predictions
from app.news import fetch_yahoo_nfl_news
from app.mlb import mlb_game, mlb_home, mlb_results
from app.intelligence.nfl_review import build_nfl_review
from app.intelligence.prediction_change import (
    PredictionComparison,
    PredictionComparisonRequest,
    compare_prediction_snapshots,
)
from app.intelligence.snapshot_store import (
    SnapshotChangesResponse,
    SnapshotClearAllResponse,
    SnapshotClearGameResponse,
    SnapshotHistoryResponse,
    SnapshotStoreHealth,
    SnapshotStoreUnavailable,
    nfl_snapshot_store,
)
from app.sports_api import (
    sport_capabilities,
    sports_catalog,
    sports_home,
)

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store_health = nfl_snapshot_store.health()
    logger.info(
        "NFL snapshot store initialized: type=%s persistence=%s "
        "database_reachable=%s table_reachable=%s",
        store_health.snapshot_store_type,
        store_health.snapshot_persistence,
        store_health.database_reachable,
        store_health.snapshot_table_reachable,
    )
    yield


app = FastAPI(title="SportsIntel API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3300"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "SportsIntel API",
        "nfl_snapshot_store": nfl_snapshot_store.health().model_dump(),
    }


@app.get(
    "/api/sports/nfl/snapshot-store/health",
    response_model=SnapshotStoreHealth,
)
def nfl_snapshot_store_health() -> SnapshotStoreHealth:
    return nfl_snapshot_store.health()


def _snapshot_service_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="NFL snapshot history service is unavailable",
    )


@app.get("/api/home")
def home():
    predictions = all_predictions()
    survivor = max(predictions, key=lambda item: item.survivor_score)
    spread = max(predictions, key=lambda item: abs(item.projected_margin + item.market_spread))
    total = max(predictions, key=lambda item: abs(item.projected_total - item.market_total))
    impactful_news = [item for item in fetch_yahoo_nfl_news() if item.impact != 0][:4]
    return {
        "week": 1,
        "best_survivor": survivor,
        "best_spread": spread,
        "best_total": total,
        "games": predictions,
        "latest_news": impactful_news,
    }


@app.get("/api/sports")
def sports_list():
    return sports_catalog()


@app.get("/api/sports/{sport}/capabilities")
def sports_capabilities(sport: str):
    return sport_capabilities(sport)


@app.get("/api/sports/{sport}")
def sport_home(sport: str):
    return sports_home(sport)


@app.get("/api/sports/nfl/review")
def nfl_review():
    review = build_nfl_review(sports_home("nfl"))
    try:
        review.update(nfl_snapshot_store.diagnostics().model_dump())
    except SnapshotStoreUnavailable as exc:
        raise _snapshot_service_unavailable() from exc
    return review


@app.post(
    "/api/sports/nfl/compare",
    response_model=PredictionComparison,
)
def compare_nfl_predictions(
    request: PredictionComparisonRequest,
) -> PredictionComparison:
    return compare_prediction_snapshots(request.previous, request.current)


@app.post(
    "/api/sports/nfl/history/clear",
    response_model=SnapshotClearAllResponse,
)
def clear_nfl_snapshot_history() -> SnapshotClearAllResponse:
    try:
        return nfl_snapshot_store.clear_all()
    except SnapshotStoreUnavailable as exc:
        raise _snapshot_service_unavailable() from exc


@app.get(
    "/api/sports/nfl/{game_id}/history",
    response_model=SnapshotHistoryResponse,
)
def nfl_snapshot_history(
    game_id: str,
    limit: int = Query(default=10, ge=1, le=20),
) -> SnapshotHistoryResponse:
    try:
        snapshots = nfl_snapshot_store.get_history(game_id, limit)
        snapshot_count = nfl_snapshot_store.get_snapshot_count(game_id)
    except SnapshotStoreUnavailable as exc:
        raise _snapshot_service_unavailable() from exc
    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail="NFL snapshot history not found",
        )
    return SnapshotHistoryResponse(
        game_id=game_id,
        snapshot_count=snapshot_count,
        snapshots=snapshots,
        snapshot_store_type=nfl_snapshot_store.store_type,
        snapshot_persistence=nfl_snapshot_store.persistence_enabled,
    )


@app.get(
    "/api/sports/nfl/{game_id}/changes",
    response_model=SnapshotChangesResponse,
)
def nfl_snapshot_changes(game_id: str) -> SnapshotChangesResponse:
    try:
        result = nfl_snapshot_store.get_changes(game_id)
    except SnapshotStoreUnavailable as exc:
        raise _snapshot_service_unavailable() from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="NFL snapshot history not found",
        )
    return result


@app.delete(
    "/api/sports/nfl/{game_id}/history",
    response_model=SnapshotClearGameResponse,
)
def clear_nfl_game_snapshot_history(
    game_id: str,
) -> SnapshotClearGameResponse:
    try:
        return SnapshotClearGameResponse(
            game_id=game_id,
            removed_snapshots=nfl_snapshot_store.clear_game(game_id),
        )
    except SnapshotStoreUnavailable as exc:
        raise _snapshot_service_unavailable() from exc


@app.get("/api/mlb")
def mlb():
    return mlb_home()


@app.get("/api/mlb/results")
def mlb_results_history(days: int = 7):
    return mlb_results(days)


@app.get("/api/mlb/{game_id}")
def mlb_game_detail(game_id: str):
    result = mlb_game(game_id)
    if result:
        return result
    raise HTTPException(status_code=404, detail="MLB game not found")


@app.get("/api/games/{game_id}")
def game(game_id: str):
    for prediction in all_predictions():
        if prediction.game_id == game_id:
            return prediction
    raise HTTPException(status_code=404, detail="Game not found")
