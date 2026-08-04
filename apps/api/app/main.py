from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.engine import all_predictions
from app.news import fetch_yahoo_nfl_news
from app.mlb import mlb_game, mlb_home, mlb_results
from app.intelligence.nfl_review import build_nfl_review
from app.sports_api import (
    sport_capabilities,
    sports_catalog,
    sports_home,
)

app = FastAPI(title="SportsIntel API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3300"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "SportsIntel API"}


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
    return build_nfl_review(sports_home("nfl"))


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
